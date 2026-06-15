"""GeminiClient — Gemini Flash VLM adapter.

Default VLM for VeriDoc (free tier, dev + prod).
Wraps google-genai SDK; requests JSON output via response_mime_type so
the raw response is always parseable without schema enforcement (M0).

M1 structured extraction: uses Pydantic post-validation with bounded retry
(Gemini-native Instructor async integration is deferred to a later milestone).
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
from typing import Any, TypeVar

from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel, ValidationError

from services.api.clients.base import VLMError

T = TypeVar("T", bound=BaseModel)

_FALLBACK_MODEL = "gemini-2.0-flash-lite"
# matches e.g. 'retryDelay': '9s' or "retryDelay": "9.3s"
_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"](\d+(?:\.\d+)?)s")


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
        model: str | None = None,
    ) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise VLMError(
                "GEMINI_API_KEY is not set. "
                "Copy .env.example → .env and add your key."
            )
        self._client = genai.Client(api_key=key)
        # GEMINI_MODEL env var allows switching models without code change
        # (e.g. gemini-1.5-flash if 2.0-flash quota is exhausted)
        self._model = model or os.environ.get("GEMINI_MODEL", _FALLBACK_MODEL)

    async def extract(
        self,
        pages: list[Image.Image],
        prompt: str,
    ) -> dict[str, Any]:
        """Send *pages* + *prompt* to Gemini and return a parsed JSON dict.

        Retries on 429 RESOURCE_EXHAUSTED using the server-supplied retryDelay.
        MAX_RETRIES env var controls the retry budget (default 3).

        Raises:
            VLMError: unrecoverable API failure or non-JSON response.
        """
        if not pages:
            raise VLMError("extract() requires at least one page image.")

        max_retries = int(os.environ.get("MAX_RETRIES", "3"))
        parts: list[types.Part] = [_pil_to_part(p) for p in pages]
        parts.append(types.Part.from_text(text=prompt))

        for attempt in range(max_retries + 1):
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
                exc_str = str(exc)
                is_rate_limited = "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str
                is_server_busy = "503" in exc_str or "UNAVAILABLE" in exc_str
                # Daily quota exhausted — retrying is pointless until midnight.
                is_daily_quota = "PerDay" in exc_str and is_rate_limited
                # Permanent zero quota — this project has no access to this model.
                is_zero_quota = "limit: 0" in exc_str
                if is_zero_quota or is_daily_quota:
                    raise VLMError(
                        f"Model '{self._model}' quota exhausted for today on this key. "
                        "Try GEMINI_MODEL=gemini-2.0-flash-lite or wait until tomorrow."
                    ) from exc
                if (is_rate_limited or is_server_busy) and attempt < max_retries:
                    # 503: server overload — shorter default wait; no retryDelay hint
                    delay = 20.0 if is_server_busy else 65.0
                    m = _RETRY_DELAY_RE.search(exc_str)
                    if m:
                        delay = float(m.group(1)) + 2.0
                    reason = "server busy" if is_server_busy else "rate-limited"
                    print(
                        f"\n    [retry {attempt + 1}/{max_retries}] "
                        f"{reason} — sleeping {delay:.0f}s…",
                        end="",
                        flush=True,
                    )
                    await asyncio.sleep(delay)
                    continue
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

        raise VLMError(f"Gemini API call failed after {max_retries} retries")

    async def extract_structured(
        self,
        pages: list[Image.Image],
        response_model: type[T],
        max_retries: int = 3,
    ) -> T:
        """Pydantic-validate-with-retry structured path for Gemini.

        Calls extract() then validates the result against *response_model*.
        On ValidationError, injects the error into the next prompt attempt.
        Raises VLMError if all retries are exhausted.
        """
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        base_prompt = (
            "Extract the requested fields from all pages of this document.\n"
            "Return a single JSON object matching this schema exactly:\n"
            f"{schema_json}\n\n"
            "Rules:\n"
            "- Use null for any field absent or unreadable.\n"
            "- Amounts: plain numbers only (no currency symbols, no commas).\n"
            "- Dates: ISO 8601 strings (YYYY-MM-DD).\n"
            "- Output ONLY the JSON object, no markdown fences."
        )
        prompt = base_prompt

        for attempt in range(max_retries):
            raw = await self.extract(pages, prompt)
            try:
                return response_model.model_validate(raw)
            except ValidationError as exc:
                if attempt < max_retries - 1:
                    prompt = (
                        f"{base_prompt}\n\n"
                        f"Previous attempt failed schema validation:\n{exc}\n"
                        "Fix the errors and return a valid JSON object."
                    )
                else:
                    raise VLMError(
                        f"Gemini structured extraction failed after {max_retries} retries: {exc}"
                    ) from exc

        raise VLMError(f"Gemini structured extraction failed after {max_retries} retries")
