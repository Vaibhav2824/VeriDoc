"""Verified invoice extraction schema — M2.

VerifiedInvoiceExtraction mirrors InvoiceExtraction but every scalar field
is wrapped in ExtractionField[T] carrying confidence + source_location.
The verifier node populates it from (InvoiceExtraction, InvoiceVerificationResponse).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from services.api.models.fields import ExtractionField, FieldVerification
from services.api.models.invoice import LineItem, TaxBreakdown


def _ef(value: Any, fv: FieldVerification) -> ExtractionField[Any]:
    """Construct an ExtractionField from a value + FieldVerification."""
    return ExtractionField(
        value=value,
        confidence=fv.confidence,
        source_location=fv.source_location,
    )


class VerifiedInvoiceExtraction(BaseModel):
    """Invoice extraction result with per-field confidence and source location.

    Use to_value_dict() for eval harness compatibility (returns plain values,
    abstained fields → None).  Use confidence_pairs() for calibration metrics.
    """

    invoice_number: ExtractionField[str | None]
    invoice_date: ExtractionField[str | None]
    due_date: ExtractionField[str | None]
    vendor_name: ExtractionField[str | None]
    vendor_gstin: ExtractionField[str | None]
    vendor_address: ExtractionField[str | None]
    buyer_name: ExtractionField[str | None]
    buyer_gstin: ExtractionField[str | None]
    currency: ExtractionField[str | None]
    subtotal: ExtractionField[float | None]
    total_amount: ExtractionField[float | None]
    tax: ExtractionField[TaxBreakdown | None]
    line_items: list[LineItem] = Field(default_factory=list)

    def to_value_dict(self) -> dict[str, Any]:
        """Return {field: value} for eval, respecting abstention (abstained → None)."""
        result: dict[str, Any] = {}
        for name, field_info in type(self).model_fields.items():
            obj = getattr(self, name)
            if isinstance(obj, ExtractionField):
                val = obj.effective_value
                if isinstance(val, TaxBreakdown):
                    val = val.model_dump()
                result[name] = val
            else:
                result[name] = obj
        return result

    def confidence_pairs(self) -> list[tuple[str, float, bool | None]]:
        """Return [(field_name, confidence, is_extracted)] for calibration.

        is_extracted=True means the field has a non-None value and is not abstained.
        is_extracted=None for fields whose value is None (GT absent or truly missing).
        """
        pairs: list[tuple[str, float, bool | None]] = []
        for name in type(self).model_fields:
            obj = getattr(self, name)
            if not isinstance(obj, ExtractionField):
                continue
            val = obj.effective_value
            extracted = val is not None and obj.status == "extracted"
            pairs.append((name, obj.confidence, extracted if val is not None else None))
        return pairs

    def abstained_fields(self) -> list[str]:
        """Return field names with status='abstained'."""
        return [
            name
            for name in type(self).model_fields
            if isinstance(getattr(self, name), ExtractionField)
            and getattr(self, name).status == "abstained"
        ]

    def hallucination_flags(self) -> list[str]:
        """Return field names where value is non-None but source_location is None."""
        flags: list[str] = []
        for name in type(self).model_fields:
            obj = getattr(self, name)
            if not isinstance(obj, ExtractionField):
                continue
            if obj.value is not None and obj.source_location is None:
                flags.append(name)
        return flags


# ── Verifier response schema (VLM output) ────────────────────────────────────


class InvoiceVerificationResponse(BaseModel):
    """VLM output from the verifier pass — confidence + location per field.

    Sent as response_model to extract_structured() in the verifier node.
    Default confidence=0.5 means "uncertain" when the model omits a field.
    """

    invoice_number: FieldVerification = Field(default_factory=FieldVerification)
    invoice_date: FieldVerification = Field(default_factory=FieldVerification)
    due_date: FieldVerification = Field(default_factory=FieldVerification)
    vendor_name: FieldVerification = Field(default_factory=FieldVerification)
    vendor_gstin: FieldVerification = Field(default_factory=FieldVerification)
    vendor_address: FieldVerification = Field(default_factory=FieldVerification)
    buyer_name: FieldVerification = Field(default_factory=FieldVerification)
    buyer_gstin: FieldVerification = Field(default_factory=FieldVerification)
    currency: FieldVerification = Field(default_factory=FieldVerification)
    subtotal: FieldVerification = Field(default_factory=FieldVerification)
    total_amount: FieldVerification = Field(default_factory=FieldVerification)
    tax_total_tax: FieldVerification = Field(
        default_factory=FieldVerification,
        description="Verification for the tax.total_tax field",
    )
