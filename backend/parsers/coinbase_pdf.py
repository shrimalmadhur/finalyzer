"""Parser for Coinbase Card PDF statements."""

import re
from datetime import datetime
from io import BytesIO
from typing import Optional

import pdfplumber

from backend.models import Transaction, TransactionSource
from backend.services.dedup import compute_transaction_hash


def parse_coinbase_pdf(contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse a Coinbase Card PDF statement.
    
    Coinbase statements have sections:
    - Payments and credits (refunds, returns - positive for us)
    - Transactions (purchases - negative for us)
    
    Format:
    | Date | Description | Amount |
    | Sep 4, 2025 | TST® ANCHORHEAD COFFEE - 1600 7TH AVE... | $6.07 |
    """
    transactions: list[Transaction] = []
    
    with pdfplumber.open(BytesIO(contents)) as pdf:
        current_section = None  # "payments" or "transactions"
        
        for page in pdf.pages:
            # Extract tables
            tables = page.extract_tables()
            
            for table in tables:
                if not table:
                    continue
                
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    
                    # Clean row
                    row = [cell.strip() if cell else "" for cell in row]
                    
                    # Skip empty rows
                    if all(not cell for cell in row):
                        continue
                    
                    # Detect section headers
                    first_cell = row[0].lower() if row[0] else ""
                    if "payments and credits" in first_cell:
                        current_section = "payments"
                        continue
                    elif "transactions" in first_cell or "new charges" in first_cell:
                        current_section = "transactions"
                        continue
                    elif any(skip in first_cell for skip in [
                        "fees", "interest", "total", "date", "description",
                        "balance", "payment", "credit limit", "minimum"
                    ]):
                        continue
                    
                    # Try to parse as transaction
                    txn = _parse_transaction_row(row, current_section, file_hash)
                    if txn:
                        transactions.append(txn)
            
            # Also try text extraction for tables that don't parse well
            text = page.extract_text()
            if text:
                text_txns = _parse_from_text(text, file_hash)
                existing_hashes = {t.transaction_hash for t in transactions}
                for txn in text_txns:
                    if txn.transaction_hash not in existing_hashes:
                        transactions.append(txn)
    
    return transactions


def _parse_transaction_row(
    row: list[str],
    section: Optional[str],
    file_hash: str
) -> Optional[Transaction]:
    """Parse a transaction from a table row."""
    try:
        # Need at least date and amount
        if len(row) < 2:
            return None
        
        # Find date (first column usually)
        date_str = row[0]
        txn_date = _parse_date(date_str)
        if not txn_date:
            return None
        
        # Find amount (last column usually)
        amount_str = row[-1]
        amount = _parse_amount(amount_str)
        if amount is None:
            return None
        
        # Description is middle column(s)
        if len(row) >= 3:
            description = row[1]
        else:
            description = "Coinbase Card Transaction"
        
        # Clean up description (remove extra whitespace, newlines)
        description = " ".join(description.split())
        
        # Skip totals and summaries
        if not description or "total" in description.lower():
            return None
        
        # Determine sign based on section
        # Payments/credits are positive (money back to us)
        # Transactions/purchases are negative (spending)
        if section == "payments":
            # Credits/refunds - keep as positive or make positive
            amount = abs(amount)
        else:
            # Purchases - make negative
            amount = -abs(amount)
        
        # Skip zero amounts
        if amount == 0:
            return None
        
        txn_hash = compute_transaction_hash(
            TransactionSource.COINBASE, txn_date, description, amount
        )
        
        return Transaction(
            source=TransactionSource.COINBASE,
            source_file_hash=file_hash,
            transaction_hash=txn_hash,
            date=txn_date,
            description=description,
            amount=amount,
        )
    except Exception:
        return None


def _parse_from_text(text: str, file_hash: str) -> list[Transaction]:
    """Parse transactions from raw text as fallback."""
    transactions: list[Transaction] = []
    current_section = None
    
    lines = text.split("\n")
    
    # Pattern for transaction lines: "Sep 4, 2025 DESCRIPTION $XX.XX"
    # Date can be "Sep 4, 2025" or "Sept 14, 2025"
    txn_pattern = re.compile(
        r"^((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\s+"  # Date
        r"(.+?)\s+"  # Description
        r"(-?\$?[\d,]+\.?\d*)\s*$"  # Amount
    )
    
    for line in lines:
        line = line.strip()
        line_lower = line.lower()
        
        # Detect sections
        if "payments and credits" in line_lower:
            current_section = "payments"
            continue
        elif "transactions" in line_lower and "total" not in line_lower:
            current_section = "transactions"
            continue
        
        # Skip non-transaction lines
        if any(skip in line_lower for skip in [
            "total", "fees", "interest", "balance", "payment due",
            "credit limit", "minimum", "coinbase one card", "page"
        ]):
            continue
        
        # Try to match transaction
        match = txn_pattern.match(line)
        if match:
            date_str = match.group(1)
            description = match.group(2).strip()
            amount_str = match.group(3)
            
            txn_date = _parse_date(date_str)
            if not txn_date:
                continue
            
            amount = _parse_amount(amount_str)
            if amount is None:
                continue
            
            # Clean description
            description = " ".join(description.split())
            
            # Determine sign
            if current_section == "payments":
                amount = abs(amount)
            else:
                amount = -abs(amount)
            
            if amount == 0:
                continue
            
            txn_hash = compute_transaction_hash(
                TransactionSource.COINBASE, txn_date, description, amount
            )
            
            transactions.append(Transaction(
                source=TransactionSource.COINBASE,
                source_file_hash=file_hash,
                transaction_hash=txn_hash,
                date=txn_date,
                description=description,
                amount=amount,
            ))
    
    return transactions


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from various formats."""
    if not date_str:
        return None
    
    # Normalize "Sept" to "Sep"
    date_str = date_str.replace("Sept ", "Sep ")
    
    formats = [
        "%b %d, %Y",   # Sep 4, 2025
        "%B %d, %Y",   # September 4, 2025
        "%m/%d/%Y",    # 09/04/2025
        "%m-%d-%Y",    # 09-04-2025
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
        
        # Handle negative in parentheses
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        
        # Handle empty or dash
        if not cleaned or cleaned == "-":
            return None
        
        return float(cleaned)
    except ValueError:
        return None


def is_coinbase_pdf(contents: bytes) -> bool:
    """Check if this PDF is a Coinbase Card statement."""
    try:
        with pdfplumber.open(BytesIO(contents)) as pdf:
            if pdf.pages:
                text = pdf.pages[0].extract_text() or ""
                return "Coinbase" in text and ("One Card" in text or "Card" in text)
    except Exception:
        pass
    return False

