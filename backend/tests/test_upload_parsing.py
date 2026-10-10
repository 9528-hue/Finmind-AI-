import io

from app.routers.transactions import (
    _map_columns,
    _normalize_row,
    _read_dataframe,
)


def test_csv_upload_skips_title_and_finds_messy_header():
    contents = (
        b"demo_synthetic_bank_data,,,,,\n"
        b"\n"
        b"Txn Date,Party,Narration,Dr,Cr,Closing Bal\n"
        b"01-Sep-2026,Corner Cafe,Coffee purchase,250.00,,9750.00\n"
    )

    frame = _read_dataframe(contents, "statement.csv")
    mapping = _map_columns(list(frame.columns))
    record, problem = _normalize_row(frame.iloc[0].to_dict(), mapping, "INR")

    assert problem is None
    assert record is not None
    assert record["timestamp"].date().isoformat() == "2026-09-01"
    assert record["merchant"] == "Corner Cafe"
    assert record["description"] == "Coffee purchase"
    assert record["amount"] == 250
    assert record["transaction_type"] == "debit"
    assert frame.attrs["header_row_index"] == 2
    assert frame.index[0] == 0


def test_csv_upload_detects_semicolon_delimiter_and_money_in_out():
    contents = (
        "Bank export\n"
        "Date;Description;Money Out;Money In;Currency\n"
        '2026-09-02;"Customer, enterprise payment";;1250.00;USD\n'
    ).encode()

    frame = _read_dataframe(contents, "statement.csv")
    mapping = _map_columns(list(frame.columns))
    record, problem = _normalize_row(frame.iloc[0].to_dict(), mapping, "INR")

    assert problem is None
    assert record is not None
    assert record["amount"] == 1250
    assert record["description"] == "Customer, enterprise payment"
    assert record["transaction_type"] == "credit"
    assert record["currency"] == "USD"


def test_excel_upload_skips_preamble_and_selects_transaction_sheet():
    from openpyxl import Workbook

    workbook = Workbook()
    readme = workbook.active
    readme.title = "Read me"
    readme.append(["Synthetic statement"])
    statement = workbook.create_sheet("Transactions")
    statement.append(["Statement for September"])
    statement.append(["Transaction Date", "Merchant", "Amount", "Type"])
    statement.append(["2026-09-03", "Office Supply Co", "840.50", "debit"])
    contents = io.BytesIO()
    workbook.save(contents)

    frame = _read_dataframe(contents.getvalue(), "statement.xlsx")
    mapping = _map_columns(list(frame.columns))
    record, problem = _normalize_row(frame.iloc[0].to_dict(), mapping, "INR")

    assert problem is None
    assert record is not None
    assert record["merchant"] == "Office Supply Co"
    assert record["amount"] == 840.5
    assert record["transaction_type"] == "debit"
    assert frame.attrs["header_row_index"] == 1
