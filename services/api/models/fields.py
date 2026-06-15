"""Trust-layer field wrapper — M2.

Every extracted field is wrapped in ExtractionField[T] so it carries:
  value           — the extracted data (typed)
  confidence      — verifier-assigned score in [0, 1]
  source_location — page + bbox where the value appears, or null
  status          — "extracted" | "abstained"

Fields with source_location=None are automatically flagged as potential
hallucinations (the source-grounding guardrail).
Fields with confidence < threshold are flipped to status="abstained" by the
gate node, and their value is treated as None downstream.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

FieldStatus = Literal["extracted", "abstained"]


class SourceLocation(BaseModel):
    """Approximate location of a field value within the source document."""

    page: int = Field(ge=0, description="0-indexed page number")
    bbox: list[float] = Field(
        description="[x0, y0, x1, y1] in normalized coordinates [0, 1]",
        min_length=4,
        max_length=4,
    )


class FieldVerification(BaseModel):
    """Verifier output for a single field — confidence + source location."""

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_location: SourceLocation | None = None


class ExtractionField(BaseModel, Generic[T]):
    """Single extracted field with provenance and trust signal.

    Constructed by the verifier node; consumed by the gate node and API.
    """

    value: T
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_location: SourceLocation | None = None
    status: FieldStatus = "extracted"

    @property
    def is_grounded(self) -> bool:
        """True when the value has a source location (not a potential hallucination)."""
        return self.source_location is not None

    @property
    def effective_value(self) -> T | None:
        """Return value if extracted, None if abstained."""
        if self.status == "abstained":
            return None
        return self.value
