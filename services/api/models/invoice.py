"""Pydantic v2 schema for invoice extraction — M1.

All fields are Optional so missing values are None (abstained) rather than
validation errors.  The extractor populates these; the verifier (M2) adds
confidence scores and source_location to each field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str | None = None
    hsn_sac: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None


class TaxBreakdown(BaseModel):
    cgst: float | None = None
    sgst: float | None = None
    igst: float | None = None
    total_tax: float | None = None


class InvoiceExtraction(BaseModel):
    """Structured extraction output for an invoice document.

    All monetary amounts are plain floats (no currency symbols).
    Dates are ISO 8601 strings (YYYY-MM-DD) or None.
    """

    invoice_number: str | None = Field(None, description="Unique invoice identifier")
    invoice_date: str | None = Field(None, description="Issue date as YYYY-MM-DD")
    due_date: str | None = Field(None, description="Payment due date as YYYY-MM-DD")
    vendor_name: str | None = Field(None, description="Name of the selling party")
    vendor_gstin: str | None = Field(None, description="Seller's GST Identification Number")
    vendor_address: str | None = Field(None, description="Seller's full address")
    buyer_name: str | None = Field(None, description="Name of the buying party")
    buyer_gstin: str | None = Field(None, description="Buyer's GST Identification Number")
    currency: str | None = Field(None, description="ISO 4217 currency code, e.g. INR or USD")
    subtotal: float | None = Field(None, description="Pre-tax subtotal amount")
    tax: TaxBreakdown | None = Field(None, description="Tax breakdown (CGST/SGST/IGST)")
    total_amount: float | None = Field(None, description="Final invoice total including tax")
    line_items: list[LineItem] = Field(default_factory=list, description="Invoice line items")
