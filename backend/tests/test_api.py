"""
FinMind AI — Comprehensive Backend Tests
==========================================
Tests cover:
1. Health check
2. Authentication (register, login, /me, wrong password, duplicate)
3. Transaction creation + risk scoring
4. CSV upload (7 valid rows)
5. Duplicate CSV prevention (re-upload = 0 new, 7 duplicates)
6. INR risk messages use ₹ not $
7. USD risk messages use $
8. User isolation (User A cannot see User B's data)
9. Analytics
10. Alerts
11. AI chat (no key → unavailable message, no fake data)
12. Reports (CSV + PDF endpoints exist)
13. Risk engine currency awareness
"""

import csv
import io
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.services.auth_service import _load_secret_key

# â”€â”€ In-memory SQLite for tests â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TEST_DB_URL = "sqlite:///./test_FinMind.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
Base.metadata.drop_all(bind=test_engine)
Base.metadata.create_all(bind=test_engine)

client = TestClient(app)

# Shared state (populated by earlier tests)
_token_a: str = ""
_token_b: str = ""
_txn_id: str = ""

# â”€â”€ Test CSV matching the acceptance test spec â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TEST_CSV = b"""Date,Description,Debit,Credit,Balance
2026-09-01,Salary,0,50000,50000
2026-09-02,Amazon,2499,0,47501
2026-09-03,Swiggy,650,0,46851
2026-09-04,Uber,350,0,46501
2026-09-05,Electricity Bill,2200,0,44301
2026-09-06,Salary,0,50000,94301
2026-09-07,Unknown Merchant,25000,0,69301
"""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Health
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "connected"}


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "FINMIND AI"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Authentication
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_register_user_a():
    r = client.post("/auth/register", json={
        "email": "alice@example.com",
        "full_name": "Alice",
        "password": "Secure123!",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data


def test_register_duplicate():
    r = client.post("/auth/register", json={
        "email": "alice@example.com",
        "full_name": "Alice",
        "password": "Secure123!",
    })
    assert r.status_code == 409


def test_register_user_b():
    r = client.post("/auth/register", json={
        "email": "bob@example.com",
        "full_name": "Bob",
        "password": "Password456!",
    })
    assert r.status_code == 201


def test_login_user_a():
    global _token_a
    r = client.post("/auth/login", json={
        "email": "alice@example.com",
        "password": "Secure123!",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    _token_a = data["access_token"]


def test_login_user_b():
    global _token_b
    r = client.post("/auth/login", json={
        "email": "bob@example.com",
        "password": "Password456!",
    })
    assert r.status_code == 200
    _token_b = r.json()["access_token"]


def test_login_wrong_password():
    r = client.post("/auth/login", json={
        "email": "alice@example.com",
        "password": "wrongpass",
    })
    assert r.status_code == 401


def test_get_me():
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {_token_a}"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "alice@example.com"
    assert "hashed_password" not in data


def test_unauthorized_without_token():
    r = client.get("/transactions/")
    assert r.status_code == 401


def test_auth_rejects_missing_secret_key_in_production(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="SECRET_KEY must be configured"):
        _load_secret_key()


def test_auth_uses_random_key_when_development_secret_is_missing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    first_key = _load_secret_key()
    second_key = _load_secret_key()

    assert len(first_key) >= 32
    assert first_key != second_key


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Transaction creation + risk scoring
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _auth_a():
    return {"Authorization": f"Bearer {_token_a}"}


def _auth_b():
    return {"Authorization": f"Bearer {_token_b}"}


def test_create_inr_transaction():
    global _txn_id
    r = client.post("/transactions/", json={
        "amount": 650.0,
        "currency": "INR",
        "merchant": "Swiggy",
        "category": "Food",
        "transaction_type": "debit",
    }, headers=_auth_a())
    assert r.status_code == 201
    data = r.json()
    assert data["merchant"] == "Swiggy"
    assert data["currency"] == "INR"
    assert 0 <= data["risk_score"] <= 100
    _txn_id = data["id"]


def test_create_high_risk_usd_transaction():
    """A $15,000 cryptocurrency wire transfer should be high risk."""
    r = client.post("/transactions/", json={
        "amount": 15_000.0,
        "currency": "USD",
        "merchant": "Coinbase",
        "category": "Cryptocurrency",
        "transaction_type": "debit",
        "payment_method": "Wire",
        "location": "Unknown",
    }, headers=_auth_a())
    assert r.status_code == 201
    data = r.json()
    assert data["risk_level"] in ("medium", "high")
    assert data["risk_score"] >= 30


def test_salary_credit_not_high_risk():
    """INR 50,000 salary credit should NOT be high risk."""
    r = client.post("/transactions/", json={
        "amount": 50_000.0,
        "currency": "INR",
        "merchant": "Employer",
        "category": "Income",
        "transaction_type": "credit",
    }, headers=_auth_a())
    assert r.status_code == 201
    data = r.json()
    # Salary should be low or medium â€” never high based on amount alone
    assert data["risk_level"] in ("low", "medium")
    # Score should not be triggered as high (>= 70) purely due to large credit
    assert data["risk_score"] < 70, (
        f"Salary credit got risk_score={data['risk_score']} â€” should not be high risk"
    )


def test_list_transactions():
    r = client.get("/transactions/", headers=_auth_a())
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_transaction_filters_search_type_and_date():
    transaction = client.get(f"/transactions/{_txn_id}", headers=_auth_a()).json()
    txn_date = transaction["timestamp"][:10]
    r = client.get(
        f"/transactions/?search=Swiggy&transaction_type=debit&category=Food&date_from={txn_date}&date_to={txn_date}&currency=INR",
        headers=_auth_a(),
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["merchant"] == "Swiggy"


def test_transaction_filters_reject_reversed_date_range():
    r = client.get(
        "/transactions/?date_from=2026-09-10&date_to=2026-09-01",
        headers=_auth_a(),
    )
    assert r.status_code == 400
    assert "Start date" in r.json()["detail"]


def test_transaction_amount_risk_and_status_filters():
    sample = client.get("/transactions/?limit=1", headers=_auth_a()).json()[0]
    r = client.get(
        f"/transactions/?amount_min={sample['amount']}&amount_max={sample['amount']}&transaction_status={sample['status']}",
        headers=_auth_a(),
    )
    assert r.status_code == 200
    assert r.json()
    assert all(row["amount"] == sample["amount"] and row["status"] == sample["status"] for row in r.json())

    risk_filter = client.get(
        f"/transactions/?risk_score_min={sample['risk_score']}&risk_score_max={sample['risk_score']}&risk_level={sample['risk_level']}",
        headers=_auth_a(),
    )
    assert risk_filter.status_code == 200
    assert risk_filter.json()
    assert all(row["risk_level"] == sample["risk_level"] and row["risk_score"] == sample["risk_score"] for row in risk_filter.json())


def test_transaction_pagination_includes_total_count():
    first = client.get("/transactions/?skip=0&limit=1", headers=_auth_a())
    second = client.get("/transactions/?skip=1&limit=1", headers=_auth_a())
    assert first.status_code == second.status_code == 200
    assert int(first.headers["X-Total-Count"]) >= 2
    assert len(first.json()) == len(second.json()) == 1
    assert first.json()[0]["id"] != second.json()[0]["id"]


def test_transaction_filters_reject_reversed_numeric_ranges():
    amount = client.get("/transactions/?amount_min=10&amount_max=1", headers=_auth_a())
    risk = client.get("/transactions/?risk_score_min=90&risk_score_max=20", headers=_auth_a())
    assert amount.status_code == risk.status_code == 400


def test_get_transaction_by_id():
    r = client.get(f"/transactions/{_txn_id}", headers=_auth_a())
    assert r.status_code == 200
    assert r.json()["id"] == _txn_id


def test_user_can_correct_transaction_category():
    r = client.patch(
        f"/transactions/{_txn_id}",
        json={"category": "Groceries"},
        headers=_auth_a(),
    )
    assert r.status_code == 200
    assert r.json()["category"] == "Groceries"
    analytics = client.get("/analytics/?currency=INR", headers=_auth_a()).json()
    assert any(item["category"] == "Groceries" for item in analytics["category_breakdown"])


def test_transaction_stats():
    r = client.get("/transactions/stats", headers=_auth_a())
    assert r.status_code == 200
    data = r.json()
    assert "total_count" in data
    assert data["total_count"] >= 1


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CSV Upload â€” 7 valid rows
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_csv_upload_preview_does_not_import():
    count_before = len(client.get("/transactions/?limit=200", headers=_auth_a()).json())
    r = client.post(
        "/transactions/upload?preview_only=true",
        files={"file": ("statement.csv", io.BytesIO(TEST_CSV), "text/csv")},
        headers=_auth_a(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["filename"] == "statement.csv"
    assert data["total_rows"] == data["valid_rows"] == data["imported"] == 7
    assert data["duplicates"] == data["skipped"] == 0
    assert len(data["preview_rows"]) == 7
    count_after = len(client.get("/transactions/?limit=200", headers=_auth_a()).json())
    assert count_after == count_before


def test_csv_upload_preview_finds_headers_after_statement_title():
    statement = (
        b"demo_synthetic_bank_data,,,,,\n"
        b"\n"
        b"Txn Date,Party,Narration,Dr,Cr,Closing Bal\n"
        b"2026-09-11,Office Supply Co,Printer paper,840.50,,9159.50\n"
    )
    response = client.post(
        "/transactions/upload?preview_only=true",
        files={"file": ("statement.csv", io.BytesIO(statement), "text/csv")},
        headers=_auth_a(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 1
    assert data["valid_rows"] == 1
    assert data["preview_rows"][0] == {
        "row": 4,
        "date": "2026-09-11T12:00:00",
        "merchant": "Office Supply Co",
        "amount": 840.5,
        "currency": "INR",
        "transaction_type": "debit",
        "category": "Other",
    }


def test_csv_upload_first_time():
    """First upload: 7 rows â†’ 7 imported."""
    r = client.post(
        "/transactions/upload",
        files={"file": ("statement.csv", io.BytesIO(TEST_CSV), "text/csv")},
        headers=_auth_a(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["imported"] == 7, f"Expected 7 imported, got {data['imported']}"
    assert data["duplicates"] == 0
    assert data["valid_rows"] == 7
    assert data["detected_currencies"] == ["INR"]
    assert data["date_range"]["start"] <= data["date_range"]["end"]


def test_csv_upload_duplicate():
    """Second identical upload: 0 new rows, 7 duplicates."""
    r = client.post(
        "/transactions/upload",
        files={"file": ("statement.csv", io.BytesIO(TEST_CSV), "text/csv")},
        headers=_auth_a(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["imported"] == 0, f"Expected 0 imported on re-upload, got {data['imported']}"
    assert data["duplicates"] == 7, f"Expected 7 duplicates, got {data['duplicates']}"
    preview = client.post(
        "/transactions/upload?preview_only=true",
        files={"file": ("statement.csv", io.BytesIO(TEST_CSV), "text/csv")},
        headers=_auth_a(),
    )
    assert preview.status_code == 200
    assert preview.json()["imported"] == 0
    assert preview.json()["duplicates"] == 7


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Risk engine â€” currency-aware signals
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.parametrize("extension", ["xlsx", "xls"])
def test_excel_upload_preview_and_import(extension):
    content = io.BytesIO()
    headers = ["Transaction Date", "Description", "Amount", "Type", "Currency"]
    merchant = f"Excel {extension.upper()} merchant"
    values = ["2026-09-10", merchant, "123.45", "debit", "INR"]
    if extension == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        sheet.append(values)
        workbook.save(content)
    else:
        import xlwt

        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("Statement")
        for column, value in enumerate(headers):
            sheet.write(0, column, value)
        for column, value in enumerate(values):
            sheet.write(1, column, value)
        workbook.save(content)

    filename = f"statement-{extension}.{extension}"
    preview = client.post(
        "/transactions/upload?preview_only=true",
        files={"file": (filename, io.BytesIO(content.getvalue()), "application/octet-stream")},
        headers=_auth_a(),
    )
    assert preview.status_code == 200
    assert preview.json()["valid_rows"] == 1
    assert preview.json()["preview_rows"][0]["merchant"] == merchant
    search = f"Excel%20{extension.upper()}%20merchant"
    assert client.get(f"/transactions/?search={search}", headers=_auth_a()).json() == []

    imported = client.post(
        "/transactions/upload",
        files={"file": (filename, io.BytesIO(content.getvalue()), "application/octet-stream")},
        headers=_auth_a(),
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == 1
    assert len(client.get(f"/transactions/?search={search}", headers=_auth_a()).json()) == 1


def test_inr_risk_signals_use_rupee_symbol():
    """A very large INR transaction should produce signals with ₹ not $."""
    from app.services.risk_engine import calculate_risk
    import datetime

    result = calculate_risk(
        amount=300_000.0,
        currency="INR",
        merchant="Unknown Vendor",
        category="Other",
        location=None,
        payment_method=None,
        timestamp=datetime.datetime(2026, 9, 1, 14, 0),
        user_recent_transactions=[],
        user_avg_amount=0.0,
        is_new_merchant=True,
        transaction_type="debit",
    )
    assert result["risk_level"] in ("medium", "high")
    # All signal strings mentioning an amount must use ₹ not $
    for signal in result["signals"]:
        if "300" in signal or "transaction" in signal.lower():
            assert "₹" in signal or "INR" in signal, (
                f"INR signal should not use $: {signal}"
            )
            assert "$" not in signal, f"INR signal must not contain $: {signal}"


def test_ambiguous_date_parsing_prefers_day_first_for_dd_mm_yyyy():
    from app.routers.transactions import _parse_timestamp

    assert _parse_timestamp("11/09/2024").date().isoformat() == "2024-09-11"
    assert _parse_timestamp("09/11/2024").date().isoformat() == "2024-11-09"
    assert _parse_timestamp("2024/09/11").date().isoformat() == "2024-09-11"


def test_usd_risk_signals_use_dollar_symbol():
    """A very large USD transaction should produce signals with $."""
    from app.services.risk_engine import calculate_risk
    import datetime

    result = calculate_risk(
        amount=15_000.0,
        currency="USD",
        merchant="Unknown Wire",
        category="Wire Transfer",
        location=None,
        payment_method="Wire",
        timestamp=datetime.datetime(2026, 9, 1, 14, 0),
        user_recent_transactions=[],
        user_avg_amount=0.0,
        is_new_merchant=True,
        transaction_type="debit",
    )
    assert result["risk_level"] == "high"
    found_dollar = any("$" in s for s in result["signals"])
    assert found_dollar, f"USD signals should contain $: {result['signals']}"


def test_inr_and_usd_histories_not_mixed():
    """Historical INR avg must not influence risk scoring of USD transaction."""
    from app.services.risk_engine import calculate_risk
    import datetime

    # User has INR history with avg ~1000 INR per transaction
    inr_history = [
        {"timestamp": "2026-08-01T12:00:00", "merchant": "Swiggy", "amount": 1000.0}
    ] * 10

    # Now a USD $500 transaction â€” should NOT be penalized because
    # $500 > 4 * INR_avg (which would be ~4000, not meaningful in USD context)
    result = calculate_risk(
        amount=500.0,
        currency="USD",
        merchant="Amazon",
        category="Shopping",
        location=None,
        payment_method=None,
        timestamp=datetime.datetime(2026, 9, 2, 14, 0),
        user_recent_transactions=inr_history,
        user_avg_amount=0.0,  # avg_amount 0 means "don't compare" â†’ no historical flag
        is_new_merchant=False,
        transaction_type="debit",
    )
    # Should be low risk â€” no historical average comparison because avg_amount=0
    for signal in result["signals"]:
        assert "historical average" not in signal.lower(), (
            f"Should not compare INR history against USD: {signal}"
        )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# User isolation
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_user_b_cannot_see_user_a_transactions():
    """Bob must not see Alice's transactions."""
    r_b = client.get("/transactions/", headers=_auth_b())
    assert r_b.status_code == 200
    b_ids = {t["id"] for t in r_b.json()}

    r_a = client.get("/transactions/", headers=_auth_a())
    a_ids = {t["id"] for t in r_a.json()}

    overlap = a_ids & b_ids
    assert len(overlap) == 0, f"User B can see User A's transactions: {overlap}"


def test_user_b_cannot_access_user_a_transaction_by_id():
    """Bob cannot fetch Alice's specific transaction."""
    r = client.get(f"/transactions/{_txn_id}", headers=_auth_b())
    assert r.status_code == 404


def test_user_b_cannot_update_user_a_transaction():
    r = client.patch(
        f"/transactions/{_txn_id}",
        json={"category": "Salary"},
        headers=_auth_b(),
    )
    assert r.status_code == 404


def test_user_b_cannot_see_user_a_alerts():
    """Bob must not see Alice's alerts."""
    # Alice may have alerts from high-risk CSV rows
    r_a = client.get("/alerts/", headers=_auth_a())
    r_b = client.get("/alerts/", headers=_auth_b())
    a_ids = {a["id"] for a in r_a.json()}
    b_ids = {a["id"] for a in r_b.json()}
    assert len(a_ids & b_ids) == 0


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Analytics
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_analytics():
    r = client.get("/analytics/", headers=_auth_a())
    assert r.status_code == 200
    data = r.json()
    assert "total_income" in data
    assert "total_expenses" in data
    assert "category_breakdown" in data
    assert "monthly_trends" in data
    # Income must not be zero (we uploaded salary rows)
    assert data["total_income"] > 0, "Expected income > 0 after uploading salary CSV rows"


def test_analytics_date_range_and_derived_kpis():
    r = client.get(
        "/analytics/?currency=INR&date_from=2026-09-02&date_to=2026-09-02&interval=day",
        headers=_auth_a(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["transaction_count"] == 1
    assert data["total_income"] == 0
    assert data["total_expenses"] == 2499
    assert data["net_cash_flow"] == -2499
    assert data["average_transaction_amount"] == 2499
    assert data["largest_transaction_amount"] == 2499
    assert data["savings_rate"] is None
    assert data["cash_flow_trends"] == [{
        "month": "2026-09-02",
        "income": 0,
        "expenses": 2499,
        "net": -2499,
    }]
    assert data["top_merchants"][0]["merchant"] == "Amazon"
    assert sum(level["count"] for level in data["risk_distribution"]) == 1


def test_analytics_rejects_reversed_date_range():
    r = client.get(
        "/analytics/?date_from=2026-09-10&date_to=2026-09-01",
        headers=_auth_a(),
    )
    assert r.status_code == 400


def test_dashboard_numbers_match_stats():
    """Dashboard metric numbers must match /transactions/stats."""
    stats_r = client.get("/transactions/stats", headers=_auth_a())
    analytics_r = client.get("/analytics/", headers=_auth_a())
    assert stats_r.status_code == 200
    assert analytics_r.status_code == 200
    stats = stats_r.json()
    analytics = analytics_r.json()
    assert stats["currency"] == analytics["currency"] == "INR"
    assert stats["total_income"] == analytics["total_income"]
    assert stats["total_expenses"] == analytics["total_expenses"]

    usd_stats = client.get("/transactions/stats?currency=USD", headers=_auth_a()).json()
    usd_analytics = client.get("/analytics/?currency=USD", headers=_auth_a()).json()
    assert usd_stats["currency"] == usd_analytics["currency"] == "USD"
    assert usd_stats["total_income"] == usd_analytics["total_income"]
    assert usd_stats["total_expenses"] == usd_analytics["total_expenses"]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Alerts
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_alerts():
    r = client.get("/alerts/", headers=_auth_a())
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AI chat â€” no fake data
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_ai_health():
    r = client.get("/ai/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "key_configured" in data


def test_ai_chat_no_key_uses_local_fallback(monkeypatch):
    """Without an API key, common questions still receive account-grounded answers."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    r = client.post("/ai/chat", json={"message": "What is my balance?"},
                    headers=_auth_a())
    assert r.status_code == 200
    data = r.json()
    assert data["ai_unavailable"] is True
    reply = data["reply"].lower()
    assert "account balance" in reply
    assert "uploaded transactions don't provide a current account balance" in reply
    assert "463" not in reply
    assert "182" not in reply


def test_ai_chat_no_key_responds_to_greeting(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    response = client.post(
        "/ai/chat", json={"message": "hello"}, headers=_auth_a()
    )
    assert response.status_code == 200
    assert response.json()["ai_unavailable"] is True
    assert "hello alice" in response.json()["reply"].lower()


def test_ai_chat_no_key_reports_canonical_expenses(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    analytics = client.get("/analytics/?currency=INR", headers=_auth_a()).json()
    response = client.post(
        "/ai/chat", json={"message": "How much did I spend?"},
        headers=_auth_a(),
    )
    assert response.status_code == 200
    assert response.json()["ai_unavailable"] is True
    assert f"INR {analytics['total_expenses']:,.2f}" in response.json()["reply"]


def test_ai_chat_no_key_answers_merchant_transaction_questions(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    response = client.post(
        "/ai/chat", json={"message": "How much did I spend at Amazon?"},
        headers=_auth_a(),
    )
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Amazon" in reply
    assert "INR 2,499.00" in reply


def test_ai_chat_no_key_understands_follow_up_period(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    response = client.post(
        "/ai/chat",
        json={
            "message": "and in September?",
            "history": [
                {"role": "user", "content": "How much did I spend at Amazon?"},
                {"role": "assistant", "content": "You spent INR 2,499.00 at Amazon."},
            ],
        },
        headers=_auth_a(),
    )
    assert response.status_code == 200
    assert "INR 2,499.00" in response.json()["reply"]


def test_ai_context_uses_canonical_analytics(monkeypatch):
    import app.routers.ai as ai_router

    captured = {}

    async def capture_chat(**kwargs):
        captured.update(kwargs["user_stats"])
        return "analytics context received", False

    monkeypatch.setattr(ai_router, "chat", capture_chat)
    response = client.post(
        "/ai/chat", json={"message": "Summarize my expenses."}, headers=_auth_a()
    )
    assert response.status_code == 200
    canonical = captured["analytics_by_currency"]["INR"]
    dashboard = client.get("/analytics/?currency=INR", headers=_auth_a()).json()
    assert canonical["total_income"] == dashboard["total_income"]
    assert canonical["total_expenses"] == dashboard["total_expenses"]
    assert canonical["net_cash_flow"] == dashboard["net_cash_flow"]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Reports
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_reports_csv_download():
    r = client.get("/reports/transactions/csv", headers=_auth_a())
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    content = r.text
    # Should have more than just the header row since we uploaded data
    lines = [l for l in content.strip().split("\n") if l.strip()]
    assert len(lines) > 1, "CSV report should contain transaction data rows"


def test_reports_csv_respects_transaction_filters():
    r = client.get(
        "/reports/transactions/csv?search=Amazon&transaction_type=debit&currency=INR",
        headers=_auth_a(),
    )
    assert r.status_code == 200
    assert "Amazon" in r.text
    assert "Swiggy" not in r.text


def test_reports_csv_respects_amount_and_risk_filters():
    sample = client.get("/transactions/?search=Amazon&limit=1", headers=_auth_a()).json()[0]
    r = client.get(
        "/reports/transactions/csv?"
        f"amount_min={sample['amount']}&amount_max={sample['amount']}"
        f"&risk_score_min={sample['risk_score']}&risk_score_max={sample['risk_score']}"
        f"&risk_level={sample['risk_level']}&transaction_status={sample['status']}",
        headers=_auth_a(),
    )
    assert r.status_code == 200
    assert "Amazon" in r.text
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert all(float(row["Amount"]) == sample["amount"] for row in rows)
    assert all(float(row["Risk Score"]) == sample["risk_score"] for row in rows)
    assert all(row["Risk Level"] == sample["risk_level"] and row["Status"] == sample["status"] for row in rows)


def test_reports_csv_prevents_formula_injection():
    created = client.post(
        "/transactions/",
        json={
            "amount": 23,
            "currency": "INR",
            "merchant": "=HYPERLINK(\"https://example.invalid\")",
            "category": "Other",
            "transaction_type": "debit",
            "description": "+CMD",
            "timestamp": "2026-09-08T12:00:00",
        },
        headers=_auth_a(),
    )
    assert created.status_code == 201
    exported = client.get("/reports/transactions/csv?search=HYPERLINK", headers=_auth_a())
    assert exported.status_code == 200
    assert "'=HYPERLINK" in exported.text
    assert "'+CMD" in exported.text


@pytest.mark.parametrize(
    ("report_type", "expected_header"),
    [
        ("monthly", "Month,Currency,Income,Revenue,Expenses,Net Cash Flow,Savings,Savings Rate,Transactions,Risky Transactions"),
        ("category", "Category,Currency,Expense Total,Transactions"),
        ("merchant", "Merchant,Currency,Total Spending,Transaction Count,Average Transaction,Largest Transaction"),
        ("risk", "Risk Level,Currency,Transactions,Flagged,Average Risk Score"),
        ("fraud", "Transaction ID,Date,Merchant,Description,Amount,Currency,Category,Risk Score,Risk Level,Risk Signals,Flagged"),
        ("alerts", "Alert ID,Title,Description,Severity,Transaction ID,Amount,Currency,Risk Level,Created At,Read Status"),
    ],
)
def test_analytics_csv_reports_are_available_and_user_scoped(report_type, expected_header):
    r = client.get(f"/reports/analytics/csv?report_type={report_type}", headers=_auth_a())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0] == expected_header

    user_b = client.get(f"/reports/analytics/csv?report_type={report_type}", headers=_auth_b())
    assert user_b.status_code == 200
    assert user_b.text.splitlines()[0] == expected_header
    if report_type in ("monthly", "category", "risk"):
        assert len(user_b.text.splitlines()) == 1


def test_reports_pdf_download():
    try:
        import reportlab  # noqa: F401
        r = client.get("/reports/summary/pdf", headers=_auth_a())
        assert r.status_code == 200
        assert "pdf" in r.headers["content-type"].lower()
        # Basic PDF magic bytes check
        assert r.content[:4] == b"%PDF"
    except ImportError:
        pytest.skip("reportlab not installed")


def test_financial_security_pdf_download():
    try:
        import reportlab  # noqa: F401
        r = client.get("/reports/security/pdf", headers=_auth_a())
        assert r.status_code == 200
        assert "application/pdf" in r.headers["content-type"]
        assert r.content.startswith(b"%PDF")
    except ImportError:
        pytest.skip("reportlab not installed")


def test_business_revenue_is_only_reported_for_explicit_revenue_category():
    salary = client.get(
        "/analytics/?currency=INR&date_from=2026-09-01&date_to=2026-09-30",
        headers=_auth_a(),
    ).json()
    assert salary["total_revenue"] is None

    created = client.post(
        "/transactions/",
        json={
            "amount": 12500,
            "currency": "INR",
            "merchant": "Test Client",
            "category": "Business Revenue",
            "transaction_type": "credit",
            "timestamp": "2026-09-08T12:00:00",
        },
        headers=_auth_a(),
    )
    assert created.status_code == 201
    analytics = client.get(
        "/analytics/?currency=INR&date_from=2026-09-08&date_to=2026-09-08",
        headers=_auth_a(),
    ).json()
    assert analytics["total_income"] == 12500
    assert analytics["total_revenue"] == 12500


def test_reports_flagged_csv():
    r = client.get("/reports/transactions/csv?flagged_only=true", headers=_auth_a())
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Cleanup
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_cleanup():
    """Drop test database tables and remove file."""
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()  # release Windows file lock
    import time
    time.sleep(0.1)  # give OS time to release
    if os.path.exists("test_FinMind.db"):
        try:
            os.remove("test_FinMind.db")
        except PermissionError:
            pass  # Windows may still hold the lock; not a test failure
