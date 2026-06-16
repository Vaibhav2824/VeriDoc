"""Import ground-truth bank-statement labels + docs from a downloaded batch.

Expects PDF+JSON pairs as published by AgamiAI/Indian-Bank-Statements on
Hugging Face (https://huggingface.co/datasets/AgamiAI/Indian-Bank-Statements),
laid out as <root>/<Subtype>/NNNNN.pdf + NNNNN.json. Converts each JSON file
into an eval/labels/<stem>.json file matching the bank-statement label schema
(BankStatementExtraction fields), and copies the matching PDF into eval/docs/.

Labels are tagged with _meta.doc_type = "bank_statement" so eval/run.py
(invoice-only) and eval/run_bank.py (bank-statement-only) can each filter
the shared eval/labels/ directory to just the docs they know how to score.
Two transaction shapes are normalized: "Type1" (separate debit/credit/balance
fields) and "Type2" (cr_dr + transaction_amount + available_balance).

Usage:
    uv run python scripts/import_bank_statement_batch.py "samples/Bank Statements Batch 1"
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).parent.parent
_DOCS_DIR = _REPO_ROOT / "eval" / "docs"
_LABELS_DIR = _REPO_ROOT / "eval" / "labels"


def _parse_date(value: str | None) -> str | None:
    """Parse 'YYYY-MM-DD[ HH:MM:SS]' or 'DD/MM/YYYY' -> ISO 'YYYY-MM-DD'."""
    if not value:
        return None
    date_part = value.strip().split(" ")[0]
    if "-" in date_part:
        return date_part
    if "/" in date_part:
        dd, mm, yyyy = date_part.split("/")
        return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    return date_part


def _normalize_ref_no(value: str | None) -> str | None:
    return None if value in (None, "", "-") else value


def _normalize_transaction(raw: dict[str, Any]) -> dict[str, Any]:
    if "cr_dr" in raw:  # Type2 shape: single signed amount + running balance
        amount = raw.get("transaction_amount")
        debit = amount if raw.get("cr_dr") == "DR" else None
        credit = amount if raw.get("cr_dr") == "CR" else None
        balance = raw.get("available_balance")
    else:  # Type1 shape: separate debit/credit/balance fields
        debit = raw.get("debit")
        credit = raw.get("credit")
        balance = raw.get("balance")

    return {
        "date": _parse_date(raw.get("value_date") or raw.get("date")),
        "narration": raw.get("description"),
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "ref_no": _normalize_ref_no(raw.get("cheque_no")),
    }


def _row_to_label(raw: dict[str, Any], doc_file: str) -> dict[str, Any]:
    transactions = [_normalize_transaction(t) for t in raw.get("transactions", [])]

    return {
        "_meta": {
            "doc_file": doc_file,
            "doc_type": "bank_statement",
            "labeled_by": "huggingface_ground_truth",
            "labeled_at": "2026-06-17",
            "note": "Auto-generated from AgamiAI/Indian-Bank-Statements ground truth",
        },
        "account_holder_name": raw.get("account_holder"),
        "account_number": raw.get("account_number"),
        "bank_name": raw.get("bank_name"),
        "ifsc": raw.get("ifsc_code"),
        "statement_period": {
            "start": raw.get("start_date"),
            "end": raw.get("end_date"),
        },
        "opening_balance": raw.get("opening_balance"),
        "closing_balance": raw.get("closing_balance"),
        "currency": raw.get("currency"),
        "transactions": transactions,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: uv run python scripts/import_bank_statement_batch.py "
            '"samples/Bank Statements Batch 1"',
            file=sys.stderr,
        )
        return 1

    root = Path(sys.argv[1])
    json_files = sorted(root.glob("*/*.json"))
    if not json_files:
        print(f"No JSON files found under {root}/*/*.json", file=sys.stderr)
        return 1

    _LABELS_DIR.mkdir(parents=True, exist_ok=True)
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)

    written, copied, failed = 0, 0, []
    for json_path in json_files:
        subtype = json_path.parent.name  # e.g. "Digital_Type1"
        stem = f"bankstmt_{subtype.lower()}_{json_path.stem}"
        doc_file = f"{stem}.pdf"

        try:
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            label = _row_to_label(raw, doc_file)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            failed.append(f"{json_path}: {exc}")
            continue

        (_LABELS_DIR / f"{stem}.json").write_text(
            json.dumps(label, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written += 1

        src_pdf = json_path.with_suffix(".pdf")
        if src_pdf.exists():
            shutil.copyfile(src_pdf, _DOCS_DIR / doc_file)
            copied += 1

    print(f"Labels written: {written}/{len(json_files)}")
    print(f"PDFs copied:    {copied}/{len(json_files)}")
    if failed:
        print(f"\nFailed rows ({len(failed)}):")
        for failure in failed:
            print(f"  - {failure}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
