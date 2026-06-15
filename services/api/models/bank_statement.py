"""Pydantic v2 schema for bank-statement extraction — M1.

Account numbers are PII and must be masked before persistence/display.
Call mask_account_number() on any BankStatementExtraction before storing.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field


class StatementPeriod(BaseModel):
    start: str | None = Field(None, description="Period start date as YYYY-MM-DD")
    end: str | None = Field(None, description="Period end date as YYYY-MM-DD")


class Transaction(BaseModel):
    date: str | None = Field(None, description="Transaction date as YYYY-MM-DD")
    narration: str | None = Field(None, description="Transaction description / reference text")
    debit: float | None = Field(None, description="Debit amount (None if credit transaction)")
    credit: float | None = Field(None, description="Credit amount (None if debit transaction)")
    balance: float | None = Field(None, description="Running balance after this transaction")
    ref_no: str | None = Field(None, description="Bank reference / cheque number")


class BankStatementExtraction(BaseModel):
    """Structured extraction output for a bank statement document.

    account_number is PII — always call mask_account_number() before storing.
    """

    account_holder_name: str | None = Field(None, description="Name on the account")
    account_number: str | None = Field(
        None, description="Full account number — mask before persistence"
    )
    bank_name: str | None = Field(None, description="Name of the bank")
    ifsc: str | None = Field(None, description="IFSC code (India-specific)")
    statement_period: StatementPeriod | None = Field(None, description="Statement date range")
    opening_balance: float | None = Field(None, description="Balance at period start")
    closing_balance: float | None = Field(None, description="Balance at period end")
    currency: str | None = Field(None, description="ISO 4217 currency code")
    transactions: list[Transaction] = Field(
        default_factory=list, description="All transactions in the statement period"
    )


# ── PII masking ───────────────────────────────────────────────────────────────

_ACCOUNT_MASK_RE = re.compile(r"\d")


def mask_account_number(account_number: str, visible_digits: int = 4) -> str:
    """Mask all but the last *visible_digits* of an account number.

    Example: "123456789012" → "XXXXXXXX9012"
    Preserves non-digit characters (hyphens, spaces) positionally.
    """
    digits = [c for c in account_number if c.isdigit()]
    keep_from = max(0, len(digits) - visible_digits)
    masked_digits = ["X"] * keep_from + digits[keep_from:]

    result: list[str] = []
    digit_idx = 0
    for char in account_number:
        if char.isdigit():
            result.append(masked_digits[digit_idx])
            digit_idx += 1
        else:
            result.append(char)
    return "".join(result)


def mask_statement(statement: BankStatementExtraction) -> BankStatementExtraction:
    """Return a copy of *statement* with account_number masked."""
    data = statement.model_dump()
    if data.get("account_number"):
        data["account_number"] = mask_account_number(data["account_number"])
    return BankStatementExtraction.model_validate(data)
