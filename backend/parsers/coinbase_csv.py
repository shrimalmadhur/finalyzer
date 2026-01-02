"""Parser for Coinbase Card CSV exports."""

import csv
from datetime import datetime
from io import StringIO

from backend.models import Transaction, TransactionSource
from backend.services.dedup import compute_transaction_hash


def parse_coinbase_csv(contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse a Coinbase Card CSV export.
    
    Coinbase Card CSV typically has columns:
    - Timestamp or Date
    - Transaction Type
    - Asset
    - Quantity Transacted
    - USD Amount or Amount
    - Description/Merchant
    """
    transactions: list[Transaction] = []
    
    # Decode and parse CSV
    text = contents.decode("utf-8", errors="ignore")
    reader = csv.DictReader(StringIO(text))
    
    fieldnames = reader.fieldnames
    if not fieldnames:
        return transactions
    
    # Map headers
    header_map = _build_header_map(fieldnames)
    
    for row in reader:
        try:
            # Extract fields
            date_str = _get_field(row, header_map, "date")
            description = _get_field(row, header_map, "description")
            amount_str = _get_field(row, header_map, "amount")
            txn_type = _get_field(row, header_map, "type")
            
            if not date_str or not amount_str:
                continue
            
            # Build description from available fields
            if not description:
                description = txn_type or "Coinbase Card Transaction"
            
            # Parse date
            txn_date = _parse_date(date_str)
            if not txn_date:
                continue
            
            # Parse amount
            amount = _parse_amount(amount_str)
            
            # Coinbase typically shows spending as positive
            # We want expenses as negative
            if txn_type and "reward" in txn_type.lower():
                # Rewards are credits (positive)
                amount = abs(amount)
            else:
                # Spending is negative
                amount = -abs(amount)
            
            # Create transaction
            txn_hash = compute_transaction_hash(
                TransactionSource.COINBASE, txn_date, description, amount
            )
            
            transaction = Transaction(
                source=TransactionSource.COINBASE,
                source_file_hash=file_hash,
                transaction_hash=txn_hash,
                date=txn_date,
                description=description,
                amount=amount,
                raw_category=txn_type if txn_type else None,
            )
            transactions.append(transaction)
            
        except (ValueError, KeyError):
            continue
    
    return transactions


def _build_header_map(fieldnames: list[str]) -> dict[str, str]:
    """Build a mapping from standard field names to actual CSV headers."""
    header_map: dict[str, str] = {}
    
    for field in fieldnames:
        field_lower = field.lower().strip()
        
        if "timestamp" in field_lower or "date" in field_lower:
            header_map["date"] = field
        elif "description" in field_lower or "merchant" in field_lower or "notes" in field_lower:
            header_map["description"] = field
        elif "usd" in field_lower or "amount" in field_lower:
            # Prefer USD amount over crypto amount
            if "usd" in field_lower or "amount" not in header_map:
                header_map["amount"] = field
        elif "type" in field_lower or "transaction type" in field_lower:
            header_map["type"] = field
        elif "asset" in field_lower:
            header_map["asset"] = field
    
    return header_map


def _get_field(row: dict, header_map: dict[str, str], field: str) -> str:
    """Get a field value using the header map."""
    if field in header_map:
        return row.get(header_map[field], "").strip()
    return ""


def _parse_date(date_str: str) -> datetime | None:
    """Parse date string in various formats."""
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",  # ISO format
        "%Y-%m-%d %H:%M:%S",   # Standard datetime
        "%Y-%m-%d",            # Date only
        "%m/%d/%Y",            # US format
        "%m/%d/%y",            # Short year
        "%d/%m/%Y",            # European format
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # Try parsing just the date part if there's a T separator
    if "T" in date_str:
        try:
            return datetime.strptime(date_str.split("T")[0], "%Y-%m-%d").date()
        except ValueError:
            pass
    
    return None


def _parse_amount(amount_str: str) -> float:
    """Parse amount string to float."""
    # Remove currency symbols, commas, and whitespace
    cleaned = amount_str.replace("$", "").replace(",", "").replace(" ", "")
    
    # Handle empty or invalid strings
    if not cleaned or cleaned == "-":
        return 0.0
    
    # Handle parentheses for negative numbers
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    
    return float(cleaned)

