"""Tests for services.mcp.server (M3) — mocked VLMClient, no live calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pypdfium2 as pdfium
import pytest

import services.mcp.server as mcp_server
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


@pytest.fixture(autouse=True)
def _reset_client_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "_client", None)


async def test_extract_invoice_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client(_full_invoice(), _full_verif_response())
    monkeypatch.setattr(mcp_server, "_get_client", lambda: client)

    result = await mcp_server.extract_invoice(str(pdf))

    assert result["invoice_number"]["value"] == "INV-001"


async def test_extract_bank_statement_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client(
        BankStatementExtraction(account_holder_name="Jane Doe", account_number="1234567890")
    )
    monkeypatch.setattr(mcp_server, "_get_client", lambda: client)

    result = await mcp_server.extract_bank_statement(str(pdf))

    assert result["account_holder_name"] == "Jane Doe"
    assert result["account_number"] == "XXXXXX7890"  # PII masked


async def test_extract_document_tool_routes_to_invoice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf = _make_pdf(tmp_path)
    client = _mock_client(
        DocTypeClassification(doc_type="invoice", confidence=0.9),
        _full_invoice(),
        _full_verif_response(),
    )
    monkeypatch.setattr(mcp_server, "_get_client", lambda: client)

    result = await mcp_server.extract_document(str(pdf))

    assert result["doc_type"] == "invoice"
    assert result["invoice"]["invoice_number"]["value"] == "INV-001"
    assert result["bank_statement"] is None


async def test_get_client_lazily_constructs_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = _mock_client()
    call_count = {"n": 0}

    def fake_make_client() -> AsyncMock:
        call_count["n"] += 1
        return sentinel

    monkeypatch.setattr(mcp_server, "make_client", fake_make_client)

    first = mcp_server._get_client()
    second = mcp_server._get_client()

    assert first is sentinel
    assert second is sentinel
    assert call_count["n"] == 1  # constructed once, reused on the second call


async def test_tools_registered_with_mcp() -> None:
    tools = await mcp_server.mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {"extract_document", "extract_invoice", "extract_bank_statement"}


async def test_call_tool_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end through the MCP dispatch layer, not just a direct function call."""
    pdf = _make_pdf(tmp_path)
    client = _mock_client(_full_invoice(), _full_verif_response())
    monkeypatch.setattr(mcp_server, "_get_client", lambda: client)

    result = await mcp_server.mcp.call_tool("extract_invoice", {"path": str(pdf)})

    assert isinstance(result, tuple)
    _content, structured = result
    assert isinstance(structured, dict)
    assert structured["invoice_number"]["value"] == "INV-001"
