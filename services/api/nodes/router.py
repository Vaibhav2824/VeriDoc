"""Router node — M3.

Classifies a document as "invoice" or "bank_statement".

Two paths:
  1. Fine-tuned artifact (fast path) — TF-IDF + LogisticRegression trained
     on 130 labeled docs. Loads from training/artifacts/ at first call.
     <1 ms per doc, zero API tokens. Confidence is the model's class probability.
  2. VLM prompt (fallback) — sends the first page image to the configured
     VLMClient. Used when the artifact is absent or text extraction fails.

The artifact path is tried first when:
  - training/artifacts/router_tfidf.pkl + router_clf.pkl exist
  - doc_path is provided (so text can be extracted with pypdfium2)
  - sklearn and pypdfium2 are importable (always true in this project)
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

from PIL import Image

from services.api.clients.base import VLMClient
from services.api.models.router import DocType, DocTypeClassification

log = logging.getLogger(__name__)

_ARTIFACTS = Path(__file__).parent.parent.parent.parent / "training" / "artifacts"
_TFIDF_PATH = _ARTIFACTS / "router_tfidf.pkl"
_CLF_PATH = _ARTIFACTS / "router_clf.pkl"

# Lazy-loaded artifact (None = not yet attempted; False = unavailable)
_tfidf: Any = None
_clf: Any = None
_artifact_checked: bool = False

_ROUTER_INSTRUCTION = """\
You are a document classification assistant.

Look at the page image and decide whether this document is an "invoice"
(a bill for goods/services, with line items, a vendor and a buyer, a total
amount due) or a "bank_statement" (an account summary showing a list of
transactions, an opening and closing balance, over a statement period).

Return doc_type as exactly "invoice" or "bank_statement", and a confidence
score [0.0-1.0] reflecting how certain you are.
"""


def _load_artifact() -> bool:
    """Try to load the fine-tuned TF-IDF + LR artifacts. Returns True if loaded."""
    global _tfidf, _clf, _artifact_checked
    if _artifact_checked:
        return _tfidf is not None

    _artifact_checked = True
    if not (_TFIDF_PATH.exists() and _CLF_PATH.exists()):
        log.debug("Router artifacts not found at %s — using VLM fallback", _ARTIFACTS)
        return False

    try:
        import sklearn  # noqa: F401

        _tfidf = pickle.loads(_TFIDF_PATH.read_bytes())  # noqa: S301
        _clf = pickle.loads(_CLF_PATH.read_bytes())  # noqa: S301
        log.info("Loaded fine-tuned router from %s", _ARTIFACTS)
        return True
    except Exception:
        log.warning("Failed to load router artifact — using VLM fallback", exc_info=True)
        _tfidf = None
        _clf = None
        return False


def _classify_with_artifact(doc_path: str) -> DocTypeClassification | None:
    """Return a classification using the fine-tuned artifact, or None on failure."""
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(doc_path)
        page = doc[0]
        tp = page.get_textpage()
        text = tp.get_text_range()[:1024]
        if not text.strip():
            return None

        vec = _tfidf.transform([text])
        proba = _clf.predict_proba(vec)[0]
        classes: list[str] = list(_clf.classes_)
        pred_idx = int(proba.argmax())
        pred_label: DocType = classes[pred_idx]  # type: ignore[assignment]
        confidence = float(proba[pred_idx])

        log.debug(
            "Artifact router: %s → %s (%.3f)", Path(doc_path).name, pred_label, confidence
        )
        return DocTypeClassification(doc_type=pred_label, confidence=confidence)
    except Exception:
        log.debug("Artifact classification failed — falling back to VLM", exc_info=True)
        return None


async def classify_doc_type(
    pages: list[Image.Image],
    client: VLMClient,
    max_retries: int = 2,
    doc_path: str | None = None,
) -> DocTypeClassification:
    """Classify the document type (invoice vs bank_statement).

    Tries the fine-tuned artifact first (fast, free). Falls back to a VLM
    call if the artifact is unavailable or text extraction yields nothing.

    Args:
        pages: Per-page PIL Images (only pages[0] is used by the VLM fallback).
        client: VLMClient to use if the VLM fallback is needed.
        max_retries: Retries for the VLM fallback call.
        doc_path: Path to the source PDF; required for the artifact path.

    Returns:
        DocTypeClassification with doc_type + confidence.

    Raises:
        VLMError: All retries exhausted (VLM fallback only).
    """
    if doc_path and _load_artifact():
        result = _classify_with_artifact(doc_path)
        if result is not None:
            return result

    return await client.extract_structured(
        pages[:1],
        DocTypeClassification,
        max_retries=max_retries,
        instruction=_ROUTER_INSTRUCTION,
    )
