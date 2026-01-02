"""Parser for Chase credit card CSV exports."""

import csv
from datetime import datetime
from io import StringIO

from backend.models import Transaction, TransactionSource
from backend.parsers.validation import (
    ParseResult,
    ValidationError,
    logger,
    log_parse_result,
    parse_amount_safe,
    validate_csv_contents,
    validate_date,
    validate_description,
)
from backend.services.dedup import compute_transaction_hash


def parse_chase_csv(contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse a Chase credit card CSV export.

    Chase CSV format:
    Transaction Date,Post Date,Description,Category,Type,Amount,Memo
    12/30/2024,12/31/2024,VAMAN SPA,Health & Wellness,Sale,-32.69,

    Raises:
        ValidationError: If the file cannot be parsed
    """
    result = ParseResult(transactions=[])

    # Validate and decode CSV
    try:
        text = validate_csv_contents(contents)
    except ValidationError as e:
        logger.error(f"Chase CSV validation failed: {e}")
        raise

    reader = csv.DictReader(StringIO(text))

    fieldnames = reader.fieldnames
    if not fieldnames:
        logger.warning("Chase CSV: No headers found")
        return result.transactions

    # Verify expected Chase headers
    expected_headers = ["Transaction Date", "Description", "Amount"]
    missing_headers = [h for h in expected_headers if h not in fieldnames]
    if missing_headers:
        logger.warning(f"Chase CSV: Missing expected headers: {missing_headers}")
        result.errors.append(f"Missing headers: {', '.join(missing_headers)}")

    for row in reader:
        result.total_rows_processed += 1

        try:
            # Extract fields - Chase CSV has consistent headers
            date_str = row.get("Transaction Date", "").strip()
            description = row.get("Description", "").strip()
            amount_str = row.get("Amount", "").strip()
            raw_category = row.get("Category", "").strip()
            txn_type = row.get("Type", "").strip().lower()

            # Validate required fields
            if not date_str or not description or not amount_str:
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Missing required field")
                continue

            # Skip payments - these are credit card bill payments, not spending
            if _is_payment(txn_type, description, raw_category):
                result.payments_filtered += 1
                continue

            # Parse date (Chase uses MM/DD/YYYY format)
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

            # Parse amount with validation - Chase CSV already has negative for purchases
            amount, amount_valid = parse_amount_safe(amount_str)
            if not amount_valid:
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Invalid amount '{amount_str}'")
                continue

            # Validate description
            if not validate_description(description):
                result.rows_skipped += 1
                result.warnings.append(f"Row {result.total_rows_processed}: Invalid description")
                continue

            # Create transaction
            txn_hash = compute_transaction_hash(
                TransactionSource.CHASE_CREDIT, txn_date, description, amount
            )

            transaction = Transaction(
                source=TransactionSource.CHASE_CREDIT,
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
    log_parse_result(result, "Chase CSV")

    return result.transactions


def _is_payment(txn_type: str, description: str, category: str) -> bool:
    """
    Check if this transaction is a credit card payment (not actual spending).
    
    These should be excluded because:
    - They're just transfers from your bank account to pay the CC bill
    - They'd double-count spending (you already tracked the original purchase)
    """
    description_lower = description.lower()
    category_lower = category.lower() if category else ""
    
    # Check transaction type - Chase uses "Payment" for bill payments
    if txn_type == "payment":
        return True
    
    # Check description patterns for payments
    payment_keywords = [
        "payment thank you",
        "automatic payment",
        "autopay",
        "online payment",
        "payment - thank you",
        "mobile payment",
        "ach payment",
        "payment received",
    ]
    
    for keyword in payment_keywords:
        if keyword in description_lower:
            return True
    
    # Check category
    if "payment" in category_lower:
        return True
    
    return False


def _parse_date(date_str: str) -> datetime | None:
    """Parse date string in Chase CSV format."""
    formats = [
        "%m/%d/%Y",  # 12/30/2024
        "%m/%d/%y",  # 12/30/24
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None

