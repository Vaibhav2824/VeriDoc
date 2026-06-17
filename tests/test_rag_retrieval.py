"""Tests for services.api.rag.retrieval (M3) — mocked store and embeddings."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.api.models.fields import ExtractionField, SourceLocation
from services.api.models.verified_invoice import VerifiedInvoiceExtraction
from services.api.rag.retrieval import (
    _rag_configured,
    format_exemplars_for_prompt,
    ingest_invoice_exemplar,
    retrieve_invoice_exemplars,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _ef(value: object, confidence: float = 0.95) -> ExtractionField[Any]:
    return ExtractionField(
        value=value,
        confidence=confidence,
        source_location=SourceLocation(page=0, bbox=[0.1, 0.1, 0.5, 0.2]),
    )


def _make_extraction(
    vendor_name: str = "Acme Corp",
    vendor_address: str = "123 Main St",
) -> VerifiedInvoiceExtraction:
    return VerifiedInvoiceExtraction(
        invoice_number=_ef("INV-001"),
        invoice_date=_ef(None),
        due_date=_ef(None),
        vendor_name=_ef(vendor_name),
        vendor_gstin=_ef(None),
        vendor_address=_ef(vendor_address),
        buyer_name=_ef(None),
        buyer_gstin=_ef(None),
        currency=_ef("INR"),
        subtotal=_ef(None),
        total_amount=_ef(1000.0),
        tax=_ef(None),
        line_items=[],
    )


# ── _rag_configured ───────────────────────────────────────────────────────────


def test_rag_not_configured_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert _rag_configured() is False


def test_rag_not_configured_with_placeholder_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/dbname")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    assert _rag_configured() is False


def test_rag_configured_when_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@real-host/db")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    assert _rag_configured() is True


# ── retrieve_invoice_exemplars ────────────────────────────────────────────────


async def test_retrieve_returns_empty_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = await retrieve_invoice_exemplars(_make_extraction())
    assert result == []


async def test_retrieve_returns_exemplar_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@real/db")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    fake_fields = {"vendor_name": "Acme", "total_amount": 1000.0}
    fake_row = MagicMock()
    fake_row.extracted_fields = fake_fields

    with (
        patch(
            "services.api.rag.embeddings.embed_text",
            new=AsyncMock(return_value=[0.1] * 768),
        ),
        patch("services.api.rag.store.get_engine", return_value=MagicMock()),
        patch(
            "services.api.rag.store.retrieve_similar",
            return_value=[fake_row],
        ),
    ):
        result = await retrieve_invoice_exemplars(_make_extraction())

    assert result == [fake_fields]


async def test_retrieve_swallows_non_vlmerror(monkeypatch: pytest.MonkeyPatch) -> None:
    """Store errors are non-fatal — extraction pipeline must not break."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@real/db")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    with (
        patch(
            "services.api.rag.embeddings.embed_text",
            new=AsyncMock(side_effect=RuntimeError("store down")),
        ),
    ):
        result = await retrieve_invoice_exemplars(_make_extraction())

    assert result == []


# ── ingest_invoice_exemplar ───────────────────────────────────────────────────


async def test_ingest_skipped_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # Should return without error
    await ingest_invoice_exemplar(_make_extraction(), "doc.pdf")


async def test_ingest_calls_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@real/db")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    mock_ingest = MagicMock()
    with (
        patch(
            "services.api.rag.embeddings.embed_text",
            new=AsyncMock(return_value=[0.1] * 768),
        ),
        patch("services.api.rag.store.get_engine", return_value=MagicMock()),
        patch("services.api.rag.store.ingest_exemplar", mock_ingest),
    ):
        await ingest_invoice_exemplar(_make_extraction(), "doc.pdf")

    mock_ingest.assert_called_once()
    call_kwargs = mock_ingest.call_args.kwargs
    assert call_kwargs["source_doc_name"] == "doc.pdf"
    assert call_kwargs["doc_type"] == "invoice"


async def test_ingest_swallows_store_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@real/db")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    with (
        patch(
            "services.api.rag.embeddings.embed_text",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ),
    ):
        await ingest_invoice_exemplar(_make_extraction(), "doc.pdf")


# ── format_exemplars_for_prompt ───────────────────────────────────────────────


def test_format_empty_returns_empty_string() -> None:
    assert format_exemplars_for_prompt([]) == ""


def test_format_includes_vendor_in_header() -> None:
    result = format_exemplars_for_prompt([{"vendor_name": "Acme Corp", "total_amount": 500.0}])
    assert "Acme Corp" in result
    assert "Example 1" in result


def test_format_omits_none_values() -> None:
    result = format_exemplars_for_prompt([{"vendor_name": "Acme", "invoice_date": None}])
    assert "invoice_date" not in result
    assert "vendor_name" in result


def test_format_multiple_exemplars() -> None:
    result = format_exemplars_for_prompt(
        [{"vendor_name": "A"}, {"vendor_name": "B"}]
    )
    assert "Example 1" in result
    assert "Example 2" in result
