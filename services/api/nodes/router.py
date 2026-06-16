"""Router node — M3.

Classifies a document as "invoice" or "bank_statement" so the graph can
dispatch to the right extractor schema. Uses only the first page (cheap
call — classification doesn't need the full multi-page document) and is
the node intended for a future fine-tuned-on-Kaggle/Colab classifier
swap-in (see PRD §10 M3); the VLM-prompt version here is the baseline.
"""

from __future__ import annotations

from PIL import Image

from services.api.clients.base import VLMClient
from services.api.models.router import DocTypeClassification

_ROUTER_INSTRUCTION = """\
You are a document classification assistant.

Look at the page image and decide whether this document is an "invoice"
(a bill for goods/services, with line items, a vendor and a buyer, a total
amount due) or a "bank_statement" (an account summary showing a list of
transactions, an opening and closing balance, over a statement period).

Return doc_type as exactly "invoice" or "bank_statement", and a confidence
score [0.0-1.0] reflecting how certain you are.
"""


async def classify_doc_type(
    pages: list[Image.Image],
    client: VLMClient,
    max_retries: int = 2,
) -> DocTypeClassification:
    """Classify the document type from its first page.

    Args:
        pages: Per-page PIL Images (only pages[0] is sent to the VLM).
        client: VLMClient to use for classification.
        max_retries: Retries for the classification VLM call.

    Returns:
        DocTypeClassification with doc_type + confidence.

    Raises:
        VLMError: All retries exhausted or non-recoverable API error.
    """
    return await client.extract_structured(
        pages[:1],
        DocTypeClassification,
        max_retries=max_retries,
        instruction=_ROUTER_INSTRUCTION,
    )
