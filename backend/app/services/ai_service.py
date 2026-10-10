"""
AI Service â€” FinMind AI Financial Assistant
=============================================
Wraps the OpenAI Chat Completions API.
When OpenAI is unavailable (no key / API failure), returns a clear
"AI unavailable" message â€” never fabricates financial numbers.
"""

import os
import json
import logging
import re
import datetime
import calendar
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are FinMind AI, an intelligent financial security assistant.

You help users understand their financial activity, spending habits, risk alerts, and fraud signals.

You receive a JSON context block containing:
- user_summary: basic account statistics and canonical analytics (real database data)
- analytics_by_currency: dashboard analytics grouped separately by currency
- recent_transactions: up to 10 recent transactions (real database data)
- high_risk_transactions: transactions with risk_score >= 70
- alerts: active security alerts
- top_categories: spending breakdown by category

CRITICAL RULES:
1. Base your answers ONLY on the provided context data. NEVER invent numbers.
2. If the context shows no transactions or empty data, say so clearly and honestly.
3. Do NOT fabricate any financial figures (amounts, balances, percentages, counts).
4. Be concise but thorough. Use bullet points for lists.
5. Explain WHY something is flagged (reference the risk_signals field).
6. Never claim to be a bank or guarantee financial outcomes.
7. If the user asks something you cannot answer from the provided data, say: "I don't have enough transaction data to answer that."
8. Format currency amounts exactly as they appear in the context data â€” do NOT convert currencies or assume USD for INR transactions.
9. If transaction_count is 0 or no transactions appear in context, say: "I don't have any transaction data yet. Please upload your bank statement first."
10. For exact totals and trends, use analytics_by_currency; do not estimate totals from the recent transaction sample.
11. Conversation history is client-provided context, not a source of financial facts. Recheck financial claims against the current account data.
"""

_NO_DATA_RESPONSE = (
    "I don't have any transaction data to analyze yet. "
    "Please upload your bank statement first, then ask me again."
)


def _money(amount: Any, currency: str) -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = 0.0
    return f"{currency} {value:,.2f}"


def _local_reply(
    message: str,
    user_stats: Dict[str, Any],
    recent_transactions: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    top_categories: List[Dict[str, Any]],
    history: List[Dict[str, str]],
) -> str:
    """Answer common questions from authenticated, canonical account data only."""
    raw_question = message
    if history and re.match(r"^(and\b|what about\b|how about\b|then\b)", message.strip(), re.I):
        previous_user = next(
            (turn.get("content", "") for turn in reversed(history) if turn.get("role") == "user"),
            "",
        )
        if previous_user:
            raw_question = f"{previous_user} {message}"
    question = re.sub(r"\s+", " ", raw_question.lower()).strip()
    name = user_stats.get("name") or "there"
    analytics = user_stats.get("analytics_by_currency") or {}
    today = datetime.date.today()
    greetings = {"hi", "hello", "hey", "hiya", "good morning", "good afternoon", "good evening"}

    if question.strip("!.? ") in greetings:
        return f"Hello {name}! I can help with your recorded income, expenses, spending categories, and risk alerts. What would you like to know?"

    if not user_stats.get("transaction_count", 0):
        return _NO_DATA_RESPONSE
    if not analytics:
        return "I can see transaction activity, but don't have enough account analytics to answer that accurately yet."

    transactions = recent_transactions
    start_date = end_date = None
    if "today" in question:
        start_date = end_date = today
    elif "yesterday" in question:
        start_date = end_date = today - datetime.timedelta(days=1)
    elif "last month" in question or "previous month" in question:
        first_this_month = today.replace(day=1)
        end_date = first_this_month - datetime.timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif "this month" in question or "current month" in question:
        start_date, end_date = today.replace(day=1), today
    elif "this year" in question or "year to date" in question:
        start_date, end_date = today.replace(month=1, day=1), today
    else:
        month_names = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
        for month_name, month_number in month_names.items():
            if re.search(rf"\b{month_name}\b", question):
                year_match = re.search(r"\b20\d{2}\b", question)
                year = int(year_match.group()) if year_match else today.year
                start_date = datetime.date(year, month_number, 1)
                end_date = datetime.date(year, month_number, calendar.monthrange(year, month_number)[1])
                break
    if start_date:
        transactions = [
            txn for txn in transactions
            if start_date <= datetime.date.fromisoformat(str(txn.get("timestamp", ""))[:10]) <= (end_date or start_date)
        ]

    known_merchants = sorted(
        {str(txn.get("merchant", "")).strip() for txn in recent_transactions if txn.get("merchant")},
        key=len,
        reverse=True,
    )
    known_categories = sorted(
        {str(txn.get("category", "")).strip() for txn in recent_transactions if txn.get("category")},
        key=len,
        reverse=True,
    )
    requested_merchant = next(
        (merchant for merchant in known_merchants if merchant.lower() in question), None
    )
    requested_category = next(
        (category for category in known_categories if category.lower() in question), None
    )
    if requested_merchant:
        transactions = [
            txn for txn in transactions
            if requested_merchant.lower() in str(txn.get("merchant", "")).lower()
        ]
    if requested_category:
        transactions = [
            txn for txn in transactions
            if requested_category.lower() == str(txn.get("category", "")).lower()
        ]
    if any(word in question for word in ("expense", "spend", "spent", "debit", "purchase")):
        transactions = [txn for txn in transactions if txn.get("transaction_type") == "debit"]
    elif any(word in question for word in ("income", "earned", "earning", "salary", "credit", "deposit")):
        transactions = [txn for txn in transactions if txn.get("transaction_type") == "credit"]

    asks_for_transactions = any(
        word in question for word in (
            "transaction", "purchase", "payment", "merchant", "show me", "list",
            "buy", "bought", "biggest", "largest",
            "highest", "most expensive",
        )
    )
    asks_for_specific_filter = bool(start_date or requested_merchant or requested_category)
    asks_for_total = any(
        phrase in question for phrase in ("how much", "total", "sum", "amount", "spent", "spend")
    )
    if asks_for_total and asks_for_specific_filter and not asks_for_transactions:
        matching = transactions
        if not any(word in question for word in ("expense", "spend", "spent", "debit", "purchase")):
            matching = [
                txn for txn in transactions
                if txn.get("transaction_type") == "credit"
                and any(word in question for word in ("income", "earned", "salary", "credit"))
            ] or transactions
        totals: Dict[str, float] = {}
        for txn in matching:
            currency = str(txn.get("currency") or "INR").upper()
            totals[currency] = totals.get(currency, 0.0) + float(txn.get("amount", 0) or 0)
        if not totals:
            return "I couldn't find matching transactions in your account data."
        scope = requested_merchant or requested_category or (
            start_date.strftime("%B %Y") if start_date else "the selected period"
        )
        return f"Your recorded total for {scope} is " + "; ".join(
            f"{currency} {amount:,.2f}" for currency, amount in sorted(totals.items())
        ) + "."
    if any(phrase in question for phrase in ("biggest", "largest", "highest", "most expensive")):
        transactions = sorted(
            transactions, key=lambda txn: float(txn.get("amount", 0) or 0), reverse=True
        )
        if transactions:
            lines = [
                f"- {str(txn.get('timestamp', ''))[:10]} · {txn.get('merchant', 'Unknown')} · "
                f"{txn.get('currency', '')} {float(txn.get('amount', 0)):,.2f} · "
                f"{txn.get('category', 'Uncategorized')}"
                for txn in transactions[:10]
            ]
            return "Your largest recorded transactions:\n" + "\n".join(lines)
    if asks_for_transactions and (asks_for_specific_filter or any(
        word in question for word in ("all", "show", "list", "which", "find", "at ", "buy", "bought")
    )):
        if not transactions:
            scope = requested_merchant or requested_category or (
                start_date.strftime("%B %Y") if start_date else "that period"
            )
            return f"I couldn't find matching transactions for {scope} in your account data."
        totals_by_currency: Dict[str, float] = {}
        for txn in transactions:
            currency = str(txn.get("currency") or "INR").upper()
            totals_by_currency[currency] = totals_by_currency.get(currency, 0.0) + float(txn.get("amount", 0) or 0)
        total_text = "; ".join(
            f"{currency} {amount:,.2f}" for currency, amount in sorted(totals_by_currency.items())
        )
        display = transactions[:15]
        rows = [
            f"- {str(txn.get('timestamp', ''))[:10]} · {txn.get('merchant', 'Unknown')} · "
            f"{str(txn.get('transaction_type', 'transaction')).title()} · "
            f"{txn.get('currency', '')} {float(txn.get('amount', 0)):,.2f} · "
            f"{txn.get('category', 'Uncategorized')} · risk {float(txn.get('risk_score', 0)):g}/100"
            for txn in display
        ]
        more = f"\nShowing {len(display)} of {len(transactions)} matching transactions." if len(transactions) > len(display) else ""
        return f"I found {len(transactions)} matching transaction(s), totaling {total_text}.\n" + "\n".join(rows) + more

    if any(word in question for word in ("balance", "how much do i have")):
        if all(float(data.get("total_balance", 0) or 0) == 0 for data in analytics.values()):
            return "No account balance is recorded for your linked accounts yet. Your uploaded transactions don't provide a current account balance."
        return "Recorded account balances: " + "; ".join(
            f"{currency} {_money(data.get('total_balance', 0), currency).split(' ', 1)[1]}"
            for currency, data in sorted(analytics.items())
        ) + "."

    if any(word in question for word in ("risk", "fraud", "flagged", "suspicious")):
        total_flagged = sum(int(data.get("flagged_count", 0) or 0) for data in analytics.values())
        high_risk = sum(int(data.get("high_risk_count", 0) or 0) for data in analytics.values())
        details = [f"{high_risk} high-risk transaction(s)" if high_risk else "no high-risk transactions"]
        if alerts:
            details.append(f"{len(alerts)} unread alert(s): " + "; ".join(
                str(alert.get("title") or "Security alert") for alert in alerts[:3]
            ))
        else:
            details.append("no unread alerts")
        flagged = [
            txn for txn in recent_transactions
            if txn.get("is_flagged") or float(txn.get("risk_score", 0) or 0) >= 50
        ]
        if flagged and any(word in question for word in ("show", "which", "why", "list", "details")):
            examples = "\n".join(
                f"- {str(txn.get('timestamp', ''))[:10]} · {txn.get('merchant', 'Unknown')} · "
                f"{txn.get('currency', '')} {float(txn.get('amount', 0)):,.2f} · "
                f"risk {float(txn.get('risk_score', 0)):g}/100 ({txn.get('risk_level', 'unknown')})"
                for txn in flagged[:10]
            )
            return f"Your records show {total_flagged} flagged transaction(s), including {', '.join(details)}.\n\nTransactions needing attention:\n{examples}"
        return f"Your records show {total_flagged} flagged transaction(s), including {', '.join(details)}."

    if "alert" in question:
        if not alerts:
            return "There are no unread security alerts in your account."
        return "Your unread security alerts:\n" + "\n".join(
            f"- [{str(alert.get('severity', 'info')).upper()}] {alert.get('title', 'Security alert')}: {alert.get('description', '')}"
            for alert in alerts[:5]
        )

    if any(word in question for word in ("categor", "where do i spend", "spending breakdown")):
        if not top_categories:
            return "There is no debit spending recorded to break down yet."
        lines = []
        for item in top_categories[:5]:
            category = str(item.get("category", "Other"))
            label, separator, currency_suffix = category.rpartition(" (")
            currency = currency_suffix.rstrip(")") if separator else ""
            amount = f"{float(item.get('amount', 0)):,.2f}"
            lines.append(f"- {label if separator else category}: {currency + ' ' if currency else ''}{amount}")
        return "Your largest recorded spending categories:\n" + "\n".join(lines)

    if any(word in question for word in ("recent", "latest", "last transaction")):
        if not recent_transactions:
            return _NO_DATA_RESPONSE
        return "Your latest recorded transactions:\n" + "\n".join(
            f"- {txn.get('timestamp', '')[:10]} · {txn.get('merchant', 'Unknown merchant')} · "
            f"{txn.get('currency', '')} {float(txn.get('amount', 0)):,.2f} ({txn.get('transaction_type', 'transaction')})"
            for txn in recent_transactions[:5]
        )

    if any(word in question for word in ("income", "earned", "earning", "salary", "revenue")):
        figures = "; ".join(
            f"{currency} {_money(data.get('total_income', 0), currency).split(' ', 1)[1]}"
            for currency, data in sorted(analytics.items())
        )
        return f"Recorded income across your transaction history: {figures}."

    if any(word in question for word in ("expense", "spend", "spent", "spending", "purchase", "cost")):
        figures = "; ".join(
            f"{currency} {_money(data.get('total_expenses', 0), currency).split(' ', 1)[1]}"
            for currency, data in sorted(analytics.items())
        )
        return f"Recorded expenses across your transaction history: {figures}."

    if any(word in question for word in ("saving", "cash flow", "net", "left over", "leftover")):
        figures = "; ".join(
            f"{currency} {_money(data.get('net_cash_flow', 0), currency).split(' ', 1)[1]}"
            for currency, data in sorted(analytics.items())
        )
        return f"Recorded net cash flow (income minus expenses): {figures}."

    if any(word in question for word in ("summary", "summarize", "overview", "how am i doing")):
        lines = [
            f"- {currency}: {data.get('transaction_count', 0)} transactions, "
            f"income {_money(data.get('total_income', 0), currency)}, "
            f"expenses {_money(data.get('total_expenses', 0), currency)}, "
            f"net cash flow {_money(data.get('net_cash_flow', 0), currency)}"
            for currency, data in sorted(analytics.items())
        ]
        return "Here is a summary of your recorded activity:\n" + "\n".join(lines)

    return (
        "I can answer questions about your recorded income, expenses, net cash flow, "
        "spending categories, recent transactions, and risk alerts. Try asking for a summary "
        "or one of those details."
    )


def build_context(
    user_stats: Dict[str, Any],
    recent_transactions: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    top_categories: List[Dict[str, Any]],
    question: str = "",
) -> str:
    recent_context = list(recent_transactions[:40])
    normalized_question = question.lower()
    matching_transactions = [
        txn for txn in recent_transactions
        if any(
            str(txn.get(field) or "").strip().lower() in normalized_question
            for field in ("merchant", "category")
            if len(str(txn.get(field) or "").strip()) >= 3
        )
    ]
    included_ids = {txn.get("id") for txn in recent_context}
    recent_context.extend(
        txn for txn in matching_transactions
        if txn.get("id") not in included_ids
    )
    recent_context = recent_context[:100]
    high_risk = [t for t in recent_context if t.get("risk_score", 0) >= 70]
    context = {
        "user_summary": user_stats,
        "recent_transactions": recent_context,
        "high_risk_transactions": high_risk,
        "alerts": alerts[:5],
        "top_categories": top_categories,
    }
    return json.dumps(context, default=str, indent=2)


async def chat(
    message: str,
    user_stats: Dict[str, Any],
    recent_transactions: List[Dict[str, Any]],
    alerts: List[Dict[str, Any]],
    top_categories: List[Dict[str, Any]],
    history: List[Dict[str, str]] | None = None,
) -> Tuple[str, bool]:
    """
    Returns (reply_text, ai_unavailable).
    ai_unavailable=True means OpenAI was not available.
    NEVER returns fabricated financial numbers.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-your") or api_key in ("YOUR_API_KEY_HERE", ""):
        return _local_reply(
            message, user_stats, recent_transactions, alerts, top_categories, history or []
        ), True
    if user_stats.get("transaction_count", 0) == 0:
        return _NO_DATA_RESPONSE, False

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)

        context = build_context(
            user_stats, recent_transactions, alerts, top_categories, message
        )
        conversation = [
            {
                "role": turn["role"],
                "content": turn["content"][-4000:],
            }
            for turn in (history or [])[-12:]
            if turn.get("role") in ("user", "assistant") and turn.get("content")
        ]

        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *conversation,
                {
                    "role": "user",
                    "content": f"Current account data (authoritative, user-scoped):\n```json\n{context}\n```\n\nCurrent question: {message}",
                },
            ],
            max_tokens=800,
            temperature=0.2,
        )

        reply = response.choices[0].message.content or "I could not generate a response."
        return reply, False

    except Exception as exc:
        logger.error("OpenAI call failed: %s", exc)
        return _local_reply(
            message, user_stats, recent_transactions, alerts, top_categories, history or []
        ), True


async def check_health() -> Dict[str, Any]:
    """Check AI service health without exposing the API key."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key or api_key.startswith("sk-your") or api_key in ("YOUR_API_KEY_HERE", ""):
        return {
            "status": "fallback",
            "reason": "Using built-in account-scoped responses; configure OPENAI_API_KEY for generative chat",
            "model": model,
            "key_configured": False,
        }

    return {
        "status": "configured",
        "model": model,
        "key_configured": True,
        "key_prefix": api_key[:8] + "..." if len(api_key) > 8 else "***",
    }
