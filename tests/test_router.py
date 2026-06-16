"""Tests for services.api.nodes.router (M3) — mocked VLMClient."""

from __future__ import annotations

from unittest.mock import AsyncMock

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
