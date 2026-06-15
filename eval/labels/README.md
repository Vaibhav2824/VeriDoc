# eval/labels — Ground Truth Format

Each file is a JSON label for one invoice document in `eval/docs/`.

**Naming:** `{doc_stem}.json` matches `eval/docs/{doc_stem}.pdf` (or .png).

## Schema

```json
{
  "_meta": {
    "doc_file": "invoice_001.pdf",
    "labeled_by": "human",
    "labeled_at": "2026-01-15",
    "note": "optional free-text note about this document"
  },
  "invoice_number": "INV-2024-001",
  "invoice_date": "2024-01-15",
  "due_date": null,
  "vendor_name": "ACME Supplies Pvt Ltd",
  "vendor_gstin": "27AABCU9603R1ZX",
  "vendor_address": "123 Industrial Area, Mumbai 400001",
  "buyer_name": "Beta Traders",
  "buyer_gstin": null,
  "currency": "INR",
  "subtotal": 10000.00,
  "tax": {
    "cgst": 900.00,
    "sgst": 900.00,
    "igst": null,
    "total_tax": 1800.00
  },
  "total_amount": 11800.00,
  "line_items": [
    {
      "description": "Steel Pipes 20mm",
      "hsn_sac": "7304",
      "quantity": 100,
      "unit_price": 100.00,
      "line_total": 10000.00
    }
  ]
}
```

## Rules

- Use `null` for fields absent or illegible in the document — **not** an empty string.
- Amounts: plain numbers, no currency symbols or commas (`11800.00` not `"₹ 11,800"`).
- Dates: ISO 8601 (`YYYY-MM-DD`). The harness normalises other formats but ISO is safest.
- `line_items`: include all rows visible in the document; omit `hsn_sac` (null) if not shown.
- `_meta.labeled_by`: your name — used for inter-annotator agreement tracking later.

## Workflow

```bash
# 1. Download Kaggle dataset (see below)
# 2. Generate a draft label for one doc:
uv run python scripts/create_label.py eval/docs/invoice_001.pdf

# 3. Edit the generated JSON — correct any wrong/missing values
# 4. Repeat steps 2-3 for each doc (~10 for the M0 baseline)

# 5. Run the eval harness to get the baseline number:
uv run python -m eval.run
```

## Kaggle dataset setup

Dataset: https://www.kaggle.com/datasets/devp1866/high-quality-ocr-ready-invoice-pdfs

```bash
# Option A — Kaggle CLI (recommended)
pip install kaggle
# Place your kaggle.json API token at ~/.kaggle/kaggle.json
kaggle datasets download devp1866/high-quality-ocr-ready-invoice-pdfs
unzip high-quality-ocr-ready-invoice-pdfs.zip -d eval/docs/

# Option B — manual
# Download the ZIP from the Kaggle page and extract PDFs to eval/docs/
```

Pick any 10 PDFs from the dataset for the M0 baseline.
