"""Shared validation utilities for financial statement parsers."""

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Configure logging for parsers
logger = logging.getLogger("finalyzer.parsers")


@dataclass
class ParseResult:
    """Result of parsing a financial statement."""

    transactions: list[Any]
    total_rows_processed: int = 0
    rows_skipped: int = 0
    payments_filtered: int = 0
    duplicates_filtered: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate the parsing success rate."""
        if self.total_rows_processed == 0:
            return 0.0
        parsed = len(self.transactions)
        return (parsed / self.total_rows_processed) * 100


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_file_contents(contents: bytes, min_size: int = 10) -> None:
    """
    Validate file contents before parsing.

    Args:
        contents: Raw file bytes
        min_size: Minimum expected file size in bytes

    Raises:
        ValidationError: If validation fails
    """
    if not contents:
        raise ValidationError("File is empty")

    if len(contents) < min_size:
        raise ValidationError(f"File too small ({len(contents)} bytes), minimum {min_size} bytes expected")


def validate_csv_contents(contents: bytes) -> str:
    """
    Validate and decode CSV contents.

    Args:
        contents: Raw CSV file bytes

    Returns:
        Decoded text content

    Raises:
        ValidationError: If validation fails
    """
    validate_file_contents(contents)

    # Try common encodings
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    text = None

    for encoding in encodings:
        try:
            text = contents.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise ValidationError("Could not decode file with any supported encoding (utf-8, latin-1, cp1252)")

    # Check for minimum CSV structure
    lines = text.strip().split("\n")
    if len(lines) < 1:
        raise ValidationError("CSV file has no content")

    # Check for comma or tab delimiter
    first_line = lines[0]
    if "," not in first_line and "\t" not in first_line:
        raise ValidationError("File does not appear to be a valid CSV (no delimiters found)")

    return text


def validate_amount(amount: float, min_val: float = -1_000_000, max_val: float = 1_000_000) -> bool:
    """
    Validate that an amount is within reasonable bounds.

    Args:
        amount: The amount to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        True if valid, False otherwise
    """
    if amount is None:
        return False

    # Check for NaN or infinity
    if amount != amount or abs(amount) == float("inf"):
        return False

    return min_val <= amount <= max_val


def validate_date(txn_date: date, min_year: int = 2000, max_year: int = 2100) -> bool:
    """
    Validate that a date is within reasonable bounds.

    Args:
        txn_date: The date to validate
        min_year: Minimum allowed year
        max_year: Maximum allowed year

    Returns:
        True if valid, False otherwise
    """
    if txn_date is None:
        return False

    return min_year <= txn_date.year <= max_year


def validate_description(description: str, min_length: int = 1, max_length: int = 500) -> bool:
    """
    Validate a transaction description.

    Args:
        description: The description to validate
        min_length: Minimum length
        max_length: Maximum length

    Returns:
        True if valid, False otherwise
    """
    if not description:
        return False

    description = description.strip()
    length = len(description)

    return min_length <= length <= max_length


def clean_amount_string(amount_str: str) -> str:
    """
    Clean an amount string for parsing.

    Args:
        amount_str: Raw amount string

    Returns:
        Cleaned amount string ready for float conversion
    """
    if not amount_str:
        return "0"

    # Remove currency symbols and whitespace
    cleaned = amount_str.replace("$", "").replace(" ", "").strip()

    # Remove thousand separators
    cleaned = cleaned.replace(",", "")

    # Handle parentheses for negative numbers
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]

    # Handle trailing minus sign
    if cleaned.endswith("-"):
        cleaned = "-" + cleaned[:-1]

    return cleaned


def parse_amount_safe(amount_str: str, default: float = 0.0) -> tuple[float, bool]:
    """
    Safely parse an amount string.

    Args:
        amount_str: Raw amount string
        default: Default value if parsing fails

    Returns:
        Tuple of (parsed amount, success flag)
    """
    try:
        cleaned = clean_amount_string(amount_str)
        if not cleaned or cleaned == "-":
            return default, False

        amount = float(cleaned)

        if not validate_amount(amount):
            return default, False

        return amount, True
    except (ValueError, TypeError):
        return default, False


def normalize_description(description: str) -> str:
    """
    Normalize a transaction description.

    Args:
        description: Raw description

    Returns:
        Normalized description
    """
    if not description:
        return ""

    # Remove extra whitespace
    description = " ".join(description.split())

    # Remove common noise patterns
    noise_patterns = [
        r"\s*\*+\s*",  # Asterisks
        r"\s+\d{10,}$",  # Long trailing numbers (reference IDs)
        r"\s+#\d+$",  # Store numbers
        r"\s+XX+\d+$",  # Masked card numbers
    ]

    for pattern in noise_patterns:
        description = re.sub(pattern, "", description)

    return description.strip()


def is_likely_payment(description: str, category: str = "") -> bool:
    """
    Check if a transaction is likely a credit card payment.

    These should be filtered out because they represent
    transfers, not actual spending.

    Args:
        description: Transaction description
        category: Optional category

    Returns:
        True if likely a payment
    """
    description_lower = description.lower()
    category_lower = category.lower() if category else ""

    payment_indicators = [
        "payment - thank you",
        "payment thank you",
        "autopay payment",
        "automatic payment",
        "online payment",
        "ach payment",
        "mobile payment",
        "payment received",
        "bill pay",
        "epay",
        "check payment",
    ]

    for indicator in payment_indicators:
        if indicator in description_lower:
            return True

    if "payment" in category_lower:
        return True

    return False


def log_parse_result(result: ParseResult, parser_name: str) -> None:
    """
    Log parsing results for debugging.

    Args:
        result: The parse result
        parser_name: Name of the parser
    """
    logger.info(
        f"{parser_name}: Parsed {len(result.transactions)} transactions "
        f"(processed {result.total_rows_processed}, "
        f"skipped {result.rows_skipped}, "
        f"payments {result.payments_filtered}, "
        f"duplicates {result.duplicates_filtered})"
    )

    if result.errors:
        for error in result.errors[:5]:  # Log first 5 errors
            logger.warning(f"{parser_name}: {error}")

    if result.warnings:
        for warning in result.warnings[:5]:  # Log first 5 warnings
            logger.debug(f"{parser_name}: {warning}")
