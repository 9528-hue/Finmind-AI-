"""
FinMind AI — ML Router
=======================
Endpoints for:
  - Model status and version info
  - Transaction categorization (Model A)
  - Anomaly scoring (Model B)
  - Cash flow forecasting (Model C)
  - Business scenario simulation (USP 5)
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Transaction, User
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class CategorizePrediction(BaseModel):
    description: str
    category: Optional[str]
    confidence: float
    model_used: bool
    low_confidence: bool


class CategorizeRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)


class AnomalyRequest(BaseModel):
    transaction_id: Optional[str] = None
    amount: float
    transaction_type: str = "debit"
    category: str = "Other"
    merchant: str = ""


class ScenarioDef(BaseModel):
    type: str
    revenue_pct_change: Optional[float] = None
    monthly_expense_delta: Optional[float] = None
    monthly_salary: Optional[float] = None
    monthly_rent_delta: Optional[float] = None
    monthly_cost_delta: Optional[float] = None
    monthly_marketing_delta: Optional[float] = None
    amount: Optional[float] = None
    delay_months: Optional[int] = None


class SimulatorRequest(BaseModel):
    scenarios: List[ScenarioDef] = Field(min_length=1, max_length=5)
    scenario_name: str = Field(default="Custom Scenario", max_length=100)
    interval: str = "monthly"
    n_periods: int = Field(default=3, ge=1, le=12)
    opening_balance: Optional[float] = None


# ── Model Status ─────────────────────────────────────────────────────────────

@router.get("/status", summary="Model status and registry info")
def ml_status():
    """Return current ML model loading status and registry metadata."""
    from app.ml import model_registry
    registry = model_registry.list_models()

    status = {}
    for model_name in ["categorizer", "anomaly_general"]:
        try:
            if model_name == "categorizer":
                from app.ml.inference import categorizer
                info = categorizer.model_info()
                status[model_name] = {
                    "loaded": info["loaded"],
                    "artifact": info.get("artifact_path"),
                    "registry": registry.get(model_name),
                }
            elif model_name == "anomaly_general":
                from app.ml.inference import anomaly
                model = anomaly.get_general_model()
                status[model_name] = {
                    "loaded": model is not None,
                    "registry": registry.get(model_name),
                }
        except Exception as exc:
            status[model_name] = {"loaded": False, "error": str(exc)}

    return {
        "models": status,
        "registry": registry,
        "note": (
            "categorizer: TF-IDF + Logistic Regression (synthetic dataset). "
            "anomaly: Isolation Forest (synthetic normal distribution). "
            "forecast: statsmodels ExponentialSmoothing/ARIMA (user data, on-demand). "
            "simulator: deterministic arithmetic on forecast output."
        ),
    }


@router.post("/train", summary="Trigger model training (admin/development use)")
def trigger_training(
    model: str = Query("all", pattern="^(all|categorizer|anomaly)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger model training. In production, training runs offline.
    Exposed here for demo/development purposes.
    """
    results = {}

    if model in ("all", "categorizer"):
        try:
            from app.ml.training.train_categorizer import train_and_save
            metrics = train_and_save(verbose=False)
            # Reset cached model so next call loads the new artifact
            import app.ml.inference.categorizer as cat_module
            cat_module._pipeline = None
            cat_module._load_attempted = False
            results["categorizer"] = {"status": "trained", "metrics": metrics}
        except Exception as exc:
            logger.error("Categorizer training failed: %s", exc)
            results["categorizer"] = {"status": "failed", "error": str(exc)}

    if model in ("all", "anomaly"):
        try:
            from app.ml.training.train_anomaly import build_general_model
            metrics = build_general_model(verbose=False)
            # Reset cached model
            import app.ml.inference.anomaly as anom_module
            anom_module._general_model = None
            anom_module._general_model_loaded = False
            results["anomaly"] = {"status": "trained", "metrics": metrics}
        except Exception as exc:
            logger.error("Anomaly training failed: %s", exc)
            results["anomaly"] = {"status": "failed", "error": str(exc)}

    return results


# ── Categorization (Model A) ─────────────────────────────────────────────────

@router.post("/categorize", response_model=CategorizePrediction)
def categorize_transaction(
    payload: CategorizeRequest,
    current_user: User = Depends(get_current_user),
):
    """Classify a transaction description using the trained ML categorizer."""
    from app.ml.inference.categorizer import predict, CONFIDENCE_THRESHOLD

    category, confidence, model_used = predict(payload.description)
    return CategorizePrediction(
        description=payload.description,
        category=category,
        confidence=round(confidence, 4),
        model_used=model_used,
        low_confidence=model_used and confidence < CONFIDENCE_THRESHOLD,
    )


# ── Anomaly Scoring (Model B) ─────────────────────────────────────────────────

@router.post("/anomaly/score", summary="Score transaction for anomaly")
def score_anomaly(
    payload: AnomalyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a transaction for anomalousness using Isolation Forest + IQR."""
    from app.ml.inference.anomaly import score_transaction

    # Load recent transactions for context
    recent = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.timestamp.desc())
        .limit(200)
        .all()
    )
    user_transactions = [
        {
            "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            "amount": t.amount,
            "transaction_type": t.transaction_type,
            "category": t.category,
            "merchant": t.merchant,
        }
        for t in recent
    ]

    result = score_transaction(
        amount=payload.amount,
        txn_type=payload.transaction_type,
        category=payload.category,
        merchant=payload.merchant,
        timestamp=None,
        user_transactions=user_transactions,
        user_id=current_user.id,
    )
    return result


@router.get("/anomaly/transactions", summary="List anomalous transactions for user")
def get_anomalous_transactions(
    threshold: float = Query(35.0, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return transactions with anomaly score above threshold for the authenticated user."""
    from app.ml.inference.anomaly import score_transaction

    recent = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.timestamp.desc())
        .limit(500)
        .all()
    )

    user_transactions = [
        {
            "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            "amount": t.amount,
            "transaction_type": t.transaction_type,
            "category": t.category,
            "merchant": t.merchant,
        }
        for t in recent
    ]

    results = []
    for txn in recent[:limit * 3]:  # score top candidates
        score_result = score_transaction(
            amount=txn.amount,
            txn_type=txn.transaction_type,
            category=txn.category,
            merchant=txn.merchant,
            timestamp=txn.timestamp,
            user_transactions=user_transactions,
            user_id=current_user.id,
        )
        if score_result["anomaly_score"] >= threshold:
            results.append({
                "transaction_id": txn.id,
                "timestamp": txn.timestamp.isoformat() if txn.timestamp else "",
                "merchant": txn.merchant,
                "amount": txn.amount,
                "currency": txn.currency,
                "category": txn.category,
                "transaction_type": txn.transaction_type,
                **score_result,
            })
            if len(results) >= limit:
                break

    results.sort(key=lambda r: r["anomaly_score"], reverse=True)
    return {"anomalous_transactions": results, "threshold": threshold, "count": len(results)}


# ── Forecasting (Model C) ─────────────────────────────────────────────────────

@router.get("/forecast", summary="Cash flow forecast from user transaction history")
def get_forecast(
    interval: str = Query("monthly", pattern="^(monthly|weekly)$"),
    n_periods: int = Query(3, ge=1, le=12),
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a cash flow forecast from the authenticated user's transaction history.
    Returns insufficient_data message honestly when history is too short.
    """
    from app.ml.inference.forecaster import forecast_cashflow

    q = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if currency:
        from sqlalchemy import func
        q = q.filter(func.upper(Transaction.currency) == currency.upper())

    transactions = q.order_by(Transaction.timestamp.asc()).all()

    txn_dicts = [
        {
            "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            "amount": t.amount,
            "transaction_type": t.transaction_type,
            "currency": t.currency,
            "category": t.category,
        }
        for t in transactions
    ]

    result = forecast_cashflow(txn_dicts, n_periods=n_periods, interval=interval)
    result["currency"] = currency or "all"
    result["n_transactions_used"] = len(txn_dicts)
    return result


# ── Business Simulator (USP 5) ───────────────────────────────────────────────

@router.post("/simulate", summary="Run a business financial simulation")
def run_simulation(
    payload: SimulatorRequest,
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run a business financial simulation against the user's actual transaction data.
    NEVER modifies real transactions or balances.
    """
    from app.ml.inference.forecaster import forecast_cashflow
    from app.ml.inference.simulator import simulate

    q = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if currency:
        from sqlalchemy import func
        q = q.filter(func.upper(Transaction.currency) == currency.upper())

    transactions = q.order_by(Transaction.timestamp.asc()).all()
    txn_dicts = [
        {
            "timestamp": t.timestamp.isoformat() if t.timestamp else "",
            "amount": t.amount,
            "transaction_type": t.transaction_type,
            "currency": t.currency,
            "category": t.category,
        }
        for t in transactions
    ]

    # Get baseline forecast
    baseline = forecast_cashflow(
        txn_dicts,
        n_periods=payload.n_periods,
        interval=payload.interval,
    )

    # Convert scenario models to plain dicts
    scenarios_dicts = [sc.model_dump(exclude_none=True) for sc in payload.scenarios]

    result = simulate(
        baseline_result=baseline,
        scenarios=scenarios_dicts,
        scenario_name=payload.scenario_name,
        opening_balance=payload.opening_balance,
    )

    result["n_transactions_used"] = len(txn_dicts)
    result["currency"] = currency or "all"
    return result
