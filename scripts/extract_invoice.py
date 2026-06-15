"""CLI: extract invoice fields from a PDF or image and print JSON to stdout.

Usage:
    uv run python scripts/extract_invoice.py <path/to/invoice.pdf>
    uv run python scripts/extract_invoice.py <path/to/invoice.png>

Requires GROQ_API_KEY or GEMINI_API_KEY in the environment or .env file.
Copy .env.example → .env and fill in your key before running.

Exit codes:
    0  success
    1  usage error / file not found / API failure
"""

from __future__ import annotations

import asyncio
import json
import sys

from dotenv import load_dotenv

from services.api.clients import make_client
from services.api.clients.base import VLMError
from services.api.extractor import extract_invoice
from services.api.ingest import IngestError


async def _run(path: str) -> int:
    load_dotenv()
    try:
        client = make_client()
    except VLMError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    try:
        result = await extract_invoice(path, client)
    except IngestError as exc:
        print(f"[error] ingest failed: {exc}", file=sys.stderr)
        return 1
    except VLMError as exc:
        print(f"[error] VLM extraction failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: uv run python scripts/extract_invoice.py <path>",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(asyncio.run(_run(sys.argv[1])))


if __name__ == "__main__":
    main()
