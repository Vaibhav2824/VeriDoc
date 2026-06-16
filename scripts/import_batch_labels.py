"""Import ground-truth labels + docs from a Kaggle batch CSV.

Converts each row of a `batch_N.csv` (columns: filename, json_data, ocred_text)
into an `eval/labels/<stem>.json` file matching the invoice label schema
(see eval/labels/README.md), and copies the matching PDF into `eval/docs/`.

This is how the original 10-doc M0/M1/M2 benchmark was built; this script
generalizes that conversion to the full batch so the benchmark can grow
toward the PRD's 50-100 (M1) / 300+ (M2) targets.

Usage:
    uv run python scripts/import_batch_labels.py "samples/Batch 1/batch_1.csv"
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_DOCS_DIR = _REPO_ROOT / "eval" / "docs"
_LABELS_DIR = _REPO_ROOT / "eval" / "labels"


def _parse_amount(s: str) -> float:
    """Parse a number like '1,676,976.00' or 'INR 1,676,976.00' -> float."""
    cleaned = re.sub(r"[^0-9.\-]", "", s)
    return float(cleaned)


def _parse_currency(s: str, default: str = "INR") -> str:
    m = re.match(r"^([A-Za-z]+)", s.strip())
    return m.group(1) if m else default


def _parse_date_ddmmyyyy(s: str) -> str | None:
    """Parse 'DD/MM/YYYY' -> ISO 'YYYY-MM-DD'. Returns None if unparseable."""
    parts = s.strip().split("/")
    if len(parts) != 3:
        return None
    dd, mm, yyyy = parts
    return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"


def _row_to_label(filename: str, raw: dict) -> dict:
    seller = raw.get("seller", {})
    client = raw.get("client", {})
    summary = raw.get("summary", {})
    items = raw.get("items", [])

    currency = _parse_currency(summary.get("total_gross_worth", "INR"))

    line_items = [
        {
            "description": item.get("description"),
            "hsn_sac": None,
            "quantity": _parse_amount(item["quantity"]) if item.get("quantity") else None,
            "unit_price": _parse_amount(item["net_price"]) if item.get("net_price") else None,
            "line_total": _parse_amount(item["net_worth"]) if item.get("net_worth") else None,
        }
        for item in items
    ]

    return {
        "_meta": {
            "doc_file": filename,
            "labeled_by": "csv_ground_truth",
            "labeled_at": "2026-06-16",
            "note": "Auto-generated from batch_1.csv ground truth",
        },
        "invoice_number": raw.get("invoice_no"),
        "invoice_date": (
            _parse_date_ddmmyyyy(raw["date_of_issue"]) if raw.get("date_of_issue") else None
        ),
        "due_date": None,
        "vendor_name": seller.get("name"),
        "vendor_gstin": seller.get("gstin"),
        "vendor_address": seller.get("address"),
        "buyer_name": client.get("name"),
        "buyer_gstin": None,
        "currency": currency,
        "subtotal": _parse_amount(summary["net_worth"]) if summary.get("net_worth") else None,
        "tax": {
            "cgst": None,
            "sgst": None,
            "igst": None,
            "total_tax": (
                _parse_amount(summary["vat_amount"]) if summary.get("vat_amount") else None
            ),
        },
        "total_amount": (
            _parse_amount(summary["gross_worth"]) if summary.get("gross_worth") else None
        ),
        "line_items": line_items,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(
            'Usage: uv run python scripts/import_batch_labels.py "samples/Batch 1/batch_1.csv"',
            file=sys.stderr,
        )
        return 1

    csv_path = Path(sys.argv[1])
    invoices_dir = csv_path.parent / "invoices"

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    _LABELS_DIR.mkdir(parents=True, exist_ok=True)
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)

    written, copied, failed = 0, 0, []
    for row in rows:
        filename = row["filename"]
        stem = Path(filename).stem
        try:
            raw = json.loads(row["json_data"])
            label = _row_to_label(filename, raw)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            failed.append(f"{filename}: {exc}")
            continue

        (_LABELS_DIR / f"{stem}.json").write_text(
            json.dumps(label, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written += 1

        src_pdf = invoices_dir / filename
        if src_pdf.exists():
            shutil.copyfile(src_pdf, _DOCS_DIR / filename)
            copied += 1

    print(f"Labels written: {written}/{len(rows)}")
    print(f"PDFs copied:    {copied}/{len(rows)}")
    if failed:
        print(f"\nFailed rows ({len(failed)}):")
        for failure in failed:
            print(f"  - {failure}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
