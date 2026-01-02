"""Parser for Chase Spending Report PDFs (annual/custom date range reports)."""

import re
from datetime import datetime
from io import BytesIO
from typing import Optional

import pdfplumber

from backend.models import Transaction, TransactionSource
from backend.services.dedup import compute_transaction_hash


def parse_chase_report_pdf(contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse a Chase Spending Report PDF.
    
    These reports have transactions grouped by category in tables:
    | Transaction Date | Posted Date | Description | Amount |
    
    Categories appear as headers like "AUTOMOTIVE", "BILLS_AND_UTILITIES", etc.
    """
    transactions: list[Transaction] = []
    current_category = None
    
    with pdfplumber.open(BytesIO(contents)) as pdf:
        for page in pdf.pages:
            # Extract tables from the page
            tables = page.extract_tables()
            
            for table in tables:
                if not table:
                    continue
                
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    
                    # Clean up row values
                    row = [cell.strip() if cell else "" for cell in row]
                    
                    # Skip header rows
                    if _is_header_row(row):
                        continue
                    
                    # Check if this is a category header (single cell with category name)
                    if len(row) >= 1 and _is_category_header(row[0]):
                        current_category = row[0]
                        continue
                    
                    # Try to parse as transaction row
                    # Format: Transaction Date | Posted Date | Description | Amount
                    if len(row) >= 4:
                        txn = _parse_transaction_row(row, current_category, file_hash)
                        if txn:
                            transactions.append(txn)
            
            # Also try to extract from text for tables that don't parse well
            text = page.extract_text()
            if text:
                text_txns = _parse_transactions_from_text(text, file_hash)
                # Add only if we didn't get them from tables
                existing_hashes = {t.transaction_hash for t in transactions}
                for txn in text_txns:
                    if txn.transaction_hash not in existing_hashes:
                        transactions.append(txn)
    
    return transactions


def _is_header_row(row: list[str]) -> bool:
    """Check if this is a table header row."""
    first_cell = row[0].lower() if row[0] else ""
    return any(h in first_cell for h in [
        "transaction date", "posted date", "description", "amount",
        "category", "total amount"
    ])


def _is_category_header(text: str) -> bool:
    """Check if this text is a category header."""
    categories = [
        "AUTOMOTIVE", "BILLS_AND_UTILITIES", "EDUCATION", "ENTERTAINMENT",
        "FEES_AND_ADJUSTMENTS", "FOOD_AND_DRINK", "GAS", "GIFTS_AND_DONATIONS",
        "GROCERIES", "HEALTH_AND_WELLNESS", "HOME", "PERSONAL",
        "PROFESSIONAL_SERVICES", "SHOPPING", "TRAVEL"
    ]
    return text.upper() in categories


def _parse_transaction_row(
    row: list[str], 
    category: Optional[str], 
    file_hash: str
) -> Optional[Transaction]:
    """Parse a transaction from a table row."""
    try:
        # Expected format: Transaction Date | Posted Date | Description | Amount
        date_str = row[0]
        description = row[2] if len(row) > 2 else ""
        amount_str = row[3] if len(row) > 3 else row[-1]
        
        # Skip if no valid date
        txn_date = _parse_date(date_str)
        if not txn_date:
            return None
        
        # Skip if no description
        if not description or description.lower() in ["total", ""]:
            return None
        
        # Parse amount
        amount = _parse_amount(amount_str)
        if amount is None:
            return None
        
        # Skip zero amounts
        if amount == 0:
            return None
        
        # Make expenses negative (Chase report shows them as positive)
        if amount > 0:
            amount = -amount
        
        # Map category
        raw_category = _map_chase_category(category) if category else None
        
        # Create transaction hash
        txn_hash = compute_transaction_hash(
            TransactionSource.CHASE_CREDIT, txn_date, description, amount
        )
        
        return Transaction(
            source=TransactionSource.CHASE_CREDIT,
            source_file_hash=file_hash,
            transaction_hash=txn_hash,
            date=txn_date,
            description=description,
            amount=amount,
            raw_category=raw_category,
        )
    except Exception:
        return None


def _parse_transactions_from_text(text: str, file_hash: str) -> list[Transaction]:
    """Parse transactions from raw text as fallback."""
    transactions: list[Transaction] = []
    current_category = None
    
    lines = text.split("\n")
    
    # Category pattern
    category_pattern = re.compile(
        r"^(AUTOMOTIVE|BILLS_AND_UTILITIES|EDUCATION|ENTERTAINMENT|"
        r"FEES_AND_ADJUSTMENTS|FOOD_AND_DRINK|GAS|GIFTS_AND_DONATIONS|"
        r"GROCERIES|HEALTH_AND_WELLNESS|HOME|PERSONAL|"
        r"PROFESSIONAL_SERVICES|SHOPPING|TRAVEL)$"
    )
    
    # Transaction pattern: "Mon DD, YYYY Mon DD, YYYY DESCRIPTION $XX.XX" or similar
    # Example: "Jan 26, 2025 Jan 29, 2025 UNCLE IKES CAR WASH $20.25"
    txn_pattern = re.compile(
        r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+"  # Transaction date
        r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s+"  # Posted date
        r"(.+?)\s+"  # Description
        r"\$?([\d,]+\.?\d*)\s*$"  # Amount
    )
    
    for line in lines:
        line = line.strip()
        
        # Check for category header
        cat_match = category_pattern.match(line)
        if cat_match:
            current_category = cat_match.group(1)
            continue
        
        # Try to match transaction
        txn_match = txn_pattern.match(line)
        if txn_match:
            date_str = txn_match.group(1)
            description = txn_match.group(3).strip()
            amount_str = txn_match.group(4)
            
            txn_date = _parse_date(date_str)
            if not txn_date:
                continue
            
            amount = _parse_amount(amount_str)
            if amount is None:
                continue
            
            # Make expenses negative
            if amount > 0:
                amount = -amount
            
            raw_category = _map_chase_category(current_category) if current_category else None
            
            txn_hash = compute_transaction_hash(
                TransactionSource.CHASE_CREDIT, txn_date, description, amount
            )
            
            transactions.append(Transaction(
                source=TransactionSource.CHASE_CREDIT,
                source_file_hash=file_hash,
                transaction_hash=txn_hash,
                date=txn_date,
                description=description,
                amount=amount,
                raw_category=raw_category,
            ))
    
    return transactions


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from various formats."""
    if not date_str:
        return None
    
    formats = [
        "%b %d, %Y",   # Jan 26, 2025
        "%B %d, %Y",   # January 26, 2025
        "%m/%d/%Y",    # 01/26/2025
        "%m-%d-%Y",    # 01-26-2025
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    
    return None


def _parse_amount(amount_str: str) -> Optional[float]:
    """Parse amount string to float."""
    if not amount_str:
        return None
    
    try:
        # Remove $ and commas
        cleaned = amount_str.replace("$", "").replace(",", "").strip()
        
        # Handle negative amounts (could be in parentheses or with minus)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        elif cleaned.startswith("-"):
            pass  # Already negative
        
        return float(cleaned)
    except ValueError:
        return None


def _map_chase_category(category: str) -> str:
    """Map Chase report category to our category format."""
    if not category:
        return ""
    
    mapping = {
        "AUTOMOTIVE": "Gas",
        "BILLS_AND_UTILITIES": "Bills & Utilities",
        "EDUCATION": "Other",
        "ENTERTAINMENT": "Entertainment",
        "FEES_AND_ADJUSTMENTS": "Other",
        "FOOD_AND_DRINK": "Food & Dining",
        "GAS": "Gas",
        "GIFTS_AND_DONATIONS": "Shopping",
        "GROCERIES": "Groceries",
        "HEALTH_AND_WELLNESS": "Health",
        "HOME": "Shopping",
        "PERSONAL": "Other",
        "PROFESSIONAL_SERVICES": "Other",
        "SHOPPING": "Shopping",
        "TRAVEL": "Travel",
    }
    
    return mapping.get(category.upper(), category)


def is_chase_spending_report(contents: bytes) -> bool:
    """Check if this PDF is a Chase Spending Report (vs regular statement)."""
    try:
        with pdfplumber.open(BytesIO(contents)) as pdf:
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ""
                # Chase Spending Reports have these distinctive markers
                return "Spending Report" in text or "Spending By Category" in text
    except Exception:
        pass
    return False

