"""Tests for eval.router_eval (M3) — mocked VLMClient, no live calls."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pypdfium2 as pdfium
import pytest

import eval.router_eval as router_eval_module
from eval.router_eval import (
    compute_fingerprint,
    ground_truth_doc_type,
    load_cache,
    run_router_eval,
    save_cache,
)
from services.api.models.router import DocTypeClassification


def _make_pdf(tmp_path: Path, name: str) -> Path:
    doc = pdfium.PdfDocument.new()
    doc.new_page(width=595, height=842)
    out = tmp_path / name
    doc.save(str(out))
    doc.close()
    return out


def _mock_client(model: str = "mock-model", *side_effect: object) -> AsyncMock:
    client = AsyncMock()
    client.extract_structured = AsyncMock(side_effect=list(side_effect))
    client._model = model
    return client


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_eval_module, "_CACHE_PATH", tmp_path / "router_cache.json")


# ── ground_truth_doc_type ──────────────────────────────────────────────────────


def test_ground_truth_defaults_to_invoice() -> None:
    assert ground_truth_doc_type({"_meta": {"doc_file": "x.pdf"}}) == "invoice"
    assert ground_truth_doc_type({}) == "invoice"


def test_ground_truth_reads_tagged_bank_statement() -> None:
    label = {"_meta": {"doc_type": "bank_statement"}}
    assert ground_truth_doc_type(label) == "bank_statement"


# ── fingerprint / cache plumbing ────────────────────────────────────────────────


def test_fingerprint_differs_by_model() -> None:
    a = compute_fingerprint(_mock_client("model-a"))
    b = compute_fingerprint(_mock_client("model-b"))
    assert a != b


def test_load_cache_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_cache(tmp_path / "nope.json") == {}


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    data = {"doc.pdf": {"fingerprint": "x", "doc_type": "invoice", "confidence": 0.9}}
    save_cache(data, path)
    assert load_cache(path) == data


# ── run_router_eval ──────────────────────────────────────────────────────────


async def test_correct_invoice_classification(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, "invoice.pdf")
    client = _mock_client("mock-model", DocTypeClassification(doc_type="invoice", confidence=0.95))
    pairs = [(pdf, {"_meta": {"doc_file": "invoice.pdf"}})]

    results, errors = await run_router_eval(client, pairs)

    assert not errors
    assert results[0]["true_type"] == "invoice"
    assert results[0]["predicted_type"] == "invoice"
    assert results[0]["correct"] is True


async def test_misclassified_bank_statement(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, "statement.pdf")
    client = _mock_client("mock-model", DocTypeClassification(doc_type="invoice", confidence=0.6))
    pairs = [(pdf, {"_meta": {"doc_file": "statement.pdf", "doc_type": "bank_statement"}})]

    results, errors = await run_router_eval(client, pairs)

    assert not errors
    assert results[0]["true_type"] == "bank_statement"
    assert results[0]["predicted_type"] == "invoice"
    assert results[0]["correct"] is False


async def test_cache_hit_skips_call(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, "invoice.pdf")
    client = _mock_client("mock-model")
    fingerprint = compute_fingerprint(client)
    save_cache(
        {pdf.name: {"fingerprint": fingerprint, "doc_type": "invoice", "confidence": 0.9}},
        router_eval_module._CACHE_PATH,
    )
    pairs = [(pdf, {"_meta": {"doc_file": "invoice.pdf"}})]

    results, errors = await run_router_eval(client, pairs)

    assert not errors
    assert results[0]["correct"] is True
    client.extract_structured.assert_not_awaited()


async def test_cache_saved_immediately_after_each_success_not_batched(tmp_path: Path) -> None:
    """Regression: a long run is mostly failures under quota exhaustion, so a
    save gated on "n_calls % N" (counting every attempt, success or fail) can
    skip every multiple of N and never persist a success if the run is later
    interrupted before its own final save_cache() call at the end.
    """
    pdf1 = _make_pdf(tmp_path, "doc1.pdf")
    pdf2 = _make_pdf(tmp_path, "doc2.pdf")
    client = _mock_client(
        "mock-model",
        DocTypeClassification(doc_type="invoice", confidence=0.9),
        RuntimeError("simulated crash"),
    )
    pairs = [
        (pdf1, {"_meta": {"doc_file": "doc1.pdf"}}),
        (pdf2, {"_meta": {"doc_file": "doc2.pdf"}}),
    ]

    with pytest.raises(RuntimeError, match="simulated crash"):
        await run_router_eval(client, pairs)

    on_disk = load_cache(router_eval_module._CACHE_PATH)
    assert "doc1.pdf" in on_disk


async def test_use_cache_false_ignores_cache(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, "invoice.pdf")
    client = _mock_client("mock-model", DocTypeClassification(doc_type="invoice", confidence=0.9))
    fingerprint = compute_fingerprint(client)
    save_cache(
        {pdf.name: {"fingerprint": fingerprint, "doc_type": "bank_statement", "confidence": 0.9}},
        router_eval_module._CACHE_PATH,
    )
    pairs = [(pdf, {"_meta": {"doc_file": "invoice.pdf"}})]

    results, errors = await run_router_eval(client, pairs, use_cache=False)

    assert not errors
    client.extract_structured.assert_awaited_once()
    assert results[0]["predicted_type"] == "invoice"  # fresh call, not the stale cached value
