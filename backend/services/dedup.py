"""Deduplication logic for Finalyzer."""

import hashlib
from datetime import date

from backend.models import TransactionSource


def compute_file_hash(contents: bytes) -> str:
    """Compute SHA256 hash of file contents."""
    return hashlib.sha256(contents).hexdigest()


def compute_transaction_hash(
    source: TransactionSource,
    txn_date: date,
    description: str,
    amount: float,
) -> str:
    """
    Compute a unique hash for a transaction.

    This hash is used to detect duplicate transactions even across
    different file uploads.
    """
    # Normalize the data for consistent hashing
    normalized = f"{source.value}|{txn_date.isoformat()}|{description.strip().lower()}|{amount:.2f}"
    return hashlib.sha256(normalized.encode()).hexdigest()
