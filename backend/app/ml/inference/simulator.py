"""
FinMind AI — Business Financial Digital Twin Simulator (USP 5)
==============================================================
Allows users to model "what-if" scenarios against their actual
historical financial data and forecast.

CRITICAL: This service NEVER modifies real transactions or balances.
All outputs are simulation results only.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


SCENARIO_TYPES = [
    "revenue_change",           # % increase/decrease in revenue
    "expense_change",           # add/remove a recurring expense
    "one_time_expense",         # one-time capital expense
    "hiring",                   # hire employee with monthly salary
    "rent_change",              # rent increase/decrease
    "delayed_payment",          # large customer payment delayed N months
    "vendor_cost_change",       # vendor cost increase/decrease
    "marketing_spend_change",   # change marketing budget
]


def _apply_scenario(
    historical: List[Dict[str, Any]],
    scenario: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Apply a scenario modification to historical/forecast periods.
    Returns a modified copy — does NOT mutate input.
    """
    scenario_type = scenario.get("type", "")
    periods = [dict(p) for p in historical]  # shallow copy

    for period in periods:
        if not period.get("is_forecast", True):
            continue  # only modify future periods

        if scenario_type == "revenue_change":
            pct = float(scenario.get("revenue_pct_change", 0)) / 100.0
            period["revenue"] = max(0.0, round(period["revenue"] * (1 + pct), 2))
            period["net"] = round(period["revenue"] - period["expenses"], 2)

        elif scenario_type == "expense_change":
            monthly_delta = float(scenario.get("monthly_expense_delta", 0))
            period["expenses"] = max(0.0, round(period["expenses"] + monthly_delta, 2))
            period["net"] = round(period["revenue"] - period["expenses"], 2)

        elif scenario_type == "one_time_expense":
            # Applied only to the FIRST forecast period
            if period == periods[0]:
                amount = float(scenario.get("amount", 0))
                period["expenses"] = round(period["expenses"] + amount, 2)
                period["net"] = round(period["revenue"] - period["expenses"], 2)

        elif scenario_type == "hiring":
            monthly_salary = float(scenario.get("monthly_salary", 0))
            period["expenses"] = round(period["expenses"] + monthly_salary, 2)
            period["net"] = round(period["revenue"] - period["expenses"], 2)

        elif scenario_type == "rent_change":
            rent_delta = float(scenario.get("monthly_rent_delta", 0))
            period["expenses"] = max(0.0, round(period["expenses"] + rent_delta, 2))
            period["net"] = round(period["revenue"] - period["expenses"], 2)

        elif scenario_type == "delayed_payment":
            delay_months = int(scenario.get("delay_months", 1))
            amount = float(scenario.get("amount", 0))
            # Revenue reduction in first `delay_months` periods
            idx = periods.index(period)
            if idx < delay_months:
                period["revenue"] = max(0.0, round(period["revenue"] - amount / delay_months, 2))
                period["net"] = round(period["revenue"] - period["expenses"], 2)

        elif scenario_type == "vendor_cost_change":
            monthly_delta = float(scenario.get("monthly_cost_delta", 0))
            period["expenses"] = max(0.0, round(period["expenses"] + monthly_delta, 2))
            period["net"] = round(period["revenue"] - period["expenses"], 2)

        elif scenario_type == "marketing_spend_change":
            monthly_delta = float(scenario.get("monthly_marketing_delta", 0))
            period["expenses"] = max(0.0, round(period["expenses"] + monthly_delta, 2))
            period["net"] = round(period["revenue"] - period["expenses"], 2)

        period["is_scenario"] = True

    return periods


def simulate(
    baseline_result: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    scenario_name: str = "Custom Scenario",
    opening_balance: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Run a business scenario simulation.

    Args:
        baseline_result: output from forecaster.forecast_cashflow()
        scenarios: list of scenario dicts
        scenario_name: human-readable name for this simulation
        opening_balance: known opening cash (from balance column); None = unknown

    Returns:
        {
            scenario_name: str,
            baseline: list[period_dicts],
            simulated: list[period_dicts],
            cumulative_net_baseline: float,
            cumulative_net_simulated: float,
            cash_runway_note: str,
            impact_summary: list[str],
            is_simulation: True,
        }
    """
    if baseline_result.get("status") != "ok":
        return {
            "error": "Cannot simulate: baseline forecast failed. " + baseline_result.get("reason", ""),
            "status": "baseline_unavailable",
        }

    all_periods = baseline_result.get("historical", []) + baseline_result.get("forecast", [])

    simulated = [dict(p) for p in all_periods]

    for scenario in scenarios:
        simulated = _apply_scenario(simulated, scenario)

    baseline_forecast = [p for p in all_periods if p.get("is_forecast", False)]
    simulated_forecast = [p for p in simulated if p.get("is_forecast", False) or p.get("is_scenario", False)]

    cum_baseline = sum(p.get("net", 0) for p in baseline_forecast)
    cum_simulated = sum(p.get("net", 0) for p in [p for p in simulated if p.get("is_forecast", False) or p.get("is_scenario", False)])

    impact = round(cum_simulated - cum_baseline, 2)
    impact_pct = round((impact / abs(cum_baseline) * 100) if cum_baseline != 0 else 0, 1)

    impact_summary = []
    for sc in scenarios:
        sc_type = sc.get("type", "unknown")
        impact_summary.append(f"Scenario '{sc_type}' applied to forecast periods.")

    if impact > 0:
        impact_summary.append(f"Net positive impact: +{impact:,.2f} over forecast period (+{impact_pct}%).")
    elif impact < 0:
        impact_summary.append(f"Net negative impact: {impact:,.2f} over forecast period ({impact_pct}%).")
    else:
        impact_summary.append("No net change in cash flow over the forecast period.")

    # Cash runway estimate
    if opening_balance is not None:
        avg_monthly_net = cum_simulated / max(len(simulated_forecast), 1)
        if avg_monthly_net < 0:
            runway_months = int(opening_balance / abs(avg_monthly_net))
            runway_note = (
                f"At the simulated burn rate, estimated cash runway is ~{runway_months} month(s) "
                f"from an opening balance of {opening_balance:,.2f}. "
                "This is an estimate based on the forecast scenario — actual results will vary."
            )
        else:
            runway_note = (
                "Simulated scenario shows positive or neutral cash flow over the forecast period. "
                "Cash runway is not a limiting concern under these assumptions."
            )
    else:
        runway_note = (
            "Opening cash balance is unknown (no balance column in uploaded statements). "
            "Cash runway cannot be calculated. Upload statements with a balance column to enable this."
        )

    return {
        "scenario_name": scenario_name,
        "baseline": all_periods,
        "simulated": simulated,
        "cumulative_net_baseline": round(cum_baseline, 2),
        "cumulative_net_simulated": round(cum_simulated, 2),
        "impact": impact,
        "impact_pct": impact_pct,
        "cash_runway_note": runway_note,
        "impact_summary": impact_summary,
        "is_simulation": True,
        "disclaimer": (
            "SIMULATION ONLY — These projections are based on scenario assumptions. "
            "No real transactions or balances have been modified."
        ),
    }
