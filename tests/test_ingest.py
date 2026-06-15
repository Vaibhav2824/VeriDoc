"""Tests for services.api.ingest — document loading and normalisation."""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image

from services.api.ingest import IngestError, load_document

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_png(tmp_path: Path, width: int = 100, height: int = 80) -> Path:
    """Write a small solid-colour PNG and return its path."""
    img = Image.new("RGB", (width, height), color=(200, 100, 50))
    out = tmp_path / "test.png"
    img.save(out)
    return out


def _make_pdf(tmp_path: Path, n_pages: int = 1) -> Path:
    """Write a minimal PDF with *n_pages* blank pages and return its path."""
    doc = pdfium.PdfDocument.new()
    for _ in range(n_pages):
        doc.new_page(width=595, height=842)  # A4 in points
    out = tmp_path / "test.pdf"
    doc.save(str(out))
    doc.close()
    return out


# ── single-page image tests ───────────────────────────────────────────────────


def test_load_png_returns_one_image(tmp_path: Path) -> None:
    png = _make_png(tmp_path)
    pages = load_document(png)
    assert len(pages) == 1
    assert isinstance(pages[0], Image.Image)


def test_load_png_mode_is_rgb(tmp_path: Path) -> None:
    png = _make_png(tmp_path)
    pages = load_document(png)
    assert pages[0].mode == "RGB"


def test_load_jpeg(tmp_path: Path) -> None:
    img = Image.new("RGB", (80, 60), color=(10, 20, 30))
    jpg = tmp_path / "test.jpg"
    img.save(jpg, format="JPEG")
    pages = load_document(jpg)
    assert len(pages) == 1


def test_load_accepts_string_path(tmp_path: Path) -> None:
    png = _make_png(tmp_path)
    pages = load_document(str(png))  # str, not Path
    assert len(pages) == 1


# ── PDF tests ─────────────────────────────────────────────────────────────────


def test_load_single_page_pdf(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, n_pages=1)
    pages = load_document(pdf)
    assert len(pages) == 1
    assert isinstance(pages[0], Image.Image)


def test_load_multi_page_pdf(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, n_pages=3)
    pages = load_document(pdf)
    assert len(pages) == 3


def test_pdf_pages_are_rgb(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, n_pages=2)
    pages = load_document(pdf)
    assert all(p.mode == "RGB" for p in pages)


def test_pdf_pages_have_nonzero_dimensions(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, n_pages=1)
    pages = load_document(pdf)
    w, h = pages[0].size
    assert w > 0 and h > 0


# ── error handling ────────────────────────────────────────────────────────────


def test_missing_file_raises_ingest_error(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="not found"):
        load_document(tmp_path / "nonexistent.pdf")


def test_unsupported_extension_raises_ingest_error(tmp_path: Path) -> None:
    bad = tmp_path / "doc.docx"
    bad.write_bytes(b"fake")
    with pytest.raises(IngestError, match="Unsupported"):
        load_document(bad)


def test_corrupt_image_raises_ingest_error(tmp_path: Path) -> None:
    bad = tmp_path / "corrupt.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)  # truncated PNG
    with pytest.raises(IngestError):
        load_document(bad)
