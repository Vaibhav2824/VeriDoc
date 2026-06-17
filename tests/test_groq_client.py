"""Tests for services.api.clients.groq_client (M3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.api.clients.base import VLMError
from services.api.clients.groq_client import GroqClient


def test_missing_api_key_raises_vlm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(VLMError, match="GROQ_API_KEY"):
        GroqClient()


def test_async_groq_constructed_with_retries_disabled() -> None:
    """The SDK's own retry layer honors Groq's Retry-After header, which for a
    daily-quota 429 can be many minutes per call. max_retries=0 makes a failed
    call fail in under a second instead - confirmed empirically (a single
    failing classification call dropped from 11+ minutes to 0.8s with this set).
    """
    with (
        patch("services.api.clients.groq_client.AsyncGroq") as mock_async_groq,
        patch("services.api.clients.groq_client.instructor.from_groq"),
    ):
        GroqClient(api_key="fake-key")

    mock_async_groq.assert_called_once_with(api_key="fake-key", max_retries=0)


def test_default_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "some-other-model")
    client = GroqClient(api_key="fake-key")
    assert client._model == "some-other-model"


def test_explicit_model_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "some-other-model")
    client = GroqClient(api_key="fake-key", model="explicit-model")
    assert client._model == "explicit-model"
