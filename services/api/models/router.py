"""Doc-type classification schema — M3.

Output of the Router node: which schema (invoice vs bank statement) the
Extractor node should use for this document.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DocType = Literal["invoice", "bank_statement"]


class DocTypeClassification(BaseModel):
    """Router output — the document type and how confident the call is."""

    doc_type: DocType
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
