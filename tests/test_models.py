"""Tests for Pydantic extraction schemas (M1.F1)."""

from __future__ import annotations

from services.api.models.bank_statement import (
    BankStatementExtraction,
    Transaction,
    mask_account_number,
    mask_statement,
)
from services.api.models.invoice import InvoiceExtraction, LineItem, TaxBreakdown

# ── InvoiceExtraction ─────────────────────────────────────────────────────────


class TestInvoiceExtraction:
    def test_all_none_by_default(self) -> None:
        inv = InvoiceExtraction()
        assert inv.invoice_number is None
        assert inv.total_amount is None
        assert inv.line_items == []

    def test_valid_full_invoice(self) -> None:
        inv = InvoiceExtraction(
            invoice_number="INV-001",
            invoice_date="2024-01-15",
            vendor_name="Acme Corp",
            vendor_gstin="27AADCA8322L1ZK",
            currency="INR",
            subtotal=1000.0,
            tax=TaxBreakdown(cgst=90.0, sgst=90.0, total_tax=180.0),
            total_amount=1180.0,
            line_items=[
                LineItem(description="Widget", quantity=10, unit_price=100.0, line_total=1000.0)
            ],
        )
        assert inv.invoice_number == "INV-001"
        assert inv.tax is not None
        assert inv.tax.total_tax == 180.0
        assert len(inv.line_items) == 1

    def test_model_dump_roundtrip(self) -> None:
        inv = InvoiceExtraction(invoice_number="X", total_amount=500.0)
        data = inv.model_dump()
        restored = InvoiceExtraction.model_validate(data)
        assert restored.invoice_number == "X"
        assert restored.total_amount == 500.0

    def test_partial_tax(self) -> None:
        inv = InvoiceExtraction(tax=TaxBreakdown(igst=200.0))
        assert inv.tax is not None
        assert inv.tax.cgst is None
        assert inv.tax.igst == 200.0

    def test_null_fields_from_dict(self) -> None:
        raw = {"invoice_number": "A", "total_amount": None, "tax": None}
        inv = InvoiceExtraction.model_validate(raw)
        assert inv.invoice_number == "A"
        assert inv.total_amount is None
        assert inv.tax is None


# ── BankStatementExtraction ───────────────────────────────────────────────────


class TestBankStatementExtraction:
    def test_all_none_by_default(self) -> None:
        stmt = BankStatementExtraction()
        assert stmt.account_number is None
        assert stmt.transactions == []

    def test_valid_statement(self) -> None:
        stmt = BankStatementExtraction(
            account_holder_name="Rahul Sharma",
            account_number="123456789012",
            bank_name="State Bank of India",
            currency="INR",
            opening_balance=5000.0,
            closing_balance=7500.0,
            transactions=[
                Transaction(
                    date="2024-01-10", narration="NEFT credit", credit=2500.0, balance=7500.0
                )
            ],
        )
        assert stmt.account_number == "123456789012"
        assert len(stmt.transactions) == 1


# ── PII masking ───────────────────────────────────────────────────────────────


class TestMaskAccountNumber:
    def test_masks_all_but_last_four(self) -> None:
        assert mask_account_number("123456789012") == "XXXXXXXX9012"

    def test_short_number_keeps_all_if_le_visible(self) -> None:
        # 3 digits, visible_digits=4 → nothing masked
        assert mask_account_number("123", visible_digits=4) == "123"

    def test_exact_visible_digits(self) -> None:
        assert mask_account_number("12345678", visible_digits=4) == "XXXX5678"

    def test_preserves_non_digit_chars(self) -> None:
        # Hyphens in account number stay in place
        masked = mask_account_number("1234-5678-9012", visible_digits=4)
        assert masked == "XXXX-XXXX-9012"

    def test_single_digit_visible(self) -> None:
        assert mask_account_number("9876543210", visible_digits=1) == "XXXXXXXXX0"


class TestMaskStatement:
    def test_masks_account_number_in_copy(self) -> None:
        stmt = BankStatementExtraction(account_number="123456789012")
        masked = mask_statement(stmt)
        assert masked.account_number == "XXXXXXXX9012"
        # Original unchanged
        assert stmt.account_number == "123456789012"

    def test_none_account_number_passthrough(self) -> None:
        stmt = BankStatementExtraction(account_number=None)
        masked = mask_statement(stmt)
        assert masked.account_number is None
