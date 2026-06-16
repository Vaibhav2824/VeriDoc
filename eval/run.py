"""Eval harness — run extraction on all labeled docs and report accuracy.

Usage:
    uv run python -m eval.run

Reads labels from eval/labels/*.json, finds matching docs in eval/docs/,
runs extract_invoice on each, computes accuracy + M2 trust metrics, and
updates eval/REPORT.md.

Requires GROQ_API_KEY or GEMINI_API_KEY in environment or .env file.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from eval.metrics import (
    auto_processing_rate,
    calibration_metrics,
    corpus_metrics,
    doc_accuracy,
    hallucination_rate,
)
from services.api.clients import make_client
from services.api.clients.base import VLMClient, VLMError
from services.api.extractor import extract_invoice
from services.api.ingest import IngestError
from services.api.models.verified_invoice import VerifiedInvoiceExtraction
from services.api.tracing import client_model

_REPO_ROOT = Path(__file__).parent.parent
_LABELS_DIR = _REPO_ROOT / "eval" / "labels"
_DOCS_DIR = _REPO_ROOT / "eval" / "docs"
_REPORT_PATH = _REPO_ROOT / "eval" / "REPORT.md"

# ── extraction cache ─────────────────────────────────────────────────────────
#
# Free-tier VLM daily quotas are small relative to the 100-doc benchmark (a
# single pass needs ~200 calls; see eval/REPORT.md's "Known limitation" note),
# so a full run routinely spans multiple days/keys. Cache successful per-doc
# extractions locally, keyed by a fingerprint of the active model + the
# pipeline source files that determine the output, so re-runs skip docs
# already extracted under the same code+model and only spend quota on new
# ones — while any pipeline change or model switch invalidates the cache
# automatically instead of silently serving stale results.

_CACHE_PATH = _REPO_ROOT / "eval" / ".cache" / "extractions.json"
_FINGERPRINT_FILES = [
    "services/api/extractor.py",
    "services/api/nodes/verifier.py",
    "services/api/nodes/gate.py",
    "services/api/models/invoice.py",
    "services/api/models/verified_invoice.py",
    "services/api/models/fields.py",
    "services/api/clients/base.py",
    "services/api/clients/groq_client.py",
    "services/api/clients/gemini.py",
]


def compute_fingerprint(client: VLMClient) -> str:
    """Hash of the active model + extraction pipeline source.

    Any change to either invalidates every cached entry, so the cache can
    never serve a result that doesn't reflect the current code and model.
    """
    h = hashlib.sha256()
    h.update(client_model(client).encode())
    for rel in _FINGERPRINT_FILES:
        h.update((_REPO_ROOT / rel).read_bytes())
    return h.hexdigest()


def load_cache(path: Path | None = None) -> dict[str, Any]:
    path = path if path is not None else _CACHE_PATH
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict[str, Any], path: Path | None = None) -> None:
    path = path if path is not None else _CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


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
    client: VLMClient,
    pairs: list[tuple[Path, dict]],
    use_cache: bool = True,
) -> tuple[list[dict], list[VerifiedInvoiceExtraction], list[str]]:
    """Extract + score each (doc, label) pair.

    Successful extractions are cached by doc name + fingerprint (see
    compute_fingerprint); cache hits skip the VLM call entirely so re-runs
    only spend quota on docs not yet extracted under the current code+model.

    Returns:
        (doc_accuracy_results, verified_extractions, errors)
    """
    doc_results: list[dict] = []
    extractions: list[VerifiedInvoiceExtraction] = []
    errors: list[str] = []
    sleep_s = float(os.environ.get("EVAL_RATE_LIMIT_SLEEP", "4"))

    cache = load_cache() if use_cache else {}
    fingerprint = compute_fingerprint(client) if use_cache else None
    n_calls = 0
    n_cache_hits = 0

    for i, (doc_path, ground_truth) in enumerate(pairs, start=1):
        cached = cache.get(doc_path.name)
        from_cache = use_cache and cached is not None and cached.get("fingerprint") == fingerprint

        print(f"  [{i}/{len(pairs)}] {doc_path.name} ... ", end="", flush=True)

        if from_cache:
            assert cached is not None
            n_cache_hits += 1
            verified = VerifiedInvoiceExtraction.model_validate(cached["result"])
        else:
            if n_calls > 0 and sleep_s > 0:
                await asyncio.sleep(sleep_s)
            n_calls += 1
            try:
                verified = await extract_invoice(doc_path, client, max_retries=3)
            except (IngestError, VLMError) as exc:
                msg = f"{doc_path.name}: {exc}"
                errors.append(msg)
                print(f"ERROR -- {exc}")
                continue
            if use_cache:
                cache[doc_path.name] = {
                    "fingerprint": fingerprint,
                    "result": verified.model_dump(),
                }

        predicted = verified.to_value_dict()
        result = doc_accuracy(predicted, ground_truth)
        doc_results.append(result)
        extractions.append(verified)
        scored = [v for v in result.values() if v is not None]
        n_match = sum(scored)
        n_abstained = len(verified.abstained_fields())
        abstain_note = f" ({n_abstained} abstained)" if n_abstained else ""
        cache_note = " [cached]" if from_cache else ""
        print(f"{n_match}/{len(scored)} fields matched{abstain_note}{cache_note}")

    if use_cache:
        save_cache(cache)
    if n_cache_hits:
        print(f"\n({n_cache_hits} doc(s) served from cache, {n_calls} fresh VLM call(s))")

    return doc_results, extractions, errors


# ── report writing ────────────────────────────────────────────────────────────

_M2_SECTION_HEADER = "## M2 — Verifier + confidence"


def _format_m2_section(
    acc_metrics: dict,
    trust_metrics: dict,
    n_docs: int,
    errors: list[str],
) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    macro = acc_metrics["macro_accuracy"]
    macro_str = f"{macro:.1%}" if macro is not None else "—"
    ece = trust_metrics.get("ece")
    ece_str = f"{ece:.4f}" if ece is not None else "—"
    hlr = trust_metrics.get("hallucination_rate")
    hlr_str = f"{hlr:.1%}" if hlr is not None else "—"
    apr = trust_metrics.get("auto_processing_rate_99pct")
    apr_str = f"{apr:.1%}" if apr is not None else "—"
    abs_rate = trust_metrics.get("abstention_rate")
    abs_str = f"{abs_rate:.1%}" if abs_rate is not None else "—"

    lines = [
        "## M2 — Verifier + confidence",
        "",
        f"**Last run:** {ts} · **Docs evaluated:** {n_docs}",
        "",
        "| Metric | Value | Notes |",
        "|---|---|---|",
        f"| **Macro field accuracy** | **{macro_str}** | After gate (abstained = miss) |",
        f"| Hallucination rate | {hlr_str} | Non-null value with no source location |",
        f"| ECE | {ece_str} | Expected Calibration Error (lower is better) |",
        f"| % auto-processed @ 99% precision | {apr_str} | Coverage at 99% precision threshold |",
        f"| Abstention rate | {abs_str} | Fields routed to human review |",
        "| Cost per doc | — | Wire Langfuse keys in .env for real numbers |",
        "",
        "### Per-field accuracy (after gate)",
        "",
        "| Field | Accuracy | Docs scored |",
        "|---|---|---|",
    ]

    field_acc = acc_metrics.get("field_accuracy", {})
    for field in sorted(field_acc):
        acc = field_acc[field]
        lines.append(f"| `{field}` | {acc:.1%} | (of {n_docs}) |")

    n_scored = acc_metrics.get("n_scored_pairs", 0)
    lines += ["", f"Total scored (field x doc) pairs: {n_scored}"]

    if errors:
        lines += ["", "### Extraction errors", ""]
        for e in errors:
            lines.append(f"- {e}")

    return "\n".join(lines)


def update_report(
    acc_metrics: dict,
    trust_metrics: dict,
    n_docs: int,
    errors: list[str],
) -> None:
    report = _REPORT_PATH.read_text(encoding="utf-8")
    new_section = _format_m2_section(acc_metrics, trust_metrics, n_docs, errors)

    if _M2_SECTION_HEADER in report:
        before, _, rest = report.partition(_M2_SECTION_HEADER)
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

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore eval/.cache/extractions.json and re-extract every doc.",
    )
    args = parser.parse_args()

    pairs = load_labels(_LABELS_DIR)
    if not pairs:
        print(
            "No labels found in eval/labels/.\n"
            "Run: uv run python -m scripts.create_label eval/docs/<invoice.pdf>"
        )
        return 0

    print(f"Found {len(pairs)} labeled document(s). Running extraction...\n")

    try:
        client = make_client()
    except VLMError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    doc_results, extractions, errors = await run_eval(client, pairs, use_cache=not args.no_cache)

    if not doc_results:
        print("\nNo documents successfully evaluated.")
        return 1

    acc_metrics = corpus_metrics(doc_results)
    macro = acc_metrics["macro_accuracy"]

    # M2 trust metrics from verified extractions
    trust_metrics = {
        "ece": calibration_metrics(doc_results, extractions).get("ece"),
        "hallucination_rate": hallucination_rate(extractions),
        "auto_processing_rate_99pct": auto_processing_rate(doc_results, extractions, 0.99),
        "abstention_rate": (
            sum(len(v.abstained_fields()) for v in extractions)
            / max(1, acc_metrics["n_scored_pairs"])
        ),
    }

    print(f"\n{'-' * 50}")
    print(f"  Macro field accuracy : {macro:.1%}" if macro is not None else "  Macro: N/A")
    print(f"  Docs evaluated       : {acc_metrics['n_docs']}")
    print(f"  Scored (field x doc) : {acc_metrics['n_scored_pairs']}")
    ece = trust_metrics["ece"]
    print(f"  ECE                  : {ece:.4f}" if ece is not None else "  ECE: N/A")
    hlr = trust_metrics["hallucination_rate"]
    print(f"  Hallucination rate   : {hlr:.1%}" if hlr is not None else "  Hallucination: N/A")
    apr = trust_metrics["auto_processing_rate_99pct"]
    print(
        f"  Auto-process @99%p   : {apr:.1%}" if apr is not None else "  Auto-process @99%p: N/A"
    )
    if errors:
        print(f"  Errors               : {len(errors)}")
    print(f"{'-' * 50}")
    print("\nPer-field accuracy:")
    for field, acc in sorted(acc_metrics["field_accuracy"].items()):
        bar = "#" * round(acc * 20)
        print(f"  {field:<25} {acc:.1%}  {bar}")

    update_report(acc_metrics, trust_metrics, len(doc_results), errors)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
