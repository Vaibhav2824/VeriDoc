"""Document ingestion: PDF or image → list of per-page PIL Images.

Supports PDF (multi-page via pypdfium2) and common image formats
(single-page: PNG, JPEG, TIFF, BMP, WEBP).  All downstream code
receives a uniform list[PIL.Image.Image] regardless of source format.
"""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

_PDF_SUFFIX = ".pdf"
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
_RENDER_DPI = 150  # readable text without ballooning memory


class IngestError(ValueError):
    """Raised when a document cannot be loaded or has an unsupported format."""


def load_document(path: str | Path) -> list[Image.Image]:
    """Load *path* and return one PIL Image per page.

    Args:
        path: Filesystem path to a PDF or image file.

    Returns:
        Ordered list of PIL Images; always at least one element.

    Raises:
        IngestError: File not found, unreadable, or unsupported format.
    """
    p = Path(path)
    if not p.exists():
        raise IngestError(f"File not found: {p}")

    suffix = p.suffix.lower()

    if suffix == _PDF_SUFFIX:
        return _load_pdf(p)
    if suffix in _IMAGE_SUFFIXES:
        return _load_image(p)

    raise IngestError(
        f"Unsupported file format '{suffix}'. "
        f"Supported: PDF, {', '.join(sorted(_IMAGE_SUFFIXES))}"
    )


def _load_pdf(path: Path) -> list[Image.Image]:
    scale = _RENDER_DPI / 72.0  # pypdfium2 renders at 72 DPI by default
    try:
        doc = pdfium.PdfDocument(str(path))
    except Exception as exc:
        raise IngestError(f"Could not open PDF '{path}': {exc}") from exc

    pages: list[Image.Image] = []
    try:
        for page in doc:
            bitmap = page.render(scale=scale, rotation=0)
            pages.append(bitmap.to_pil())
    finally:
        doc.close()

    if not pages:
        raise IngestError(f"PDF '{path}' contains no renderable pages.")
    return pages


def _load_image(path: Path) -> list[Image.Image]:
    try:
        img = Image.open(path)
        img.load()  # force decode; catches corrupt files early
        return [img.convert("RGB")]
    except Exception as exc:
        raise IngestError(f"Could not open image '{path}': {exc}") from exc
