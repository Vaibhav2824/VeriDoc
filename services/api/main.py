"""FastAPI application — M4.

Endpoints:
  POST /v1/extract              Upload a document; returns {job_id} immediately.
                                Extraction runs as a background task.
  GET  /v1/jobs/{job_id}        Job status + result when done.
  GET  /v1/queue                All review-queue items across completed jobs.
  POST /v1/queue/{job_id}/{field}/resolve
                                Mark a review-queue item as resolved.

Run:
  uv run uvicorn services.api.main:app --reload
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

log = logging.getLogger("veridoc.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="VeriDoc API",
    description="Agentic VLM document extraction with calibrated confidence + abstention.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for prod
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB init (best-effort; API works without DB for demo purposes) ─────────────

_db_available = False


def _try_init_db() -> None:
    global _db_available
    try:
        from services.api.db import init_schema
        init_schema()
        _db_available = True
        log.info("DB schema initialised")
    except Exception as exc:
        log.warning("DB unavailable (%s) — jobs will not be persisted", exc)


@app.on_event("startup")
async def _startup() -> None:
    _try_init_db()


# ── Background extraction task ────────────────────────────────────────────────

async def _run_extraction(job_id: str, tmp_path: str, doc_name: str) -> None:
    from services.api.clients import make_client
    from services.api.graph import run_extraction_pipeline
    from services.api.models.review_queue import build_review_queue

    confidence_threshold = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.80"))

    if _db_available:
        from services.api.db import update_job
        update_job(job_id, status="running", event_type="extraction_started",
                   event_payload={"doc_name": doc_name})

    t0 = time.time()
    try:
        client = make_client()
        result = await run_extraction_pipeline(tmp_path, client, confidence_threshold)

        # Build review queue
        source = result.invoice or result.bank_statement
        queue_items: list[dict[str, Any]] = []
        if source is not None:
            queue = build_review_queue(source, doc_name, confidence_threshold)
            queue_items = [item.model_dump() for item in queue.items]

        result_dict: dict[str, Any] = {
            "doc_type": result.doc_type,
            "router_confidence": result.router_confidence,
        }
        if result.invoice is not None:
            result_dict["invoice"] = result.invoice.model_dump()
        if result.bank_statement is not None:
            result_dict["bank_statement"] = result.bank_statement.model_dump()

        elapsed = time.time() - t0
        if _db_available:
            from services.api.db import update_job
            update_job(
                job_id,
                status="done",
                doc_type=result.doc_type,
                result_json=result_dict,
                review_queue_json=queue_items,
                processing_time_s=elapsed,
                event_type="extraction_done",
                event_payload={"doc_type": result.doc_type,
                               "queue_items": len(queue_items),
                               "processing_time_s": round(elapsed, 2)},
            )
        else:
            _in_memory[job_id] = {"status": "done", "doc_name": doc_name,
                                   "result": result_dict, "queue": queue_items,
                                   "processing_time_s": elapsed}

    except Exception as exc:
        log.exception("Extraction failed for job %s", job_id)
        elapsed = time.time() - t0
        if _db_available:
            from services.api.db import update_job
            update_job(job_id, status="failed", error_message=str(exc),
                       processing_time_s=elapsed,
                       event_type="extraction_failed",
                       event_payload={"error": str(exc)[:500]})
        else:
            _in_memory[job_id] = {"status": "failed", "doc_name": doc_name,
                                   "error": str(exc)}
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


# In-memory fallback when DB is not available
_in_memory: dict[str, Any] = {}


# ── Endpoints ─────────────────────────────────────────────────────────────────

class ExtractResponse(BaseModel):
    job_id: str
    message: str = "Extraction started"


@app.post("/v1/extract", response_model=ExtractResponse, status_code=202)
async def extract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> ExtractResponse:
    """Upload a PDF or image; returns a job_id immediately.

    The document type is detected automatically (invoice or bank statement).
    Poll GET /v1/jobs/{job_id} for results.
    """
    if not file.filename:
        raise HTTPException(400, "filename required")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    # Save to a temp file (the background task owns cleanup)
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    # Create job record
    doc_name = file.filename
    if _db_available:
        from services.api.db import create_job
        job_id = create_job(doc_name)
    else:
        import uuid
        job_id = str(uuid.uuid4())
        _in_memory[job_id] = {"status": "pending", "doc_name": doc_name}

    background_tasks.add_task(_run_extraction, job_id, tmp_path, doc_name)
    return ExtractResponse(job_id=job_id)


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Return job status and result (when status=done)."""
    if _db_available:
        from services.api.db import get_job as _get_job
        job = _get_job(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return {
            "job_id": job.id,
            "doc_name": job.doc_name,
            "status": job.status,
            "doc_type": job.doc_type,
            "result": job.result_json,
            "review_queue": job.review_queue_json or [],
            "error": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
    else:
        if job_id not in _in_memory:
            raise HTTPException(404, "Job not found")
        return {"job_id": job_id, **_in_memory[job_id]}


@app.get("/v1/queue")
async def get_queue() -> list[dict[str, Any]]:
    """Return all pending review-queue items across all completed jobs."""
    if _db_available:
        from services.api.db import list_queue_items
        return list_queue_items()
    items = []
    for jid, state in _in_memory.items():
        for item in state.get("queue", []):
            items.append({"job_id": jid, "doc_name": state.get("doc_name", ""), **item})
    return items


class ResolveRequest(BaseModel):
    corrected_value: Any = None
    resolved_by: str = "human"


@app.post("/v1/queue/{job_id}/{field_name}/resolve")
async def resolve_queue_item(
    job_id: str,
    field_name: str,
    body: ResolveRequest,
) -> dict[str, str]:
    """Mark a review-queue field as resolved (human-corrected)."""
    if _db_available:
        from services.api.db import get_job as _get_job
        from services.api.db import update_job
        job = _get_job(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        queue = job.review_queue_json or []
        updated = [
            {**item, "resolved": True, "corrected_value": body.corrected_value,
             "resolved_by": body.resolved_by}
            if item.get("field_name") == field_name else item
            for item in queue
        ]
        update_job(job_id, status=job.status, review_queue_json=updated,
                   event_type="field_resolved",
                   event_payload={"field_name": field_name,
                                  "resolved_by": body.resolved_by})
    return {"status": "resolved", "field_name": field_name, "job_id": job_id}


@app.get("/v1/stats")
async def get_stats() -> dict[str, Any]:
    """Aggregate stats: job counts, doc type breakdown, latency p95, queue size."""
    if _db_available:
        from services.api.db import get_stats as _get_stats
        return _get_stats()
    # in-memory fallback
    by_status: dict[str, int] = {}
    by_doc_type: dict[str, int] = {}
    times: list[float] = []
    queue_total = 0
    for state in _in_memory.values():
        s = state.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        dt = (state.get("result") or {}).get("doc_type")
        if dt:
            by_doc_type[str(dt)] = by_doc_type.get(str(dt), 0) + 1
        pt = state.get("processing_time_s")
        if pt is not None:
            times.append(float(pt))
        for item in state.get("queue", []):
            if not item.get("resolved"):
                queue_total += 1
    times_sorted = sorted(times)
    p95 = times_sorted[int(len(times_sorted) * 0.95)] if times_sorted else None
    avg = sum(times) / len(times) if times else None
    return {
        "total_jobs": len(_in_memory),
        "by_status": by_status,
        "by_doc_type": by_doc_type,
        "avg_processing_time_s": round(avg, 2) if avg is not None else None,
        "p95_processing_time_s": round(p95, 2) if p95 is not None else None,
        "pending_review_items": queue_total,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "db": "connected" if _db_available else "unavailable"}
