"""Parser for American Express CSV exports."""

import csv
from datetime import datetime
from io import StringIO

from backend.models import Transaction, TransactionSource
from backend.parsers.validation import (
    ParseResult,
    ValidationError,
    is_likely_payment,
    logger,
    log_parse_result,
    normalize_description,
    parse_amount_safe,
    validate_csv_contents,
    validate_date,
    validate_description,
)
from backend.services.dedup import compute_transaction_hash


def parse_amex_csv(contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse an American Express CSV export.

    Supports multiple Amex CSV formats:

    Format 1 (Activity Download):
    - Date, Description, Amount, Category (optional)

    Format 2 (Statement View):
    - Date, Description, Card Member, Account #, Amount

    Amount handling:
    - Positive amounts = charges (converted to negative for our system)
    - Negative amounts = credits/refunds (converted to positive for our system)

    Raises:
        ValidationError: If the file cannot be parsed
    """
    result = ParseResult(transactions=[])

    # Validate and decode CSV
    try:
        text = validate_csv_contents(contents)
    except ValidationError as e:
        logger.error(f"Amex CSV validation failed: {e}")
        raise

    reader = csv.DictReader(StringIO(text))

    # Normalize header names (Amex headers can vary)
    fieldnames = reader.fieldnames
    if not fieldnames:
        logger.warning("Amex CSV: No headers found")
        return result.transactions

    # Map common header variations
    header_map = _build_header_map(fieldnames)

    # Verify required headers are present
    if "date" not in header_map or "description" not in header_map or "amount" not in header_map:
        missing = []
        if "date" not in header_map:
            missing.append("date")
        if "description" not in header_map:
            missing.append("description")
        if "amount" not in header_map:
            missing.append("amount")
        logger.warning(f"Amex CSV: Missing required headers: {missing}")
        result.errors.append(f"Missing required headers: {', '.join(missing)}")

    for row in reader:
        result.total_rows_processed += 1

        try:
            # Extract fields using mapped headers
            date_str = _get_field(row, header_map, "date")
            description = _get_field(row, header_map, "description")
            amount_str = _get_field(row, header_map, "amount")
            raw_category = _get_field(row, header_map, "category")

            # Validate required fields
            if not date_str or not description or not amount_str:
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Missing required field")
                continue

            # Skip payments (credit card bill payments)
            if _is_payment(description):
                result.payments_filtered += 1
                continue

            # Parse date (Amex uses various formats)
            txn_date = _parse_date(date_str)
            if not txn_date:
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Invalid date '{date_str}'")
                continue

            # Validate date is reasonable
            if not validate_date(txn_date):
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Date out of range '{txn_date}'")
                continue

            # Parse amount with validation
            amount, amount_valid = parse_amount_safe(amount_str)
            if not amount_valid:
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Invalid amount '{amount_str}'")
                continue

            # Amex shows charges as positive, credits/payments as negative
            # We want expenses as negative, credits as positive
            amount = -amount

            # Clean up description
            description = _clean_description(description)

            # Validate description
            if not validate_description(description):
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Invalid description")
                continue

            # Create transaction
            txn_hash = compute_transaction_hash(
                TransactionSource.AMEX, txn_date, description, amount
            )

            transaction = Transaction(
                source=TransactionSource.AMEX,
                source_file_hash=file_hash,
                transaction_hash=txn_hash,
                date=txn_date,
                description=description,
                amount=amount,
                raw_category=raw_category if raw_category else None,
            )
            result.transactions.append(transaction)

        except (ValueError, KeyError) as e:
            result.rows_skipped += 1
            result.errors.append(f"Row {result.total_rows_processed}: Parse error - {e}")
            continue

    # Log results
    log_parse_result(result, "Amex CSV")

    return result.transactions


def _build_header_map(fieldnames: list[str]) -> dict[str, str]:
    """Build a mapping from standard field names to actual CSV headers."""
    header_map: dict[str, str] = {}
    
    # Normalize and map headers
    for field in fieldnames:
        field_lower = field.lower().strip()
        
        if "date" in field_lower:
            header_map["date"] = field
        elif "description" in field_lower or "merchant" in field_lower:
            header_map["description"] = field
        elif "amount" in field_lower:
            header_map["amount"] = field
        elif "category" in field_lower:
            header_map["category"] = field
        elif "reference" in field_lower:
            header_map["reference"] = field
        elif "card member" in field_lower or "cardholder" in field_lower:
            header_map["card_member"] = field
        elif "account" in field_lower:
            header_map["account"] = field
    
    return header_map


def _get_field(row: dict, header_map: dict[str, str], field: str) -> str:
    """Get a field value using the header map."""
    if field in header_map:
        return row.get(header_map[field], "").strip()
    return ""


def _parse_date(date_str: str) -> datetime | None:
    """Parse date string in various formats."""
    formats = [
        "%m/%d/%Y",  # 01/15/2024
        "%m/%d/%y",  # 01/15/24
        "%Y-%m-%d",  # 2024-01-15
        "%d/%m/%Y",  # 15/01/2024
        "%m-%d-%Y",  # 01-15-2024
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None


def _is_payment(description: str) -> bool:
    """Check if this is a credit card payment (not actual spending)."""
    description_lower = description.lower()
    
    payment_keywords = [
        "payment received",
        "payment - thank you",
        "payment thank you",
        "autopay payment",
        "automatic payment",
        "online payment",
        "ach payment",
        "mobile payment - thank you",
    ]
    
    for keyword in payment_keywords:
        if keyword in description_lower:
            return True
    
    return False


def _clean_description(description: str) -> str:
    """Clean up transaction description."""
    # Remove extra whitespace
    description = " ".join(description.split())
    return description.strip()

