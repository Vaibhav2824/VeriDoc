"""Tests for services.api.extractor (M2) — mocked VLMClient."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pypdfium2 as pdfium
import pytest
from PIL import Image

from services.api.clients.base import VLMError
from services.api.extractor import extract_bank_statement, extract_invoice
from services.api.ingest import IngestError
from services.api.models.bank_statement import BankStatementExtraction, Transaction
from services.api.models.fields import FieldVerification, SourceLocation
from services.api.models.invoice import InvoiceExtraction, TaxBreakdown
from services.api.models.verified_invoice import (
    InvoiceVerificationResponse,
    VerifiedInvoiceExtraction,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_pdf(tmp_path: Path, n_pages: int = 1) -> Path:
    doc = pdfium.PdfDocument.new()
    for _ in range(n_pages):
        doc.new_page(width=595, height=842)
    out = tmp_path / "invoice.pdf"
    doc.save(str(out))
    doc.close()
    return out


def _make_png(tmp_path: Path) -> Path:
    img = Image.new("RGB", (400, 600), color=(255, 255, 255))
    out = tmp_path / "invoice.png"
    img.save(out)
    return out


def _mock_client_structured(response: object) -> AsyncMock:
    client = AsyncMock()
    client.extract_structured = AsyncMock(return_value=response)
    client._model = "mock-model"
    return client


def _full_invoice() -> InvoiceExtraction:
    return InvoiceExtraction(
        invoice_number="INV-001",
        total_amount=1180.0,
        vendor_name="Acme",
        currency="INR",
        subtotal=1000.0,
        tax=TaxBreakdown(cgst=90.0, sgst=90.0, total_tax=180.0),
    )


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


def test_verification_response_coerces_explicit_null() -> None:
    """Some VLMs (Gemini) emit `"due_date": null` instead of omitting the key.

    default_factory only kicks in for an absent key, so the schema must
    also tolerate an explicit null and fall back to the same default.
    """
    high = {
        "confidence": 0.95,
        "source_location": {"page": 0, "bbox": [0.1, 0.1, 0.5, 0.2]},
    }
    verif = InvoiceVerificationResponse.model_validate(
        {
            "invoice_number": high,
            "invoice_date": high,
            "due_date": None,
            "vendor_name": high,
            "vendor_gstin": high,
            "vendor_address": high,
            "buyer_name": high,
            "buyer_gstin": None,
            "currency": high,
            "subtotal": high,
            "total_amount": high,
            "tax_total_tax": high,
        }
    )

    assert verif.due_date == FieldVerification()
    assert verif.due_date.confidence == 0.5
    assert verif.due_date.source_location is None
    assert verif.buyer_gstin == FieldVerification()


def _mock_client_two_pass(
    extraction: InvoiceExtraction,
    verification: InvoiceVerificationResponse,
) -> AsyncMock:
    """Mock returning extraction first call, verification second call."""
    client = AsyncMock()
    client.extract_structured = AsyncMock(side_effect=[extraction, verification])
    client._model = "mock-model"
    return client


# ── invoice happy path ────────────────────────────────────────────────────────


async def test_extract_invoice_returns_verified(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client_two_pass(_full_invoice(), _full_verif_response())

    result = await extract_invoice(pdf, client)

    assert isinstance(result, VerifiedInvoiceExtraction)
    assert result.invoice_number.value == "INV-001"
    assert result.total_amount.value == 1180.0


async def test_extract_invoice_carries_confidence(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client_two_pass(_full_invoice(), _full_verif_response())

    result = await extract_invoice(pdf, client)

    assert result.invoice_number.confidence == pytest.approx(0.95)
    assert result.invoice_number.source_location is not None


async def test_extract_invoice_accepts_string_path(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client_two_pass(_full_invoice(), _full_verif_response())

    result = await extract_invoice(str(pdf), client)

    assert isinstance(result, VerifiedInvoiceExtraction)


async def test_extract_invoice_gate_abstains_low_confidence(tmp_path: Path) -> None:
    """Fields below default threshold (0.80) should be abstained."""
    pdf = _make_pdf(tmp_path)
    low_conf = FieldVerification(confidence=0.3)
    low_verif = InvoiceVerificationResponse(
        invoice_number=low_conf,
        invoice_date=low_conf,
        due_date=low_conf,
        vendor_name=low_conf,
        vendor_gstin=low_conf,
        vendor_address=low_conf,
        buyer_name=low_conf,
        buyer_gstin=low_conf,
        currency=low_conf,
        subtotal=low_conf,
        total_amount=low_conf,
        tax_total_tax=low_conf,
    )
    client = _mock_client_two_pass(_full_invoice(), low_verif)

    result = await extract_invoice(pdf, client, confidence_threshold=0.80)

    assert result.invoice_number.status == "abstained"
    assert result.invoice_number.effective_value is None


async def test_extract_invoice_high_confidence_not_abstained(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client_two_pass(_full_invoice(), _full_verif_response())

    result = await extract_invoice(pdf, client, confidence_threshold=0.80)

    assert result.invoice_number.status == "extracted"
    assert result.invoice_number.effective_value == "INV-001"


async def test_to_value_dict_abstained_returns_none(tmp_path: Path) -> None:
    """Abstained fields should appear as None in to_value_dict()."""
    pdf = _make_pdf(tmp_path)
    low_conf = FieldVerification(confidence=0.1)
    low_verif = InvoiceVerificationResponse(
        invoice_number=low_conf,
        invoice_date=low_conf,
        due_date=low_conf,
        vendor_name=low_conf,
        vendor_gstin=low_conf,
        vendor_address=low_conf,
        buyer_name=low_conf,
        buyer_gstin=low_conf,
        currency=low_conf,
        subtotal=low_conf,
        total_amount=low_conf,
        tax_total_tax=low_conf,
    )
    client = _mock_client_two_pass(_full_invoice(), low_verif)

    result = await extract_invoice(pdf, client, confidence_threshold=0.80)
    val_dict = result.to_value_dict()

    assert val_dict["invoice_number"] is None
    assert val_dict["total_amount"] is None


# ── error propagation ─────────────────────────────────────────────────────────


async def test_ingest_error_propagates(tmp_path: Path) -> None:
    client = _mock_client_two_pass(_full_invoice(), _full_verif_response())
    with pytest.raises(IngestError):
        await extract_invoice(tmp_path / "missing.pdf", client)


async def test_vlm_error_propagates(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = AsyncMock()
    client.extract_structured = AsyncMock(side_effect=VLMError("quota exceeded"))
    client._model = "mock-model"

    with pytest.raises(VLMError, match="quota exceeded"):
        await extract_invoice(pdf, client)


# ── bank statement happy path ─────────────────────────────────────────────────


async def test_extract_bank_statement_returns_model(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    stmt = BankStatementExtraction(
        account_number="123456789012",
        bank_name="SBI",
        opening_balance=1000.0,
        closing_balance=2500.0,
        transactions=[Transaction(date="2024-01-10", credit=1500.0, balance=2500.0)],
    )
    client = _mock_client_structured(stmt)

    result = await extract_bank_statement(pdf, client)

    assert isinstance(result, BankStatementExtraction)
    assert result.bank_name == "SBI"


async def test_extract_bank_statement_masks_pii(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    stmt = BankStatementExtraction(account_number="123456789012")
    client = _mock_client_structured(stmt)

    result = await extract_bank_statement(pdf, client, mask_pii=True)

    assert result.account_number == "XXXXXXXX9012"


async def test_extract_bank_statement_no_mask(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    stmt = BankStatementExtraction(account_number="123456789012")
    client = _mock_client_structured(stmt)

    result = await extract_bank_statement(pdf, client, mask_pii=False)

    assert result.account_number == "123456789012"
