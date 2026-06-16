"""Tests for services.api.graph (M3) — mocked VLMClient, both routing branches."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pypdfium2 as pdfium
import pytest

from services.api.graph import ExtractionResult, run_extraction_pipeline
from services.api.models.bank_statement import BankStatementExtraction
from services.api.models.fields import FieldVerification, SourceLocation
from services.api.models.invoice import InvoiceExtraction
from services.api.models.router import DocTypeClassification
from services.api.models.verified_invoice import InvoiceVerificationResponse


def _make_pdf(tmp_path: Path) -> Path:
    doc = pdfium.PdfDocument.new()
    doc.new_page(width=595, height=842)
    out = tmp_path / "doc.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _full_invoice() -> InvoiceExtraction:
    return InvoiceExtraction(invoice_number="INV-001", vendor_name="Acme", total_amount=1180.0)


def _full_verif_response() -> InvoiceVerificationResponse:
    high = FieldVerification(
        confidence=0.95,
        source_location=SourceLocation(page=0, bbox=[0.1, 0.1, 0.5, 0.2]),
    )
    return InvoiceVerificationResponse(
        invoice_number=high,
        invoice_date=high,
        due_date=high,
        vendor_name=high,
        vendor_gstin=high,
        vendor_address=high,
        buyer_name=high,
        buyer_gstin=high,
        currency=high,
        subtotal=high,
        total_amount=high,
        tax_total_tax=high,
    )


def _mock_client(*side_effect: object) -> AsyncMock:
    client = AsyncMock()
    client.extract_structured = AsyncMock(side_effect=list(side_effect))
    client._model = "mock-model"
    return client


async def test_routes_to_invoice_pipeline(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client(
        DocTypeClassification(doc_type="invoice", confidence=0.9),
        _full_invoice(),
        _full_verif_response(),
    )

    result = await run_extraction_pipeline(pdf, client)

    assert isinstance(result, ExtractionResult)
    assert result.doc_type == "invoice"
    assert result.router_confidence == pytest.approx(0.9)
    assert result.bank_statement is None
    assert result.invoice is not None
    assert result.invoice.invoice_number.value == "INV-001"


async def test_routes_to_bank_statement_pipeline(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client(
        DocTypeClassification(doc_type="bank_statement", confidence=0.85),
        BankStatementExtraction(account_holder_name="Jane Doe", account_number="1234567890"),
    )

    result = await run_extraction_pipeline(pdf, client)

    assert result.doc_type == "bank_statement"
    assert result.router_confidence == pytest.approx(0.85)
    assert result.invoice is None
    assert result.bank_statement is not None
    assert result.bank_statement.account_holder_name == "Jane Doe"
    # PII masking still applies on the bank-statement path
    assert result.bank_statement.account_number == "XXXXXX7890"


async def test_router_only_sees_first_page(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client(
        DocTypeClassification(doc_type="invoice", confidence=0.7),
        _full_invoice(),
        _full_verif_response(),
    )

    await run_extraction_pipeline(pdf, client)

    first_call_pages = client.extract_structured.call_args_list[0].args[0]
    assert len(first_call_pages) == 1
