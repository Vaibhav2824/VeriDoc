"""VLM client factory and public re-exports."""

from __future__ import annotations

import os

from services.api.clients.base import VLMClient, VLMError
from services.api.clients.gemini import GeminiClient

__all__ = ["GeminiClient", "VLMClient", "VLMError", "make_client"]


def make_client() -> VLMClient:
    """Return a VLMClient based on the first available API key.

    Priority: GROQ_API_KEY → GEMINI_API_KEY

    Raises:
        VLMError: if neither key is set.
    """
    if os.environ.get("GROQ_API_KEY"):
        from services.api.clients.groq_client import GroqClient

        return GroqClient()  # type: ignore[return-value]

    return GeminiClient()  # type: ignore[return-value]
