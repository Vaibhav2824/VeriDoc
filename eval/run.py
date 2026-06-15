"""Eval harness — run extraction on all labeled docs and report accuracy.

Usage:
    uv run python -m eval.run

Reads labels from eval/labels/*.json, finds matching docs in eval/docs/,
runs extract_invoice on each, computes metrics, and updates eval/REPORT.md.

Requires GEMINI_API_KEY in environment or .env file.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from eval.metrics import corpus_metrics, doc_accuracy
from services.api.clients.base import VLMError
from services.api.clients.gemini import GeminiClient
from services.api.extractor import extract_invoice
from services.api.ingest import IngestError

_REPO_ROOT = Path(__file__).parent.parent
_LABELS_DIR = _REPO_ROOT / "eval" / "labels"
_DOCS_DIR = _REPO_ROOT / "eval" / "docs"
_REPORT_PATH = _REPO_ROOT / "eval" / "REPORT.md"


# ── label loading ─────────────────────────────────────────────────────────────


def load_labels(labels_dir: Path) -> list[tuple[Path, dict]]:
    """Return list of (doc_path, ground_truth_dict) for all label files found."""
    pairs: list[tuple[Path, dict]] = []
    for label_file in sorted(labels_dir.glob("*.json")):
        try:
            label = json.loads(label_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[warn] Skipping {label_file.name}: invalid JSON — {exc}")
            continue

        doc_name = (label.get("_meta") or {}).get("doc_file") or (
            label_file.stem + ".pdf"
        )
        doc_path = _DOCS_DIR / doc_name
        if not doc_path.exists():
            print(f"[warn] Doc not found for label {label_file.name}: {doc_path}")
            continue

        pairs.append((doc_path, label))
    return pairs


# ── extraction run ────────────────────────────────────────────────────────────


async def run_eval(
    client: GeminiClient,
    pairs: list[tuple[Path, dict]],
) -> tuple[list[dict], list[str]]:
    """Extract + score each (doc, label) pair.

    Returns:
        (doc_results, errors) where doc_results is a list of per-field accuracy
        dicts ready for corpus_metrics(), and errors is a list of error strings.
    """
    doc_results = []
    errors = []

    for i, (doc_path, ground_truth) in enumerate(pairs, start=1):
        print(f"  [{i}/{len(pairs)}] {doc_path.name} … ", end="", flush=True)
        try:
            predicted = await extract_invoice(doc_path, client)
            result = doc_accuracy(predicted, ground_truth)
            doc_results.append(result)
            scored = [v for v in result.values() if v is not None]
            n_match = sum(scored)
            print(f"{n_match}/{len(scored)} fields matched")
        except (IngestError, VLMError) as exc:
            msg = f"{doc_path.name}: {exc}"
            errors.append(msg)
            print(f"ERROR — {exc}")

    return doc_results, errors


# ── report writing ────────────────────────────────────────────────────────────

_REPORT_SECTION_HEADER = "## Baseline (M0)"
_REPORT_PENDING_MARKER = "**Status: PENDING**"


def _format_report_section(metrics: dict, n_docs: int, errors: list[str]) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    macro = metrics["macro_accuracy"]
    macro_str = f"{macro:.1%}" if macro is not None else "—"

    lines = [
        "## Baseline (M0)",
        "",
        f"**Last run:** {ts} · **Docs evaluated:** {n_docs}",
        "",
        "| Metric | Value | Notes |",
        "|---|---|---|",
        f"| **Macro field accuracy** | **{macro_str}** | M0 — the baseline number |",
        "| Hallucination rate | — | Not measured at M0 (no source-grounding yet) |",
        "| ECE | — | Not applicable at M0 (no calibrated confidence yet) |",
        "| % auto-processed @ 99% precision | — | Not applicable at M0 (no abstention yet) |",
        "| Cost per doc | — | Wire Langfuse in M1 |",
        "| p95 latency (s) | — | Wire Langfuse in M1 |",
        "",
        "### Per-field accuracy",
        "",
        "| Field | Accuracy | Docs scored |",
        "|---|---|---|",
    ]

    field_acc = metrics.get("field_accuracy", {})
    n_scored = metrics.get("n_scored_pairs", 0)
    for field in sorted(field_acc):
        acc = field_acc[field]
        lines.append(f"| `{field}` | {acc:.1%} | (of {n_docs}) |")

    lines += [
        "",
        f"Total scored (field × doc) pairs: {n_scored}",
    ]

    if errors:
        lines += ["", "### Extraction errors", ""]
        for e in errors:
            lines.append(f"- {e}")

    return "\n".join(lines)


def update_report(metrics: dict, n_docs: int, errors: list[str]) -> None:
    report = _REPORT_PATH.read_text(encoding="utf-8")
    new_section = _format_report_section(metrics, n_docs, errors)

    if _REPORT_SECTION_HEADER in report:
        # Replace existing M0 section (everything up to the next ## header or EOF)
        before, _, rest = report.partition(_REPORT_SECTION_HEADER)
        # Find the next section
        next_section = rest.find("\n## ", 1)
        after = rest[next_section:] if next_section != -1 else ""
        report = before + new_section + "\n\n---\n" + after
    else:
        report = report + "\n\n" + new_section

    _REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport updated: {_REPORT_PATH.relative_to(_REPO_ROOT)}")


# ── entry point ───────────────────────────────────────────────────────────────


async def main() -> int:
    load_dotenv()

    pairs = load_labels(_LABELS_DIR)
    if not pairs:
        print(
            "No labels found in eval/labels/.\n"
            "Run: uv run python scripts/create_label.py eval/docs/<invoice.pdf>\n"
            "then edit the generated JSON file to correct any mistakes."
        )
        return 0

    print(f"Found {len(pairs)} labeled document(s). Running extraction...\n")

    try:
        client = GeminiClient()
    except VLMError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    doc_results, errors = await run_eval(client, pairs)

    if not doc_results:
        print("\nNo documents successfully evaluated.")
        return 1

    metrics = corpus_metrics(doc_results)
    macro = metrics["macro_accuracy"]

    print(f"\n{'─' * 50}")
    print(f"  Macro field accuracy : {macro:.1%}" if macro is not None else "  Macro: —")
    print(f"  Docs evaluated       : {metrics['n_docs']}")
    print(f"  Scored (field × doc) : {metrics['n_scored_pairs']}")
    if errors:
        print(f"  Errors               : {len(errors)}")
    print(f"{'─' * 50}")
    print("\nPer-field accuracy:")
    for field, acc in sorted(metrics["field_accuracy"].items()):
        bar = "█" * round(acc * 20)
        print(f"  {field:<25} {acc:.1%}  {bar}")

    update_report(metrics, len(doc_results), errors)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
