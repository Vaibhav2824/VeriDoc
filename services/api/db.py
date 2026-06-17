"""SQLAlchemy models for extraction jobs and immutable audit log — M4.

Schema:
  extraction_jobs — one row per uploaded document; status lifecycle:
                    pending → running → done | failed
  audit_events    — append-only log of every state change per job

Both tables live in the same Postgres instance as the pgvector exemplar
store (DATABASE_URL env var). init_schema() is idempotent — safe to call
at every startup.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, Text, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class ExtractionJob(Base):
    """Tracks one document's extraction lifecycle."""

    __tablename__ = "extraction_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    doc_name: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # pending | running | done | failed
    status: Mapped[str] = mapped_column(String(16), default="pending")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    review_queue_json: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_time_s: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuditEvent(Base):
    """Immutable append-only audit log — one row per state change."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Engine management ─────────────────────────────────────────────────────────

_engine = None


def get_engine():  # type: ignore[no-untyped-def]
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "")
        if not url or "host/dbname" in url:
            raise RuntimeError("DATABASE_URL not configured")
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        _engine = create_engine(url)
    return _engine


def init_schema() -> None:
    """Create tables if they don't exist. Idempotent."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


# ── Job helpers ───────────────────────────────────────────────────────────────

def create_job(doc_name: str) -> str:
    """Insert a new pending job, return its UUID."""
    engine = get_engine()
    job = ExtractionJob(id=str(uuid4()), doc_name=doc_name, status="pending")
    with Session(engine) as s:
        s.add(job)
        s.add(AuditEvent(job_id=job.id, event_type="doc_received",
                         payload={"doc_name": doc_name}))
        s.commit()
    return job.id


def update_job(
    job_id: str,
    *,
    status: str,
    doc_type: str | None = None,
    result_json: dict[str, Any] | None = None,
    review_queue_json: list[dict[str, Any]] | None = None,
    error_message: str | None = None,
    processing_time_s: float | None = None,
    event_type: str,
    event_payload: dict[str, Any] | None = None,
) -> None:
    engine = get_engine()
    with Session(engine) as s:
        job = s.get(ExtractionJob, job_id)
        if job is None:
            return
        job.status = status
        job.updated_at = datetime.now(UTC)
        if doc_type is not None:
            job.doc_type = doc_type
        if result_json is not None:
            job.result_json = result_json
        if review_queue_json is not None:
            job.review_queue_json = review_queue_json
        if error_message is not None:
            job.error_message = error_message
        if processing_time_s is not None:
            job.processing_time_s = processing_time_s
        s.add(AuditEvent(job_id=job_id, event_type=event_type, payload=event_payload))
        s.commit()


def get_job(job_id: str) -> ExtractionJob | None:
    engine = get_engine()
    with Session(engine) as s:
        return s.get(ExtractionJob, job_id)


def get_stats() -> dict[str, Any]:
    """Aggregate stats across all jobs — used by /v1/stats."""
    from sqlalchemy import select
    engine = get_engine()
    with Session(engine) as s:
        jobs = s.scalars(select(ExtractionJob)).all()
        by_status: dict[str, int] = {}
        by_doc_type: dict[str, int] = {}
        times: list[float] = []
        queue_total = 0
        for job in jobs:
            by_status[job.status] = by_status.get(job.status, 0) + 1
            if job.doc_type:
                by_doc_type[job.doc_type] = by_doc_type.get(job.doc_type, 0) + 1
            if job.processing_time_s is not None:
                times.append(job.processing_time_s)
            for item in (job.review_queue_json or []):
                if not item.get("resolved"):
                    queue_total += 1
        times_sorted = sorted(times)
        p95 = times_sorted[int(len(times_sorted) * 0.95)] if times_sorted else None
        avg = sum(times) / len(times) if times else None
        return {
            "total_jobs": len(jobs),
            "by_status": by_status,
            "by_doc_type": by_doc_type,
            "avg_processing_time_s": round(avg, 2) if avg is not None else None,
            "p95_processing_time_s": round(p95, 2) if p95 is not None else None,
            "pending_review_items": queue_total,
        }


def list_queue_items() -> list[dict[str, Any]]:
    """Return all review queue items across all done jobs."""
    from sqlalchemy import select
    engine = get_engine()
    with Session(engine) as s:
        jobs = s.scalars(
            select(ExtractionJob).where(
                ExtractionJob.status == "done",
                ExtractionJob.review_queue_json.isnot(None),
            )
        ).all()
        items = []
        for job in jobs:
            for item in (job.review_queue_json or []):
                items.append({"job_id": job.id, "doc_name": job.doc_name, **item})
        return items
