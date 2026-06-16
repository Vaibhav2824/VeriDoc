"""MCP server exposing VeriDoc's document extraction as MCP tools — M3.

Run with:
    uv run python -m services.mcp.server

Exposes three tools to MCP-compatible clients (Claude Desktop, etc.):
  - extract_document: auto-detects invoice vs bank statement (LangGraph router)
  - extract_invoice: extract assuming the doc is an invoice (skips the router)
  - extract_bank_statement: extract assuming the doc is a bank statement (skips the router)

Requires GROQ_API_KEY or GEMINI_API_KEY in the environment or .env file.
"""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from services.api.clients import make_client
from services.api.clients.base import VLMClient
from services.api.extractor import extract_bank_statement as _extract_bank_statement_pipeline
from services.api.extractor import extract_invoice as _extract_invoice_pipeline
from services.api.graph import run_extraction_pipeline

load_dotenv()

mcp = FastMCP(
    "VeriDoc",
    instructions=(
        "Extracts structured, trust-scored fields from invoices and bank statements. "
        "Every invoice field carries a calibrated confidence and source location; "
        "low-confidence fields are abstained rather than guessed."
    ),
)

_client: VLMClient | None = None


def _get_client() -> VLMClient:
    """Lazily construct the shared VLMClient (avoids re-reading env on every call)."""
    global _client
    if _client is None:
        _client = make_client()
    return _client


@mcp.tool()
async def extract_document(path: str) -> dict[str, Any]:
    """Classify a document (invoice or bank statement) and extract its fields.

    Args:
        path: Filesystem path to a PDF or image file.

    Returns:
        doc_type, router_confidence, and the extracted result for that type.
        Invoice fields carry confidence + source_location + status (fields
        below the confidence threshold are abstained rather than auto-accepted);
        bank statement fields do not yet (its verifier is a later milestone).
    """
    result = await run_extraction_pipeline(path, _get_client())
    return result.model_dump()


@mcp.tool()
async def extract_invoice(path: str) -> dict[str, Any]:
    """Extract invoice fields, assuming *path* is already known to be an invoice.

    Skips the doc-type router. Every field carries a calibrated confidence,
    source location, and status; fields below the confidence threshold are
    abstained rather than auto-accepted.
    """
    result = await _extract_invoice_pipeline(path, _get_client())
    return result.model_dump()


@mcp.tool()
async def extract_bank_statement(path: str) -> dict[str, Any]:
    """Extract bank statement fields, assuming *path* is already known to be a
    bank statement. Skips the doc-type router. The account number is PII-masked
    before being returned.
    """
    result = await _extract_bank_statement_pipeline(path, _get_client())
    return result.model_dump()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
