"""Text embeddings for pgvector few-shot exemplar retrieval — M3.

Always uses Gemini's embedding model directly via google-genai, regardless
of which VLMClient (Groq or Gemini) is doing extraction — Groq has no
embeddings endpoint, so this is independent of make_client().
"""

from __future__ import annotations

import os

from google import genai
from google.genai import types

from services.api.clients.base import VLMError

# text-embedding-004 returns 404 NOT_FOUND on the current API version/key;
# gemini-embedding-001 is what's actually available, truncated to
# EMBEDDING_DIM via Matryoshka representation (output_dimensionality) so the
# stored vectors stay small without changing the pgvector schema's width.
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise VLMError(
                "GEMINI_API_KEY is not set. Embeddings require Gemini even when "
                "extraction is configured to use Groq — Groq has no embeddings endpoint."
            )
        _client = genai.Client(api_key=api_key)
    return _client


async def embed_text(text: str) -> list[float]:
    """Embed *text* into an EMBEDDING_DIM-length vector.

    Raises:
        VLMError: GEMINI_API_KEY not set, or the API call fails.
    """
    client = _get_client()
    try:
        response = await client.aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
    except Exception as exc:
        raise VLMError(f"Embedding failed: {exc}") from exc

    if not response.embeddings or response.embeddings[0].values is None:
        raise VLMError("Embedding response contained no values.")
    return list(response.embeddings[0].values)
