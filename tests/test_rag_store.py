"""Tests for services.api.rag.store (M3) — mocked Engine/Session, no real DB.

pgvector's Vector type and cosine_distance() are Postgres-specific and
can't be exercised against SQLite, so these tests verify the ingest/
retrieve functions build the right calls rather than running real SQL.
A live integration test against a real Neon instance is not included here
since DATABASE_URL is still the .env.example placeholder (see
eval/REPORT.md / CLAUDE.md's M3 status note).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import services.api.rag.store as store_module
from services.api.rag.store import Exemplar, get_engine, ingest_exemplar, retrieve_similar


@pytest.fixture(autouse=True)
def _reset_engine_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_module, "_engine", None)


def test_get_engine_raises_when_database_url_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        get_engine()


def test_get_engine_raises_on_example_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:password@host/dbname?sslmode=require"
    )

    with pytest.raises(RuntimeError, match="real connection string"):
        get_engine()


def test_get_engine_constructs_once_for_real_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@real-host/db")
    with patch.object(store_module, "create_engine") as mock_create:
        mock_create.return_value = MagicMock()
        first = get_engine()
        second = get_engine()

    mock_create.assert_called_once()
    assert first is second


def test_ingest_exemplar_adds_and_commits() -> None:
    mock_engine = MagicMock()
    with patch.object(store_module, "Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_session

        ingest_exemplar(
            doc_type="invoice",
            source_doc_name="invoice_001.pdf",
            embedding=[0.1, 0.2],
            extracted_fields={"vendor_name": "Acme"},
            engine=mock_engine,
        )

    mock_session.add.assert_called_once()
    added = mock_session.add.call_args.args[0]
    assert isinstance(added, Exemplar)
    assert added.doc_type == "invoice"
    assert added.source_doc_name == "invoice_001.pdf"
    assert added.embedding == [0.1, 0.2]
    assert added.extracted_fields == {"vendor_name": "Acme"}
    mock_session.commit.assert_called_once()


def test_retrieve_similar_queries_and_returns_scalars() -> None:
    mock_engine = MagicMock()
    expected = [MagicMock(spec=Exemplar)]
    with patch.object(store_module, "Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.scalars.return_value = expected
        mock_session_cls.return_value.__enter__.return_value = mock_session

        result = retrieve_similar(
            query_embedding=[0.1, 0.2], doc_type="invoice", k=5, engine=mock_engine
        )

    assert result == expected
    mock_session.scalars.assert_called_once()
