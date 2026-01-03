"""Data models for Finalyzer."""

from datetime import date
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TransactionSource(str, Enum):
    """Supported transaction sources."""

    CHASE_CREDIT = "chase_credit"
    AMEX = "amex"
    COINBASE = "coinbase"


class TransactionCategory(str, Enum):
    """Transaction categories assigned by LLM."""

    FOOD_DINING = "Food & Dining"
    SHOPPING = "Shopping"
    TRANSPORTATION = "Transportation"
    ENTERTAINMENT = "Entertainment"
    BILLS_UTILITIES = "Bills & Utilities"
    TRAVEL = "Travel"
    HEALTH = "Health"
    GROCERIES = "Groceries"
    GAS = "Gas"
    SUBSCRIPTIONS = "Subscriptions"
    INCOME = "Income"
    TRANSFER = "Transfer"
    OTHER = "Other"


class Transaction(BaseModel):
    """A financial transaction."""

    id: UUID = Field(default_factory=uuid4)
    source: TransactionSource
    source_file_hash: str  # SHA256 hash for deduplication
    transaction_hash: str  # SHA256(source + date + description + amount)
    date: date
    description: str
    amount: float  # Negative for expenses, positive for credits/income
    category: TransactionCategory | None = None
    raw_category: str | None = None  # Original category from statement if any
    tags: list[str] = Field(default_factory=list)  # LLM-generated tags for better search

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    """Transaction data for creation (before ID assignment)."""

    source: TransactionSource
    source_file_hash: str
    transaction_hash: str
    date: date
    description: str
    amount: float
    raw_category: str | None = None


class UploadedFile(BaseModel):
    """Record of an uploaded file."""

    id: UUID = Field(default_factory=uuid4)
    filename: str
    file_hash: str  # SHA256 of file contents
    source: TransactionSource
    transaction_count: int
    uploaded_at: str  # ISO format datetime


class UploadResponse(BaseModel):
    """Response after file upload."""

    filename: str
    source: TransactionSource
    transactions_added: int
    transactions_skipped: int  # Duplicates
    message: str


class QueryRequest(BaseModel):
    """Natural language query request."""

    query: str


class QueryResponse(BaseModel):
    """Response to a natural language query."""

    summary: str
    transactions: list[Transaction]
    total_amount: float | None = None


class SettingsUpdate(BaseModel):
    """Settings update request."""

    llm_provider: str | None = None
    openai_api_key: str | None = None
    ollama_host: str | None = None


class SettingsResponse(BaseModel):
    """Current settings response."""

    llm_provider: str
    ollama_host: str
    has_openai_key: bool
