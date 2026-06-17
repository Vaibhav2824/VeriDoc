"""Tests for services.api.nodes.router (M3) — mocked VLMClient."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from services.api.models.router import DocTypeClassification
from services.api.nodes.router import classify_doc_type


def _mock_client(response: DocTypeClassification) -> AsyncMock:
    client = AsyncMock()
    client.extract_structured = AsyncMock(return_value=response)
    client._model = "mock-model"
    return client


def _page() -> Image.Image:
    return Image.new("RGB", (400, 600), color=(255, 255, 255))


# ── VLM path (no doc_path supplied → always uses VLM) ────────────────────────

async def test_classify_doc_type_invoice() -> None:
    client = _mock_client(DocTypeClassification(doc_type="invoice", confidence=0.95))

    result = await classify_doc_type([_page()], client)

    assert result.doc_type == "invoice"
    assert result.confidence == 0.95


async def test_classify_doc_type_bank_statement() -> None:
    client = _mock_client(DocTypeClassification(doc_type="bank_statement", confidence=0.9))

    result = await classify_doc_type([_page(), _page()], client)

    assert result.doc_type == "bank_statement"


async def test_classify_doc_type_only_sends_first_page() -> None:
    client = _mock_client(DocTypeClassification(doc_type="invoice", confidence=0.8))
    pages = [_page(), _page(), _page()]

    await classify_doc_type(pages, client)

    sent_pages = client.extract_structured.call_args.args[0]
    assert len(sent_pages) == 1
    assert sent_pages[0] is pages[0]


async def test_classify_doc_type_passes_max_retries() -> None:
    client = _mock_client(DocTypeClassification(doc_type="invoice", confidence=0.8))

    await classify_doc_type([_page()], client, max_retries=5)

    assert client.extract_structured.call_args.kwargs["max_retries"] == 5


# ── Artifact path ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_artifact_state() -> Generator[None, None, None]:
    """Reset module-level artifact cache so each test starts clean."""
    import services.api.nodes.router as r_mod
    orig = (r_mod._tfidf, r_mod._clf, r_mod._artifact_checked)
    yield
    r_mod._tfidf, r_mod._clf, r_mod._artifact_checked = orig


async def test_artifact_used_when_doc_path_provided() -> None:
    """When artifact loads and doc_path is given, VLM is never called."""
    expected = DocTypeClassification(doc_type="invoice", confidence=0.95)
    client = _mock_client(DocTypeClassification(doc_type="bank_statement", confidence=0.5))

    with (
        patch("services.api.nodes.router._load_artifact", return_value=True),
        patch("services.api.nodes.router._classify_with_artifact", return_value=expected),
    ):
        result = await classify_doc_type([_page()], client, doc_path="some/doc.pdf")

    assert result.doc_type == "invoice"
    assert result.confidence == 0.95
    client.extract_structured.assert_not_called()


async def test_vlm_fallback_when_artifact_returns_none() -> None:
    """If artifact classification yields None (empty text etc.), VLM is called."""
    vlm_response = DocTypeClassification(doc_type="bank_statement", confidence=0.9)
    client = _mock_client(vlm_response)

    with (
        patch("services.api.nodes.router._load_artifact", return_value=True),
        patch("services.api.nodes.router._classify_with_artifact", return_value=None),
    ):
        result = await classify_doc_type([_page()], client, doc_path="some/doc.pdf")

    assert result.doc_type == "bank_statement"
    client.extract_structured.assert_called_once()


async def test_vlm_used_when_no_doc_path() -> None:
    """Without doc_path the artifact path is skipped entirely."""
    vlm_response = DocTypeClassification(doc_type="invoice", confidence=0.8)
    client = _mock_client(vlm_response)
    mock_load = MagicMock(return_value=True)

    with patch("services.api.nodes.router._load_artifact", mock_load):
        result = await classify_doc_type([_page()], client)

    assert result.doc_type == "invoice"
    mock_load.assert_not_called()
    client.extract_structured.assert_called_once()


async def test_vlm_fallback_when_artifact_unavailable() -> None:
    """If artifacts not on disk, VLM is called without error."""
    vlm_response = DocTypeClassification(doc_type="bank_statement", confidence=0.99)
    client = _mock_client(vlm_response)

    with patch("services.api.nodes.router._load_artifact", return_value=False):
        result = await classify_doc_type([_page()], client, doc_path="some/doc.pdf")

    assert result.doc_type == "bank_statement"
    client.extract_structured.assert_called_once()
