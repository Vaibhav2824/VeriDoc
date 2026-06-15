"""Unit tests for eval.metrics — all pure functions, no I/O."""

from __future__ import annotations

import pytest

from eval.metrics import (
    corpus_metrics,
    doc_accuracy,
    field_match,
    normalize_address,
    normalize_date,
    normalize_number,
    normalize_string,
)

# ── normalize_string ──────────────────────────────────────────────────────────


def test_normalize_string_lowercases() -> None:
    assert normalize_string("ABC Corp") == "abc corp"


def test_normalize_string_strips_whitespace() -> None:
    assert normalize_string("  Vendor Name  ") == "vendor name"


def test_normalize_string_collapses_internal_spaces() -> None:
    assert normalize_string("ACME   Industries") == "acme industries"


# ── normalize_number ──────────────────────────────────────────────────────────


def test_normalize_number_float() -> None:
    assert normalize_number(1234.56) == pytest.approx(1234.56)


def test_normalize_number_int() -> None:
    assert normalize_number(500) == pytest.approx(500.0)


def test_normalize_number_string_with_commas() -> None:
    assert normalize_number("1,234.56") == pytest.approx(1234.56)


def test_normalize_number_string_plain() -> None:
    assert normalize_number("99.99") == pytest.approx(99.99)


def test_normalize_number_invalid_returns_none() -> None:
    assert normalize_number("N/A") is None


# ── normalize_date ────────────────────────────────────────────────────────────


def test_normalize_date_iso() -> None:
    assert normalize_date("2024-03-15") == "2024-03-15"


def test_normalize_date_dd_mm_yyyy_slash() -> None:
    assert normalize_date("15/03/2024") == "2024-03-15"


def test_normalize_date_dd_mm_yyyy_dash() -> None:
    assert normalize_date("15-03-2024") == "2024-03-15"


def test_normalize_date_unknown_format_passthrough() -> None:
    assert normalize_date("March 15, 2024") == "2024-03-15"


def test_normalize_date_strips_whitespace() -> None:
    assert normalize_date("  2024-03-15  ") == "2024-03-15"


# ── normalize_address ─────────────────────────────────────────────────────────


def test_normalize_address_strips_commas_and_newlines() -> None:
    a = "Plot 14, MIDC Industrial Area, Andheri East\nMumbai, Maharashtra - 400093"
    b = "Plot 14, MIDC Industrial Area, Andheri East, Mumbai, Maharashtra - 400093"
    assert normalize_address(a) == normalize_address(b)


def test_normalize_address_lowercases() -> None:
    assert normalize_address("MUMBAI") == "mumbai"


def test_normalize_address_mismatch() -> None:
    assert normalize_address("Mumbai") != normalize_address("Delhi")


# ── field_match ───────────────────────────────────────────────────────────────


def test_field_match_string_exact() -> None:
    assert field_match("ACME Corp", "ACME Corp", "vendor_name") is True


def test_field_match_string_case_insensitive() -> None:
    assert field_match("acme corp", "ACME Corp", "vendor_name") is True


def test_field_match_string_mismatch() -> None:
    assert field_match("ACME Corp", "Beta Inc", "vendor_name") is False


def test_field_match_none_predicted_is_miss() -> None:
    assert field_match(None, "INV-001", "invoice_number") is False


def test_field_match_number_equal() -> None:
    assert field_match(1500.0, 1500.0, "total_amount") is True


def test_field_match_number_rounding() -> None:
    assert field_match(1500.004, 1500.0, "total_amount") is True


def test_field_match_number_string_vs_float() -> None:
    assert field_match("1,500.00", 1500.0, "total_amount") is True


def test_field_match_number_mismatch() -> None:
    assert field_match(1400.0, 1500.0, "total_amount") is False


def test_field_match_date_different_formats() -> None:
    assert field_match("15/03/2024", "2024-03-15", "invoice_date") is True


def test_field_match_date_mismatch() -> None:
    assert field_match("2024-03-14", "2024-03-15", "invoice_date") is False


def test_field_match_address_newline_vs_comma() -> None:
    model = "Plot 14, MIDC Area\nMumbai, Maharashtra - 400093"
    gt = "Plot 14, MIDC Area, Mumbai, Maharashtra - 400093"
    assert field_match(model, gt, "vendor_address") is True


def test_field_match_address_mismatch() -> None:
    assert field_match("123 Main St, Delhi", "456 MG Road, Mumbai", "vendor_address") is False


# ── doc_accuracy ──────────────────────────────────────────────────────────────


def test_doc_accuracy_perfect_match() -> None:
    gt = {
        "invoice_number": "INV-001",
        "total_amount": 1000.0,
        "invoice_date": "2024-01-01",
    }
    pred = {
        "invoice_number": "INV-001",
        "total_amount": 1000.0,
        "invoice_date": "2024-01-01",
    }
    result = doc_accuracy(pred, gt)
    assert result["invoice_number"] is True
    assert result["total_amount"] is True
    assert result["invoice_date"] is True


def test_doc_accuracy_gt_null_field_is_not_scored() -> None:
    gt = {"invoice_number": "INV-001", "due_date": None}
    pred = {"invoice_number": "INV-001", "due_date": "2024-06-01"}
    result = doc_accuracy(pred, gt)
    assert result["due_date"] is None  # GT null → not scored


def test_doc_accuracy_nested_tax_total_tax() -> None:
    gt = {"tax": {"total_tax": 180.0}}
    pred = {"tax": {"total_tax": 180.0}}
    result = doc_accuracy(pred, gt)
    assert result["tax.total_tax"] is True


def test_doc_accuracy_nested_tax_mismatch() -> None:
    gt = {"tax": {"total_tax": 180.0}}
    pred = {"tax": {"total_tax": 90.0}}
    result = doc_accuracy(pred, gt)
    assert result["tax.total_tax"] is False


def test_doc_accuracy_missing_predicted_field_is_miss() -> None:
    gt = {"vendor_name": "ACME Corp"}
    pred: dict[str, object] = {}  # vendor_name not extracted
    result = doc_accuracy(pred, gt)
    assert result["vendor_name"] is False


# ── corpus_metrics ────────────────────────────────────────────────────────────


def test_corpus_metrics_empty_returns_none_accuracy() -> None:
    result = corpus_metrics([])
    assert result["macro_accuracy"] is None
    assert result["n_docs"] == 0


def test_corpus_metrics_single_perfect_doc() -> None:
    doc_result = {"invoice_number": True, "total_amount": True, "due_date": None}
    result = corpus_metrics([doc_result])
    assert result["macro_accuracy"] == pytest.approx(1.0)
    assert result["n_scored_pairs"] == 2  # due_date not scored


def test_corpus_metrics_single_partial_doc() -> None:
    doc_result: dict[str, bool | None] = {"invoice_number": True, "total_amount": False}
    result = corpus_metrics([doc_result])
    assert result["macro_accuracy"] == pytest.approx(0.5)


def test_corpus_metrics_multiple_docs() -> None:
    results: list[dict[str, bool | None]] = [
        {"invoice_number": True, "total_amount": True},
        {"invoice_number": False, "total_amount": True},
    ]
    metrics = corpus_metrics(results)
    # invoice_number: 1/2=0.5, total_amount: 2/2=1.0 → macro = 3/4=0.75
    assert metrics["macro_accuracy"] == pytest.approx(0.75)
    assert metrics["field_accuracy"]["invoice_number"] == pytest.approx(0.5)
    assert metrics["field_accuracy"]["total_amount"] == pytest.approx(1.0)
    assert metrics["n_docs"] == 2
    assert metrics["n_scored_pairs"] == 4


def test_corpus_metrics_field_absent_in_all_docs_not_reported() -> None:
    """A field that is None in every doc should not appear in field_accuracy."""
    results: list[dict[str, bool | None]] = [{"invoice_number": None}, {"invoice_number": None}]
    metrics = corpus_metrics(results)
    assert "invoice_number" not in metrics["field_accuracy"]
