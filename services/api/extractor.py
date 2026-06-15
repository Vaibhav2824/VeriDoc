"""Structured document extractor — M1.

extract_invoice() and extract_bank_statement() use the VLMClient's
extract_structured() method (Instructor-backed for Groq, Pydantic-validate-
with-retry for Gemini) to guarantee schema-valid output.

Every call emits a Langfuse trace with latency and model metadata.
Langfuse is optional: if LANGFUSE_SECRET_KEY is unset, tracing is a no-op.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from services.api.clients.base import VLMClient, VLMError
from services.api.ingest import load_document
from services.api.models.bank_statement import BankStatementExtraction, mask_statement
from services.api.models.invoice import InvoiceExtraction

# ── Langfuse setup (no-op if keys absent) ────────────────────────────────────

_langfuse: Any = None


def _get_langfuse() -> Any:
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


def _trace(
    *,
    name: str,
    doc_name: str,
    model: str,
    latency_s: float,
    success: bool,
    error: str | None = None,
    doc_type: str = "invoice",
) -> None:
    """Emit one Langfuse trace for a document extraction call."""
    lf = _get_langfuse()
    if lf is None:
        return
    try:
        trace = lf.trace(
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
        trace.generation(
            name="vlm_call",
            model=model,
            metadata={"latency_s": round(latency_s, 3)},
        )
        lf.flush()
    except Exception:
        pass  # tracing must never break extraction


def _client_model(client: VLMClient) -> str:
    """Extract the model identifier from a client for tracing."""
    return getattr(client, "_model", "unknown")


# ── Invoice extraction ────────────────────────────────────────────────────────


async def extract_invoice(
    path: str | Path,
    client: VLMClient,
    max_retries: int = 3,
) -> InvoiceExtraction:
    """Extract invoice fields from *path* and return a validated InvoiceExtraction.

    Uses client.extract_structured() which enforces the Pydantic schema and
    retries up to *max_retries* times on validation failure.  On final failure
    the function abstains: returns an InvoiceExtraction with all fields None.

    Args:
        path: Path to a PDF or image file.
        client: Any VLMClient implementation.
        max_retries: Max schema-validation retries before abstaining.

    Returns:
        InvoiceExtraction (all fields None if all retries failed).

    Raises:
        IngestError: File not found or unsupported format.
        VLMError: Non-recoverable API error (quota, auth, network).
    """
    doc_name = Path(path).name
    pages = load_document(path)
    model = _client_model(client)
    t0 = time.monotonic()

    try:
        result = await client.extract_structured(pages, InvoiceExtraction, max_retries)
        latency = time.monotonic() - t0
        _trace(
            name="extract_invoice",
            doc_name=doc_name,
            model=model,
            latency_s=latency,
            success=True,
            doc_type="invoice",
        )
        return result
    except VLMError as exc:
        latency = time.monotonic() - t0
        _trace(
            name="extract_invoice",
            doc_name=doc_name,
            model=model,
            latency_s=latency,
            success=False,
            error=str(exc),
            doc_type="invoice",
        )
        raise


# ── Bank statement extraction ─────────────────────────────────────────────────


async def extract_bank_statement(
    path: str | Path,
    client: VLMClient,
    max_retries: int = 3,
    mask_pii: bool = True,
) -> BankStatementExtraction:
    """Extract bank statement fields and return a validated BankStatementExtraction.

    Account numbers are masked by default (mask_pii=True) as required by
    the PII guardrail — always keep this True unless you are in a secure
    persistence layer that handles masking separately.

    Args:
        path: Path to a PDF or image file (may be multi-page).
        client: Any VLMClient implementation.
        max_retries: Max schema-validation retries.
        mask_pii: If True (default), mask account_number before returning.

    Returns:
        BankStatementExtraction (account_number masked if mask_pii=True).

    Raises:
        IngestError: File not found or unsupported format.
        VLMError: Non-recoverable API error.
    """
    doc_name = Path(path).name
    pages = load_document(path)
    model = _client_model(client)
    t0 = time.monotonic()

    try:
        result = await client.extract_structured(
            pages, BankStatementExtraction, max_retries
        )
        latency = time.monotonic() - t0
        _trace(
            name="extract_bank_statement",
            doc_name=doc_name,
            model=model,
            latency_s=latency,
            success=True,
            doc_type="bank_statement",
        )
        return mask_statement(result) if mask_pii else result
    except VLMError as exc:
        latency = time.monotonic() - t0
        _trace(
            name="extract_bank_statement",
            doc_name=doc_name,
            model=model,
            latency_s=latency,
            success=False,
            error=str(exc),
            doc_type="bank_statement",
        )
        raise
