"""Router accuracy eval — M3.

Runs the doc-type classifier (services.api.nodes.router.classify_doc_type)
against every labeled document in eval/labels/ — both invoice and
bank_statement — and reports classification accuracy. This is the
"baseline router-accuracy number" called out as missing in CLAUDE.md's M3
status note (the benchmark had no labeled bank-statement docs to measure
against until scripts/import_bank_statement_batch.py landed).

Like eval.run, classifications are cached locally (eval/.cache/) keyed by
a fingerprint of the model + router source, so re-runs only spend quota on
docs not yet classified under the current code+model.

Usage:
    uv run python -m eval.router_eval [--no-cache]

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

from eval.run import load_labels
from services.api.clients import make_client
from services.api.clients.base import VLMClient, VLMError
from services.api.ingest import IngestError, load_document
from services.api.nodes.router import classify_doc_type
from services.api.tracing import client_model

_REPO_ROOT = Path(__file__).parent.parent
_LABELS_DIR = _REPO_ROOT / "eval" / "labels"
_REPORT_PATH = _REPO_ROOT / "eval" / "REPORT.md"

_CACHE_PATH = _REPO_ROOT / "eval" / ".cache" / "router_classifications.json"
_FINGERPRINT_FILES = [
    "services/api/nodes/router.py",
    "services/api/models/router.py",
    "services/api/clients/base.py",
    "services/api/clients/groq_client.py",
    "services/api/clients/gemini.py",
]


def compute_fingerprint(client: VLMClient) -> str:
    """Hash of the active model + router source (see eval.run.compute_fingerprint)."""
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


def ground_truth_doc_type(label: dict[str, Any]) -> str:
    """Bank-statement labels are tagged _meta.doc_type; invoice labels predate
    that tag and default to "invoice" (see scripts/import_bank_statement_batch.py).
    """
    return (label.get("_meta") or {}).get("doc_type", "invoice")


async def run_router_eval(
    client: VLMClient,
    pairs: list[tuple[Path, dict[str, Any]]],
    use_cache: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Classify every doc and compare to its ground-truth doc_type.

    Returns:
        (per_doc_results, errors) — each result has doc_name, true_type,
        predicted_type, confidence, correct.
    """
    sleep_s = float(os.environ.get("EVAL_RATE_LIMIT_SLEEP", "4"))
    cache = load_cache() if use_cache else {}
    fingerprint = compute_fingerprint(client) if use_cache else None
    n_calls = 0

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, (doc_path, label) in enumerate(pairs, start=1):
        true_type = ground_truth_doc_type(label)
        cached = cache.get(doc_path.name)
        from_cache = use_cache and cached is not None and cached.get("fingerprint") == fingerprint

        print(f"  [{i}/{len(pairs)}] {doc_path.name} (true={true_type}) ... ", end="", flush=True)

        if from_cache:
            assert cached is not None
            predicted_type = cached["doc_type"]
            confidence = cached["confidence"]
        else:
            if n_calls > 0 and sleep_s > 0:
                await asyncio.sleep(sleep_s)
            n_calls += 1
            try:
                pages = load_document(doc_path)
                classification = await classify_doc_type(pages, client)
            except (IngestError, VLMError) as exc:
                errors.append(f"{doc_path.name}: {exc}")
                print(f"ERROR -- {exc}")
                continue
            predicted_type = classification.doc_type
            confidence = classification.confidence
            if use_cache:
                cache[doc_path.name] = {
                    "fingerprint": fingerprint,
                    "doc_type": predicted_type,
                    "confidence": confidence,
                }
                # Save after every success, not batched: a long run is mostly
                # failures under quota exhaustion, so gating on n_calls % N can
                # skip every checkpoint and never persist anything before a kill.
                save_cache(cache)

        correct = predicted_type == true_type
        results.append(
            {
                "doc_name": doc_path.name,
                "true_type": true_type,
                "predicted_type": predicted_type,
                "confidence": confidence,
                "correct": correct,
            }
        )
        cache_note = " [cached]" if from_cache else ""
        print(f"predicted={predicted_type} ({'OK' if correct else 'WRONG'}){cache_note}")

    if use_cache:
        save_cache(cache)

    return results, errors


# ── report writing ────────────────────────────────────────────────────────────

_ROUTER_SECTION_HEADER = "### Router accuracy"


def _format_router_section(results: list[dict[str, Any]], errors: list[str]) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    n_total = len(results)
    n_correct = sum(1 for r in results if r["correct"])
    accuracy = n_correct / n_total if n_total else None
    accuracy_str = f"{accuracy:.1%}" if accuracy is not None else "—"

    by_type: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        by_type.setdefault(r["true_type"], []).append(r)

    lines = [
        _ROUTER_SECTION_HEADER,
        "",
        f"**Last run:** {ts} · **Docs classified:** {n_total}",
        "",
        f"**Accuracy: {accuracy_str}** ({n_correct}/{n_total})",
        "",
        "| True type | Accuracy | Docs |",
        "|---|---|---|",
    ]
    for doc_type in sorted(by_type):
        rows = by_type[doc_type]
        acc = sum(1 for r in rows if r["correct"]) / len(rows)
        lines.append(f"| `{doc_type}` | {acc:.1%} | {len(rows)} |")

    misclassified = [r for r in results if not r["correct"]]
    if misclassified:
        lines += ["", "Misclassified:", ""]
        for r in misclassified:
            lines.append(
                f"- `{r['doc_name']}`: true=`{r['true_type']}`, "
                f"predicted=`{r['predicted_type']}` (confidence {r['confidence']:.2f})"
            )

    if errors:
        lines += ["", "Errors:", ""]
        for e in errors:
            lines.append(f"- {e}")

    return "\n".join(lines)


def update_report(results: list[dict[str, Any]], errors: list[str]) -> None:
    report = _REPORT_PATH.read_text(encoding="utf-8")
    new_section = _format_router_section(results, errors)

    if _ROUTER_SECTION_HEADER in report:
        before, _, rest = report.partition(_ROUTER_SECTION_HEADER)
        next_idx = rest.find("\n## ", 1)
        sub_idx = rest.find("\n### ", 1)
        if sub_idx != -1 and (next_idx == -1 or sub_idx < next_idx):
            next_idx = sub_idx
        after = rest[next_idx:] if next_idx != -1 else ""
        report = before + new_section + "\n\n" + after
    else:
        marker = "## M3 — Agentify + MCP + RAG + fine-tune"
        if marker in report:
            before, _, rest = report.partition(marker)
            next_idx = rest.find("\n---\n")
            tail = rest[:next_idx] if next_idx != -1 else rest
            after = rest[next_idx:] if next_idx != -1 else ""
            report = before + marker + tail.rstrip("\n") + "\n\n" + new_section + "\n\n" + after
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
        help="Ignore eval/.cache/router_classifications.json and re-classify every doc.",
    )
    args = parser.parse_args()

    pairs = load_labels(_LABELS_DIR)
    if not pairs:
        print("No labels found in eval/labels/.")
        return 0

    print(f"Found {len(pairs)} labeled document(s). Classifying...\n")

    try:
        client = make_client()
    except VLMError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    results, errors = await run_router_eval(client, pairs, use_cache=not args.no_cache)

    if not results:
        print("\nNo documents were successfully classified.")
        return 1

    n_correct = sum(1 for r in results if r["correct"])
    print(f"\n{'-' * 50}")
    print(f"  Router accuracy : {n_correct}/{len(results)} ({n_correct / len(results):.1%})")
    if errors:
        print(f"  Errors          : {len(errors)}")
    print(f"{'-' * 50}")

    update_report(results, errors)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
