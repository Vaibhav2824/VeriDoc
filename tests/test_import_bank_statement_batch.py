"""Tests for scripts.import_bank_statement_batch's pure conversion logic (M3)."""

from __future__ import annotations

from scripts.import_bank_statement_batch import (
    _normalize_ref_no,
    _normalize_transaction,
    _parse_date,
    _row_to_label,
)


def test_parse_date_iso_with_time() -> None:
    assert _parse_date("2024-01-01 11:30:55") == "2024-01-01"


def test_parse_date_iso_plain() -> None:
    assert _parse_date("2024-01-01") == "2024-01-01"


def test_parse_date_dd_mm_yyyy() -> None:
    assert _parse_date("02/01/2024") == "2024-01-02"


def test_parse_date_none() -> None:
    assert _parse_date(None) is None
    assert _parse_date("") is None


def test_normalize_ref_no_treats_dash_and_empty_as_none() -> None:
    assert _normalize_ref_no("") is None
    assert _normalize_ref_no("-") is None
    assert _normalize_ref_no(None) is None
    assert _normalize_ref_no("567302") == "567302"


def test_normalize_transaction_type1_shape() -> None:
    raw = {
        "date": "2024-01-02 12:44:20",
        "value_date": "2024-01-02",
        "description": "Chq Paid",
        "cheque_no": "567302",
        "debit": 23702.04,
        "credit": None,
        "balance": 41516.31,
    }

    result = _normalize_transaction(raw)

    assert result == {
        "date": "2024-01-02",
        "narration": "Chq Paid",
        "debit": 23702.04,
        "credit": None,
        "balance": 41516.31,
        "ref_no": "567302",
    }


def test_normalize_transaction_type2_shape_debit() -> None:
    raw = {
        "date": "02/01/2024",
        "value_date": "02/01/2024",
        "description": "RTGS-Dr",
        "cheque_no": "-",
        "cr_dr": "DR",
        "transaction_amount": 475617.41,
        "available_balance": 803454.76,
    }

    result = _normalize_transaction(raw)

    assert result == {
        "date": "2024-01-02",
        "narration": "RTGS-Dr",
        "debit": 475617.41,
        "credit": None,
        "balance": 803454.76,
        "ref_no": None,
    }


def test_normalize_transaction_type2_shape_credit() -> None:
    raw = {
        "date": "02/01/2024",
        "value_date": "02/01/2024",
        "description": "IMPS-Cr",
        "cheque_no": "-",
        "cr_dr": "CR",
        "transaction_amount": 101795.99,
        "available_balance": 905250.75,
    }

    result = _normalize_transaction(raw)

    assert result["debit"] is None
    assert result["credit"] == 101795.99


def test_row_to_label_shape() -> None:
    raw = {
        "bank_name": "Progressive National Bank",
        "account_holder": "TRADE LINKS INDIA",
        "account_number": "78439336112",
        "ifsc_code": "PROG0920445",
        "currency": "INR",
        "opening_balance": 59131.72,
        "closing_balance": 21661.82,
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "transactions": [],
    }

    label = _row_to_label(raw, "bankstmt_digital_type1_00001.pdf")

    assert label["_meta"]["doc_type"] == "bank_statement"
    assert label["_meta"]["doc_file"] == "bankstmt_digital_type1_00001.pdf"
    assert label["account_holder_name"] == "TRADE LINKS INDIA"
    assert label["bank_name"] == "Progressive National Bank"
    assert label["ifsc"] == "PROG0920445"
    assert label["statement_period"] == {"start": "2024-01-01", "end": "2024-03-31"}
    assert label["transactions"] == []
