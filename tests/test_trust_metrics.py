"""Tests for M2 trust metrics: ECE, hallucination rate, auto-processing rate."""

from __future__ import annotations

import pytest

from eval.metrics import auto_processing_rate, calibration_metrics, hallucination_rate
from services.api.models.fields import ExtractionField, SourceLocation
from services.api.models.verified_invoice import VerifiedInvoiceExtraction

# ── helpers ───────────────────────────────────────────────────────────────────


def _ef(value: object, confidence: float, has_source: bool = True) -> ExtractionField:
    loc = SourceLocation(page=0, bbox=[0.1, 0.1, 0.5, 0.2]) if has_source else None
    return ExtractionField(value=value, confidence=confidence, source_location=loc)


def _make_verified(
    *,
    invoice_number: str | None = "INV-001",
    confidence: float = 0.95,
    has_source: bool = True,
    status: str = "extracted",
) -> VerifiedInvoiceExtraction:
    ef: ExtractionField[str | None] = ExtractionField(
        value=invoice_number,
        confidence=confidence,
        source_location=SourceLocation(page=0, bbox=[0.0, 0.0, 0.5, 0.1]) if has_source else None,
        status=status,  # type: ignore[arg-type]
    )
    null_ef: ExtractionField[None] = ExtractionField(
        value=None, confidence=0.5, source_location=None
    )
    return VerifiedInvoiceExtraction(
        invoice_number=ef,
        invoice_date=null_ef,
        due_date=null_ef,
        vendor_name=null_ef,
        vendor_gstin=null_ef,
        vendor_address=null_ef,
        buyer_name=null_ef,
        buyer_gstin=null_ef,
        currency=null_ef,
        subtotal=null_ef,
        total_amount=null_ef,
        tax=null_ef,
    )


# ── calibration_metrics ───────────────────────────────────────────────────────


class TestCalibrationMetrics:
    def test_empty_returns_none_ece(self) -> None:
        result = calibration_metrics([], [])
        assert result["ece"] is None

    def test_perfect_calibration(self) -> None:
        # All high-confidence, all correct
        verified = _make_verified(confidence=0.95)
        doc_result: dict[str, bool | None] = {"invoice_number": True}
        result = calibration_metrics([doc_result], [verified])
        # ECE should be low when high confidence matches high accuracy
        assert result["ece"] is not None
        assert result["ece"] < 0.2

    def test_overconfident_model(self) -> None:
        # Confidence=0.99, but accuracy=0% → high ECE
        verified = _make_verified(confidence=0.99)
        doc_result: dict[str, bool | None] = {"invoice_number": False}
        result = calibration_metrics([doc_result], [verified])
        assert result["ece"] is not None
        assert result["ece"] > 0.5

    def test_reliability_data_structure(self) -> None:
        verified = _make_verified(confidence=0.9)
        doc_result: dict[str, bool | None] = {"invoice_number": True}
        result = calibration_metrics([doc_result], [verified])
        assert isinstance(result["reliability"], list)
        for entry in result["reliability"]:
            assert "bin_mid" in entry
            assert "accuracy" in entry
            assert "confidence" in entry
            assert "n" in entry

    def test_mismatched_lengths_returns_none(self) -> None:
        verified = _make_verified(confidence=0.9)
        result = calibration_metrics([{"invoice_number": True}], [verified, verified])
        assert result["ece"] is None


# ── hallucination_rate ────────────────────────────────────────────────────────


class TestHallucinationRate:
    def test_empty_returns_none(self) -> None:
        assert hallucination_rate([]) is None

    def test_no_hallucinations(self) -> None:
        verified = _make_verified(has_source=True)
        rate = hallucination_rate([verified])
        assert rate == 0.0

    def test_hallucination_detected(self) -> None:
        # invoice_number has value but no source_location
        verified = _make_verified(has_source=False)
        rate = hallucination_rate([verified])
        assert rate is not None
        assert rate > 0.0

    def test_null_value_not_hallucination(self) -> None:
        # None value with no source → not a hallucination (field not extracted)
        verified = _make_verified(invoice_number=None, has_source=False)
        rate = hallucination_rate([verified])
        assert rate == 0.0


# ── auto_processing_rate ──────────────────────────────────────────────────────


class TestAutoProcessingRate:
    def test_empty_returns_none(self) -> None:
        assert auto_processing_rate([], []) is None

    def test_all_correct_high_confidence(self) -> None:
        verified = _make_verified(confidence=0.99)
        doc_result: dict[str, bool | None] = {"invoice_number": True}
        rate = auto_processing_rate([doc_result], [verified], target_precision=0.99)
        assert rate is not None
        assert rate > 0.0

    def test_all_wrong_no_auto_process(self) -> None:
        # All wrong — can't achieve 99% precision
        verified = _make_verified(confidence=0.99)
        doc_result: dict[str, bool | None] = {"invoice_number": False}
        rate = auto_processing_rate([doc_result], [verified], target_precision=0.99)
        # No threshold achieves 99% precision when all predictions are wrong
        assert rate is None or rate == 0.0

    def test_mismatched_lengths_returns_none(self) -> None:
        verified = _make_verified(confidence=0.9)
        rate = auto_processing_rate([{"invoice_number": True}], [verified, verified])
        assert rate is None


# ── gate: apply_gate ─────────────────────────────────────────────────────────


class TestApplyGate:
    def test_high_confidence_not_abstained(self) -> None:
        from services.api.nodes.gate import apply_gate

        verified = _make_verified(confidence=0.95)
        gated = apply_gate(verified, threshold=0.80)
        assert gated.invoice_number.status == "extracted"

    def test_low_confidence_abstained(self) -> None:
        from services.api.nodes.gate import apply_gate

        verified = _make_verified(confidence=0.3)
        gated = apply_gate(verified, threshold=0.80)
        assert gated.invoice_number.status == "abstained"

    def test_null_value_not_abstained_even_low_confidence(self) -> None:
        from services.api.nodes.gate import apply_gate

        verified = _make_verified(invoice_number=None, confidence=0.1)
        gated = apply_gate(verified, threshold=0.80)
        # None value is not abstained — it was genuinely not found
        assert gated.invoice_number.status == "extracted"

    def test_confidence_preserved_after_gate(self) -> None:
        from services.api.nodes.gate import apply_gate

        verified = _make_verified(confidence=0.95)
        gated = apply_gate(verified, threshold=0.80)
        assert gated.invoice_number.confidence == pytest.approx(0.95)
