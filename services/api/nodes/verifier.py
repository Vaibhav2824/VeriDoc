"""Verifier node — M2.

Second VLM pass: given an invoice's extracted values and the original page images,
ask the model to confirm each value, assign confidence [0,1], and identify the
source location (page + bbox) where it appears.

The verifier is the "trust layer" core: it separates extraction confidence from
extraction itself so the two can be measured and improved independently.
"""

from __future__ import annotations

import json

from PIL import Image

from services.api.clients.base import VLMClient
from services.api.models.fields import ExtractionField
from services.api.models.invoice import InvoiceExtraction
from services.api.models.verified_invoice import (
    InvoiceVerificationResponse,
    VerifiedInvoiceExtraction,
    _ef,
)

_VERIFIER_INSTRUCTION = """\
You are a document verification assistant.

You have been given invoice page images and a set of field values that were
previously extracted from the document. Your task is to:

1. Locate each field value in the document images.
2. Assign a confidence score [0.0–1.0] reflecting how certain you are the
   value is correct and present in the document:
   - 0.9–1.0: clearly visible, exact or near-exact match
   - 0.7–0.9: present but with minor formatting differences
   - 0.5–0.7: uncertain — value may be approximate or partially visible
   - 0.0–0.5: cannot find or confirm this value in the document
3. Return the page (0-indexed) and approximate bounding box [x0, y0, x1, y1]
   in normalized coordinates [0–1] where the value appears.
   Set source_location to null if you cannot locate the value.

Previously extracted values:
{extracted_json}

Return a JSON object with one entry per field (see schema).
"""


async def verify_invoice(
    extraction: InvoiceExtraction,
    pages: list[Image.Image],
    client: VLMClient,
    max_retries: int = 2,
) -> VerifiedInvoiceExtraction:
    """Run the verifier pass: confirm extracted values and assign confidence.

    Args:
        extraction: Output of the extractor node (plain field values).
        pages: Original document page images.
        client: VLMClient to use for verification.
        max_retries: Retries for the verifier VLM call.

    Returns:
        VerifiedInvoiceExtraction with confidence + source_location per field.
    """
    extracted_json = json.dumps(
        {
            "invoice_number": extraction.invoice_number,
            "invoice_date": extraction.invoice_date,
            "due_date": extraction.due_date,
            "vendor_name": extraction.vendor_name,
            "vendor_gstin": extraction.vendor_gstin,
            "vendor_address": extraction.vendor_address,
            "buyer_name": extraction.buyer_name,
            "buyer_gstin": extraction.buyer_gstin,
            "currency": extraction.currency,
            "subtotal": extraction.subtotal,
            "total_amount": extraction.total_amount,
            "tax_total_tax": extraction.tax.total_tax if extraction.tax else None,
        },
        ensure_ascii=False,
        indent=2,
    )

    instruction = _VERIFIER_INSTRUCTION.format(extracted_json=extracted_json)

    verif = await client.extract_structured(
        pages,
        InvoiceVerificationResponse,
        max_retries=max_retries,
        instruction=instruction,
    )

    tax_ef: ExtractionField[object] = ExtractionField(
        value=extraction.tax,
        confidence=verif.tax_total_tax.confidence,
        source_location=verif.tax_total_tax.source_location,
    )

    return VerifiedInvoiceExtraction(
        invoice_number=_ef(extraction.invoice_number, verif.invoice_number),
        invoice_date=_ef(extraction.invoice_date, verif.invoice_date),
        due_date=_ef(extraction.due_date, verif.due_date),
        vendor_name=_ef(extraction.vendor_name, verif.vendor_name),
        vendor_gstin=_ef(extraction.vendor_gstin, verif.vendor_gstin),
        vendor_address=_ef(extraction.vendor_address, verif.vendor_address),
        buyer_name=_ef(extraction.buyer_name, verif.buyer_name),
        buyer_gstin=_ef(extraction.buyer_gstin, verif.buyer_gstin),
        currency=_ef(extraction.currency, verif.currency),
        subtotal=_ef(extraction.subtotal, verif.subtotal),
        total_amount=_ef(extraction.total_amount, verif.total_amount),
        tax=tax_ef,  # type: ignore[arg-type]
        line_items=extraction.line_items,
    )
