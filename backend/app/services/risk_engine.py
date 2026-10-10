"""
Fraud / Risk Detection Engine
==============================
Rule-based scoring that produces a 0-100 risk score with
human-readable signal explanations.  Designed to be replaced
with an ML model without changing the public interface.
"""

import json
import datetime
from typing import Any, Optional, List, Dict

# ── Currency-aware thresholds ────────────────────────────────
CURRENCY_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "USD": {
        "large": 2_000.0,
        "very_large": 10_000.0,
    },
    "INR": {
        "large": 50_000.0,
        "very_large": 250_000.0,
    },
    "EUR": {
        "large": 2_000.0,
        "very_large": 10_000.0,
    },
    "GBP": {
        "large": 1_500.0,
        "very_large": 8_000.0,
    },
}

DEFAULT_CURRENCY_THRESHOLDS: Dict[str, float] = {
    "large": 2_000.0,
    "very_large": 10_000.0,
}

# Currency symbols for human-readable signals
CURRENCY_SYMBOLS: Dict[str, str] = {
    "USD": "$",
    "INR": "₹",
    "EUR": "€",
    "GBP": "£",
}

HIGH_VELOCITY_COUNT = 5                   # txns in the window
VELOCITY_WINDOW_MINUTES = 30
NIGHT_HOUR_START = 0
NIGHT_HOUR_END = 5                        # 00:00 – 04:59 UTC

HIGH_RISK_CATEGORIES = {
    "gambling", "cryptocurrency", "wire transfer",
    "foreign exchange", "money transfer",
}

SUSPICIOUS_MERCHANTS = {
    "unknown merchant", "unverified", "new vendor",
}

# Categories that are typically income — apply reduced risk scoring
INCOME_CATEGORIES = {"income", "salary", "dividend", "refund"}


def _risk_level(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _currency_fmt(currency: str, amount: float) -> str:
    """Format an amount with the correct currency symbol/code."""
    sym = CURRENCY_SYMBOLS.get(currency.upper())
    if sym:
        return f"{sym}{amount:,.2f}"
    # Unknown currency — use the code
    return f"{currency.upper()} {amount:,.2f}"


def calculate_risk(
    amount: float,
    currency: str,
    merchant: str,
    category: str,
    location: Optional[str],
    payment_method: Optional[str],
    timestamp: datetime.datetime,
    user_recent_transactions: List[Dict[str, Any]],   # list of recent txn dicts
    user_avg_amount: float,                            # historical average amount (same currency)
    is_new_merchant: bool,
    transaction_type: str = "debit",                  # "debit" | "credit"
) -> Dict[str, Any]:
    """
    Returns:
        {
            "risk_score": float (0-100),
            "risk_level": str,
            "signals": list[str],
        }
    """
    score = 0.0
    signals: list[str] = []

    cur = currency.upper() if currency else "USD"
    thresholds = CURRENCY_THRESHOLDS.get(cur, DEFAULT_CURRENCY_THRESHOLDS)
    is_income = transaction_type == "credit" or category.lower() in INCOME_CATEGORIES

    # ── Rule 1: Transaction amount ───────────────────────────
    # Income credits (salary, etc.) get a significantly reduced large-amount penalty
    # to avoid false positives on legitimate salary deposits.
    if amount >= thresholds["very_large"]:
        if is_income:
            # Only mild flag for very large income credits
            score += 10
            signals.append(f"Very large income credit ({_currency_fmt(cur, amount)})")
        else:
            score += 35
            signals.append(f"Very large transaction ({_currency_fmt(cur, amount)})")
    elif amount >= thresholds["large"]:
        if is_income:
            # No flag for ordinary salary-range income credits
            pass
        else:
            score += 20
            signals.append(f"Large transaction ({_currency_fmt(cur, amount)})")

    # ── Rule 1b: Amount vs historical average ─────────────────
    # Only compare same-currency averages; avg_amount of 0 means no history
    if user_avg_amount > 0 and amount > user_avg_amount * 4 and not is_income:
        score += 20
        signals.append(
            f"Amount is {amount / user_avg_amount:.1f}× your historical average "
            f"({_currency_fmt(cur, user_avg_amount)})"
        )

    # ── Rule 2: High-risk category ───────────────────────────
    if category.lower() in HIGH_RISK_CATEGORIES:
        score += 25
        signals.append(f"High-risk category: {category}")

    # ── Rule 3: Suspicious / new merchant ────────────────────
    if merchant.lower() in SUSPICIOUS_MERCHANTS or "unknown" in merchant.lower():
        score += 20
        signals.append(f"Suspicious or unrecognized merchant: {merchant}")
    elif is_new_merchant and not is_income:
        score += 10
        signals.append(f"New / unrecognized merchant: {merchant}")

    # ── Rule 4: Transaction velocity ─────────────────────────
    cutoff = timestamp - datetime.timedelta(minutes=VELOCITY_WINDOW_MINUTES)
    recent = []
    for t in user_recent_transactions:
        try:
            ts = datetime.datetime.fromisoformat(t["timestamp"])
            if ts >= cutoff:
                recent.append(t)
        except (KeyError, ValueError):
            pass

    if len(recent) >= HIGH_VELOCITY_COUNT:
        score += 20
        signals.append(
            f"High transaction velocity: {len(recent)} transactions in {VELOCITY_WINDOW_MINUTES} min"
        )

    # ── Rule 5: Unusual hour ─────────────────────────────────
    hour = timestamp.hour
    if NIGHT_HOUR_START <= hour < NIGHT_HOUR_END:
        score += 10
        signals.append(f"Unusual transaction time: {timestamp.strftime('%H:%M')} UTC")

    # ── Rule 6: Unknown location ─────────────────────────────
    if location and location.lower() in {"unknown", "foreign", "offshore"}:
        score += 15
        signals.append(f"Unusual location: {location}")

    # ── Rule 7: Risky payment method ─────────────────────────
    if payment_method and payment_method.lower() in {"crypto", "cash", "wire"}:
        score += 10
        signals.append(f"Risky payment method: {payment_method}")

    score = min(score, 100.0)

    return {
        "risk_score": round(score, 1),
        "risk_level": _risk_level(score),
        "signals": signals,
    }


def encode_signals(signals: List[str]) -> str:
    return json.dumps(signals)


def decode_signals(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []
