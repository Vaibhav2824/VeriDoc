"""Gate node — M2.

Applies the confidence threshold to a VerifiedInvoiceExtraction:
fields below the threshold are marked status='abstained' and their
effective_value returns None downstream.

Also enforces the hallucination guardrail: fields with a non-None value
but source_location=None are logged as potential hallucinations.
These are NOT auto-abstained (the verifier may simply not know the bbox),
but they are tracked in the hallucination metric.
"""

from __future__ import annotations

import os

from services.api.models.fields import ExtractionField
from services.api.models.verified_invoice import VerifiedInvoiceExtraction


def _default_threshold() -> float:
    return float(os.environ.get("CONFIDENCE_THRESHOLD", "0.80"))


def apply_gate(
    verified: VerifiedInvoiceExtraction,
    threshold: float | None = None,
) -> VerifiedInvoiceExtraction:
    """Return a copy of *verified* with low-confidence fields abstained.

    Fields whose confidence < threshold get status='abstained'.
    Fields already None (not extracted) are left as-is regardless of confidence.

    Args:
        verified: Output of the verifier node.
        threshold: Confidence cutoff; defaults to CONFIDENCE_THRESHOLD env var (0.80).

    Returns:
        New VerifiedInvoiceExtraction with abstention applied.
    """
    if threshold is None:
        threshold = _default_threshold()

    updated: dict[str, object] = {}
    for name in type(verified).model_fields:
        obj = getattr(verified, name)
        if not isinstance(obj, ExtractionField):
            updated[name] = obj
            continue

        if obj.value is not None and obj.confidence < threshold:
            updated[name] = ExtractionField(
                value=obj.value,
                confidence=obj.confidence,
                source_location=obj.source_location,
                status="abstained",
            )
        else:
            updated[name] = obj

    return VerifiedInvoiceExtraction.model_validate(updated)
