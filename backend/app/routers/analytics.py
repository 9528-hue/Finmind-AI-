import datetime
import os
from collections import defaultdict
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Transaction, Account, User
from app.schemas import (
    AnalyticsOut,
    CategoryBreakdown,
    MerchantSpend,
    MonthlyTrend,
    RiskDistribution,
)
from app.services.auth_service import get_current_user
from app.services.financial_metrics import is_revenue_category

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/", response_model=AnalyticsOut)
def get_analytics(
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    interval: str = Query("month", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")

    currency_codes = {
        (code or "").upper()
        for (code,) in db.query(Transaction.currency)
        .filter(Transaction.user_id == current_user.id)
        .distinct()
        .all()
        if code
    }
    selected_currency = (
        currency.upper() if currency else
        (os.getenv("DEFAULT_CURRENCY", "INR").upper()
         if os.getenv("DEFAULT_CURRENCY", "INR").upper() in currency_codes
         else (sorted(currency_codes)[0] if currency_codes else os.getenv("DEFAULT_CURRENCY", "INR").upper()))
    )
    txn_query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        func.upper(Transaction.currency) == selected_currency,
    )
    if date_from:
        txn_query = txn_query.filter(
            Transaction.timestamp >= datetime.datetime.combine(date_from, datetime.time.min)
        )
    if date_to:
        txn_query = txn_query.filter(
            Transaction.timestamp < datetime.datetime.combine(
                date_to + datetime.timedelta(days=1), datetime.time.min
            )
        )
    txns = txn_query.all()
    accounts = (
        db.query(Account)
        .filter(
            Account.user_id == current_user.id,
            func.upper(Account.currency) == selected_currency,
        )
        .all()
    )

    total_balance = sum(a.balance for a in accounts)
    income = sum(t.amount for t in txns if t.transaction_type == "credit")
    revenue_values = [
        t.amount for t in txns
        if t.transaction_type == "credit" and is_revenue_category(t.category)
    ]
    total_revenue = round(sum(revenue_values), 2) if revenue_values else None
    expenses = sum(t.amount for t in txns if t.transaction_type == "debit")
    flagged = sum(1 for t in txns if t.is_flagged)
    avg_risk = sum(t.risk_score for t in txns) / len(txns) if txns else 0.0
    average_transaction = (
        sum(t.amount for t in txns) / len(txns) if txns else 0.0
    )
    largest_transaction = max((t.amount for t in txns), default=0.0)
    savings_rate = round((income - expenses) / income * 100, 1) if income else None

    # Category breakdown (debit only)
    cat_totals: Dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})
    debit_total = sum(t.amount for t in txns if t.transaction_type == "debit")
    for t in txns:
        if t.transaction_type == "debit":
            cat_totals[t.category]["amount"] += t.amount
            cat_totals[t.category]["count"] += 1

    category_breakdown = [
        CategoryBreakdown(
            category=cat,
            amount=round(data["amount"], 2),
            count=data["count"],
            percentage=round(data["amount"] / debit_total * 100, 1) if debit_total else 0,
        )
        for cat, data in sorted(cat_totals.items(), key=lambda x: x[1]["amount"], reverse=True)
    ]

    # Monthly trends (last 6 months)
    monthly: Dict[str, dict] = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    for t in txns:
        key = t.timestamp.strftime("%b %Y")
        if t.transaction_type == "credit":
            monthly[key]["income"] += t.amount
        else:
            monthly[key]["expenses"] += t.amount

    # Sort by date and take last 6
    def month_sort_key(k: str):
        return datetime.datetime.strptime(k, "%b %Y")

    sorted_months = sorted(monthly.keys(), key=month_sort_key)[-6:]
    monthly_trends = [
        MonthlyTrend(
            month=m,
            income=round(monthly[m]["income"], 2),
            expenses=round(monthly[m]["expenses"], 2),
            net=round(monthly[m]["income"] - monthly[m]["expenses"], 2),
        )
        for m in sorted_months
    ]

    def period_key(timestamp: datetime.datetime) -> str:
        if interval == "day":
            return timestamp.strftime("%Y-%m-%d")
        if interval == "week":
            iso = timestamp.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        return timestamp.strftime("%Y-%m")

    trend_totals: Dict[str, dict] = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})
    merchant_totals: Dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    for txn in txns:
        bucket = trend_totals[period_key(txn.timestamp)]
        if txn.transaction_type == "credit":
            bucket["income"] += txn.amount
        else:
            bucket["expenses"] += txn.amount
            merchant_totals[txn.merchant]["amount"] += txn.amount
            merchant_totals[txn.merchant]["count"] += 1
        level = (txn.risk_level or "low").lower()
        risk_counts[level] = risk_counts.get(level, 0) + 1

    cash_flow_trends = [
        MonthlyTrend(
            month=period,
            income=round(values["income"], 2),
            expenses=round(values["expenses"], 2),
            net=round(values["income"] - values["expenses"], 2),
        )
        for period, values in sorted(trend_totals.items())
    ]
    total_risk_records = sum(risk_counts.values())
    risk_distribution = [
        RiskDistribution(
            level=level,
            count=count,
            percentage=round(count / total_risk_records * 100, 1) if total_risk_records else 0,
        )
        for level, count in risk_counts.items()
    ]
    top_merchants = [
        MerchantSpend(merchant=merchant, amount=round(values["amount"], 2), count=values["count"])
        for merchant, values in sorted(
            merchant_totals.items(), key=lambda item: item[1]["amount"], reverse=True
        )[:5]
    ]

    return AnalyticsOut(
        total_balance=round(total_balance, 2),
        total_income=round(income, 2),
        total_revenue=total_revenue,
        total_expenses=round(expenses, 2),
        net_cash_flow=round(income - expenses, 2),
        currency=selected_currency,
        transaction_count=len(txns),
        flagged_count=flagged,
        avg_risk_score=round(avg_risk, 1),
        savings_rate=savings_rate,
        average_transaction_amount=round(average_transaction, 2),
        largest_transaction_amount=round(largest_transaction, 2),
        high_risk_count=risk_counts.get("high", 0),
        medium_risk_count=risk_counts.get("medium", 0),
        category_breakdown=category_breakdown,
        monthly_trends=monthly_trends,
        cash_flow_trends=cash_flow_trends,
        top_merchants=top_merchants,
        risk_distribution=risk_distribution,
    )
