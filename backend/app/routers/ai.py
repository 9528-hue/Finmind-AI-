import os
from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Transaction, Alert, Account, User
from app.routers.analytics import get_analytics
from app.schemas import ChatMessage, ChatResponse
from app.services.auth_service import get_current_user
from app.services.ai_service import chat, check_health

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/health")
async def ai_health():
    """Check AI service health — does NOT expose the API key."""
    return await check_health()


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(
    payload: ChatMessage,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat with the AI assistant using the authenticated user's real database data.
    The LLM receives only a structured context — it never touches the database directly.
    """
    # Build context from real DB data (only this user's records)
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()

    # Keep analytics canonical over all rows and include recent transaction details for chat.
    all_txns = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.timestamp.desc())
        .all()
    )
    recent_txns = all_txns
    currency_codes = sorted({(txn.currency or "").upper() for txn in all_txns if txn.currency})
    analytics_by_currency = {
        currency: get_analytics(
            currency=currency,
            date_from=None,
            date_to=None,
            interval="month",
            db=db,
            current_user=current_user,
        ).model_dump()
        for currency in currency_codes
    }

    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id, Alert.is_read == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
        .limit(5)
        .all()
    )

    # Keep financial totals separated by currency; adding different currencies
    # without an exchange-rate source would produce misleading AI context.
    currency_income: Dict[str, float] = {}
    currency_expenses: Dict[str, float] = {}
    for t in all_txns:
        cur = t.currency or "INR"
        if t.transaction_type == "credit":
            currency_income[cur] = currency_income.get(cur, 0) + t.amount
        else:
            currency_expenses[cur] = currency_expenses.get(cur, 0) + t.amount

    user_stats = {
        "name": current_user.full_name,
        "total_accounts": len(accounts),
        "transaction_count": len(all_txns),
        "flagged_count": sum(1 for t in all_txns if t.is_flagged),
        "high_risk_count": sum(1 for t in all_txns if t.risk_level == "high"),
        "unread_alerts": len(alerts),
        "income_by_currency": currency_income,
        "expenses_by_currency": currency_expenses,
        "analytics_by_currency": analytics_by_currency,
    }

    recent_txn_dicts = [
        {
            "id": t.id,
            "merchant": t.merchant,
            "amount": t.amount,
            "currency": t.currency,
            "category": t.category,
            "transaction_type": t.transaction_type,
            "risk_score": t.risk_score,
            "risk_level": t.risk_level,
            "risk_signals": t.risk_signals,
            "is_flagged": t.is_flagged,
            "timestamp": t.timestamp.isoformat(),
            "status": t.status,
            "description": t.description,
        }
        for t in recent_txns
    ]

    # Category totals for context (debit transactions only, grouped by currency)
    cat_totals: Dict[str, float] = {}
    for t in all_txns:
        if t.transaction_type == "debit":
            key = f"{t.category} ({t.currency})"
            cat_totals[key] = cat_totals.get(key, 0) + t.amount
    top_cats = [
        {"category": k, "amount": round(v, 2)}
        for k, v in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:8]
    ]

    alert_dicts = [
        {"title": a.title, "severity": a.severity, "description": a.description}
        for a in alerts
    ]

    reply_text, ai_unavailable = await chat(
        message=payload.message,
        user_stats=user_stats,
        recent_transactions=recent_txn_dicts,
        alerts=alert_dicts,
        top_categories=top_cats,
        history=[turn.model_dump() for turn in payload.history],
    )

    return ChatResponse(reply=reply_text, ai_unavailable=ai_unavailable)
