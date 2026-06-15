"""Tests for services.api.extractor — mocked VLMClient, real synthetic PDF/image."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pypdfium2 as pdfium
import pytest
from PIL import Image

from services.api.clients.base import VLMError
from services.api.extractor import NAIVE_INVOICE_PROMPT, extract_invoice
from services.api.ingest import IngestError

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


def _mock_client(response: dict[str, Any]) -> AsyncMock:
    client = AsyncMock()
    client.extract = AsyncMock(return_value=response)
    return client


# ── happy-path tests ──────────────────────────────────────────────────────────


async def test_extract_invoice_returns_dict(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    expected = {"invoice_number": "INV-2024-001", "total_amount": 4250.0}
    client = _mock_client(expected)

    result = await extract_invoice(pdf, client)

    assert result == expected


async def test_extract_invoice_accepts_string_path(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client({"invoice_number": "X"})

    result = await extract_invoice(str(pdf), client)  # str, not Path

    assert result["invoice_number"] == "X"


async def test_extract_invoice_accepts_image(tmp_path: Path) -> None:
    png = _make_png(tmp_path)
    client = _mock_client({"total_amount": 100.0})

    result = await extract_invoice(png, client)

    assert result["total_amount"] == 100.0


async def test_extract_invoice_passes_page_images_to_client(tmp_path: Path) -> None:
    """Each PDF page must become one PIL Image forwarded to client.extract."""
    pdf = _make_pdf(tmp_path, n_pages=3)
    client = _mock_client({})

    await extract_invoice(pdf, client)

    pages_arg: list[Image.Image] = client.extract.call_args[0][0]
    assert len(pages_arg) == 3
    assert all(isinstance(p, Image.Image) for p in pages_arg)


async def test_extract_invoice_passes_naive_prompt(tmp_path: Path) -> None:
    """The naive prompt must be forwarded verbatim (M0 contract)."""
    pdf = _make_pdf(tmp_path)
    client = _mock_client({})

    await extract_invoice(pdf, client)

    prompt_arg: str = client.extract.call_args[0][1]
    assert prompt_arg == NAIVE_INVOICE_PROMPT


# ── prompt content sanity checks ──────────────────────────────────────────────


def test_naive_prompt_covers_all_prd_fields() -> None:
    """NAIVE_INVOICE_PROMPT must reference every field from PRD §8.1."""
    required_fields = [
        "invoice_number",
        "invoice_date",
        "due_date",
        "vendor_name",
        "vendor_gstin",
        "vendor_address",
        "buyer_name",
        "buyer_gstin",
        "currency",
        "subtotal",
        "total_amount",
        "line_items",
        "tax",
    ]
    for field in required_fields:
        assert field in NAIVE_INVOICE_PROMPT, f"Prompt missing field: {field}"


# ── error propagation tests ───────────────────────────────────────────────────


async def test_ingest_error_propagates(tmp_path: Path) -> None:
    client = _mock_client({})
    with pytest.raises(IngestError):
        await extract_invoice(tmp_path / "missing.pdf", client)


async def test_vlm_error_propagates(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path)
    client = AsyncMock()
    client.extract = AsyncMock(side_effect=VLMError("quota exceeded"))

    with pytest.raises(VLMError, match="quota exceeded"):
        await extract_invoice(pdf, client)


async def test_returns_null_fields_unchanged(tmp_path: Path) -> None:
    """VLM may return null values; extractor must pass them through as-is."""
    pdf = _make_pdf(tmp_path)
    response = {"invoice_number": None, "total_amount": None, "line_items": None}
    client = _mock_client(response)

    result = await extract_invoice(pdf, client)

    assert result["invoice_number"] is None
    assert result["total_amount"] is None
