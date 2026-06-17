"""RAG helpers for few-shot retrieval and exemplar ingestion — M3.

Bridges embeddings.embed_text() + store.retrieve_similar()/ingest_exemplar()
into functions consumed by the extraction pipeline.

All functions degrade gracefully when RAG is not configured (DATABASE_URL or
GEMINI_API_KEY absent) — they return empty / None instead of raising, so the
pipeline keeps working with no RAG config.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from services.api.models.verified_invoice import VerifiedInvoiceExtraction
from services.api.rag.exemplar_text import invoice_exemplar_text

log = logging.getLogger(__name__)


def _rag_configured() -> bool:
    """True when DATABASE_URL and GEMINI_API_KEY are both set."""
    url = os.environ.get("DATABASE_URL", "")
    key = os.environ.get("GEMINI_API_KEY", "")
    return bool(url and "host/dbname" not in url and key)


async def retrieve_invoice_exemplars(
    extraction: VerifiedInvoiceExtraction,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Return up to *k* similar past invoice exemplars as plain field-value dicts.

    Embeds the layout signal from *extraction* (vendor/address/line-items) and
    does a cosine-distance lookup in the pgvector store. Returns an empty list
    when RAG is not configured or the store has fewer than *k* rows.

    Never raises — failures are logged at DEBUG and swallowed.
    """
    if not _rag_configured():
        return []

    from services.api.rag.embeddings import embed_text
    from services.api.rag.store import get_engine, retrieve_similar

    try:
        query_text = invoice_exemplar_text(extraction)
        if not query_text.strip():
            return []
        embedding = await embed_text(query_text)
        engine = get_engine()
        rows = retrieve_similar(embedding, "invoice", k=k, engine=engine)
        return [row.extracted_fields for row in rows]
    except Exception:
        log.debug("RAG retrieval failed (non-fatal)", exc_info=True)
        return []


async def ingest_invoice_exemplar(
    extraction: VerifiedInvoiceExtraction,
    doc_name: str,
) -> None:
    """Store *extraction* as a future few-shot exemplar. Best-effort — never raises."""
    if not _rag_configured():
        return

    from services.api.rag.embeddings import embed_text
    from services.api.rag.store import get_engine, ingest_exemplar

    try:
        text = invoice_exemplar_text(extraction)
        if not text.strip():
            return
        embedding = await embed_text(text)
        engine = get_engine()
        ingest_exemplar(
            doc_type="invoice",
            source_doc_name=doc_name,
            embedding=embedding,
            extracted_fields=extraction.to_value_dict(),
            engine=engine,
        )
        log.debug("Ingested exemplar for %s", doc_name)
    except Exception:
        log.debug("RAG ingest failed (non-fatal)", exc_info=True)


def format_exemplars_for_prompt(exemplars: list[dict[str, Any]]) -> str:
    """Format retrieved exemplars into a few-shot block for the extraction instruction.

    Returns an empty string when *exemplars* is empty (caller appends as-is).
    """
    if not exemplars:
        return ""

    lines = ["REFERENCE EXAMPLES from similar past documents:\n"]
    for i, fields in enumerate(exemplars, start=1):
        vendor = fields.get("vendor_name") or ""
        header = f"--- Example {i}" + (f" ({vendor})" if vendor else "") + " ---"
        lines.append(header)
        for key, val in fields.items():
            if val is not None and key != "line_items":
                lines.append(f"  {key}: {val!r}")
        lines.append("")
    lines.append(
        "Use these examples as reference for field formats and layout conventions "
        "when extracting from the current document.\n"
    )
    return "\n".join(lines)
