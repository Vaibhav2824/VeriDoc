"""Pure helpers for building exemplar embedding text from extractions — M3 RAG.

No I/O — these functions only shape data for embeddings.embed_text().
"""

from __future__ import annotations

from services.api.models.invoice import InvoiceExtraction
from services.api.models.verified_invoice import VerifiedInvoiceExtraction


def invoice_exemplar_text(extraction: InvoiceExtraction | VerifiedInvoiceExtraction) -> str:
    """Build a short text summary of an invoice's layout signals.

    Used both to embed a newly-extracted invoice for storage as a future
    exemplar, and to embed a query when retrieving similar past exemplars.
    Deliberately omits volatile fields (amounts, dates, invoice numbers) and
    keeps only fields that correlate with *template/layout* similarity:
    vendor name, vendor address, and line-item descriptions.
    """
    if isinstance(extraction, VerifiedInvoiceExtraction):
        vendor_name = extraction.vendor_name.value
        vendor_address = extraction.vendor_address.value
        line_items = extraction.line_items
    else:
        vendor_name = extraction.vendor_name
        vendor_address = extraction.vendor_address
        line_items = extraction.line_items

    descriptions = [item.description for item in line_items if item.description]
    parts = [p for p in [vendor_name, vendor_address, *descriptions] if p]
    return "\n".join(parts)
