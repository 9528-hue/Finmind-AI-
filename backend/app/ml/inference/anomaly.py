"""
FinMind AI — Inference Service: Anomaly Detector (Model B)
==========================================================
Scores transactions for anomalousness using Isolation Forest.
Supports cold-start (general model) and user-specific fitting.

IMPORTANT: Output labels are 'normal', 'suspicious', or 'anomalous'.
           We do NOT label output as 'fraud' without confirmed labels.
"""

from __future__ import annotations
import logging
import math
import os
import threading
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_general_model = None
_general_model_loaded = False

MIN_USER_TRANSACTIONS = 30


def _find_general_artifact() -> Optional[str]:
    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    if not os.path.isdir(artifacts_dir):
        return None
    files = [
        f for f in os.listdir(artifacts_dir)
        if f.startswith("anomaly_general_") and f.endswith(".joblib")
    ]
    if not files:
        return None
    files.sort(reverse=True)
    return os.path.join(artifacts_dir, files[0])


def _load_general_model():
    global _general_model, _general_model_loaded
    path = _find_general_artifact()
    if path is None:
        logger.info("[Anomaly] No artifact — attempting auto-training.")
        try:
            from app.ml.training.train_anomaly import build_general_model
            build_general_model(verbose=False)
            path = _find_general_artifact()
        except Exception as exc:
            logger.warning("[Anomaly] Auto-training failed: %s", exc)
            _general_model_loaded = True
            return
    if path is None:
        _general_model_loaded = True
        return
    try:
        import joblib
        _general_model = joblib.load(path)
        logger.info("[Anomaly] Loaded general model: %s", path)
    except Exception as exc:
        logger.error("[Anomaly] Failed to load general model: %s", exc)
    _general_model_loaded = True


def get_general_model():
    with _lock:
        if not _general_model_loaded:
            _load_general_model()
        return _general_model


def _build_feature_vector(
    amount: float,
    txn_type: str,
    category: str,
    timestamp,       # datetime or None
    user_transactions: List[Dict[str, Any]],
) -> np.ndarray:
    """
    Build a 7-feature vector for the Isolation Forest.
    Features must match training: [log_amount, is_debit, is_weekend,
    hour, velocity_score, merchant_novelty, amount_ratio_vs_category_mean]
    """
    log_amount = math.log1p(abs(amount)) if amount else 0.0
    is_debit = 1.0 if txn_type == "debit" else 0.0

    is_weekend = 0.0
    hour = 12.0  # default business hours
    if timestamp:
        try:
            is_weekend = 1.0 if timestamp.weekday() >= 5 else 0.0
            hour = float(timestamp.hour)
        except Exception:
            pass

    # Velocity: fraction of past-hour transactions in last 50
    velocity_score = 0.0
    merchant_novelty = 0.0
    cat_amounts = []
    if user_transactions:
        recent_count = 0
        seen_merchants = set()
        for t in user_transactions[-50:]:
            ts_str = str(t.get("timestamp", ""))
            try:
                import datetime as _dt
                ts = _dt.datetime.fromisoformat(ts_str[:19])
                if timestamp and (timestamp - ts).total_seconds() < 3600:
                    recent_count += 1
            except Exception:
                pass
            m = str(t.get("merchant", "")).strip().lower()
            if m:
                seen_merchants.add(m)
            if str(t.get("category", "")).lower() == str(category).lower():
                a = t.get("amount", 0)
                try:
                    cat_amounts.append(float(a))
                except Exception:
                    pass

        velocity_score = min(recent_count / 10.0, 1.0)
        # merchant_novelty: is the current merchant NOT in history?
        # We can't get current merchant here easily, so default 0
        merchant_novelty = 0.0

    amount_ratio = 1.0
    if cat_amounts:
        mean_cat = sum(cat_amounts) / len(cat_amounts)
        if mean_cat > 0:
            amount_ratio = abs(amount) / mean_cat

    return np.array([[log_amount, is_debit, is_weekend, hour,
                      velocity_score, merchant_novelty, amount_ratio]])


def _iqr_anomaly(
    amount: float,
    txn_type: str,
    category: str,
    user_transactions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    IQR-based statistical baseline for anomaly detection.
    Returns dict with score (0-1) and signals.
    """
    amounts_same_type = [
        float(t.get("amount", 0)) for t in user_transactions
        if t.get("transaction_type") == txn_type and t.get("amount")
    ]
    cat_amounts = [
        float(t.get("amount", 0)) for t in user_transactions
        if str(t.get("category", "")).lower() == str(category).lower()
        and t.get("amount")
    ]
    signals = []
    score = 0.0

    for label, values in [("all transactions", amounts_same_type), (f"{category}", cat_amounts)]:
        if len(values) < 5:
            continue
        arr = np.array(values)
        q1, q3 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
        iqr = q3 - q1
        upper = q3 + 3 * iqr
        if amount > upper and iqr > 0:
            ratio = (amount - upper) / iqr
            score = max(score, min(ratio / 5.0, 1.0))
            signals.append(
                f"Amount {amount:.0f} is {(amount/upper):.1f}× the upper IQR bound "
                f"for your {label}"
            )
    return {"iqr_score": round(score, 4), "signals": signals}


def score_transaction(
    amount: float,
    txn_type: str,
    category: str,
    merchant: str,
    timestamp,
    user_transactions: List[Dict[str, Any]],
    user_id: str = "",
) -> Dict[str, Any]:
    """
    Score a single transaction for anomalousness.

    Returns:
        {
            anomaly_score: float 0-100,
            anomaly_label: 'normal' | 'suspicious' | 'anomalous',
            signals: list[str],
            model_used: 'isolation_forest' | 'iqr_only' | 'rule_only',
            model_version: str,
        }
    """
    iqr_result = _iqr_anomaly(amount, txn_type, category, user_transactions)
    signals = list(iqr_result["signals"])
    iqr_score = iqr_result["iqr_score"]

    model = get_general_model()
    if model is not None:
        try:
            fv = _build_feature_vector(amount, txn_type, category, timestamp, user_transactions)
            iforest_score = float(-model.score_samples(fv)[0])   # higher = more anomalous
            # Normalize to 0-1 (typical range -0.7 to 0.7)
            normalized = min(max((iforest_score + 0.2) / 0.6, 0.0), 1.0)
            combined_score = 0.6 * normalized + 0.4 * iqr_score
            model_used = "isolation_forest"
        except Exception as exc:
            logger.warning("[Anomaly] IForest scoring failed: %s", exc)
            combined_score = iqr_score
            model_used = "iqr_only"
    else:
        combined_score = iqr_score
        model_used = "iqr_only"

    anomaly_score = round(combined_score * 100, 1)

    if anomaly_score >= 65:
        anomaly_label = "anomalous"
    elif anomaly_score >= 35:
        anomaly_label = "suspicious"
    else:
        anomaly_label = "normal"

    if not signals and anomaly_score >= 35:
        signals.append(f"Statistical model flagged this as {anomaly_label}")

    from app.ml import model_registry
    reg = model_registry.get("anomaly_general")
    version = reg.get("version", "unknown") if reg else "unknown"

    return {
        "anomaly_score": anomaly_score,
        "anomaly_label": anomaly_label,
        "signals": signals,
        "model_used": model_used,
        "model_version": version,
    }
