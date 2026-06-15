"""GroqClient — Groq inference VLM adapter.

High-throughput alternative to Gemini; generous free tier (14k+ req/day).
Uses Groq's OpenAI-compatible chat completions API with vision support.
Default model: meta-llama/llama-4-scout-17b-16e-instruct (vision, 128k ctx).
"""

from __future__ import annotations

import base64
import io
import json
import os
from typing import Any, TypeVar

import instructor
from groq import AsyncGroq
from PIL import Image
from pydantic import BaseModel

from services.api.clients.base import VLMError

T = TypeVar("T", bound=BaseModel)

_FALLBACK_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _pil_to_base64(img: Image.Image) -> str:
    """Encode a PIL Image as a base64 PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _image_content_blocks(pages: list[Image.Image]) -> list[dict[str, Any]]:
    return [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_pil_to_base64(p)}"}}
        for p in pages
    ]


class GroqClient:
    """Groq vision model adapter implementing VLMClient."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        key = api_key or os.environ.get("GROQ_API_KEY")
        if not key:
            raise VLMError(
                "GROQ_API_KEY is not set. "
                "Get a free key at console.groq.com and add it to .env."
            )
        self._async_groq = AsyncGroq(api_key=key)
        self._instructor = instructor.from_groq(self._async_groq, mode=instructor.Mode.JSON)
        self._model = model or os.environ.get("GROQ_MODEL", _FALLBACK_MODEL)

    async def extract(
        self,
        pages: list[Image.Image],
        prompt: str,
    ) -> dict[str, Any]:
        """Raw extraction path — returns parsed JSON dict (M0 compat)."""
        if not pages:
            raise VLMError("extract() requires at least one page image.")

        content: list[dict[str, Any]] = _image_content_blocks(pages)
        content.append({"type": "text", "text": prompt})

        try:
            response = await self._async_groq.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                messages=[{"role": "user", "content": content}],
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
        except VLMError:
            raise
        except Exception as exc:
            raise VLMError(f"Groq API call failed: {exc}") from exc

        raw = (response.choices[0].message.content or "").strip()
        try:
            result: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VLMError(f"Groq returned non-JSON response: {raw[:300]!r}") from exc

        if not isinstance(result, dict):
            raise VLMError(
                f"Expected a JSON object from Groq, got {type(result).__name__}."
            )

        return result

    async def extract_structured(
        self,
        pages: list[Image.Image],
        response_model: type[T],
        max_retries: int = 3,
    ) -> T:
        """Instructor-backed structured extraction with automatic schema retries."""
        if not pages:
            raise VLMError("extract_structured() requires at least one page image.")

        content: list[dict[str, Any]] = _image_content_blocks(pages)
        content.append({
            "type": "text",
            "text": (
                "Extract the requested fields from all pages of this document. "
                "Use null for any field that is absent or cannot be read. "
                "Amounts must be plain numbers (no currency symbols or commas). "
                "Dates must be ISO 8601 strings: YYYY-MM-DD."
            ),
        })

        try:
            result: T = await self._instructor.chat.completions.create(  # type: ignore[call-overload,misc]
                model=self._model,
                response_model=response_model,
                messages=[{"role": "user", "content": content}],  # type: ignore[list-item,misc]
                max_retries=max_retries,
                max_tokens=4096,
            )
        except VLMError:
            raise
        except Exception as exc:
            raise VLMError(
                f"Groq structured extraction failed after {max_retries} retries: {exc}"
            ) from exc

        return result
