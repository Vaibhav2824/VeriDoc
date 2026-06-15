"""Tests for GeminiClient — all calls are mocked; no real API key required."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from services.api.clients.base import VLMError
from services.api.clients.gemini import GeminiClient

# ── fixtures ──────────────────────────────────────────────────────────────────


def _blank_page(width: int = 200, height: int = 300) -> Image.Image:
    return Image.new("RGB", (width, height), color=(240, 240, 240))


def _make_client(mock_raw_client: MagicMock) -> GeminiClient:
    """Construct a GeminiClient whose internal genai.Client is replaced by a mock."""
    with patch("services.api.clients.gemini.genai.Client", return_value=mock_raw_client):
        return GeminiClient(api_key="test-key-not-real")


def _mock_sdk_client(response_json: str) -> MagicMock:
    """Return a MagicMock genai client whose async generate_content returns response_json."""
    mock_response = MagicMock()
    mock_response.text = response_json

    mock_raw = MagicMock()
    mock_raw.aio.models.generate_content = AsyncMock(return_value=mock_response)
    return mock_raw


# ── happy-path tests ──────────────────────────────────────────────────────────


async def test_extract_returns_dict() -> None:
    payload = {"invoice_number": "INV-2024-001", "total_amount": 1500.0}
    mock_raw = _mock_sdk_client(json.dumps(payload))
    client = _make_client(mock_raw)

    result = await client.extract([_blank_page()], "Extract invoice fields.")

    assert isinstance(result, dict)
    assert result["invoice_number"] == "INV-2024-001"
    assert result["total_amount"] == 1500.0


async def test_extract_passes_all_pages_to_sdk() -> None:
    """Each page becomes one Part; prompt is the final Part — 3 pages → 4 parts."""
    mock_raw = _mock_sdk_client(json.dumps({"ok": True}))
    client = _make_client(mock_raw)
    pages = [_blank_page(), _blank_page(), _blank_page()]

    await client.extract(pages, "prompt")

    call_kwargs = mock_raw.aio.models.generate_content.call_args
    contents = call_kwargs.kwargs.get("contents") or call_kwargs.args[0]
    # [image_part, image_part, image_part, text_part]
    assert len(contents) == 4


async def test_extract_forwards_prompt_as_last_part() -> None:
    """The prompt text must appear in the final Part sent to the SDK."""
    from google.genai import types as gtypes

    mock_raw = _mock_sdk_client(json.dumps({}))
    client = _make_client(mock_raw)
    prompt = "Extract the invoice number."

    await client.extract([_blank_page()], prompt)

    call_kwargs = mock_raw.aio.models.generate_content.call_args
    contents = call_kwargs.kwargs.get("contents") or call_kwargs.args[0]
    last_part = contents[-1]
    assert isinstance(last_part, gtypes.Part)
    assert last_part.text == prompt


async def test_extract_requests_json_mime_type() -> None:
    mock_raw = _mock_sdk_client(json.dumps({}))
    client = _make_client(mock_raw)

    await client.extract([_blank_page()], "prompt")

    call_kwargs = mock_raw.aio.models.generate_content.call_args
    config = call_kwargs.kwargs.get("config")
    assert config is not None
    assert config.response_mime_type == "application/json"


async def test_extract_uses_configured_model() -> None:
    mock_raw = _mock_sdk_client(json.dumps({}))
    with patch("services.api.clients.gemini.genai.Client", return_value=mock_raw):
        client = GeminiClient(api_key="key", model="gemini-2.5-flash")

    await client.extract([_blank_page()], "prompt")

    call_kwargs = mock_raw.aio.models.generate_content.call_args
    model_arg = call_kwargs.kwargs.get("model") or call_kwargs.args[0]
    assert model_arg == "gemini-2.5-flash"


# ── error-handling tests ──────────────────────────────────────────────────────


async def test_non_json_response_raises_vlm_error() -> None:
    mock_raw = _mock_sdk_client("This is not JSON at all.")
    client = _make_client(mock_raw)

    with pytest.raises(VLMError, match="non-JSON"):
        await client.extract([_blank_page()], "prompt")


async def test_json_array_response_raises_vlm_error() -> None:
    mock_raw = _mock_sdk_client(json.dumps([1, 2, 3]))
    client = _make_client(mock_raw)

    with pytest.raises(VLMError, match="JSON object"):
        await client.extract([_blank_page()], "prompt")


async def test_empty_pages_raises_vlm_error() -> None:
    mock_raw = _mock_sdk_client(json.dumps({}))
    client = _make_client(mock_raw)

    with pytest.raises(VLMError, match="at least one page"):
        await client.extract([], "prompt")


async def test_api_failure_raises_vlm_error() -> None:
    mock_raw = MagicMock()
    mock_raw.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("quota exceeded")
    )
    client = _make_client(mock_raw)

    with pytest.raises(VLMError, match="API call failed"):
        await client.extract([_blank_page()], "prompt")


async def test_null_response_text_raises_vlm_error() -> None:
    mock_response = MagicMock()
    mock_response.text = None
    mock_raw = MagicMock()
    mock_raw.aio.models.generate_content = AsyncMock(return_value=mock_response)
    client = _make_client(mock_raw)

    with pytest.raises(VLMError):
        await client.extract([_blank_page()], "prompt")


def test_missing_api_key_raises_vlm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("services.api.clients.gemini.genai.Client"):
        with pytest.raises(VLMError, match="GEMINI_API_KEY"):
            GeminiClient(api_key=None)
