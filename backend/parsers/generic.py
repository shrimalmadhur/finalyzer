"""Generic LLM-based transaction parser for any PDF or CSV statement."""

import hashlib
import logging
import uuid
from datetime import date
from io import BytesIO
from typing import Literal

import pandas as pd
import pdfplumber

from backend.models import Transaction, TransactionSource
from backend.parsers.document_types import DocumentMetadata, RawTransaction
from backend.parsers.llm_client import ParsingError, llm_extract_json
from backend.parsers.validation import validate_file_contents
from backend.services.progress import update_progress

logger = logging.getLogger(__name__)


async def parse_generic(filename: str, contents: bytes, file_hash: str) -> list[Transaction]:
    """
    Parse any financial statement using LLM-based extraction.

    Args:
        filename: Name of the uploaded file
        contents: File contents as bytes
        file_hash: SHA256 hash of file contents

    Returns:
        List of Transaction objects with all required fields populated

    Raises:
        ParsingError: If parsing fails
    """
    try:
        print("🔍 [parse_generic] Step 1: Validating file size...")
        # Validate file size
        validate_file_contents(contents)

        print("🔍 [parse_generic] Step 2: Detecting file type...")
        # Detect file type
        file_type = _detect_file_type(filename)
        print(f"🔍 [parse_generic] Detected file type: {file_type}")

        print("🔍 [parse_generic] Step 3: Extracting content...")
        # Extract content from document
        if file_type == "pdf":
            full_text, tables = _extract_pdf_content(contents)
            content_preview = full_text[:2000]  # For document analysis
            extraction_content = _format_pdf_tables(tables) if tables else full_text
            print(f"📄 PDF: Extracted {len(full_text)} chars of text, {len(tables)} tables")
        else:  # CSV
            df = _extract_csv_content(contents)
            content_preview = df.head(10).to_string(index=False)  # For document analysis
            extraction_content = df.to_string(index=False)  # For transaction extraction
            print(f"📊 CSV: Extracted {len(df)} rows")
        print("🔍 [parse_generic] Content extracted successfully")

        # Phase 1: Analyze document metadata
        print("🔍 [parse_generic] Step 4: Analyzing document metadata...")
        metadata = await _analyze_document(content_preview)
        print(f"🔍 [parse_generic] Metadata: source={metadata.source}, year={metadata.statement_year}")

        # Phase 2: Extract transactions in batches
        print("🔍 [parse_generic] Step 5: Extracting transactions in batches...")
        raw_transactions = await _extract_transactions_batch(
            content=extraction_content, metadata=metadata, file_type=file_type, file_hash=file_hash
        )
        print(f"🔍 [parse_generic] Extracted {len(raw_transactions)} raw transactions")

        if not raw_transactions:
            logger.warning(f"No transactions extracted from {filename}")
            return []

        # Convert to Transaction objects with all required fields
        transactions = []
        for raw_txn in raw_transactions:
            txn = _create_transaction(
                raw_txn=raw_txn, source=metadata.source, file_hash=file_hash
            )
            transactions.append(txn)

        # Deduplicate within file
        transactions = _deduplicate_within_file(transactions)

        # Validate all required fields present
        _validate_transactions(transactions, file_hash)

        logger.info(f"Successfully extracted {len(transactions)} transactions from {filename}")
        return transactions

    except Exception as e:
        logger.error(f"Generic parser failed for {filename}: {e}")
        raise ParsingError(f"Failed to parse {filename}: {str(e)}")


def _detect_file_type(filename: str) -> Literal["pdf", "csv"]:
    """Detect file type from filename."""
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        return "pdf"
    elif filename_lower.endswith(".csv"):
        return "csv"
    else:
        # Default to CSV for unknown extensions
        return "csv"


def _extract_pdf_content(contents: bytes) -> tuple[str, list[list[list[str]]]]:
    """
    Extract text and tables from PDF.

    Returns:
        (full_text, tables) tuple
    """
    full_text = ""
    all_tables = []

    try:
        with pdfplumber.open(BytesIO(contents)) as pdf:
            for page in pdf.pages:
                # Extract text
                text = page.extract_text() or ""
                full_text += text + "\n\n"

                # Extract tables
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ParsingError(f"Failed to extract PDF content: {e}")

    if not full_text.strip() and not all_tables:
        raise ParsingError("PDF appears to be empty or unreadable")

    return full_text, all_tables


def _extract_csv_content(contents: bytes) -> pd.DataFrame:
    """Extract CSV as pandas DataFrame."""
    try:
        # Try multiple encodings
        for encoding in ["utf-8", "latin-1", "cp1252"]:
            try:
                df = pd.read_csv(BytesIO(contents), encoding=encoding)
                # Return even if empty - let the parsing flow handle it
                return df
            except UnicodeDecodeError:
                continue

        raise ParsingError("Failed to decode CSV with any supported encoding")

    except ParsingError:
        raise
    except Exception as e:
        logger.error(f"CSV extraction failed: {e}")
        raise ParsingError(f"Failed to extract CSV content: {e}")


def _format_pdf_tables(tables: list[list[list[str]]]) -> str:
    """Format PDF tables as string for LLM processing."""
    formatted = ""
    for i, table in enumerate(tables):
        formatted += f"\n--- Table {i + 1} ---\n"
        for row in table:
            if row:  # Skip empty rows
                formatted += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
    return formatted


async def _analyze_document(content_preview: str) -> DocumentMetadata:
    """
    Phase 1: Analyze document to extract metadata via LLM.

    Args:
        content_preview: First 2000 characters of document

    Returns:
        DocumentMetadata with source, year, period
    """
    prompt = f"""Analyze this financial statement and extract metadata.

Document preview (first 2000 characters):
{content_preview}

Extract the following as JSON:
{{
  "source": "chase_credit" | "amex" | "coinbase" | "unknown",
  "statement_year": 2024,
  "statement_period": "December 2024",
  "document_type": "monthly_statement"
}}

Detection rules:
- Look for brand names: "Chase", "JPMorgan Chase", "American Express", "Amex", "Coinbase"
- Look for statement headers, account numbers, company names
- If Chase detected, use "chase_credit"
- If American Express or Amex detected, use "amex"
- If Coinbase detected, use "coinbase"
- If uncertain, use "unknown"
- Extract the primary year from statement dates or transaction dates (NOT current year)
- statement_period should be like "December 2024" or "2024-12-01 to 2024-12-31"
- document_type: "monthly_statement", "year_end_summary", or "transaction_export"

Only respond with JSON, nothing else."""

    try:
        return await llm_extract_json(prompt, DocumentMetadata, timeout=30.0)
    except Exception as e:
        logger.error(f"Document analysis failed: {e}")
        # Fallback to UNKNOWN source
        return DocumentMetadata(
            source="UNKNOWN",
            statement_year=date.today().year,
            statement_period="Unknown",
            document_type="unknown",
        )


async def _extract_transactions_batch(
    content: str, metadata: DocumentMetadata, file_type: Literal["pdf", "csv"], file_hash: str
) -> list[RawTransaction]:
    """
    Phase 2: Extract transactions from document via LLM.

    Args:
        content: Document content (tables or CSV data)
        metadata: Document metadata from Phase 1
        file_type: "pdf" or "csv"

    Returns:
        List of RawTransaction objects
    """
    print(f"🔍 [_extract_transactions_batch] Starting batch extraction for {file_type}")

    # Update progress: starting batch processing
    update_progress(file_hash, "processing", 15, "Preparing to extract transactions...")

    # Split content into batches for large files
    if file_type == "csv":
        # For CSV, batch by rows (50 rows per batch to avoid LLM timeouts)
        lines = content.split('\n')
        header = lines[0] if lines else ""
        data_lines = lines[1:] if len(lines) > 1 else []

        batches = []
        batch_size = 50  # Reduced from 200 to avoid Ollama timeouts

        for i in range(0, len(data_lines), batch_size):
            batch_lines = data_lines[i:i + batch_size]
            batch_content = header + '\n' + '\n'.join(batch_lines)
            batches.append(batch_content)

        print(f"📊 Processing CSV in {len(batches)} batches ({len(data_lines)} total rows)")
        print("   ℹ️  Note: LLM will filter out payments and invalid transactions")

        # Update progress with batch count
        update_progress(file_hash, "processing", 20, f"Processing {len(batches)} batches of transactions...")
    else:
        # For PDF, use character-based batching (1500 chars per batch to avoid incomplete responses)
        batches = []
        batch_size = 1500  # Smaller batches ensure LLM can complete JSON response within token limit

        for i in range(0, len(content), batch_size):
            batches.append(content[i:i + batch_size])

        print(f"📄 Processing PDF in {len(batches)} batches ({len(content)} total chars)")

        # Update progress with batch count
        update_progress(file_hash, "processing", 20, f"Processing {len(batches)} batches of transactions...")

    # Process batches in parallel for speed
    from pydantic import BaseModel

    class TransactionList(BaseModel):
        transactions: list[RawTransaction]

    # Track cumulative transaction count across batches
    cumulative_count = {"total": 0}  # Using dict to allow mutation in nested function

    async def process_batch(batch_num: int, batch_content: str) -> list[RawTransaction]:
        """Process a single batch."""
        print(f"⚙️  Processing batch {batch_num}/{len(batches)}...")
        print(f"   Batch size: {len(batch_content)} chars")

        prompt = f"""Extract financial transactions from this statement data.

Source: {metadata.source}
Statement Period: {metadata.statement_period}
Statement Year: {metadata.statement_year}

Data to parse (Batch {batch_num}/{len(batches)}):
{batch_content}

Extract ALL transactions as a JSON array. For each transaction:
{{
  "date": "YYYY-MM-DD",
  "description": "Merchant name or transaction description",
  "amount": -123.45,
  "raw_category": "Food & Dining"
}}

CRITICAL RULES:
1. Amount signs:
   - Expenses/purchases: NEGATIVE (e.g., -50.00)
   - Credits/refunds/payments received: POSITIVE (e.g., +50.00)

2. Skip these transaction types (do NOT include):
   - Credit card payments ("Payment - Thank You", "Autopay", "AUTOMATIC PAYMENT")
   - Balance transfers between accounts
   - Statement credits/adjustments (unless actual refunds)

3. Date handling:
   - Convert MM/DD to {metadata.statement_year}-MM-DD
   - Handle MM/DD/YYYY or MM/DD/YY formats
   - If month appears to be from next year (e.g., Jan after Dec in statement), use {metadata.statement_year + 1}

4. Description cleaning:
   - Remove reference IDs, card numbers (XX1234)
   - Keep merchant name and location if present
   - Normalize spacing

5. Raw category:
   - Only include if the statement provides a category
   - Use exact category text from statement
   - Set to null if not provided

Respond with a JSON array of transactions, nothing else.
Example: [{{"date": "2024-12-01", "description": "STARBUCKS", "amount": -5.50, "raw_category": null}}]"""

        try:
            # Modify prompt to wrap in object
            wrapped_prompt = prompt.replace(
                "Respond with a JSON array",
                'Respond with JSON object: {"transactions": [...]}, nothing else',
            )

            print(f"   📞 Calling LLM for batch {batch_num}... (timeout: 180s)")
            import time
            start_time = time.time()

            result = await llm_extract_json(wrapped_prompt, TransactionList, timeout=180.0)

            elapsed = time.time() - start_time
            print(f"   ✅ LLM response received in {elapsed:.1f}s")

            batch_transactions = result.transactions

            # Update cumulative count
            cumulative_count["total"] += len(batch_transactions)
            total_so_far = cumulative_count["total"]

            print(f"✅ Batch {batch_num}/{len(batches)}: Extracted {len(batch_transactions)} transactions (total: {total_so_far})")

            # Update progress: batch completed (scale from 20% to 55%)
            batch_progress = 20 + int((batch_num / len(batches)) * 35)
            update_progress(
                file_hash,
                "processing",
                batch_progress,
                f"Processed batch {batch_num}/{len(batches)} - {total_so_far} transactions extracted"
            )

            return batch_transactions

        except Exception as e:
            print(f"❌ Batch {batch_num} extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    # Process all batches in parallel (with concurrency limit)
    print(f"🔍 [_extract_transactions_batch] Creating {len(batches)} tasks...")
    tasks = [process_batch(i + 1, batch) for i, batch in enumerate(batches)]

    # Limit concurrency to 3 parallel batches to avoid overwhelming the LLM
    semaphore = asyncio.Semaphore(3)

    async def process_with_semaphore(task):
        async with semaphore:
            return await task

    print("🔍 [_extract_transactions_batch] Starting parallel processing (max 3 concurrent)...")
    results = await asyncio.gather(*[process_with_semaphore(task) for task in tasks])
    print("🔍 [_extract_transactions_batch] All batches completed!")

    # Flatten results
    print("🔍 [_extract_transactions_batch] Flattening results...")
    all_transactions = []
    for batch_transactions in results:
        all_transactions.extend(batch_transactions)

    print(f"✅ Total transactions extracted: {len(all_transactions)}")
    return all_transactions


def _create_transaction(
    raw_txn: RawTransaction, source: TransactionSource | Literal["UNKNOWN"], file_hash: str
) -> Transaction:
    """
    Convert RawTransaction to Transaction with all required fields.

    Args:
        raw_txn: Raw transaction from LLM
        source: Transaction source from document analysis
        file_hash: SHA256 hash of file

    Returns:
        Transaction object with all required fields populated
    """
    # Convert "UNKNOWN" string to actual UNKNOWN enum value if needed
    if source == "UNKNOWN":
        source = TransactionSource.UNKNOWN  # type: ignore

    # Compute transaction hash for deduplication
    hash_input = f"{source.value}|{raw_txn.date}|{raw_txn.description}|{raw_txn.amount}"
    txn_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    return Transaction(
        id=uuid.uuid4(),
        source=source,  # type: ignore
        source_file_hash=file_hash,
        transaction_hash=txn_hash,
        date=raw_txn.date,
        description=raw_txn.description.strip(),
        amount=raw_txn.amount,
        category=None,  # Will be set by categorizer service
        raw_category=raw_txn.raw_category,
        tags=[],  # Will be set by tagger service
    )


def _deduplicate_within_file(transactions: list[Transaction]) -> list[Transaction]:
    """Remove duplicate transactions within the same file."""
    seen_hashes = set()
    deduplicated = []

    for txn in transactions:
        if txn.transaction_hash not in seen_hashes:
            seen_hashes.add(txn.transaction_hash)
            deduplicated.append(txn)
        else:
            logger.debug(f"Skipping duplicate transaction: {txn.description} on {txn.date}")

    if len(deduplicated) < len(transactions):
        logger.info(f"Removed {len(transactions) - len(deduplicated)} duplicate transactions")

    return deduplicated


def _validate_transactions(transactions: list[Transaction], file_hash: str) -> None:
    """
    Validate that all transactions have required fields populated correctly.

    Raises:
        ParsingError: If validation fails
    """
    if not transactions:
        return

    for i, txn in enumerate(transactions):
        # Required fields
        if txn.id is None:
            raise ParsingError(f"Transaction {i}: Missing id")
        if txn.source not in TransactionSource:
            raise ParsingError(f"Transaction {i}: Invalid source: {txn.source}")
        if not txn.source_file_hash or len(txn.source_file_hash) != 64:
            raise ParsingError(f"Transaction {i}: Invalid source_file_hash")
        if txn.source_file_hash != file_hash:
            raise ParsingError(f"Transaction {i}: source_file_hash mismatch")
        if not txn.transaction_hash or len(txn.transaction_hash) != 64:
            raise ParsingError(f"Transaction {i}: Invalid transaction_hash")
        if not txn.date:
            raise ParsingError(f"Transaction {i}: Missing date")
        if txn.date.year < 2000 or txn.date.year > 2030:
            raise ParsingError(f"Transaction {i}: Invalid date year: {txn.date.year}")
        if not txn.description or len(txn.description) == 0:
            raise ParsingError(f"Transaction {i}: Missing description")
        if txn.amount is None:
            raise ParsingError(f"Transaction {i}: Missing amount")

        # Optional fields can be None/empty (no validation needed)
        # tags, category, raw_category

    # Sanity checks
    if len(transactions) > 1000:
        logger.warning(f"Suspiciously high transaction count: {len(transactions)}")

    logger.debug(f"Validation passed for {len(transactions)} transactions")
