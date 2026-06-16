"""Tests for services.api.rag.embeddings (M3) — mocked google-genai client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import services.api.rag.embeddings as embeddings_module
from services.api.clients.base import VLMError
from services.api.rag.embeddings import embed_text


@pytest.fixture(autouse=True)
def _reset_client_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(embeddings_module, "_client", None)


def _mock_genai_client(values: list[float] | None) -> MagicMock:
    embedding = MagicMock()
    embedding.values = values
    response = MagicMock()
    response.embeddings = [embedding] if values is not None else []

    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(return_value=response)
    return client


async def test_embed_text_returns_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    client = _mock_genai_client([0.1, 0.2, 0.3])
    monkeypatch.setattr(embeddings_module.genai, "Client", lambda api_key: client)

    result = await embed_text("hello world")

    assert result == [0.1, 0.2, 0.3]
    call_kwargs = client.aio.models.embed_content.call_args.kwargs
    assert call_kwargs["model"] == embeddings_module.EMBEDDING_MODEL
    assert call_kwargs["contents"] == "hello world"
    assert call_kwargs["config"].output_dimensionality == embeddings_module.EMBEDDING_DIM


async def test_embed_text_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(VLMError, match="GEMINI_API_KEY"):
        await embed_text("hello")


async def test_embed_text_empty_response_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    client = _mock_genai_client(None)
    monkeypatch.setattr(embeddings_module.genai, "Client", lambda api_key: client)

    with pytest.raises(VLMError, match="no values"):
        await embed_text("hello")


async def test_embed_text_api_failure_wrapped_as_vlm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    client = MagicMock()
    client.aio.models.embed_content = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(embeddings_module.genai, "Client", lambda api_key: client)

    with pytest.raises(VLMError, match="Embedding failed"):
        await embed_text("hello")


async def test_client_constructed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    client = _mock_genai_client([0.1])
    call_count = {"n": 0}

    def fake_client(api_key: str) -> MagicMock:
        call_count["n"] += 1
        return client

    monkeypatch.setattr(embeddings_module.genai, "Client", fake_client)

    await embed_text("a")
    await embed_text("b")

    assert call_count["n"] == 1
