"""Tests for services.api.extractor (M1) — mocked VLMClient."""

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
from services.api.models.invoice import InvoiceExtraction

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
    """Return a mock VLMClient whose extract_structured returns *response*."""
    client = AsyncMock()
    client.extract_structured = AsyncMock(return_value=response)
    client._model = "mock-model"
    return client


# ── invoice happy path ────────────────────────────────────────────────────────


async def test_extract_invoice_returns_model(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    expected = InvoiceExtraction(invoice_number="INV-001", total_amount=4250.0)
    client = _mock_client_structured(expected)

    result = await extract_invoice(pdf, client)

    assert isinstance(result, InvoiceExtraction)
    assert result.invoice_number == "INV-001"
    assert result.total_amount == 4250.0


async def test_extract_invoice_accepts_string_path(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    expected = InvoiceExtraction(invoice_number="X")
    client = _mock_client_structured(expected)

    result = await extract_invoice(str(pdf), client)

    assert result.invoice_number == "X"


async def test_extract_invoice_accepts_image(tmp_path: Path) -> None:
    png = _make_png(tmp_path)
    expected = InvoiceExtraction(total_amount=100.0)
    client = _mock_client_structured(expected)

    result = await extract_invoice(png, client)

    assert result.total_amount == 100.0


async def test_extract_invoice_passes_page_images_to_client(tmp_path: Path) -> None:
    """Each PDF page becomes one PIL Image forwarded to extract_structured."""
    pdf = _make_pdf(tmp_path, n_pages=3)
    client = _mock_client_structured(InvoiceExtraction())

    await extract_invoice(pdf, client)

    pages_arg: list[Image.Image] = client.extract_structured.call_args[0][0]
    assert len(pages_arg) == 3
    assert all(isinstance(p, Image.Image) for p in pages_arg)


async def test_extract_invoice_passes_response_model(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client_structured(InvoiceExtraction())

    await extract_invoice(pdf, client)

    _, model_arg, *_ = client.extract_structured.call_args[0]
    assert model_arg is InvoiceExtraction


async def test_extract_invoice_null_fields(tmp_path: Path) -> None:
    """All-None InvoiceExtraction (abstain case) passes through unchanged."""
    pdf = _make_pdf(tmp_path)
    client = _mock_client_structured(InvoiceExtraction())

    result = await extract_invoice(pdf, client)

    assert result.invoice_number is None
    assert result.total_amount is None


# ── invoice error propagation ─────────────────────────────────────────────────


async def test_ingest_error_propagates(tmp_path: Path) -> None:
    client = _mock_client_structured(InvoiceExtraction())
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


async def test_extract_bank_statement_masks_account_by_default(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    stmt = BankStatementExtraction(account_number="123456789012")
    client = _mock_client_structured(stmt)

    result = await extract_bank_statement(pdf, client, mask_pii=True)

    assert result.account_number == "XXXXXXXX9012"


async def test_extract_bank_statement_no_mask_when_disabled(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    stmt = BankStatementExtraction(account_number="123456789012")
    client = _mock_client_structured(stmt)

    result = await extract_bank_statement(pdf, client, mask_pii=False)

    assert result.account_number == "123456789012"


async def test_extract_bank_statement_none_account_passthrough(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    stmt = BankStatementExtraction(account_number=None)
    client = _mock_client_structured(stmt)

    result = await extract_bank_statement(pdf, client)

    assert result.account_number is None
