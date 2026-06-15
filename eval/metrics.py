"""Field-level accuracy + trust metrics for VeriDoc eval harness.

All functions are pure (no I/O, no side effects) so they are trivially
unit-testable and can be called from both eval/run.py and notebooks.

M0: exact-match accuracy with field-type-aware normalisation.
M2: calibration (ECE), hallucination rate, % auto-processed.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from services.api.models.verified_invoice import VerifiedInvoiceExtraction

# ── field classification ───────────────────────────────────────────────────────

# Fields scored in M0 — flat scalars only; line_items scored in M1.
SCORED_FIELDS: list[str] = [
    "invoice_number",
    "invoice_date",
    "due_date",
    "vendor_name",
    "vendor_gstin",
    "vendor_address",
    "buyer_name",
    "buyer_gstin",
    "currency",
    "subtotal",
    "total_amount",
    "tax.total_tax",  # nested: ground_truth["tax"]["total_tax"]
]

_DATE_FIELDS = {"invoice_date", "due_date"}
_NUMBER_FIELDS = {"subtotal", "total_amount", "tax.total_tax"}
# Address fields: strip all punctuation before comparing — models use newlines
# or commas interchangeably as address-part separators.
_ADDRESS_FIELDS = {"vendor_address", "buyer_address"}
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
    "%d.%m.%Y",
    "%B %d, %Y",
    "%d %B %Y",
)


# ── normalisation helpers ──────────────────────────────────────────────────────


def normalize_string(value: str) -> str:
    """Lowercase and collapse internal whitespace."""
    return " ".join(value.strip().lower().split())


def normalize_address(value: str) -> str:
    """Strip punctuation and collapse whitespace for address comparison.

    Models often use newlines where ground truth has commas (or vice versa),
    so we compare the bare word sequence rather than punctuated form.
    """
    stripped = re.sub(r"[^\w\s]", " ", value.lower())
    return " ".join(stripped.split())


def normalize_number(value: Any) -> float | None:
    """Parse a number from int, float, or formatted string (e.g. '1,234.56')."""
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d.\-]", "", str(value).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_date(value: str) -> str:
    """Return ISO 8601 (YYYY-MM-DD) or the stripped input if no format matches."""
    stripped = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(stripped, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return stripped


# ── field comparison ──────────────────────────────────────────────────────────


def field_match(predicted: Any, ground_truth: Any, field: str) -> bool:
    """Return True if *predicted* matches *ground_truth* for *field*.

    Args:
        predicted: Extracted value (may be None / null).
        ground_truth: Ground-truth value (caller guarantees it is not None).
        field: Field name (determines normalisation strategy).

    Returns:
        True on match, False on mismatch or when predicted is None.
    """
    if predicted is None:
        return False  # abstained / not extracted — counts as a miss

    if field in _DATE_FIELDS:
        return normalize_date(str(predicted)) == normalize_date(str(ground_truth))

    if field in _NUMBER_FIELDS:
        p = normalize_number(predicted)
        g = normalize_number(ground_truth)
        if p is None or g is None:
            return False
        return abs(p - g) < 0.011  # allow rounding differences up to ~1 cent

    if field in _ADDRESS_FIELDS:
        return normalize_address(str(predicted)) == normalize_address(str(ground_truth))

    # Default: string comparison
    return normalize_string(str(predicted)) == normalize_string(str(ground_truth))


def _get_nested(doc: dict[str, Any], field: str) -> Any:
    """Resolve dotted field paths such as 'tax.total_tax'."""
    parts = field.split(".", 1)
    value = doc.get(parts[0])
    if len(parts) == 1 or not isinstance(value, dict):
        return value
    return value.get(parts[1])


# ── per-document accuracy ──────────────────────────────────────────────────────


def doc_accuracy(
    predicted: dict[str, Any],
    ground_truth: dict[str, Any],
) -> dict[str, bool | None]:
    """Compare *predicted* to *ground_truth* field by field.

    Returns:
        Dict mapping field name → True (match) | False (miss) | None (GT null, not scored).
    """
    results: dict[str, bool | None] = {}
    for field in SCORED_FIELDS:
        gt_val = _get_nested(ground_truth, field)
        if gt_val is None:
            results[field] = None  # GT absent — skip
            continue
        pred_val = _get_nested(predicted, field)
        results[field] = field_match(pred_val, gt_val, field)
    return results


# ── corpus-level aggregation ──────────────────────────────────────────────────


def corpus_metrics(
    doc_results: list[dict[str, bool | None]],
) -> dict[str, Any]:
    """Aggregate per-field accuracy across a corpus of documents.

    Returns:
        {
          "macro_accuracy": float | None,   # mean over all scored (field, doc) pairs
          "field_accuracy": {field: float}, # per-field accuracy rate
          "n_docs": int,
          "n_scored_pairs": int,            # total (field × doc) pairs that had GT
        }
    """
    if not doc_results:
        return {
            "macro_accuracy": None,
            "field_accuracy": {},
            "n_docs": 0,
            "n_scored_pairs": 0,
        }

    all_fields: set[str] = set()
    for r in doc_results:
        all_fields.update(r.keys())

    field_accuracy: dict[str, float] = {}
    all_scored: list[bool] = []

    for field in sorted(all_fields):
        scored: list[bool] = [v for r in doc_results if (v := r.get(field)) is not None]
        if not scored:
            continue
        acc = sum(scored) / len(scored)
        field_accuracy[field] = round(acc, 4)
        all_scored.extend(scored)

    macro = round(sum(all_scored) / len(all_scored), 4) if all_scored else None

    return {
        "macro_accuracy": macro,
        "field_accuracy": field_accuracy,
        "n_docs": len(doc_results),
        "n_scored_pairs": len(all_scored),
    }


# ── M2 trust metrics ──────────────────────────────────────────────────────────


def calibration_metrics(
    doc_results: list[dict[str, bool | None]],
    extractions: list[VerifiedInvoiceExtraction],
    n_bins: int = 10,
) -> dict[str, Any]:
    """Compute Expected Calibration Error (ECE) and reliability data.

    ECE measures how well confidence scores predict actual accuracy.
    Lower ECE is better; a perfectly calibrated model has ECE = 0.

    Args:
        doc_results: Per-field accuracy dicts from doc_accuracy().
        extractions: Corresponding VerifiedInvoiceExtraction objects.
        n_bins: Number of equal-width bins for ECE computation.

    Returns:
        {
          "ece": float,
          "reliability": [{"bin_mid": float, "accuracy": float, "confidence": float, "n": int}]
        }
    """
    if not extractions or len(doc_results) != len(extractions):
        return {"ece": None, "reliability": []}

    pairs: list[tuple[float, bool]] = []
    for result, verified in zip(doc_results, extractions):
        for field_name in type(verified).model_fields:
            obj = getattr(verified, field_name)
            from services.api.models.fields import ExtractionField

            if not isinstance(obj, ExtractionField):
                continue
            # Only score fields where we have ground truth
            is_correct = result.get(field_name)
            if is_correct is None:
                continue
            pairs.append((obj.confidence, bool(is_correct)))

    if not pairs:
        return {"ece": None, "reliability": []}

    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for conf, correct in pairs:
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, correct))

    reliability = []
    total_n = len(pairs)
    ece = 0.0
    for i, bucket in enumerate(bins):
        if not bucket:
            continue
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        avg_acc = sum(1 for _, ok in bucket if ok) / len(bucket)
        bin_mid = (i + 0.5) / n_bins
        reliability.append(
            {"bin_mid": round(bin_mid, 3), "accuracy": round(avg_acc, 4),
             "confidence": round(avg_conf, 4), "n": len(bucket)}
        )
        ece += abs(avg_acc - avg_conf) * len(bucket) / total_n

    return {"ece": round(ece, 4), "reliability": reliability}


def hallucination_rate(extractions: list[VerifiedInvoiceExtraction]) -> float | None:
    """Fraction of extracted (non-None) fields that have no source location.

    A field with value != None and source_location = None cannot be traced back
    to the document — this is the hallucination signal.
    """
    if not extractions:
        return None
    total_extracted = 0
    total_no_source = 0
    for verified in extractions:
        total_no_source += len(verified.hallucination_flags())
        from services.api.models.fields import ExtractionField

        for name in type(verified).model_fields:
            obj = getattr(verified, name)
            if isinstance(obj, ExtractionField) and obj.value is not None:
                total_extracted += 1
    if total_extracted == 0:
        return 0.0
    return round(total_no_source / total_extracted, 4)


def auto_processing_rate(
    doc_results: list[dict[str, bool | None]],
    extractions: list[VerifiedInvoiceExtraction],
    target_precision: float = 0.99,
) -> float | None:
    """Fraction of fields auto-accepted while achieving *target_precision*.

    Sweeps confidence thresholds from high to low; returns the coverage
    (fraction of all scored fields) at the highest threshold that still
    achieves precision >= target_precision on accepted fields.

    Args:
        doc_results: Per-field accuracy dicts.
        extractions: Corresponding VerifiedInvoiceExtraction objects.
        target_precision: Required precision on the auto-accepted set (default 0.99).

    Returns:
        Coverage rate [0, 1] or None if not computable.
    """
    if not extractions or len(doc_results) != len(extractions):
        return None

    pairs: list[tuple[float, bool]] = []
    for result, verified in zip(doc_results, extractions):
        for field_name in type(verified).model_fields:
            obj = getattr(verified, field_name)
            from services.api.models.fields import ExtractionField

            if not isinstance(obj, ExtractionField):
                continue
            is_correct = result.get(field_name)
            if is_correct is None:
                continue
            pairs.append((obj.confidence, bool(is_correct)))

    if not pairs:
        return None

    pairs_sorted = sorted(pairs, key=lambda x: x[0], reverse=True)
    total = len(pairs_sorted)
    best_coverage = 0.0

    for cutoff_idx in range(total):
        threshold = pairs_sorted[cutoff_idx][0]
        accepted = [(c, ok) for c, ok in pairs_sorted if c >= threshold]
        if not accepted:
            continue
        precision = sum(1 for _, ok in accepted if ok) / len(accepted)
        if precision >= target_precision:
            best_coverage = len(accepted) / total

    return round(best_coverage, 4) if best_coverage > 0 else None
