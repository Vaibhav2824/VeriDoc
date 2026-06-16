"""Tests for eval.run's extraction cache (M3) — fingerprinting, load/save, run_eval reuse."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pypdfium2 as pdfium
import pytest

import eval.run as run_module
from eval.run import compute_fingerprint, load_cache, run_eval, save_cache
from services.api.models.fields import ExtractionField, FieldVerification, SourceLocation
from services.api.models.invoice import InvoiceExtraction
from services.api.models.verified_invoice import (
    InvoiceVerificationResponse,
    VerifiedInvoiceExtraction,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_pdf(tmp_path: Path, name: str = "invoice.pdf") -> Path:
    doc = pdfium.PdfDocument.new()
    doc.new_page(width=595, height=842)
    out = tmp_path / name
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


def _full_verified_invoice() -> VerifiedInvoiceExtraction:
    def ef(value: object) -> ExtractionField[object]:
        return ExtractionField(
            value=value,
            confidence=0.95,
            source_location=SourceLocation(page=0, bbox=[0.1, 0.1, 0.5, 0.2]),
        )

    return VerifiedInvoiceExtraction(
        invoice_number=ef("INV-001"),
        invoice_date=ef(None),
        due_date=ef(None),
        vendor_name=ef("Acme"),
        vendor_gstin=ef(None),
        vendor_address=ef(None),
        buyer_name=ef(None),
        buyer_gstin=ef(None),
        currency=ef(None),
        subtotal=ef(None),
        total_amount=ef(1180.0),
        tax=ef(None),
        line_items=[],
    )


def _mock_client(model: str = "mock-model", *side_effect: object) -> AsyncMock:
    client = AsyncMock()
    client.extract_structured = AsyncMock(side_effect=list(side_effect))
    client._model = model
    return client


# ── compute_fingerprint ─────────────────────────────────────────────────────


def test_fingerprint_stable_for_same_client() -> None:
    client = _mock_client("model-a")
    assert compute_fingerprint(client) == compute_fingerprint(client)


def test_fingerprint_differs_by_model() -> None:
    a = compute_fingerprint(_mock_client("model-a"))
    b = compute_fingerprint(_mock_client("model-b"))
    assert a != b


# ── load_cache / save_cache ──────────────────────────────────────────────────


def test_load_cache_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_cache(tmp_path / "nope.json") == {}


def test_load_cache_invalid_json_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_cache(path) == {}


def test_save_then_load_cache_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "extractions.json"
    data = {"doc.pdf": {"fingerprint": "abc", "result": {"x": 1}}}

    save_cache(data, path)

    assert load_cache(path) == data


# ── run_eval cache behavior ──────────────────────────────────────────────────


async def test_run_eval_cache_miss_calls_vlm_and_populates_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(run_module, "_CACHE_PATH", cache_path)

    pdf = _make_pdf(tmp_path)
    client = _mock_client("mock-model", _full_invoice(), _full_verif_response())
    pairs = [(pdf, {"invoice_number": "INV-001"})]

    doc_results, extractions, errors = await run_eval(client, pairs)

    assert not errors
    assert len(doc_results) == 1
    assert client.extract_structured.await_count == 2  # extractor + verifier

    cache = load_cache(cache_path)
    assert pdf.name in cache
    assert cache[pdf.name]["fingerprint"] == compute_fingerprint(client)


async def test_run_eval_cache_hit_skips_vlm_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(run_module, "_CACHE_PATH", cache_path)

    pdf = _make_pdf(tmp_path)
    client = _mock_client("mock-model")
    fingerprint = compute_fingerprint(client)

    # Pre-populate the cache as if a prior run already extracted this doc.
    cached_result = _full_verified_invoice()
    save_cache(
        {pdf.name: {"fingerprint": fingerprint, "result": cached_result.model_dump()}}, cache_path
    )

    pairs = [(pdf, {"invoice_number": "INV-001"})]
    doc_results, extractions, errors = await run_eval(client, pairs)

    assert not errors
    assert len(doc_results) == 1
    client.extract_structured.assert_not_awaited()


async def test_run_eval_cache_miss_on_fingerprint_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale cache entry (wrong fingerprint, e.g. different model) is ignored."""
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(run_module, "_CACHE_PATH", cache_path)

    pdf = _make_pdf(tmp_path)
    save_cache({pdf.name: {"fingerprint": "stale-fingerprint", "result": {}}}, cache_path)

    client = _mock_client("mock-model", _full_invoice(), _full_verif_response())
    pairs = [(pdf, {"invoice_number": "INV-001"})]

    doc_results, extractions, errors = await run_eval(client, pairs)

    assert not errors
    assert client.extract_structured.await_count == 2


async def test_run_eval_use_cache_false_ignores_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(run_module, "_CACHE_PATH", cache_path)

    pdf = _make_pdf(tmp_path)
    client = _mock_client("mock-model", _full_invoice(), _full_verif_response())
    pairs = [(pdf, {"invoice_number": "INV-001"})]

    await run_eval(client, pairs, use_cache=False)

    assert client.extract_structured.await_count == 2
    assert not cache_path.exists()
