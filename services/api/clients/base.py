"""VLMClient protocol and shared error type for all VLM adapters."""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

from PIL import Image
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class VLMError(RuntimeError):
    """Raised when VLM extraction fails: API error, quota, invalid JSON, etc."""


class VLMClient(Protocol):
    """Structural interface that every VLM adapter must satisfy.

    Both GeminiClient and GroqClient implement this without inheritance.
    """

    async def extract(
        self,
        pages: list[Image.Image],
        prompt: str,
    ) -> dict[str, Any]:
        """Call the underlying VLM and return a parsed JSON dict (M0 raw path).

        Args:
            pages: Per-page PIL Images produced by ingest.load_document().
            prompt: Extraction prompt describing what fields to return.

        Returns:
            Parsed JSON object as a plain Python dict.

        Raises:
            VLMError: API failure, quota exceeded, non-JSON response, etc.
        """
        ...

    async def extract_structured(
        self,
        pages: list[Image.Image],
        response_model: type[T],
        max_retries: int = 3,
        instruction: str | None = None,
    ) -> T:
        """Extract and validate against *response_model* (M1 structured path).

        Uses Instructor (where available) or Pydantic-validate-with-retry to
        guarantee the response conforms to *response_model*.  On final failure
        the implementation raises VLMError; callers that need an abstain-all
        result should catch it and return response_model().

        Args:
            pages: Per-page PIL Images.
            response_model: Pydantic BaseModel subclass describing the schema.
            max_retries: Maximum extraction attempts before raising VLMError.
            instruction: Optional custom instruction text prepended to the prompt.
                If None, a generic extraction instruction is used.

        Returns:
            A validated instance of *response_model*.

        Raises:
            VLMError: All retries exhausted or non-recoverable API error.
        """
        ...
