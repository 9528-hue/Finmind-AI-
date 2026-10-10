"""
FinMind AI — Inference Service: Cash Flow Forecaster (Model C)
==============================================================
Forecasts revenue, expenses, and net cash flow using historical
transaction data aggregated by week or month.

Algorithms evaluated (in order of preference based on data size):
  1. Exponential Smoothing (statsmodels.ExponentialSmoothing)
  2. ARIMA (statsmodels.ARIMA)
  3. Naive seasonal baseline (average of last N periods)

All forecasts include explicit uncertainty notes.
NEVER uses an LLM to generate numerical forecasts.

Minimum data requirements:
  - Monthly: at least 3 complete months of data
  - Weekly: at least 6 complete weeks of data
"""

from __future__ import annotations
import logging
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_MONTHLY_POINTS = 3
MIN_WEEKLY_POINTS = 6
FORECAST_PERIODS = 3   # how many future periods to predict


def _aggregate_by_month(
    transactions: List[Dict[str, Any]]
) -> Dict[str, Dict[str, float]]:
    """Aggregate to {YYYY-MM: {revenue, expenses, net}}."""
    buckets: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"revenue": 0.0, "expenses": 0.0}
    )
    for txn in transactions:
        ts = txn.get("timestamp") or txn.get("date") or ""
        try:
            key = str(ts)[:7]  # YYYY-MM
            if len(key) < 7 or key[4] != "-":
                continue
        except Exception:
            continue
        amount = float(txn.get("amount", 0) or 0)
        if txn.get("transaction_type") == "credit":
            buckets[key]["revenue"] += amount
        else:
            buckets[key]["expenses"] += amount
    for key, vals in buckets.items():
        vals["net"] = vals["revenue"] - vals["expenses"]
    return dict(sorted(buckets.items()))


def _aggregate_by_week(
    transactions: List[Dict[str, Any]]
) -> Dict[str, Dict[str, float]]:
    """Aggregate to {YYYY-Www: {revenue, expenses, net}}."""
    buckets: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"revenue": 0.0, "expenses": 0.0}
    )
    for txn in transactions:
        ts = txn.get("timestamp") or txn.get("date") or ""
        try:
            import datetime
            dt = datetime.datetime.fromisoformat(str(ts)[:19])
            iso = dt.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        except Exception:
            continue
        amount = float(txn.get("amount", 0) or 0)
        if txn.get("transaction_type") == "credit":
            buckets[key]["revenue"] += amount
        else:
            buckets[key]["expenses"] += amount
    for key, vals in buckets.items():
        vals["net"] = vals["revenue"] - vals["expenses"]
    return dict(sorted(buckets.items()))


def _naive_forecast(values: List[float], n_periods: int, n_avg: int = 3) -> Tuple[List[float], str]:
    """Naive seasonal: average of last n_avg observed values."""
    avg = sum(values[-n_avg:]) / min(n_avg, len(values))
    return [round(avg, 2)] * n_periods, "naive_average"


def _exponential_smoothing_forecast(
    values: List[float], n_periods: int
) -> Tuple[Optional[List[float]], str]:
    try:
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = SimpleExpSmoothing(values, initialization_method="estimated")
            fit = model.fit(optimized=True)
            forecast = fit.forecast(n_periods)
            return [round(float(v), 2) for v in forecast], "exponential_smoothing"
    except Exception as exc:
        logger.debug("[Forecast] ExponentialSmoothing failed: %s", exc)
        return None, ""


def _arima_forecast(
    values: List[float], n_periods: int
) -> Tuple[Optional[List[float]], str]:
    try:
        from statsmodels.tsa.arima.model import ARIMA
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ARIMA(values, order=(1, 1, 0))
            fit = model.fit()
            forecast = fit.forecast(n_periods)
            return [round(float(v), 2) for v in forecast], "arima_1_1_0"
    except Exception as exc:
        logger.debug("[Forecast] ARIMA failed: %s", exc)
        return None, ""


def _mae(actual: List[float], predicted: List[float]) -> Optional[float]:
    if not actual or len(actual) != len(predicted):
        return None
    return round(sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual), 2)


def _best_forecast(
    values: List[float], n_periods: int
) -> Tuple[List[float], str, Optional[float]]:
    """
    Try ES → ARIMA → Naive. Use leave-one-out on last period to pick.
    Returns (forecast_values, method_name, hold_out_mae).
    """
    if len(values) < 4:
        fcast, method = _naive_forecast(values, n_periods)
        return fcast, method, None

    # Hold out last 1 point for error estimation
    train = values[:-1]
    actual_last = [values[-1]]

    best_fcast = None
    best_method = "naive_average"
    best_mae = None

    # Try ES
    es_fcast, es_method = _exponential_smoothing_forecast(train + [actual_last[0]], n_periods)
    es_holdout, _ = _exponential_smoothing_forecast(train, 1)
    if es_fcast and es_holdout:
        mae = _mae(actual_last, es_holdout)
        if best_mae is None or (mae is not None and mae < best_mae):
            best_mae = mae
            best_fcast = es_fcast
            best_method = es_method

    # Try ARIMA
    if len(values) >= 6:
        ar_fcast, ar_method = _arima_forecast(values, n_periods)
        ar_holdout, _ = _arima_forecast(train, 1)
        if ar_fcast and ar_holdout:
            mae = _mae(actual_last, ar_holdout)
            if best_mae is None or (mae is not None and mae < best_mae):
                best_mae = mae
                best_fcast = ar_fcast
                best_method = ar_method

    if best_fcast is None:
        naive_fcast, naive_method = _naive_forecast(values, n_periods)
        naive_holdout, _ = _naive_forecast(train, 1)
        best_mae = _mae(actual_last, naive_holdout)
        return naive_fcast, naive_method, best_mae

    return best_fcast, best_method, best_mae


def forecast_cashflow(
    transactions: List[Dict[str, Any]],
    n_periods: int = FORECAST_PERIODS,
    interval: str = "monthly",
) -> Dict[str, Any]:
    """
    Forecast future cash flow from transaction history.

    Args:
        transactions: list of transaction dicts with timestamp/amount/transaction_type
        n_periods: number of future periods to forecast
        interval: 'monthly' or 'weekly'

    Returns dict:
        {
          status: 'ok' | 'insufficient_data',
          reason: str (if insufficient_data),
          interval: str,
          historical: [{period, revenue, expenses, net}],
          forecast: [{period, revenue, expenses, net, is_forecast: True}],
          method: str,
          hold_out_mae: float|None,
          uncertainty_note: str,
          n_historical_periods: int,
        }
    """
    if interval == "weekly":
        aggregated = _aggregate_by_week(transactions)
        min_pts = MIN_WEEKLY_POINTS
    else:
        aggregated = _aggregate_by_month(transactions)
        min_pts = MIN_MONTHLY_POINTS
        interval = "monthly"

    periods = list(aggregated.keys())
    n_hist = len(periods)

    if n_hist < min_pts:
        return {
            "status": "insufficient_data",
            "reason": (
                f"Only {n_hist} complete {interval} period(s) of data found. "
                f"Need at least {min_pts} to produce a reliable forecast. "
                "Upload more transaction history and try again."
            ),
            "interval": interval,
            "n_historical_periods": n_hist,
            "historical": [],
            "forecast": [],
        }

    rev_vals = [aggregated[p]["revenue"] for p in periods]
    exp_vals = [aggregated[p]["expenses"] for p in periods]

    rev_fcast, rev_method, rev_mae = _best_forecast(rev_vals, n_periods)
    exp_fcast, exp_method, exp_mae = _best_forecast(exp_vals, n_periods)

    # Build forecast period labels
    forecast_periods = []
    try:
        if interval == "monthly":
            import datetime
            last = periods[-1]  # YYYY-MM
            y, m = int(last[:4]), int(last[5:7])
            for _ in range(n_periods):
                m += 1
                if m > 12:
                    m = 1
                    y += 1
                forecast_periods.append(f"{y}-{m:02d}")
        else:
            import datetime
            last = periods[-1]  # YYYY-Www
            yr, wk = int(last[:4]), int(last[6:])
            for _ in range(n_periods):
                wk += 1
                if wk > 52:
                    wk = 1
                    yr += 1
                forecast_periods.append(f"{yr}-W{wk:02d}")
    except Exception:
        forecast_periods = [f"Period+{i+1}" for i in range(n_periods)]

    historical = [
        {
            "period": p,
            "revenue": round(aggregated[p]["revenue"], 2),
            "expenses": round(aggregated[p]["expenses"], 2),
            "net": round(aggregated[p]["net"], 2),
            "is_forecast": False,
        }
        for p in periods
    ]

    forecast_list = []
    for i, fp in enumerate(forecast_periods):
        rev = rev_fcast[i] if i < len(rev_fcast) else 0.0
        exp = exp_fcast[i] if i < len(exp_fcast) else 0.0
        forecast_list.append({
            "period": fp,
            "revenue": max(rev, 0.0),
            "expenses": max(exp, 0.0),
            "net": round(max(rev, 0.0) - max(exp, 0.0), 2),
            "is_forecast": True,
        })

    hold_out_mae = None
    if rev_mae is not None and exp_mae is not None:
        hold_out_mae = round((rev_mae + exp_mae) / 2, 2)
    elif rev_mae is not None:
        hold_out_mae = rev_mae

    return {
        "status": "ok",
        "interval": interval,
        "n_historical_periods": n_hist,
        "historical": historical,
        "forecast": forecast_list,
        "method": f"revenue={rev_method}, expenses={exp_method}",
        "hold_out_mae": hold_out_mae,
        "uncertainty_note": (
            "Forecast is a statistical estimate based on historical patterns. "
            "Actual results may differ significantly. "
            f"Historical data: {n_hist} {interval} period(s). "
            f"Hold-out MAE (last period): {hold_out_mae if hold_out_mae is not None else 'N/A'}."
        ),
    }
