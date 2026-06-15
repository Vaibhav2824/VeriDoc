"""Naive invoice extractor — M0 (prompt-only, no schema enforcement).

extract_invoice() sends document pages to a VLMClient with a structured
prompt and returns the raw parsed dict.  Pydantic/Instructor validation
and the verifier layer are added in M1/M2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.api.clients.base import VLMClient
from services.api.ingest import load_document

# Prompt covers every field in PRD §8.1 (Invoice schema).
# response_mime_type="application/json" in GeminiClient already constrains
# the model to emit JSON; this prompt defines the expected shape.
NAIVE_INVOICE_PROMPT = """\
You are a precise document-extraction assistant.

Examine every page of the supplied invoice document carefully, then return a
single JSON object with the fields listed below.

Rules:
- Use null for any field that is absent or cannot be read with confidence.
- Amounts must be plain numbers (no currency symbols, no thousands commas).
- Dates must be ISO 8601 strings: YYYY-MM-DD.
- Do not add fields that are not in the schema.
- Output ONLY the JSON object — no markdown fences, no prose.

Schema:
{
  "invoice_number": "<string> | null",
  "invoice_date": "<YYYY-MM-DD> | null",
  "due_date": "<YYYY-MM-DD> | null",
  "vendor_name": "<string> | null",
  "vendor_gstin": "<string> | null",
  "vendor_address": "<string> | null",
  "buyer_name": "<string> | null",
  "buyer_gstin": "<string> | null",
  "currency": "<ISO 4217 code, e.g. INR or USD> | null",
  "subtotal": "<number> | null",
  "tax": {
    "cgst": "<number> | null",
    "sgst": "<number> | null",
    "igst": "<number> | null",
    "total_tax": "<number> | null"
  },
  "total_amount": "<number> | null",
  "line_items": [
    {
      "description": "<string>",
      "hsn_sac": "<string> | null",
      "quantity": "<number> | null",
      "unit_price": "<number> | null",
      "line_total": "<number> | null"
    }
  ]
}
"""


async def extract_invoice(
    path: str | Path,
    client: VLMClient,
) -> dict[str, Any]:
    """Extract invoice fields from *path* using a naive VLM prompt (M0).

    Args:
        path: Path to a PDF or image file (str or Path).
        client: Any VLMClient implementation (GeminiClient, OllamaClient, …).

    Returns:
        Raw parsed dict from the VLM.  Fields not found in the document are
        returned as null (None in Python).  No schema validation at M0.

    Raises:
        IngestError: File not found or unsupported format.
        VLMError: API failure or non-JSON response from the VLM.
    """
    pages = load_document(path)
    return await client.extract(pages, NAIVE_INVOICE_PROMPT)
