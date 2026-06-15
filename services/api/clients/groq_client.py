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
from typing import Any

from groq import AsyncGroq
from PIL import Image

from services.api.clients.base import VLMError

_FALLBACK_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _pil_to_base64(img: Image.Image) -> str:
    """Encode a PIL Image as a base64 PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


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
        self._client = AsyncGroq(api_key=key)
        self._model = model or os.environ.get("GROQ_MODEL", _FALLBACK_MODEL)

    async def extract(
        self,
        pages: list[Image.Image],
        prompt: str,
    ) -> dict[str, Any]:
        """Send *pages* + *prompt* to Groq and return a parsed JSON dict.

        Each page is sent as a base64 PNG image_url block; the prompt follows
        as a text block. Uses JSON mode so the response is always parseable.

        Raises:
            VLMError: API failure or non-JSON response.
        """
        if not pages:
            raise VLMError("extract() requires at least one page image.")

        content: list[dict[str, Any]] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{_pil_to_base64(p)}"},
            }
            for p in pages
        ]
        content.append({"type": "text", "text": prompt})

        try:
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
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
