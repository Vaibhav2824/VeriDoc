"""Document extractor pipeline — M3.

extract_invoice() chains:
  1. Extractor  — VLM → InvoiceExtraction (plain values, Instructor-enforced schema)
  2. Verifier   — VLM → InvoiceVerificationResponse (confidence + source_location)
  3. Gate       — apply confidence threshold → VerifiedInvoiceExtraction
  4. RAG pass   — if any fields abstained and RAG is configured: retrieve similar
                  exemplars, re-run steps 1-3 with few-shot context in the prompt.
  5. Ingest     — if final result has no abstained fields, store as future exemplar.

extract_bank_statement() runs extractor only (verifier for bank statements is M3).

Every VLM call emits a Langfuse trace (no-op when LANGFUSE_SECRET_KEY absent).
"""

from __future__ import annotations

import time
from pathlib import Path

from services.api.clients.base import VLMClient, VLMError
from services.api.ingest import load_document
from services.api.models.bank_statement import BankStatementExtraction, mask_statement
from services.api.models.invoice import InvoiceExtraction
from services.api.models.verified_invoice import VerifiedInvoiceExtraction
from services.api.nodes.gate import apply_gate
from services.api.nodes.verifier import verify_invoice
from services.api.rag.retrieval import (
    format_exemplars_for_prompt,
    ingest_invoice_exemplar,
    retrieve_invoice_exemplars,
)
from services.api.tracing import client_model as _client_model
from services.api.tracing import trace as _trace

# ── Invoice extraction pipeline ───────────────────────────────────────────────


async def extract_invoice(
    path: str | Path,
    client: VLMClient,
    max_retries: int = 3,
    confidence_threshold: float | None = None,
) -> VerifiedInvoiceExtraction:
    """Extract + verify + gate an invoice document.

    Pipeline:
      1. Extractor: VLM → InvoiceExtraction (schema-valid, bounded retries)
      2. Verifier:  VLM → confidence + source_location per field
      3. Gate:      fields below threshold → status='abstained'

    Args:
        path: Path to PDF or image file.
        client: VLMClient implementation to use.
        max_retries: Max retries for the extractor VLM call.
        confidence_threshold: Gate threshold; defaults to CONFIDENCE_THRESHOLD env var.

    Returns:
        VerifiedInvoiceExtraction — all fields carry confidence + source_location.

    Raises:
        IngestError: File not found or unsupported format.
        VLMError: Non-recoverable API error.
    """
    doc_name = Path(path).name
    pages = load_document(path)
    model = _client_model(client)
    t0 = time.monotonic()

    try:
        # ── Step 1: Extractor ─────────────────────────────────────────────────
        extraction: InvoiceExtraction = await client.extract_structured(
            pages, InvoiceExtraction, max_retries
        )
        _trace(
            name="extract_invoice_extractor",
            doc_name=doc_name,
            model=model,
            latency_s=time.monotonic() - t0,
            success=True,
        )

        # ── Step 2: Verifier ──────────────────────────────────────────────────
        t1 = time.monotonic()
        verified = await verify_invoice(extraction, pages, client, max_retries=2)
        _trace(
            name="extract_invoice_verifier",
            doc_name=doc_name,
            model=model,
            latency_s=time.monotonic() - t1,
            success=True,
        )

        # ── Step 3: Gate ──────────────────────────────────────────────────────
        gated = apply_gate(verified, threshold=confidence_threshold)

        # ── Step 4: RAG re-pass (if abstained fields and RAG configured) ──────
        if gated.abstained_fields():
            exemplars = await retrieve_invoice_exemplars(gated)
            if exemplars:
                few_shot = format_exemplars_for_prompt(exemplars)
                t_rag = time.monotonic()
                rag_extraction: InvoiceExtraction = await client.extract_structured(
                    pages, InvoiceExtraction, max_retries, instruction=few_shot
                )
                _trace(
                    name="extract_invoice_rag_extractor",
                    doc_name=doc_name,
                    model=model,
                    latency_s=time.monotonic() - t_rag,
                    success=True,
                )
                t_rag2 = time.monotonic()
                rag_verified = await verify_invoice(rag_extraction, pages, client, max_retries=2)
                _trace(
                    name="extract_invoice_rag_verifier",
                    doc_name=doc_name,
                    model=model,
                    latency_s=time.monotonic() - t_rag2,
                    success=True,
                )
                gated = apply_gate(rag_verified, threshold=confidence_threshold)

        # ── Step 5: Ingest exemplar (best-effort, only when fully confident) ───
        if not gated.abstained_fields():
            await ingest_invoice_exemplar(gated, doc_name)

        return gated

    except VLMError as exc:
        _trace(
            name="extract_invoice",
            doc_name=doc_name,
            model=model,
            latency_s=time.monotonic() - t0,
            success=False,
            error=str(exc),
        )
        raise


# ── Bank statement extraction ─────────────────────────────────────────────────


async def extract_bank_statement(
    path: str | Path,
    client: VLMClient,
    max_retries: int = 3,
    mask_pii: bool = True,
) -> BankStatementExtraction:
    """Extract bank statement fields (extractor only; verifier added in M3).

    Args:
        path: Path to PDF or image file (may be multi-page).
        client: VLMClient implementation.
        max_retries: Max retries for the extraction VLM call.
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
        result = await client.extract_structured(pages, BankStatementExtraction, max_retries)
        _trace(
            name="extract_bank_statement",
            doc_name=doc_name,
            model=model,
            latency_s=time.monotonic() - t0,
            success=True,
            doc_type="bank_statement",
        )
        return mask_statement(result) if mask_pii else result
    except VLMError as exc:
        _trace(
            name="extract_bank_statement",
            doc_name=doc_name,
            model=model,
            latency_s=time.monotonic() - t0,
            success=False,
            error=str(exc),
            doc_type="bank_statement",
        )
        raise
