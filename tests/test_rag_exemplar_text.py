"""Tests for services.api.rag.exemplar_text (M3) — pure functions, no I/O."""

from __future__ import annotations

from services.api.models.fields import ExtractionField
from services.api.models.invoice import InvoiceExtraction, LineItem
from services.api.models.verified_invoice import VerifiedInvoiceExtraction
from services.api.rag.exemplar_text import invoice_exemplar_text


def test_invoice_extraction_includes_vendor_and_line_items() -> None:
    extraction = InvoiceExtraction(
        vendor_name="Acme Corp",
        vendor_address="123 Main St",
        line_items=[
            LineItem(description="Widget A"),
            LineItem(description="Widget B"),
        ],
    )

    text = invoice_exemplar_text(extraction)

    assert text == "Acme Corp\n123 Main St\nWidget A\nWidget B"


def test_invoice_extraction_omits_missing_fields() -> None:
    extraction = InvoiceExtraction(vendor_name="Acme Corp")

    text = invoice_exemplar_text(extraction)

    assert text == "Acme Corp"


def test_invoice_extraction_omits_volatile_fields() -> None:
    """invoice_number/total_amount/dates shouldn't affect the layout signature."""
    extraction = InvoiceExtraction(
        vendor_name="Acme Corp",
        invoice_number="INV-999",
        total_amount=12345.0,
        invoice_date="2026-01-01",
    )

    text = invoice_exemplar_text(extraction)

    assert "INV-999" not in text
    assert "12345" not in text
    assert "2026-01-01" not in text


def test_verified_invoice_extraction_unwraps_extraction_field_values() -> None:
    def ef(value: object) -> ExtractionField[object]:
        return ExtractionField(value=value, confidence=0.9)

    verified = VerifiedInvoiceExtraction(
        invoice_number=ef(None),
        invoice_date=ef(None),
        due_date=ef(None),
        vendor_name=ef("Acme Corp"),
        vendor_gstin=ef(None),
        vendor_address=ef("123 Main St"),
        buyer_name=ef(None),
        buyer_gstin=ef(None),
        currency=ef(None),
        subtotal=ef(None),
        total_amount=ef(None),
        tax=ef(None),
        line_items=[LineItem(description="Widget A")],
    )

    text = invoice_exemplar_text(verified)

    assert text == "Acme Corp\n123 Main St\nWidget A"
