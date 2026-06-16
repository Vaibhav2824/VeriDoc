"""Regression gate — fails closed if macro field accuracy drops below baseline.

Usage:
    uv run python -m eval.regression [--tolerance 0.02]

Runs the same extraction pipeline as eval.run against every labeled doc in
eval/labels/, then compares the resulting macro field accuracy against the
M0 baseline (the "contract" per CLAUDE.md) minus a tolerance. Exits non-zero
if the corpus regressed, or if no document could be evaluated at all.

Requires GROQ_API_KEY or GEMINI_API_KEY in environment or .env file.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from eval.metrics import corpus_metrics
from eval.run import load_labels, run_eval
from services.api.clients import make_client
from services.api.clients.base import VLMError

# The M0 baseline is the contract (eval/REPORT.md "Baseline (M0)" section).
BASELINE_MACRO_ACCURACY = 0.98
DEFAULT_TOLERANCE = 0.02

_REPO_ROOT = Path(__file__).parent.parent
_LABELS_DIR = _REPO_ROOT / "eval" / "labels"


def check_regression(
    macro_accuracy: float | None,
    baseline: float = BASELINE_MACRO_ACCURACY,
    tolerance: float = DEFAULT_TOLERANCE,
) -> tuple[bool, str]:
    """Pure pass/fail decision given a macro accuracy result.

    Args:
        macro_accuracy: Macro field accuracy from the current run, or None
            if no document could be evaluated.
        baseline: Reference macro accuracy to compare against (M0 by default).
        tolerance: Allowed drop below *baseline* before this counts as a regression.

    Returns:
        (passed, message)
    """
    if macro_accuracy is None:
        return False, "REGRESSION GATE FAILED: no documents were successfully evaluated."

    floor = baseline - tolerance
    if macro_accuracy < floor:
        return False, (
            f"REGRESSION GATE FAILED: macro accuracy {macro_accuracy:.1%} "
            f"< floor {floor:.1%} (baseline {baseline:.1%} - tolerance {tolerance:.1%})"
        )
    return True, (
        f"REGRESSION GATE PASSED: macro accuracy {macro_accuracy:.1%} "
        f">= floor {floor:.1%} (baseline {baseline:.1%} - tolerance {tolerance:.1%})"
    )


async def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=f"Allowed drop below baseline before failing (default {DEFAULT_TOLERANCE}).",
    )
    args = parser.parse_args()

    pairs = load_labels(_LABELS_DIR)
    if not pairs:
        print("No labels found in eval/labels/ — nothing to gate against.", file=sys.stderr)
        return 1

    try:
        client = make_client()
    except VLMError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(f"Running regression gate over {len(pairs)} labeled document(s)...\n")
    doc_results, _extractions, errors = await run_eval(client, pairs)

    if errors:
        print(f"\n{len(errors)} document(s) failed extraction:")
        for e in errors:
            print(f"  - {e}")

    metrics = corpus_metrics(doc_results)
    passed, message = check_regression(metrics["macro_accuracy"], tolerance=args.tolerance)
    print(f"\n{message}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
