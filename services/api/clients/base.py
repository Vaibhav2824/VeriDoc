"""VLMClient protocol and shared error type for all VLM adapters."""

from __future__ import annotations

from typing import Any, Protocol

from PIL import Image


class VLMError(RuntimeError):
    """Raised when VLM extraction fails: API error, quota, invalid JSON, etc."""


class VLMClient(Protocol):
    """Structural interface that every VLM adapter must satisfy.

    Both GeminiClient and OllamaClient implement this without inheritance.
    """

    async def extract(
        self,
        pages: list[Image.Image],
        prompt: str,
    ) -> dict[str, Any]:
        """Call the underlying VLM and return a parsed JSON dict.

        Args:
            pages: Per-page PIL Images produced by ingest.load_document().
            prompt: Extraction prompt describing what fields to return.

        Returns:
            Parsed JSON object as a plain Python dict.

        Raises:
            VLMError: API failure, quota exceeded, non-JSON response, etc.
        """
        ...
