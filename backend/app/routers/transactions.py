import datetime
import csv
import io
import logging
import os
import re
from collections import Counter
from typing import Any, Optional

import pandas as pd
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status, UploadFile, File
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Transaction, Alert, User
from app.schemas import TransactionCategoryUpdate, TransactionCreate, TransactionOut, TransactionStats
from app.services.auth_service import get_current_user
from app.services.risk_engine import calculate_risk, encode_signals

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _get_user_context(user_id: str, currency: str, db: Session) -> tuple:
    """Return (recent_txns_as_dicts, avg_amount) for a user."""
    recent = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.timestamp.desc())
        .limit(50)
        .all()
    )
    currency = currency.upper()
    amounts = [
        t.amount for t in recent
        if t.transaction_type == "debit" and (t.currency or "").upper() == currency
    ]
    avg = sum(amounts) / len(amounts) if amounts else 0.0
    recent_dicts = [
        {
            "timestamp": t.timestamp.isoformat(),
            "merchant": t.merchant,
            "amount": t.amount,
            "currency": t.currency,
        }
        for t in recent
    ]
    return recent_dicts, avg


@router.post("/", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ts = payload.timestamp or datetime.datetime.utcnow()

    # Gather user history for risk calculation
    recent_dicts, avg_amount = _get_user_context(current_user.id, payload.currency, db)

    # Determine if the merchant is new for this user
    known_merchants = {t["merchant"].lower() for t in recent_dicts}
    is_new_merchant = payload.merchant.lower() not in known_merchants

    risk_result = calculate_risk(
        amount=payload.amount,
        merchant=payload.merchant,
        currency=payload.currency,
        category=payload.category,
        location=payload.location,
        payment_method=payload.payment_method,
        timestamp=ts,
        user_recent_transactions=recent_dicts,
        user_avg_amount=avg_amount,
        is_new_merchant=is_new_merchant,
        transaction_type=payload.transaction_type,
    )

    is_flagged = risk_result["risk_level"] in ("high", "medium") and risk_result["risk_score"] >= 50

    txn = Transaction(
        user_id=current_user.id,
        account_id=payload.account_id,
        amount=payload.amount,
        currency=payload.currency,
        merchant=payload.merchant,
        category=payload.category,
        transaction_type=payload.transaction_type,
        payment_method=payload.payment_method,
        location=payload.location,
        description=payload.description,
        status="flagged" if is_flagged else "completed",
        risk_score=risk_result["risk_score"],
        risk_level=risk_result["risk_level"],
        is_flagged=is_flagged,
        risk_signals=encode_signals(risk_result["signals"]),
        timestamp=ts,
    )
    db.add(txn)
    db.flush()  # get txn.id before committing

    # Auto-create an alert for high-risk transactions
    if risk_result["risk_level"] == "high":
        alert = Alert(
            user_id=current_user.id,
            transaction_id=txn.id,
            title=f"High-risk transaction detected: {payload.merchant}",
            description=f"Risk score {risk_result['risk_score']}/100. Signals: {', '.join(risk_result['signals'][:2])}",
            severity="high",
        )
        db.add(alert)
    elif risk_result["risk_level"] == "medium" and risk_result["risk_score"] >= 50:
        alert = Alert(
            user_id=current_user.id,
            transaction_id=txn.id,
            title=f"Suspicious activity: {payload.merchant}",
            description=f"Risk score {risk_result['risk_score']}/100. Signals: {', '.join(risk_result['signals'][:2])}",
            severity="medium",
        )
        db.add(alert)

    db.commit()
    db.refresh(txn)
    return txn


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    flagged_only: bool = Query(False),
    category: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None, pattern="^(credit|debit)$"),
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    date_from: Optional[datetime.date] = Query(None),
    date_to: Optional[datetime.date] = Query(None),
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
    q = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")
    if amount_min is not None and amount_max is not None and amount_min > amount_max:
        raise HTTPException(status_code=400, detail="Minimum amount must not exceed maximum amount")
    if risk_score_min is not None and risk_score_max is not None and risk_score_min > risk_score_max:
        raise HTTPException(status_code=400, detail="Minimum risk score must not exceed maximum risk score")
    if flagged_only:
        q = q.filter(Transaction.is_flagged == True)  # noqa: E712
    if category:
        q = q.filter(Transaction.category.ilike(f"%{category}%"))
    if transaction_type:
        q = q.filter(Transaction.transaction_type == transaction_type)
    if currency:
        q = q.filter(func.upper(Transaction.currency) == currency.upper())
    if date_from:
        q = q.filter(Transaction.timestamp >= datetime.datetime.combine(date_from, datetime.time.min))
    if date_to:
        q = q.filter(Transaction.timestamp < datetime.datetime.combine(
            date_to + datetime.timedelta(days=1), datetime.time.min
        ))
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
        q = q.filter(func.lower(Transaction.risk_level) == risk_level)
    if transaction_status:
        q = q.filter(func.lower(Transaction.status) == transaction_status.lower())

    total = q.count()
    response.headers["X-Total-Count"] = str(total)
    return q.order_by(Transaction.timestamp.desc(), Transaction.id.asc()).offset(skip).limit(limit).all()


@router.get("/stats", response_model=TransactionStats)
def transaction_stats(
    currency: Optional[str] = Query(None, min_length=3, max_length=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    currencies = {
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
         if os.getenv("DEFAULT_CURRENCY", "INR").upper() in currencies
         else (sorted(currencies)[0] if currencies else os.getenv("DEFAULT_CURRENCY", "INR").upper()))
    )
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            func.upper(Transaction.currency) == selected_currency,
        )
        .all()
    )
    income = sum(t.amount for t in txns if t.transaction_type == "credit")
    expenses = sum(t.amount for t in txns if t.transaction_type == "debit")
    flagged = sum(1 for t in txns if t.is_flagged)
    high_risk = sum(1 for t in txns if t.risk_level == "high")
    avg_risk = sum(t.risk_score for t in txns) / len(txns) if txns else 0.0

    return TransactionStats(
        currency=selected_currency,
        total_count=len(txns),
        total_amount=income + expenses,
        total_income=income,
        total_expenses=expenses,
        flagged_count=flagged,
        high_risk_count=high_risk,
        avg_risk_score=round(avg_risk, 1),
    )


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction_category(
    transaction_id: str,
    payload: TransactionCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txn = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == current_user.id)
        .first()
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn.category = payload.category
    try:
        db.commit()
        db.refresh(txn)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Could not update transaction category for %s", transaction_id)
        raise HTTPException(status_code=500, detail="Could not update transaction category") from exc
    return txn


# ─────────────────────────────────────────────────────────────────────────────
# Bulk upload: CSV / Excel bank statements
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_UPLOAD_EXTENSIONS = (".csv", ".xlsx", ".xls")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_ROWS = 20_000
MAX_SKIPPED_DETAILS = 20
# Statements usually carry a date only. Noon keeps the risk engine's
# "unusual hour" rule (00:00-04:59) from firing on every date-only row.
DEFAULT_TXN_TIME = datetime.time(12, 0)

# Canonical field -> accepted (normalized) column names, in priority order.
_COLUMN_ALIASES = {
    "date": (
        "date", "transaction_date", "txn_date", "value_date", "posting_date",
        "booking_date", "timestamp", "datetime", "date_time",
    ),
    "description": (
        "description", "narration", "details", "transaction_details",
        "transaction_description", "particulars", "remarks", "memo",
    ),
    "merchant": (
        "merchant", "merchant_name", "payee", "beneficiary", "party",
        "party_name", "vendor", "vendor_name", "customer", "customer_name",
        "counterparty",
    ),
    "debit": (
        "debit", "debit_amount", "withdrawal", "withdrawals",
        "withdrawal_amount", "withdrawal_amt", "money_out", "dr",
    ),
    "credit": (
        "credit", "credit_amount", "deposit", "deposits",
        "deposit_amount", "deposit_amt", "money_in", "cr",
    ),
    "amount": ("amount", "transaction_amount", "amt"),
    "type": ("transaction_type", "type", "dr_cr", "cr_dr"),
    "balance": ("balance", "closing_balance", "closing_bal", "running_balance"),
    "category": ("category",),
    "payment_method": ("payment_method", "mode", "payment_mode", "channel"),
    "location": ("location", "city", "place"),
    "currency": ("currency", "ccy"),
}

_DEBIT_WORDS = {"debit", "dr", "d", "withdrawal", "expense"}
_CREDIT_WORDS = {"credit", "cr", "c", "deposit", "income"}

VALID_CATEGORIES = (
    "Income", "Food", "Shopping", "Transport", "Utilities", "Housing",
    "Healthcare", "Entertainment", "Education", "Travel", "Investment",
    "Bills", "Other",
)

# Checked top to bottom; first match wins.
_CATEGORY_KEYWORDS = (
    ("Income", (
        "salary", "payroll", "stipend", "bonus", "dividend", "interest credit",
        "cashback", "refund",
    )),
    ("Utilities", (
        "electricity", "power bill", "water", "gas", "broadband", "internet",
        "wifi", "recharge", "airtel", "jio", "vodafone", "bsnl", "mobile bill",
    )),
    ("Housing", ("rent", "maintenance", "society", "mortgage", "housing")),
    ("Healthcare", (
        "pharmacy", "apollo", "hospital", "clinic", "medical", "medicine",
        "1mg", "pharmeasy", "doctor", "diagnostic", "dental",
    )),
    ("Food", (
        "swiggy", "zomato", "restaurant", "cafe", "coffee", "starbucks",
        "dominos", "mcdonalds", "kfc", "pizza", "grocery", "bigbasket",
        "blinkit", "zepto", "dmart", "food", "bakery",
    )),
    ("Travel", (
        "irctc", "flight", "makemytrip", "goibibo", "airline", "indigo",
        "hotel", "airbnb", "cleartrip", "oyo", "booking.com",
    )),
    ("Transport", (
        "uber", "ola", "rapido", "metro", "fuel", "petrol", "diesel",
        "parking", "fastag", "taxi", "cab",
    )),
    ("Entertainment", (
        "netflix", "spotify", "prime video", "hotstar", "bookmyshow",
        "cinema", "movie", "pvr", "inox", "gaming", "youtube",
    )),
    ("Education", (
        "school", "college", "tuition", "course", "udemy", "coursera",
        "university", "exam fee",
    )),
    ("Investment", (
        "mutual fund", "sip", "zerodha", "groww", "upstox", "stocks", "nps",
        "ppf", "investment",
    )),
    ("Shopping", (
        "amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa", "shopping",
        "store", "mall",
    )),
    ("Bills", ("bill", "insurance", "premium", "emi", "loan", "credit card")),
)


def _compile_keywords(words: tuple) -> re.Pattern:
    parts = []
    for word in words:
        escaped = re.escape(word)
        # Short words must match a whole word; longer ones may carry a suffix.
        parts.append(rf"\b{escaped}\b" if len(word) <= 4 else rf"\b{escaped}\w*")
    return re.compile("|".join(parts))


_CATEGORY_PATTERNS = [(name, _compile_keywords(words)) for name, words in _CATEGORY_KEYWORDS]
_CATEGORY_LOOKUP = {c.lower(): c for c in VALID_CATEGORIES}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_text(value: Any) -> Optional[str]:
    return None if _is_blank(value) else str(value).strip()


def _normalize_header(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _to_number(value: Any) -> Optional[float]:
    """Parse '1,234.50', '(500)', '-2500', '₹2,499' ... Returns None if blank/invalid."""
    if _is_blank(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = re.sub(r"[^\d.\-()]", "", str(value))
    if not text:
        return None
    negative = "(" in text or text.startswith("-")
    try:
        number = float(re.sub(r"[()\-]", "", text))
    except ValueError:
        return None
    return -number if negative else number


def _parse_timestamp(value: Any) -> Optional[datetime.datetime]:
    if _is_blank(value):
        return None
    if isinstance(value, datetime.date):  # covers datetime and pandas Timestamp
        parsed = pd.Timestamp(value)
    else:
        text = str(value).strip()
        if not text:
            return None

        # ISO year-first values should stay year-first. Otherwise, bank exports often
        # use DD/MM/YYYY or DD-MM-YYYY, and the app should interpret them consistently.
        if re.fullmatch(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", text):
            parsed = pd.to_datetime(text, errors="coerce")
        elif re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", text):
            parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
        else:
            parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    result = parsed.to_pydatetime()
    if result.tzinfo is not None:
        result = result.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    if result.time() == datetime.time(0, 0):
        result = datetime.datetime.combine(result.date(), DEFAULT_TXN_TIME)
    return result


def _map_columns(columns: list) -> dict:
    mapping = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in columns:
                mapping[field] = alias
                break
    return mapping


def _pick(raw: dict, mapping: dict, field: str) -> Any:
    column = mapping.get(field)
    return raw.get(column) if column else None


def _infer_category(merchant: str, description: str, transaction_type: str) -> str:
    text = f"{merchant} {description}".lower()
    for name, pattern in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return name
    return "Income" if transaction_type == "credit" else "Other"


def _resolve_amount(raw: dict, mapping: dict) -> tuple:
    """Return (amount, transaction_type, problem). Amount is always positive."""
    debit = _to_number(_pick(raw, mapping, "debit"))
    credit = _to_number(_pick(raw, mapping, "credit"))
    if debit or credit:
        if debit and credit:
            return None, None, "both debit and credit are filled in"
        if debit:
            return round(abs(debit), 2), "debit", None
        return round(abs(credit), 2), "credit", None

    amount = _to_number(_pick(raw, mapping, "amount"))
    if amount:
        hint = (_clean_text(_pick(raw, mapping, "type")) or "").lower()
        if hint in _DEBIT_WORDS:
            txn_type = "debit"
        elif hint in _CREDIT_WORDS:
            txn_type = "credit"
        else:
            txn_type = "debit" if amount < 0 else "credit"
        return round(abs(amount), 2), txn_type, None

    return None, None, "missing, zero or invalid amount"


def _normalize_row(raw: dict, mapping: dict, default_currency: str) -> tuple:
    """Return (record, None) for a usable row or (None, reason) for a skipped one."""
    timestamp = _parse_timestamp(_pick(raw, mapping, "date"))
    if timestamp is None:
        return None, "missing or invalid date"

    description = _clean_text(_pick(raw, mapping, "description"))
    merchant = _clean_text(_pick(raw, mapping, "merchant")) or description
    if not merchant:
        return None, "missing description / merchant"
    description = description or merchant

    amount, txn_type, problem = _resolve_amount(raw, mapping)
    if problem:
        return None, problem

    file_category = _clean_text(_pick(raw, mapping, "category"))
    if file_category:
        category = _CATEGORY_LOOKUP.get(file_category.lower(), file_category)
    else:
        category = _infer_category(merchant, description, txn_type)

    return {
        "timestamp": timestamp,
        "amount": amount,
        "transaction_type": txn_type,
        "merchant": merchant,
        "description": description,
        "category": category,
        "payment_method": _clean_text(_pick(raw, mapping, "payment_method")),
        "location": _clean_text(_pick(raw, mapping, "location")),
        "currency": (_clean_text(_pick(raw, mapping, "currency")) or default_currency).upper(),
    }, None


def _read_dataframe(contents: bytes, filename: str) -> pd.DataFrame:
    try:
        if filename.lower().endswith(".csv"):
            try:
                text = contents.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = contents.decode("latin-1")
            sample_lines = [line for line in text.splitlines()[:50] if line.strip()]
            def delimiter_score(candidate: str) -> tuple[int, int, int, int]:
                counts = [line.count(candidate) for line in sample_lines]
                nonempty_counts = [count for count in counts if count]
                if not nonempty_counts:
                    return (0, 0, 0, 0)
                occurrences = Counter(nonempty_counts)
                common_count, common_rows = occurrences.most_common(1)[0]
                return (
                    len(nonempty_counts),
                    common_rows,
                    common_count,
                    sum(nonempty_counts),
                )

            delimiter = max(",;\t|", key=delimiter_score)
            if not delimiter_score(delimiter)[0]:
                delimiter = ","
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter, skipinitialspace=True))
            sheets = {"CSV": pd.DataFrame(rows)}
        else:
            sheets = pd.read_excel(
                io.BytesIO(contents), sheet_name=None, header=None, dtype=str,
                keep_default_na=False,
            )

        first_nonempty = None
        for frame in sheets.values():
            nonempty_rows = [
                index for index in range(len(frame))
                if any(not _is_blank(value) for value in frame.iloc[index].tolist())
            ]
            if not nonempty_rows:
                continue
            if first_nonempty is None:
                first_nonempty = (frame, nonempty_rows[0])
            for header_index in range(min(len(frame), 50)):
                headers = [
                    _normalize_header(value) or f"unnamed_{column_index}"
                    for column_index, value in enumerate(frame.iloc[header_index].tolist())
                ]
                mapping = _map_columns(headers)
                if (
                    "date" in mapping
                    and ({"debit", "credit", "amount"} & set(mapping))
                    and ("description" in mapping or "merchant" in mapping)
                ):
                    data = frame.iloc[header_index + 1:].copy()
                    data.columns = headers
                    data.index = data.index - header_index - 1
                    data.attrs["header_row_index"] = header_index
                    return data

        if first_nonempty is None:
            return pd.DataFrame()

        frame, header_index = first_nonempty
        headers = [
            _normalize_header(value) or f"unnamed_{column_index}"
            for column_index, value in enumerate(frame.iloc[header_index].tolist())
        ]
        data = frame.iloc[header_index + 1:].copy()
        data.columns = headers
        data.index = data.index - header_index - 1
        data.attrs["header_row_index"] = header_index
        return data
    except ImportError:
        logger.exception("Missing dependency for reading %s", filename)
        raise HTTPException(
            status_code=500,
            detail="Excel import is not available on the server (openpyxl/xlrd not installed).",
        )
    except Exception:
        logger.exception("Could not parse uploaded file %s", filename)
        raise HTTPException(
            status_code=400,
            detail="Could not read the file. Make sure it is a valid, undamaged CSV or Excel file.",
        )


def _dup_key(timestamp: datetime.datetime, merchant: str, amount: float, txn_type: str) -> tuple:
    return (
        timestamp.replace(microsecond=0),
        (merchant or "").strip().lower(),
        round(float(amount), 2),
        txn_type,
    )


def _build_alert(user_id: str, txn: Transaction, risk: dict) -> Optional[Alert]:
    """Same alert rules as POST /transactions/, with a fuller explanation."""
    level, score = risk["risk_level"], risk["risk_score"]
    if level == "high":
        severity, title = "high", f"High-risk transaction detected: {txn.merchant}"
    elif level == "medium" and score >= 50:
        severity, title = "medium", f"Suspicious activity: {txn.merchant}"
    else:
        return None
    signals = ", ".join(risk["signals"][:3])
    description = f"Risk score {score}/100."
    if signals:
        description += f" Signals: {signals}"
    return Alert(
        user_id=user_id,
        transaction_id=txn.id,
        title=title,
        description=description,
        severity=severity,
    )


@router.post("/upload")
def upload_transactions(
    file: UploadFile = File(...),
    preview_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Import a CSV / XLS / XLSX bank statement for the authenticated user.

    Rows are normalized, categorized, de-duplicated against the user's existing
    transactions, risk-scored with the existing risk engine and stored, with
    alerts created under the same rules as POST /transactions/.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    if not file.filename.lower().endswith(ALLOWED_UPLOAD_EXTENSIONS):
        raise HTTPException(
            status_code=400, detail="Only CSV, XLSX, and XLS files are supported"
        )

    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large (limit {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    df = _read_dataframe(contents, file.filename)
    df = df[~df.apply(lambda row: all(_is_blank(v) for v in row), axis=1)]
    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file contains no transactions")
    if len(df) > MAX_UPLOAD_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many rows ({len(df)}). Upload at most {MAX_UPLOAD_ROWS} at a time.",
        )

    df.columns = [_normalize_header(c) for c in df.columns]
    columns = list(df.columns)
    mapping = _map_columns(columns)

    missing = []
    if "date" not in mapping:
        missing.append("date")
    if not ({"debit", "credit", "amount"} & set(mapping)):
        missing.append("amount (or debit / credit)")
    if "description" not in mapping and "merchant" not in mapping:
        missing.append("description / merchant")
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Missing required column(s): {', '.join(missing)}. "
                f"Columns found: {', '.join(columns)}"
            ),
        )

    default_currency = os.getenv("DEFAULT_CURRENCY", "INR")

    # ── Normalize every row ──────────────────────────────────────────────
    records = []
    skipped = []  # [{"row": n, "reason": str}]
    header_row_index = int(df.attrs.get("header_row_index", 0))
    for index, raw in zip(df.index, df.to_dict("records")):
        record, reason = _normalize_row(raw, mapping, default_currency)
        row_number = int(index) + header_row_index + 2
        if record is None:
            skipped.append({"row": row_number, "reason": reason})
        else:
            record["row"] = row_number
            records.append(record)

    if not records:
        if preview_only:
            return {
                "success": True,
                "filename": file.filename,
                "total_rows": len(df),
                "valid_rows": 0,
                "imported": 0,
                "duplicates": 0,
                "skipped": len(skipped),
                "detected_currencies": [],
                "date_range": None,
                "preview_rows": [],
                "skipped_details": skipped[:MAX_SKIPPED_DETAILS],
            }
        first = skipped[0]
        raise HTTPException(
            status_code=400,
            detail=f"No valid transactions found. First problem: row {first['row']}: {first['reason']}",
        )

    # Oldest first so each row is scored against the history before it.
    records.sort(key=lambda r: r["timestamp"])

    # ── Load the current user's context once ─────────────────────────────
    existing = (
        db.query(
            Transaction.timestamp,
            Transaction.merchant,
            Transaction.amount,
            Transaction.transaction_type,
        )
        .filter(Transaction.user_id == current_user.id)
        .all()
    )
    existing_counts = Counter(
        _dup_key(r.timestamp, r.merchant, r.amount, r.transaction_type)
        for r in existing
        if r.timestamp is not None
    )
    if preview_only:
        seen_preview = Counter()
        preview_duplicates = 0
        for record in records:
            key = _dup_key(
                record["timestamp"], record["merchant"], record["amount"], record["transaction_type"]
            )
            seen_preview[key] += 1
            if seen_preview[key] <= existing_counts[key]:
                preview_duplicates += 1

        transaction_dates = [record["timestamp"].date() for record in records]
        return {
            "success": True,
            "filename": file.filename,
            "total_rows": len(df),
            "valid_rows": len(records),
            "imported": len(records) - preview_duplicates,
            "duplicates": preview_duplicates,
            "skipped": len(skipped),
            "detected_currencies": sorted({record["currency"] for record in records}),
            "date_range": {
                "start": min(transaction_dates).isoformat(),
                "end": max(transaction_dates).isoformat(),
            } if transaction_dates else None,
            "preview_rows": [
                {
                    "row": record["row"],
                    "date": record["timestamp"].isoformat(),
                    "merchant": record["merchant"],
                    "amount": record["amount"],
                    "currency": record["currency"],
                    "transaction_type": record["transaction_type"],
                    "category": record["category"],
                }
                for record in records[:10]
            ],
            "skipped_details": skipped[:MAX_SKIPPED_DETAILS],
        }

    known_merchants = {(r.merchant or "").lower() for r in existing}

    recent_rows = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.timestamp.desc())
        .limit(50)
        .all()
    )
    recent_dicts = [
        {"timestamp": t.timestamp.isoformat(), "merchant": t.merchant, "amount": t.amount}
        for t in recent_rows
    ]
    debit_amounts: dict[str, list[float]] = {}
    for transaction in reversed(recent_rows):
        if transaction.transaction_type == "debit":
            debit_amounts.setdefault((transaction.currency or "").upper(), []).append(transaction.amount)

    # ── Score and build new transactions ─────────────────────────────────
    # A row is a duplicate when the user already has at least as many
    # identical transactions as the file has seen so far. This keeps a
    # re-upload from importing anything, while two genuinely identical rows
    # in a first upload (two same-price rides in one day) are both kept.
    seen = Counter()
    duplicates = 0
    scored = []  # [(Transaction, risk_result)]

    for record in records:
        key = _dup_key(
            record["timestamp"], record["merchant"], record["amount"], record["transaction_type"]
        )
        seen[key] += 1
        if seen[key] <= existing_counts[key]:
            duplicates += 1
            continue

        merchant_key = record["merchant"].lower()
        currency = record["currency"].upper()
        matching_amounts = debit_amounts.get(currency, [])
        avg_amount = sum(matching_amounts) / len(matching_amounts) if matching_amounts else 0.0
        try:
            risk = calculate_risk(
                amount=record["amount"],
                currency=record["currency"],
                merchant=record["merchant"],
                category=record["category"],
                location=record["location"],
                payment_method=record["payment_method"],
                timestamp=record["timestamp"],
                user_recent_transactions=recent_dicts,
                user_avg_amount=avg_amount,
                is_new_merchant=merchant_key not in known_merchants,
                transaction_type=record["transaction_type"],
            )
        except Exception:
            logger.exception("Risk scoring failed for upload row %s", record["row"])
            skipped.append({"row": record["row"], "reason": "risk scoring failed"})
            continue

        is_flagged = risk["risk_level"] in ("high", "medium") and risk["risk_score"] >= 50
        txn = Transaction(
            user_id=current_user.id,
            account_id=None,
            amount=record["amount"],
            currency=record["currency"],
            merchant=record["merchant"],
            category=record["category"],
            transaction_type=record["transaction_type"],
            payment_method=record["payment_method"],
            location=record["location"],
            description=record["description"],
            status="flagged" if is_flagged else "completed",
            risk_score=risk["risk_score"],
            risk_level=risk["risk_level"],
            is_flagged=is_flagged,
            risk_signals=encode_signals(risk["signals"]),
            timestamp=record["timestamp"],
        )
        scored.append((txn, risk))

        # Later rows in this file see this one as history.
        known_merchants.add(merchant_key)
        recent_dicts.insert(
            0,
            {
                "timestamp": record["timestamp"].isoformat(),
                "merchant": record["merchant"],
                "amount": record["amount"],
                "currency": record["currency"],
            },
        )
        del recent_dicts[50:]
        if record["transaction_type"] == "debit":
            debit_amounts.setdefault(currency, []).append(record["amount"])
            del debit_amounts[currency][:-50]

    # ── Persist ──────────────────────────────────────────────────────────
    alerts_created = 0
    if scored:
        try:
            db.add_all([txn for txn, _ in scored])
            db.flush()  # assign transaction ids for the alerts
            for txn, risk in scored:
                alert = _build_alert(current_user.id, txn, risk)
                if alert is not None:
                    db.add(alert)
                    alerts_created += 1
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Database error while importing transactions")
            raise HTTPException(
                status_code=500, detail="Database error while importing transactions"
            )

    transaction_dates = [record["timestamp"].date() for record in records]
    return {
        "success": True,
        "filename": file.filename,
        "total_rows": len(df),
        "valid_rows": len(records),
        "transaction_count": len(df),  # kept for older clients
        "imported": len(scored),
        "duplicates": duplicates,
        "skipped": len(skipped),
        "detected_currencies": sorted({record["currency"] for record in records}),
        "date_range": {
            "start": min(transaction_dates).isoformat(),
            "end": max(transaction_dates).isoformat(),
        } if transaction_dates else None,
        "flagged": sum(1 for txn, _ in scored if txn.is_flagged),
        "high_risk": sum(1 for txn, _ in scored if txn.risk_level == "high"),
        "alerts_created": alerts_created,
        "skipped_details": skipped[:MAX_SKIPPED_DETAILS],
        "columns": columns,
        "mapped_columns": mapping,
    }
    