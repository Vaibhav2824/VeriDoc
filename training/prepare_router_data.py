"""Prepare router training data — M3 fine-tune.

Extracts first-page text from every labeled PDF in eval/docs/ using
pypdfium2, pairs each with its ground-truth doc_type from eval/labels/,
and writes training/router_training_data.csv.

The CSV is used by both:
  - training/train_router.py  (local sklearn model, no GPU needed)
  - training/router_finetune.ipynb  (Kaggle/Colab DistilBERT fine-tune)

Usage:
    uv run python training/prepare_router_data.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pypdfium2 as pdfium

_REPO = Path(__file__).parent.parent
_LABELS = _REPO / "eval" / "labels"
_DOCS = _REPO / "eval" / "docs"
_OUT = Path(__file__).parent / "router_training_data.csv"


def _doc_type(label: dict[str, object], doc_name: str) -> str:
    meta = label.get("_meta") or {}
    if isinstance(meta, dict) and meta.get("doc_type"):
        return str(meta["doc_type"])
    return "bank_statement" if doc_name.startswith("bankstmt") else "invoice"


def _extract_page0_text(pdf_path: Path, max_chars: int = 1024) -> str:
    try:
        doc = pdfium.PdfDocument(str(pdf_path))
        page = doc[0]
        tp = page.get_textpage()
        return tp.get_text_range()[:max_chars]
    except Exception as exc:
        print(f"  WARN  {pdf_path.name}: {exc}", file=sys.stderr)
        return ""


def main() -> None:
    label_files = sorted(_LABELS.glob("*.json"))
    if not label_files:
        sys.exit("No label files found in eval/labels/")

    rows: list[tuple[str, str, str]] = []
    skipped = 0

    for lf in label_files:
        label = json.loads(lf.read_text(encoding="utf-8"))
        doc_name = lf.stem + ".pdf"
        pdf_path = _DOCS / doc_name
        if not pdf_path.exists():
            skipped += 1
            continue
        doc_type = _doc_type(label, lf.stem)
        text = _extract_page0_text(pdf_path)
        if text.strip():
            rows.append((doc_name, text, doc_type))
        else:
            skipped += 1

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    with _OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["doc_name", "text", "label"])
        writer.writerows(rows)

    by_type: dict[str, int] = {}
    for _, _, t in rows:
        by_type[t] = by_type.get(t, 0) + 1

    print(f"Wrote {len(rows)} rows to {_OUT.relative_to(_REPO)}")
    for t, n in sorted(by_type.items()):
        print(f"  {t}: {n}")
    if skipped:
        print(f"  skipped (missing PDF or no text): {skipped}")


if __name__ == "__main__":
    main()
