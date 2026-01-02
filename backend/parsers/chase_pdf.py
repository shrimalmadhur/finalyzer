"""Parser for Chase credit card PDF statements."""

import re
from datetime import datetime
from io import BytesIO

import pdfplumber

from backend.models import Transaction, TransactionSource
from backend.parsers.validation import (
    ParseResult,
    ValidationError,
    logger,
    log_parse_result,
    validate_file_contents,
    validate_amount,
    validate_date,
)
from backend.services.dedup import compute_transaction_hash


def parse_chase_pdf(contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse a Chase credit card PDF statement.

    Chase statements typically have transactions in a table format with:
    - Date (MM/DD)
    - Description
    - Amount

    Raises:
        ValidationError: If the file cannot be parsed
    """
    result = ParseResult(transactions=[])

    # Validate file contents
    try:
        validate_file_contents(contents, min_size=100)
    except ValidationError as e:
        logger.error(f"Chase PDF validation failed: {e}")
        raise

    try:
        with pdfplumber.open(BytesIO(contents)) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            if not full_text.strip():
                logger.warning("Chase PDF: No text content extracted")
                return result.transactions

            # Try to extract the statement year from the document
            year = _extract_year(full_text)

            # Parse transactions from the text
            result.transactions = _extract_transactions(full_text, year, file_hash, result)

    except Exception as e:
        logger.error(f"Chase PDF parsing error: {e}")
        result.errors.append(f"PDF parsing failed: {e}")

    # Log results
    log_parse_result(result, "Chase PDF")

    return result.transactions


def _extract_year(text: str) -> int:
    """Extract the statement year from the PDF text."""
    # Look for patterns like "Statement Date: 01/15/2024" or "December 2024"
    year_patterns = [
        r"Statement\s+Date[:\s]+\d{1,2}/\d{1,2}/(\d{4})",
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
        r"(\d{4})\s+Statement",
        r"Opening/Closing Date.*?(\d{4})",
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    # Default to current year if not found
    return datetime.now().year


def _extract_transactions(
    text: str, year: int, file_hash: str, result: ParseResult
) -> list[Transaction]:
    """Extract transactions from Chase PDF text."""
    transactions: list[Transaction] = []

    # Chase transaction patterns - typically: MM/DD Description Amount
    # The amount can be positive (credits) or negative (charges)
    # Pattern: date, description, amount (with optional minus sign and commas)
    transaction_pattern = re.compile(
        r"(\d{2}/\d{2})\s+"  # Date MM/DD
        r"(.+?)\s+"  # Description (non-greedy)
        r"(-?\$?[\d,]+\.\d{2})\s*$",  # Amount
        re.MULTILINE,
    )

    # Also try alternative pattern where amount might be on same line differently
    alt_pattern = re.compile(
        r"(\d{2}/\d{2})\s+"  # Date MM/DD
        r"(.+?)\s{2,}"  # Description followed by multiple spaces
        r"(-?[\d,]+\.\d{2})",  # Amount
        re.MULTILINE,
    )

    lines = text.split("\n")

    for line in lines:
        result.total_rows_processed += 1

        # Skip header lines and non-transaction lines
        if _is_header_line(line):
            result.rows_skipped += 1
            continue

        # Try primary pattern
        match = transaction_pattern.search(line)
        if not match:
            match = alt_pattern.search(line)

        if match:
            date_str = match.group(1)
            description = match.group(2).strip()
            amount_str = match.group(3)

            # Skip if description looks like a header
            if _is_header_description(description):
                result.rows_skipped += 1
                continue

            # Parse date (add year)
            try:
                month, day = map(int, date_str.split("/"))
                txn_date = datetime(year, month, day).date()
            except ValueError:
                result.rows_skipped += 1
                result.warnings.append(f"Invalid date: {date_str}")
                continue

            # Validate date
            if not validate_date(txn_date):
                result.rows_skipped += 1
                result.warnings.append(f"Date out of range: {txn_date}")
                continue

            # Parse amount (remove $ and commas, handle negatives)
            amount = _parse_amount(amount_str)

            # Validate amount
            if not validate_amount(amount):
                result.rows_skipped += 1
                result.warnings.append(f"Invalid amount: {amount_str}")
                continue

            # Chase statements show charges as positive, payments as negative
            # We want expenses as negative, credits as positive
            # So we negate the amount
            amount = -amount

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
            )
            transactions.append(transaction)
        else:
            # Line didn't match any pattern
            result.rows_skipped += 1

    return transactions


def _is_header_line(line: str) -> bool:
    """Check if a line is a header or non-transaction line."""
    header_keywords = [
        "ACCOUNT SUMMARY",
        "PAYMENT INFORMATION",
        "ACCOUNT ACTIVITY",
        "TRANSACTION",
        "DATE",
        "DESCRIPTION",
        "AMOUNT",
        "PREVIOUS BALANCE",
        "NEW BALANCE",
        "PAYMENT DUE",
        "CREDIT LIMIT",
        "AVAILABLE CREDIT",
        "Page",
        "continued",
    ]
    line_upper = line.upper()
    return any(keyword in line_upper for keyword in header_keywords)


def _is_header_description(description: str) -> bool:
    """Check if a description is actually a header."""
    header_descriptions = [
        "PAYMENTS AND OTHER CREDITS",
        "PURCHASE",
        "FEES CHARGED",
        "INTEREST CHARGED",
    ]
    return description.upper() in header_descriptions


def _parse_amount(amount_str: str) -> float:
    """Parse an amount string to float."""
    # Remove $ and commas
    cleaned = amount_str.replace("$", "").replace(",", "")
    return float(cleaned)

