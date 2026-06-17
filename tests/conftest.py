"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_rag_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear DATABASE_URL so RAG is never triggered in unit tests.

    Prevents tests from accidentally hitting the real Neon DB when the
    project's .env has DATABASE_URL set. Tests that need RAG override this
    via their own monkeypatch.setenv("DATABASE_URL", ...) call.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
