"""GeminiClient — Gemini Flash VLM adapter.

Default VLM for VeriDoc (free tier, dev + prod).
Wraps google-genai SDK; requests JSON output via response_mime_type so
the raw response is always parseable without schema enforcement (M0).
Schema enforcement via Instructor/Pydantic is added in M1.
"""

from __future__ import annotations

import io
import json
import os
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

from services.api.clients.base import VLMError

_DEFAULT_MODEL = "gemini-2.0-flash"


def _pil_to_part(img: Image.Image) -> types.Part:
    """Encode a PIL Image as a PNG-byte Part for the genai SDK."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")


class GeminiClient:
    """Gemini Flash VLM adapter implementing VLMClient."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise VLMError(
                "GEMINI_API_KEY is not set. "
                "Copy .env.example → .env and add your key."
            )
        self._client = genai.Client(api_key=key)
        self._model = model

    async def extract(
        self,
        pages: list[Image.Image],
        prompt: str,
    ) -> dict[str, Any]:
        """Send *pages* + *prompt* to Gemini and return a parsed JSON dict.

        Uses response_mime_type="application/json" so Gemini is constrained
        to emit a valid JSON object (no markdown fences, no prose).

        Raises:
            VLMError: API failure, quota exceeded, or non-JSON response.
        """
        if not pages:
            raise VLMError("extract() requires at least one page image.")

        parts: list[types.Part] = [_pil_to_part(p) for p in pages]
        parts.append(types.Part.from_text(text=prompt))

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=parts,  # type: ignore[arg-type]  # list[Part] ⊂ SDK union; stubs use invariant list
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
        except VLMError:
            raise
        except Exception as exc:
            raise VLMError(f"Gemini API call failed: {exc}") from exc

        raw = response.text or ""
        try:
            result: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VLMError(
                f"Gemini returned non-JSON response: {raw[:300]!r}"
            ) from exc

        if not isinstance(result, dict):
            raise VLMError(
                f"Expected a JSON object from Gemini, got {type(result).__name__}."
            )

        return result
