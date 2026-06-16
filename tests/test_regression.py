"""Tests for eval.regression's pass/fail decision logic (M3)."""

from __future__ import annotations

from eval.regression import check_regression


def test_passes_at_baseline() -> None:
    passed, _ = check_regression(0.98, baseline=0.98, tolerance=0.02)
    assert passed is True


def test_passes_within_tolerance() -> None:
    passed, _ = check_regression(0.97, baseline=0.98, tolerance=0.02)
    assert passed is True


def test_passes_above_baseline() -> None:
    passed, _ = check_regression(1.0, baseline=0.98, tolerance=0.02)
    assert passed is True


def test_fails_below_tolerance() -> None:
    passed, message = check_regression(0.94, baseline=0.98, tolerance=0.02)
    assert passed is False
    assert "REGRESSION GATE FAILED" in message


def test_fails_at_exact_floor_boundary() -> None:
    """Floor is baseline - tolerance; a value equal to floor should pass (>=)."""
    passed, _ = check_regression(0.96, baseline=0.98, tolerance=0.02)
    assert passed is True


def test_fails_when_no_documents_evaluated() -> None:
    passed, message = check_regression(None, baseline=0.98, tolerance=0.02)
    assert passed is False
    assert "no documents were successfully evaluated" in message
