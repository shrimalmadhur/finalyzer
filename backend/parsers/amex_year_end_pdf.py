"""Parser for American Express Year-End Summary PDF."""

import re
from datetime import datetime
from io import BytesIO

import pdfplumber

from backend.models import Transaction, TransactionSource
from backend.services.dedup import compute_transaction_hash


def is_amex_year_end_summary(text: str) -> bool:
    """
    Check if the PDF is an Amex Year-End Summary.
    
    These PDFs contain:
    - "Year-End Summary" in the title
    - "Includes charges from January 1 through December 31"
    - "Prepared for" with cardholder name
    """
    text_lower = text.lower()
    
    # Must have "Year-End Summary"
    if "year-end summary" not in text_lower:
        return False
    
    # Must have either "includes charges from" or "prepared for"
    has_charges_text = "includes charges from" in text_lower
    has_prepared_for = "prepared for" in text_lower
    
    return has_charges_text or has_prepared_for


def parse_amex_year_end_pdf(contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse an American Express Year-End Summary PDF.
    
    The PDF contains detailed transaction listings organized by category.
    Each transaction entry has:
    - Date (e.g., "01/25/2025")
    - Month Billed (e.g., "February")
    - Transaction description with location
    - Charges amount
    - Credits amount (optional)
    """
    transactions: list[Transaction] = []
    seen_hashes: set[str] = set()
    
    try:
        with pdfplumber.open(BytesIO(contents)) as pdf:
            all_text = ""
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                all_text += page_text + "\n"
            
            # Extract the year from the document
            year = _extract_year(all_text)
            
            # Parse transactions from all pages
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                page_transactions = _parse_page_transactions(page_text, year, file_hash, seen_hashes)
                transactions.extend(page_transactions)
                
                # Also try table extraction for better accuracy
                tables = page.extract_tables()
                for table in tables:
                    table_transactions = _parse_table_transactions(table, year, file_hash, seen_hashes)
                    transactions.extend(table_transactions)
    
    except Exception as e:
        print(f"Error parsing Amex Year-End PDF: {e}")
    
    return transactions


def _extract_year(text: str) -> int:
    """Extract the year from the document."""
    # Look for "Year-End Summary" followed by year
    year_match = re.search(r"(\d{4})\s*Year-End Summary", text, re.IGNORECASE)
    if year_match:
        return int(year_match.group(1))
    
    # Look for "Includes charges from January 1 through December 31, YYYY"
    year_match = re.search(r"through December 31,?\s*(\d{4})", text, re.IGNORECASE)
    if year_match:
        return int(year_match.group(1))
    
    # Fallback: look for any 4-digit year
    year_match = re.search(r"20\d{2}", text)
    if year_match:
        return int(year_match.group(0))
    
    # Default to current year
    return datetime.now().year


def _parse_page_transactions(
    text: str, 
    year: int, 
    file_hash: str,
    seen_hashes: set[str]
) -> list[Transaction]:
    """Parse transactions from page text using regex patterns."""
    transactions: list[Transaction] = []
    
    # Pattern to match transaction lines:
    # Date | Month | Description Location | Amount
    # Examples:
    # 01/25/2025 February DELTA AIR LINES ATLANTA $401.97
    # 06/18/2025 July ApPay TST* HONOLULUHONOLULU HI $20.52
    
    # Pattern for transaction with date, month, description, and amount
    txn_pattern = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{4})\s+"  # Date (MM/DD/YYYY)
        r"(\w+)\s+"  # Month billed
        r"(.+?)\s+"  # Description (non-greedy)
        r"\$?([\d,]+\.?\d*)\s*$",  # Amount
        re.MULTILINE
    )
    
    for match in txn_pattern.finditer(text):
        try:
            date_str = match.group(1)
            # month_billed = match.group(2)  # Not used but available
            description = match.group(3).strip()
            amount_str = match.group(4)
            
            # Parse date
            txn_date = _parse_date(date_str, year)
            if not txn_date:
                continue
            
            # Clean description - remove trailing state codes and extra spaces
            description = _clean_description(description)
            
            # Skip if description is too short or looks like a header
            if len(description) < 3 or _is_header_or_label(description):
                continue
            
            # Parse amount
            amount = _parse_amount(amount_str)
            
            # Skip zero amounts
            if amount == 0:
                continue
            
            # Make amount negative (expense)
            amount = -abs(amount)
            
            # Extract raw category from context (if available)
            raw_category = _extract_category_from_context(text, match.start())
            
            # Create transaction hash
            txn_hash = compute_transaction_hash(
                TransactionSource.AMEX, txn_date, description, amount
            )
            
            # Skip duplicates
            if txn_hash in seen_hashes:
                continue
            seen_hashes.add(txn_hash)
            
            transaction = Transaction(
                source=TransactionSource.AMEX,
                source_file_hash=file_hash,
                transaction_hash=txn_hash,
                date=txn_date,
                description=description,
                amount=amount,
                raw_category=raw_category,
            )
            transactions.append(transaction)
            
        except (ValueError, IndexError) as e:
            print(f"Error parsing transaction: {e}")
            continue
    
    return transactions


def _parse_table_transactions(
    table: list[list[str | None]], 
    year: int, 
    file_hash: str,
    seen_hashes: set[str]
) -> list[Transaction]:
    """Parse transactions from extracted table data."""
    transactions: list[Transaction] = []
    
    if not table or len(table) < 2:
        return transactions
    
    # Find the header row to understand column positions
    header_row = None
    data_start = 0
    
    for i, row in enumerate(table):
        if row and any(cell and "date" in str(cell).lower() for cell in row):
            header_row = row
            data_start = i + 1
            break
    
    # If no header found, try to parse based on position
    if not header_row:
        data_start = 0
    
    for row in table[data_start:]:
        if not row or len(row) < 3:
            continue
        
        try:
            # Try to extract date, description, amount from row
            date_str = None
            description = None
            amount_str = None
            
            for cell in row:
                if not cell:
                    continue
                cell_str = str(cell).strip()
                
                # Check if it's a date
                if re.match(r"\d{1,2}/\d{1,2}/\d{4}", cell_str):
                    date_str = cell_str
                # Check if it's an amount
                elif re.match(r"\$?[\d,]+\.?\d*$", cell_str.replace(",", "")):
                    if not amount_str:  # Take first amount (charges, not credits)
                        amount_str = cell_str
                # Otherwise it might be description
                elif len(cell_str) > 5 and not _is_header_or_label(cell_str):
                    if description:
                        description += " " + cell_str
                    else:
                        description = cell_str
            
            if not date_str or not description or not amount_str:
                continue
            
            # Parse date
            txn_date = _parse_date(date_str, year)
            if not txn_date:
                continue
            
            # Clean description
            description = _clean_description(description)
            
            # Parse amount
            amount = _parse_amount(amount_str)
            if amount == 0:
                continue
            
            # Make negative
            amount = -abs(amount)
            
            # Create hash
            txn_hash = compute_transaction_hash(
                TransactionSource.AMEX, txn_date, description, amount
            )
            
            # Skip duplicates
            if txn_hash in seen_hashes:
                continue
            seen_hashes.add(txn_hash)
            
            transaction = Transaction(
                source=TransactionSource.AMEX,
                source_file_hash=file_hash,
                transaction_hash=txn_hash,
                date=txn_date,
                description=description,
                amount=amount,
            )
            transactions.append(transaction)
            
        except (ValueError, IndexError):
            continue
    
    return transactions


def _parse_date(date_str: str, default_year: int) -> datetime | None:
    """Parse date string."""
    formats = [
        "%m/%d/%Y",  # 01/25/2025
        "%m/%d/%y",  # 01/25/25
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # Try parsing with just month/day and use default year
    try:
        parts = date_str.split("/")
        if len(parts) >= 2:
            month = int(parts[0])
            day = int(parts[1])
            return datetime(default_year, month, day).date()
    except (ValueError, IndexError):
        pass
    
    return None


def _parse_amount(amount_str: str) -> float:
    """Parse amount string to float."""
    # Remove currency symbols, commas, whitespace
    cleaned = amount_str.replace("$", "").replace(",", "").replace(" ", "").strip()
    
    # Handle parentheses for negative
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    
    # Handle empty or invalid
    if not cleaned or cleaned == "-":
        return 0.0
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _clean_description(description: str) -> str:
    """Clean up transaction description."""
    # Remove extra whitespace
    description = " ".join(description.split())
    
    # Remove common noise patterns
    description = re.sub(r"\s+\d{2,}$", "", description)  # Trailing numbers
    description = re.sub(r"\s+(CA|NY|WA|TX|FL|GA|HI|DC|IL|AZ|NV|CO|OR|MA)$", "", description)  # State codes
    
    # Capitalize properly
    description = description.strip()
    
    return description


def _is_header_or_label(text: str) -> bool:
    """Check if text is a header or label, not a transaction."""
    text_lower = text.lower()
    
    skip_patterns = [
        "card member",
        "account number",
        "subtotal",
        "total",
        "charges",
        "credits",
        "date",
        "month billed",
        "transaction",
        "xxxx-",
        "spending",
        "year-end",
        "american express",
        "prepared for",
        "includes charges",
    ]
    
    for pattern in skip_patterns:
        if pattern in text_lower:
            return True
    
    return False


def _extract_category_from_context(text: str, position: int) -> str | None:
    """Try to extract category from surrounding context."""
    # Look backwards for category headers
    categories = [
        "Entertainment",
        "Merchandise & Supplies",
        "Restaurant",
        "Transportation",
        "Travel",
        "Fees & Adjustments",
        "Other",
        "Airline",
        "Travel Agencies",
        "Taxis & Coach",
        "Rail Services",
        "Miscellaneous",
        "Internet Purchase",
    ]
    
    # Get text before the transaction
    context = text[:position]
    
    # Find the most recent category header
    last_category = None
    last_pos = -1
    
    for category in categories:
        pos = context.rfind(category)
        if pos > last_pos:
            last_pos = pos
            last_category = category
    
    return last_category

