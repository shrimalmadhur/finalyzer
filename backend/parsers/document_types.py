"""Pydantic models for LLM-based document parsing."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from backend.models import TransactionSource


class DocumentMetadata(BaseModel):
    """Metadata extracted from financial statement via LLM."""

    source: TransactionSource | Literal["UNKNOWN"]
    statement_year: int = Field(ge=2000, le=2100)
    statement_period: str
    document_type: str


class RawTransaction(BaseModel):
    """Raw transaction data extracted from statement via LLM."""

    date: date
    description: str = Field(min_length=1)
    amount: float
    raw_category: str | None = None
