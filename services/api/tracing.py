"""Shared Langfuse tracing helper — no-op when LANGFUSE_SECRET_KEY is absent.

Used by both the standalone extractor pipeline (services/api/extractor.py)
and the LangGraph orchestration (services/api/graph.py) so every VLM call
emits a trace regardless of which entry point runs it.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.api.clients.base import VLMClient

_langfuse: Any = None


def client_model(client: VLMClient) -> str:
    return getattr(client, "_model", "unknown")


def get_langfuse() -> Any:
    """Return a Langfuse client if credentials are configured, else None."""
    global _langfuse
    if _langfuse is not None:
        return _langfuse
    secret = os.environ.get("LANGFUSE_SECRET_KEY", "")
    public = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    if not secret or not public:
        return None
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            secret_key=secret,
            public_key=public,
            host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
    except Exception:
        pass
    return _langfuse


def trace(
    *,
    name: str,
    doc_name: str,
    model: str,
    latency_s: float,
    success: bool,
    error: str | None = None,
    doc_type: str = "invoice",
) -> None:
    lf = get_langfuse()
    if lf is None:
        return
    try:
        t = lf.trace(
            name=name,
            metadata={
                "doc_name": doc_name,
                "doc_type": doc_type,
                "model": model,
                "latency_s": round(latency_s, 3),
                "success": success,
                "error": error,
            },
        )
        t.generation(name="vlm_call", model=model, metadata={"latency_s": round(latency_s, 3)})
        lf.flush()
    except Exception:
        pass
