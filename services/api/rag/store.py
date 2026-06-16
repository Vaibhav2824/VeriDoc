"""pgvector exemplar store — M3 few-shot retrieval.

Stores successfully-extracted invoices as exemplars (embedding + extracted
fields) so similar past documents can be retrieved as few-shot context for
rare/unusual layouts (PRD §6.10). Requires a real DATABASE_URL pointing at
a Postgres instance with the pgvector extension available (e.g. Neon) —
see .env.example. This module is the standalone ingest/retrieve primitive;
it is not yet wired into the extraction pipeline's hot path.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Engine, String, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from services.api.models.router import DocType
from services.api.rag.embeddings import EMBEDDING_DIM


class Base(DeclarativeBase):
    pass


class Exemplar(Base):
    """One past document's embedding + extracted fields, for few-shot retrieval."""

    __tablename__ = "exemplars"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    source_doc_name: Mapped[str] = mapped_column(String(255))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine, constructing it on first use.

    Raises:
        RuntimeError: DATABASE_URL is unset or still the .env.example placeholder.
    """
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL", "")
        if not url or "host/dbname" in url:
            raise RuntimeError(
                "DATABASE_URL is not set to a real connection string. "
                "Copy .env.example -> .env and add your Neon Postgres URL."
            )
        _engine = create_engine(url)
    return _engine


def init_schema(engine: Engine | None = None) -> None:
    """Create the pgvector extension and the exemplars table if missing."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def ingest_exemplar(
    doc_type: DocType,
    source_doc_name: str,
    embedding: list[float],
    extracted_fields: dict[str, Any],
    engine: Engine | None = None,
) -> None:
    """Store a successfully-extracted document as a future few-shot exemplar."""
    engine = engine or get_engine()
    with Session(engine) as session:
        session.add(
            Exemplar(
                doc_type=doc_type,
                source_doc_name=source_doc_name,
                embedding=embedding,
                extracted_fields=extracted_fields,
            )
        )
        session.commit()


def retrieve_similar(
    query_embedding: list[float],
    doc_type: DocType,
    k: int = 3,
    engine: Engine | None = None,
) -> list[Exemplar]:
    """Return the *k* most similar past exemplars of *doc_type* by cosine distance."""
    engine = engine or get_engine()
    with Session(engine) as session:
        stmt = (
            select(Exemplar)
            .where(Exemplar.doc_type == doc_type)
            .order_by(Exemplar.embedding.cosine_distance(query_embedding))
            .limit(k)
        )
        return list(session.scalars(stmt))
