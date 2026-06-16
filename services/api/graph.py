"""LangGraph orchestration — M3.

Wires Router -> Extractor -> Verifier -> Gate -> Aggregator into a single
graph that dispatches by doc type, so a caller no longer needs to know in
advance whether a document is an invoice or a bank statement.

The Extractor/Verifier/Gate stages reuse the already-tested
extract_invoice() / extract_bank_statement() pipelines from
services.api.extractor verbatim (each already chains its own VLM calls,
retries, and Langfuse traces) — the graph's job is purely the doc-type
routing and result aggregation that those functions don't do on their own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from services.api.clients.base import VLMClient
from services.api.extractor import extract_bank_statement, extract_invoice
from services.api.ingest import load_document
from services.api.models.bank_statement import BankStatementExtraction
from services.api.models.router import DocType
from services.api.models.verified_invoice import VerifiedInvoiceExtraction
from services.api.nodes.router import classify_doc_type


class GraphState(TypedDict, total=False):
    doc_path: str
    pages: list[Any]  # list[PIL.Image.Image]; Any avoids a hard PIL import in the TypedDict
    doc_type: DocType
    router_confidence: float
    invoice_result: VerifiedInvoiceExtraction
    bank_statement_result: BankStatementExtraction


class ExtractionResult(BaseModel):
    """Unified graph output — exactly one of invoice/bank_statement is set."""

    model_config = {"arbitrary_types_allowed": True}

    doc_type: DocType
    router_confidence: float
    invoice: VerifiedInvoiceExtraction | None = None
    bank_statement: BankStatementExtraction | None = None


def _route_by_doc_type(state: GraphState) -> str:
    return "extract_invoice" if state["doc_type"] == "invoice" else "extract_bank_statement"


def build_graph(client: VLMClient, confidence_threshold: float | None = None) -> Any:
    """Compile the Router->Extractor(->Verifier->Gate)->Aggregator graph for *client*."""

    async def router_node(state: GraphState) -> dict[str, Any]:
        classification = await classify_doc_type(state["pages"], client)
        return {"doc_type": classification.doc_type, "router_confidence": classification.confidence}

    async def extract_invoice_node(state: GraphState) -> dict[str, Any]:
        result = await extract_invoice(
            state["doc_path"], client, confidence_threshold=confidence_threshold
        )
        return {"invoice_result": result}

    async def extract_bank_statement_node(state: GraphState) -> dict[str, Any]:
        result = await extract_bank_statement(state["doc_path"], client)
        return {"bank_statement_result": result}

    graph = StateGraph(GraphState)
    graph.add_node("router", router_node)
    graph.add_node("extract_invoice", extract_invoice_node)
    graph.add_node("extract_bank_statement", extract_bank_statement_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_by_doc_type,
        {"extract_invoice": "extract_invoice", "extract_bank_statement": "extract_bank_statement"},
    )
    graph.add_edge("extract_invoice", END)
    graph.add_edge("extract_bank_statement", END)

    return graph.compile()


async def run_extraction_pipeline(
    path: str | Path,
    client: VLMClient,
    confidence_threshold: float | None = None,
) -> ExtractionResult:
    """Ingest *path*, route it by doc type, extract, and return a unified result.

    Args:
        path: Path to a PDF or image file (invoice or bank statement).
        client: VLMClient implementation to use throughout the graph.
        confidence_threshold: Gate threshold for the invoice path; defaults
            to the CONFIDENCE_THRESHOLD env var (see services.api.nodes.gate).

    Returns:
        ExtractionResult with doc_type + router_confidence, and exactly one
        of .invoice / .bank_statement populated.

    Raises:
        IngestError: File not found or unsupported format.
        VLMError: Non-recoverable API error in any stage.
    """
    # Loaded here for the router's first-page peek; extract_invoice/extract_bank_statement
    # reload it themselves, so multi-page PDFs render twice. Accepted for now to keep
    # reusing those already-tested pipelines verbatim instead of re-deriving them inline.
    pages = load_document(path)
    graph = build_graph(client, confidence_threshold)
    final_state: GraphState = await graph.ainvoke({"doc_path": str(path), "pages": pages})

    return ExtractionResult(
        doc_type=final_state["doc_type"],
        router_confidence=final_state["router_confidence"],
        invoice=final_state.get("invoice_result"),
        bank_statement=final_state.get("bank_statement_result"),
    )
