"""
Reports Router â€” FINMIND AI
=============================
Provides downloadable CSV and PDF reports for:
  - All transactions
  - Flagged transactions only
  - Financial summary (PDF)
"""

import io
import csv
import datetime
import json
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Transaction, Alert, Account, User
from app.services.auth_service import get_current_user
from app.services.financial_metrics import is_revenue_category

router = APIRouter(prefix="/reports", tags=["reports"])


def _safe_csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_transactions(
    db: Session,
    user_id: str,
    flagged_only: bool = False,
    date_from: Optional[datetime.date] = None,
    date_to: Optional[datetime.date] = None,
    currency: Optional[str] = None,
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    search: Optional[str] = None,
    amount_min: Optional[float] = None,
    amount_max: Optional[float] = None,
    risk_score_min: Optional[float] = None,
    risk_score_max: Optional[float] = None,
    risk_level: Optional[str] = None,
    transaction_status: Optional[str] = None,
) -> list:
    q = db.query(Transaction).filter(Transaction.user_id == user_id)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise HTTPException(status_code=400, detail="Minimum amount must not exceed maximum amount")
    if risk_score_min is not None and risk_score_max is not None and risk_score_min > risk_score_max:
        raise HTTPException(status_code=400, detail="Minimum risk score must not exceed maximum risk score")
    if flagged_only:
        q = q.filter(Transaction.is_flagged == True)  # noqa: E712
    if date_from:
        q = q.filter(Transaction.timestamp >= datetime.datetime.combine(date_from, datetime.time.min))
    if date_to:
        q = q.filter(Transaction.timestamp < datetime.datetime.combine(
            date_to + datetime.timedelta(days=1), datetime.time.min
        ))
    if currency:
        q = q.filter(func.upper(Transaction.currency) == currency.upper())
    if category:
        q = q.filter(Transaction.category.ilike(f"%{category}%"))
    if transaction_type:
        q = q.filter(Transaction.transaction_type == transaction_type)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            Transaction.merchant.ilike(term)
            | Transaction.description.ilike(term)
            | Transaction.category.ilike(term)
        )
    if amount_min is not None:
        q = q.filter(Transaction.amount >= amount_min)
    if amount_max is not None:
        q = q.filter(Transaction.amount <= amount_max)
    if risk_score_min is not None:
        q = q.filter(Transaction.risk_score >= risk_score_min)
    if risk_score_max is not None:
        q = q.filter(Transaction.risk_score <= risk_score_max)
    if risk_level:
        q = q.filter(func.lower(Transaction.risk_level) == risk_level.lower())
    if transaction_status:
        q = q.filter(func.lower(Transaction.status) == transaction_status.lower())
    return q.order_by(Transaction.timestamp.desc()).all()


# â”€â”€ CSV Reports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.get("/analytics/csv")
def download_analytics_csv(
    report_type: str = Query(..., pattern="^(monthly|category|merchant|risk|fraud|alerts)$"),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    category: Optional[str] = Query(None, max_length=100),
    transaction_type: Optional[str] = Query(None, pattern="^(credit|debit)$"),
    search: Optional[str] = Query(None, max_length=100),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    amount_min: Optional[float] = Query(None, ge=0),
    amount_max: Optional[float] = Query(None, ge=0),
    risk_score_min: Optional[float] = Query(None, ge=0, le=100),
    risk_score_max: Optional[float] = Query(None, ge=0, le=100),
    transaction_status: Optional[str] = Query(None, max_length=30),
    flagged_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download user-scoped monthly, category, risk, or alert data as CSV."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")

    output = io.StringIO()
    writer = csv.writer(output)
    if report_type == "alerts":
        query = db.query(Alert).filter(Alert.user_id == current_user.id)
        transaction_filter_active = any((
            currency, category, transaction_type, search, risk_level,
            amount_min is not None, amount_max is not None,
            risk_score_min is not None, risk_score_max is not None,
            transaction_status, flagged_only,
        ))
        if transaction_filter_active:
            matching_txns = _get_transactions(
                db, current_user.id, date_from=date_from, date_to=date_to, currency=currency,
                category=category, transaction_type=transaction_type, search=search,
                amount_min=amount_min, amount_max=amount_max,
                risk_score_min=risk_score_min, risk_score_max=risk_score_max,
                risk_level=risk_level, transaction_status=transaction_status,
                flagged_only=flagged_only,
            )
            matching_ids = [txn.id for txn in matching_txns]
            query = query.filter(Alert.transaction_id.in_(matching_ids)) if matching_ids else query.filter(False)
        if date_from:
            query = query.filter(Alert.created_at >= datetime.datetime.combine(date_from, datetime.time.min))
        if date_to:
            query = query.filter(Alert.created_at < datetime.datetime.combine(
                date_to + datetime.timedelta(days=1), datetime.time.min
            ))
        txn_ids = {alert.transaction_id for alert in query.all() if alert.transaction_id}
        txn_by_id = {
            txn.id: txn for txn in db.query(Transaction).filter(
                Transaction.user_id == current_user.id,
                Transaction.id.in_(txn_ids) if txn_ids else False,
            ).all()
        }
        writer.writerow([
            "Alert ID", "Title", "Description", "Severity", "Transaction ID",
            "Amount", "Currency", "Risk Level", "Created At", "Read Status",
        ])
        for alert in query.order_by(Alert.created_at.desc()).all():
            txn = txn_by_id.get(alert.transaction_id)
            writer.writerow([
                _safe_csv_cell(alert.id), _safe_csv_cell(alert.title), _safe_csv_cell(alert.description),
                _safe_csv_cell(alert.severity), _safe_csv_cell(alert.transaction_id or ""),
                f"{txn.amount:.2f}" if txn else "",
                _safe_csv_cell(txn.currency if txn else ""),
                _safe_csv_cell(txn.risk_level if txn else ""),
                alert.created_at.isoformat(), "Yes" if alert.is_read else "No",
            ])
    else:
        transactions = _get_transactions(
            db, current_user.id, date_from=date_from, date_to=date_to,
            currency=currency, category=category, transaction_type=transaction_type,
            search=search, risk_level=risk_level, amount_min=amount_min, amount_max=amount_max,
            risk_score_min=risk_score_min, risk_score_max=risk_score_max,
            transaction_status=transaction_status, flagged_only=flagged_only,
        )
        if report_type == "monthly":
            totals = defaultdict(lambda: {
                "income": 0.0, "revenue": 0.0, "expenses": 0.0, "count": 0, "risky": 0,
            })
            for txn in transactions:
                key = (txn.timestamp.strftime("%Y-%m"), txn.currency.upper())
                totals[key]["count"] += 1
                if txn.transaction_type == "credit":
                    totals[key]["income"] += txn.amount
                    if is_revenue_category(txn.category):
                        totals[key]["revenue"] += txn.amount
                else:
                    totals[key]["expenses"] += txn.amount
                totals[key]["risky"] += int(txn.is_flagged or txn.risk_level.lower() in ("medium", "high"))
            writer.writerow([
                "Month", "Currency", "Income", "Revenue", "Expenses", "Net Cash Flow",
                "Savings", "Savings Rate", "Transactions", "Risky Transactions",
            ])
            for (month, code), values in sorted(totals.items()):
                net = values["income"] - values["expenses"]
                writer.writerow([
                    month, code, f"{values['income']:.2f}",
                    f"{values['revenue']:.2f}" if values["revenue"] else "",
                    f"{values['expenses']:.2f}", f"{net:.2f}", f"{net:.2f}",
                    f"{net / values['income'] * 100:.1f}" if values["income"] else "",
                    values["count"], values["risky"],
                ])
        elif report_type == "category":
            totals = defaultdict(lambda: {"amount": 0.0, "count": 0})
            for txn in transactions:
                if txn.transaction_type == "debit":
                    item = totals[(txn.category, txn.currency.upper())]
                    item["amount"] += txn.amount
                    item["count"] += 1
            writer.writerow(["Category", "Currency", "Expense Total", "Transactions"])
            for (category_name, code), values in sorted(
                totals.items(), key=lambda item: (item[0][1], -item[1]["amount"], item[0][0])
            ):
                writer.writerow([_safe_csv_cell(category_name), code, f"{values['amount']:.2f}", values["count"]])
        elif report_type == "merchant":
            totals = defaultdict(lambda: {"amount": 0.0, "count": 0, "largest": 0.0})
            for txn in transactions:
                if txn.transaction_type == "debit":
                    item = totals[(txn.merchant, txn.currency.upper())]
                    item["amount"] += txn.amount
                    item["count"] += 1
                    item["largest"] = max(item["largest"], txn.amount)
            writer.writerow([
                "Merchant", "Currency", "Total Spending", "Transaction Count",
                "Average Transaction", "Largest Transaction",
            ])
            for (merchant_name, code), values in sorted(
                totals.items(), key=lambda item: (item[0][1], -item[1]["amount"], item[0][0])
            ):
                writer.writerow([
                    _safe_csv_cell(merchant_name), code, f"{values['amount']:.2f}", values["count"],
                    f"{values['amount'] / values['count']:.2f}", f"{values['largest']:.2f}",
                ])
        elif report_type == "fraud":
            writer.writerow([
                "Transaction ID", "Date", "Merchant", "Description", "Amount",
                "Currency", "Category", "Risk Score", "Risk Level", "Risk Signals", "Flagged",
            ])
            for txn in transactions:
                if txn.is_flagged or txn.risk_level.lower() in ("medium", "high"):
                    writer.writerow([
                        txn.id, txn.timestamp.isoformat(), _safe_csv_cell(txn.merchant),
                        _safe_csv_cell(txn.description or ""),
                        f"{txn.amount:.2f}", txn.currency, _safe_csv_cell(txn.category),
                        f"{txn.risk_score:.1f}", _safe_csv_cell(txn.risk_level),
                        _safe_csv_cell(txn.risk_signals or ""),
                        "Yes" if txn.is_flagged else "No",
                    ])
        else:
            totals = defaultdict(lambda: {"count": 0, "flagged": 0, "score": 0.0})
            for txn in transactions:
                item = totals[(txn.risk_level.lower(), txn.currency.upper())]
                item["count"] += 1
                item["flagged"] += int(txn.is_flagged)
                item["score"] += txn.risk_score
            writer.writerow(["Risk Level", "Currency", "Transactions", "Flagged", "Average Risk Score"])
            for (level, code), values in sorted(totals.items()):
                writer.writerow([
                    level, code, values["count"], values["flagged"],
                    f"{values['score'] / values['count']:.1f}",
                ])

    filename = f"FinMind_{report_type}_{datetime.date.today()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/security/pdf")
def download_security_pdf(
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    category: Optional[str] = Query(None, max_length=100),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    search: Optional[str] = Query(None, max_length=100),
    transaction_type: Optional[str] = Query(None, pattern="^(credit|debit)$"),
    amount_min: Optional[float] = Query(None, ge=0),
    amount_max: Optional[float] = Query(None, ge=0),
    risk_score_min: Optional[float] = Query(None, ge=0, le=100),
    risk_score_max: Optional[float] = Query(None, ge=0, le=100),
    transaction_status: Optional[str] = Query(None, max_length=30),
    flagged_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a user-scoped financial security report from real transaction risk data."""
    transactions = _get_transactions(
        db, current_user.id, date_from=date_from, date_to=date_to, currency=currency,
        category=category, risk_level=risk_level, search=search, transaction_type=transaction_type,
        amount_min=amount_min, amount_max=amount_max, risk_score_min=risk_score_min,
        risk_score_max=risk_score_max, transaction_status=transaction_status,
        flagged_only=flagged_only,
    )
    alert_query = db.query(Alert).filter(Alert.user_id == current_user.id)
    if date_from:
        alert_query = alert_query.filter(Alert.created_at >= datetime.datetime.combine(date_from, datetime.time.min))
    if date_to:
        alert_query = alert_query.filter(Alert.created_at < datetime.datetime.combine(
            date_to + datetime.timedelta(days=1), datetime.time.min
        ))
    alerts = alert_query.order_by(Alert.created_at.desc()).all()
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    high = [txn for txn in transactions if txn.risk_level.lower() == "high"]
    medium = [txn for txn in transactions if txn.risk_level.lower() == "medium"]
    flagged = [txn for txn in transactions if txn.is_flagged]
    signal_counts = defaultdict(int)
    for txn in flagged:
        try:
            signals = json.loads(txn.risk_signals or "[]")
        except (json.JSONDecodeError, TypeError):
            signals = [txn.risk_signals or ""]
        if not isinstance(signals, list):
            signals = [str(signals)]
        for signal in signals:
            signal_text = str(signal).strip()
            if signal_text:
                signal_counts[signal_text] += 1

    story = [
        Paragraph("FINMIND AI — Financial Security Report", styles["Title"]),
        Paragraph(f"Generated {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]),
        Paragraph(
            f"Period: {date_from or 'All available dates'} to {date_to or 'Present'}"
            + (f" · Currency: {currency.upper()}" if currency else " · All currencies shown separately"),
            styles["Normal"],
        ),
        Spacer(1, 12),
        Paragraph("Risk overview", styles["Heading2"]),
    ]
    risk_summary = [["Metric", "Value"], ["Transactions analyzed", str(len(transactions))],
                    ["High risk", str(len(high))], ["Medium risk", str(len(medium))],
                    ["Flagged transactions", str(len(flagged))], ["Security alerts", str(len(alerts))]]
    story.append(Table(risk_summary, colWidths=[10 * cm, 7 * cm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ])))
    story.extend([Spacer(1, 12), Paragraph("Flagged transactions", styles["Heading2"])])
    rows = [["Date", "Merchant", "Amount", "Currency", "Risk", "Signals"]]
    rows.extend([
        [
            txn.timestamp.strftime("%Y-%m-%d"), txn.merchant, f"{txn.amount:,.2f}",
            txn.currency, f"{txn.risk_level} ({txn.risk_score:.0f})",
            (txn.risk_signals or "")[:90],
        ] for txn in flagged[:100]
    ])
    if len(rows) == 1:
        rows.append(["No flagged transactions in this period.", "", "", "", "", ""])
    story.append(Table(rows, repeatRows=1, colWidths=[2.2 * cm, 3.2 * cm, 2.2 * cm, 1.7 * cm, 2.4 * cm, 5.3 * cm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ])))
    story.extend([Spacer(1, 12), Paragraph("Common risk signals", styles["Heading2"])])
    signal_rows = [["Signal", "Occurrences"]] + [
        [signal, str(count)] for signal, count in sorted(signal_counts.items(), key=lambda item: -item[1])[:10]
    ]
    if len(signal_rows) == 1:
        signal_rows.append(["No recorded risk signals.", "0"])
    story.append(Table(signal_rows, colWidths=[14 * cm, 3 * cm]))
    story.extend([Spacer(1, 12), Paragraph("Security alerts", styles["Heading2"])])
    alert_rows = [["Title", "Severity", "Created", "Status"]]
    alert_rows.extend([
        [alert.title, alert.severity, alert.created_at.strftime("%Y-%m-%d"), "Read" if alert.is_read else "Unread"]
        for alert in alerts[:50]
    ])
    if len(alert_rows) == 1:
        alert_rows.append(["No alerts in this period.", "", "", ""])
    story.append(Table(alert_rows, repeatRows=1, colWidths=[9 * cm, 2.5 * cm, 3 * cm, 2.5 * cm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 5),
    ])))
    story.extend([Spacer(1, 10), Paragraph("Security recommendations", styles["Heading2"])])
    story.append(Paragraph(
        "Review each flagged transaction and its recorded signals. Confirm suspicious activity with your financial institution. "
        "Keep account credentials private and enable your institution's multi-factor authentication where available. "
        "This report is informational and does not represent a confirmed fraud determination.",
        styles["BodyText"],
    ))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=FinMind_security_{datetime.date.today()}.pdf"},
    )


@router.get("/transactions/csv")
def download_transactions_csv(
    flagged_only: bool = Query(False, description="Export only flagged transactions"),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    category: Optional[str] = Query(None, max_length=100),
    transaction_type: Optional[str] = Query(None, pattern="^(credit|debit)$"),
    search: Optional[str] = Query(None, max_length=100),
    amount_min: Optional[float] = Query(None, ge=0),
    amount_max: Optional[float] = Query(None, ge=0),
    risk_score_min: Optional[float] = Query(None, ge=0, le=100),
    risk_score_max: Optional[float] = Query(None, ge=0, le=100),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    transaction_status: Optional[str] = Query(None, max_length=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download all (or flagged-only) transactions as a CSV file."""
    txns = _get_transactions(
        db, current_user.id, flagged_only, date_from, date_to, currency,
        category, transaction_type, search, amount_min, amount_max,
        risk_score_min, risk_score_max, risk_level, transaction_status,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Merchant", "Category", "Type", "Amount", "Currency",
        "Payment Method", "Location", "Status", "Risk Score", "Risk Level",
        "Flagged", "Date", "Description",
    ])

    for t in txns:
        writer.writerow([
            t.id,
            _safe_csv_cell(t.merchant),
            _safe_csv_cell(t.category),
            _safe_csv_cell(t.transaction_type),
            f"{t.amount:.2f}",
            t.currency,
            _safe_csv_cell(t.payment_method or ""),
            _safe_csv_cell(t.location or ""),
            _safe_csv_cell(t.status),
            f"{t.risk_score:.1f}",
            _safe_csv_cell(t.risk_level),
            "Yes" if t.is_flagged else "No",
            t.timestamp.strftime("%Y-%m-%d %H:%M UTC"),
            _safe_csv_cell(t.description or ""),
        ])

    output.seek(0)
    suffix = "_flagged" if flagged_only else ""
    filename = f"FinMind_transactions{suffix}_{datetime.date.today()}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# â”€â”€ PDF Reports â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _build_pdf_report(
    user: User,
    transactions: list,
    accounts: list,
    alerts: list,
    flagged_only: bool,
) -> bytes:
    """Generate a styled PDF financial report using ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="FINMIND AI Financial Report",
        author="FINMIND AI",
    )

    styles = getSampleStyleSheet()
    w = A4[0] - 4 * cm  # usable width

    # â”€â”€ Custom styles â”€â”€
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#0f766e"),
        spaceBefore=14,
        spaceAfter=6,
    )
    normal = styles["Normal"]
    normal.fontSize = 9

    story = []

    # â”€â”€ Header â”€â”€
    story.append(Paragraph("FINMIND AI", title_style))
    story.append(Paragraph(
        f"Financial Report â€” Generated {datetime.datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}",
        subtitle_style,
    ))
    story.append(Paragraph(f"Account holder: {user.full_name} ({user.email})", subtitle_style))
    story.append(HRFlowable(width=w, thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=10))

    # â”€â”€ Summary cards â”€â”€
    currency_totals = {}
    for transaction in transactions:
        currency = (transaction.currency or "UNKNOWN").upper()
        totals = currency_totals.setdefault(currency, {"income": 0.0, "revenue": 0.0, "expenses": 0.0})
        if transaction.transaction_type == "credit":
            totals["income"] += transaction.amount
            if is_revenue_category(transaction.category):
                totals["revenue"] += transaction.amount
        else:
            totals["expenses"] += transaction.amount
    flagged_count = sum(1 for t in transactions if t.is_flagged)
    high_risk_count = sum(1 for t in transactions if t.risk_level == "high")

    story.append(Paragraph("Executive Summary", section_style))
    summary_data = [
        ["Metric", "Value"],
    ]
    if currency_totals:
        for currency, totals in sorted(currency_totals.items()):
            income = totals["income"]
            expenses = totals["expenses"]
            summary_data.extend([
                [f"Income ({currency})", f"{income:,.2f}"],
                *([[f"Business Revenue ({currency})", f"{totals['revenue']:,.2f}"]] if totals["revenue"] else []),
                [f"Expenses ({currency})", f"{expenses:,.2f}"],
                [f"Net Cash Flow ({currency})", f"{income - expenses:,.2f}"],
                [f"Savings Rate ({currency})", f"{(income - expenses) / income * 100:.1f}%" if income else "—"],
            ])
    else:
        summary_data.append(["Transaction data", "No transaction data available for this period."])
    summary_data.extend([
        ["Total Transactions", str(len(transactions))],
        ["Flagged Transactions", str(flagged_count)],
        ["High-Risk Transactions", str(high_risk_count)],
        ["Unread Alerts", str(sum(1 for a in alerts if not a.is_read))],
    ])
    summary_table = Table(summary_data, colWidths=[w * 0.6, w * 0.4])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # â”€â”€ Accounts table â”€â”€
    if accounts:
        story.append(Paragraph("Accounts", section_style))
        acct_data = [["Account Name", "Type", "Balance"]]
        for a in accounts:
            acct_data.append([a.name, a.account_type.capitalize(), f"{a.balance:,.2f} {a.currency}"])
        acct_table = Table(acct_data, colWidths=[w * 0.45, w * 0.25, w * 0.30])
        acct_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(acct_table)
        story.append(Spacer(1, 12))

    # â”€â”€ Active alerts â”€â”€
    active_alerts = [a for a in alerts if not a.is_read]
    if active_alerts:
        story.append(Paragraph(f"Active Security Alerts ({len(active_alerts)})", section_style))
        alert_data = [["Severity", "Title", "Date"]]
        for a in active_alerts:
            alert_data.append([
                a.severity.upper(),
                a.title[:60] + ("\u2026" if len(a.title) > 60 else ""),
                a.created_at.strftime("%Y-%m-%d"),
            ])
        alert_table = Table(alert_data, colWidths=[w * 0.15, w * 0.65, w * 0.20])
        alert_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ef4444")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fff5f5"), colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(alert_table)
        story.append(Spacer(1, 12))

    # â”€â”€ Transactions table â”€â”€
    label = "Flagged Transactions" if flagged_only else "Transaction History"
    story.append(Paragraph(f"{label} ({len(transactions)} records)", section_style))

    txn_data = [["Date", "Merchant", "Category", "Type", "Amount", "Risk", "Status"]]
    for t in transactions[:200]:  # cap at 200 rows for readability
        txn_data.append([
            t.timestamp.strftime("%Y-%m-%d"),
            t.merchant[:22],
            t.category[:16],
            t.transaction_type.capitalize(),
            f"{t.amount:,.2f} {t.currency}",
            t.risk_level.upper(),
            t.status.capitalize(),
        ])

    col_widths = [w * 0.12, w * 0.22, w * 0.15, w * 0.09, w * 0.14, w * 0.13, w * 0.15]
    txn_table = Table(txn_data, colWidths=col_widths, repeatRows=1)

    # Build row-level highlight for flagged rows
    ts_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
    ]
    for i, t in enumerate(transactions[:200], start=1):
        bg = colors.HexColor("#fff5f5") if t.is_flagged else (
            colors.white if i % 2 == 0 else colors.HexColor("#f8fafc")
        )
        ts_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    txn_table.setStyle(TableStyle(ts_cmds))
    story.append(txn_table)

    if len(transactions) > 200:
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"* Report shows the most recent 200 of {len(transactions)} transactions.",
            ParagraphStyle("note", parent=normal, textColor=colors.HexColor("#94a3b8"), fontSize=8),
        ))

    # â”€â”€ Footer â”€â”€
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width=w, thickness=0.5, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report is confidential. Generated by FinMind AI. "
        "For support, contact your administrator.",
        ParagraphStyle("footer", parent=normal, textColor=colors.HexColor("#94a3b8"), fontSize=7.5, alignment=TA_CENTER),
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


@router.get("/summary/pdf")
def download_summary_pdf(
    flagged_only: bool = Query(False, description="Include only flagged transactions"),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    category: Optional[str] = Query(None, max_length=100),
    transaction_type: Optional[str] = Query(None, pattern="^(credit|debit)$"),
    search: Optional[str] = Query(None, max_length=100),
    amount_min: Optional[float] = Query(None, ge=0),
    amount_max: Optional[float] = Query(None, ge=0),
    risk_score_min: Optional[float] = Query(None, ge=0, le=100),
    risk_score_max: Optional[float] = Query(None, ge=0, le=100),
    risk_level: Optional[str] = Query(None, pattern="^(low|medium|high)$"),
    transaction_status: Optional[str] = Query(None, max_length=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a full financial summary report as a styled PDF."""
    transactions = _get_transactions(
        db, current_user.id, flagged_only, date_from, date_to, currency,
        category, transaction_type, search, amount_min, amount_max,
        risk_score_min, risk_score_max, risk_level, transaction_status,
    )
    accounts = db.query(Account).filter(Account.user_id == current_user.id).all()
    alerts = (
        db.query(Alert)
        .filter(Alert.user_id == current_user.id)
        .order_by(Alert.created_at.desc())
        .all()
    )

    pdf_bytes = _build_pdf_report(current_user, transactions, accounts, alerts, flagged_only)

    suffix = "_flagged" if flagged_only else ""
    filename = f"FinMind_report{suffix}_{datetime.date.today()}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
