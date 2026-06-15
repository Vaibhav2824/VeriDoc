"""Review queue data model — M2.

Abstained and hallucination-flagged fields are routed into a ReviewQueue
so human reviewers can inspect and correct them before downstream use.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from services.api.models.fields import SourceLocation

ReviewReason = Literal["low_confidence", "no_source_location", "abstained"]


class ReviewQueueItem(BaseModel):
    """One field requiring human review."""

    doc_name: str
    field_name: str
    extracted_value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source_location: SourceLocation | None
    reason: ReviewReason


class ReviewQueue(BaseModel):
    """All fields from one document that require human review."""

    doc_name: str
    items: list[ReviewQueueItem] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0

    def by_reason(self, reason: ReviewReason) -> list[ReviewQueueItem]:
        return [i for i in self.items if i.reason == reason]


def build_review_queue(
    verified: Any,  # VerifiedInvoiceExtraction | VerifiedBankStatementExtraction
    doc_name: str,
    confidence_threshold: float,
) -> ReviewQueue:
    """Build a ReviewQueue from a verified extraction result.

    Fields with status='abstained' or source_location=None (and non-null value)
    are added to the queue.
    """
    from services.api.models.fields import ExtractionField

    items: list[ReviewQueueItem] = []
    for field_name in verified.model_fields:
        obj = getattr(verified, field_name)
        if not isinstance(obj, ExtractionField):
            continue

        reason: ReviewReason | None = None
        if obj.status == "abstained":
            reason = "abstained"
        elif obj.value is not None and obj.source_location is None:
            reason = "no_source_location"
        elif obj.confidence < confidence_threshold and obj.status == "extracted":
            reason = "low_confidence"

        if reason is not None:
            items.append(
                ReviewQueueItem(
                    doc_name=doc_name,
                    field_name=field_name,
                    extracted_value=obj.value,
                    confidence=obj.confidence,
                    source_location=obj.source_location,
                    reason=reason,
                )
            )

    return ReviewQueue(doc_name=doc_name, items=items)
