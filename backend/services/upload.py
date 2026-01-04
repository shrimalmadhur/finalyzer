"""File upload processing service."""

import asyncio
from datetime import datetime
from typing import Dict, Optional

from backend.config import settings
from backend.db.sqlite import db
from backend.db.vector import vector_store
from backend.models import (
    Transaction,
    TransactionSource,
    UploadedFile,
    UploadResponse,
)
from backend.parsers.amex_csv import parse_amex_csv
from backend.parsers.amex_year_end_pdf import is_amex_year_end_summary, parse_amex_year_end_pdf
from backend.parsers.chase_csv import parse_chase_csv
from backend.parsers.chase_pdf import parse_chase_pdf
from backend.parsers.chase_report_pdf import is_chase_spending_report, parse_chase_report_pdf
from backend.parsers.coinbase_csv import parse_coinbase_csv
from backend.parsers.coinbase_pdf import parse_coinbase_pdf, is_coinbase_pdf
from backend.parsers.generic import parse_generic
from backend.services.dedup import compute_file_hash
from backend.services.categorizer import (
    categorize_transactions_fast,
    schedule_llm_categorization,
    start_processing_job,
    complete_processing_job,
)
from backend.services.tagger import schedule_llm_tagging, tag_transactions_fast
from backend.services.progress import update_progress, get_progress, clear_progress


def detect_source(filename: str, contents: bytes) -> TransactionSource:
    """Detect the source of a financial statement based on filename and contents."""
    filename_lower = filename.lower()

    # Check filename patterns
    if "chase" in filename_lower:
        return TransactionSource.CHASE_CREDIT
    if "amex" in filename_lower or "american express" in filename_lower:
        return TransactionSource.AMEX
    if "coinbase" in filename_lower:
        return TransactionSource.COINBASE

    # For PDFs, check content to detect Amex Year-End Summary
    if filename_lower.endswith(".pdf"):
        try:
            from io import BytesIO

            import pdfplumber

            with pdfplumber.open(BytesIO(contents)) as pdf:
                first_page_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
                if is_amex_year_end_summary(first_page_text):
                    return TransactionSource.AMEX
        except Exception:
            pass

    # For CSV files, try to detect by content
    if filename_lower.endswith(".csv"):
        content_str = contents.decode("utf-8", errors="ignore").lower()

        # Amex CSV typically has these headers
        if "date,description,amount" in content_str or "reference" in content_str:
            if "amex" in content_str or "american express" in content_str:
                return TransactionSource.AMEX

        # Coinbase CSV patterns
        if "coinbase" in content_str or "crypto" in content_str:
            return TransactionSource.COINBASE

        # Default CSV to Amex (most common)
        return TransactionSource.AMEX

    # PDF files - check content to detect source
    if filename_lower.endswith(".pdf"):
        # Check if it's a Coinbase PDF
        if is_coinbase_pdf(contents):
            return TransactionSource.COINBASE
        # Default to Chase
        return TransactionSource.CHASE_CREDIT

    raise ValueError(f"Could not detect source for file: {filename}")


async def process_upload(filename: str, contents: bytes) -> UploadResponse:
    """Process an uploaded financial statement."""
    # Check for duplicate file
    file_hash = compute_file_hash(contents)
    if db.file_exists(file_hash):
        return UploadResponse(
            filename=filename,
            source=TransactionSource.CHASE_CREDIT,  # Placeholder
            transactions_added=0,
            transactions_skipped=0,
            message="This file has already been uploaded",
            file_hash=file_hash,
        )

    # Parse transactions using generic parser or format-specific parsers
    filename_lower = filename.lower()

    if settings.use_generic_parser:
        # NEW: Use LLM-based generic parser (works for any PDF or CSV)
        print(f"Using generic LLM parser for {filename}")

        # Start background processing immediately - don't block the request
        task = asyncio.create_task(_background_generic_parsing(filename, contents, file_hash))

        # Add error handler to catch any exceptions
        def handle_task_error(task):
            try:
                task.result()
            except Exception as e:
                print(f"❌ Background task error: {e}")
                import traceback
                traceback.print_exc()

        task.add_done_callback(handle_task_error)

        # Return immediately with processing status
        print(f"✅ File uploaded: {filename} - Processing in background...")
        print(f"⏳ This may take 1-2 minutes for large files. Watch the backend logs for progress.")

        return UploadResponse(
            filename=filename,
            source=TransactionSource.UNKNOWN,  # Will be determined by LLM
            transactions_added=0,
            transactions_skipped=0,
            message=f"⏳ Processing {filename} in background... This may take 1-2 minutes for large files. Transactions will appear as processing completes. Refresh the page to see new transactions.",
            file_hash=file_hash,
        )
    else:
        # OLD: Use format-specific parsers (backward compatible)
        source = detect_source(filename, contents)

        if source == TransactionSource.CHASE_CREDIT:
            if filename_lower.endswith(".csv"):
                transactions = parse_chase_csv(contents, file_hash)
            elif filename_lower.endswith(".pdf"):
                # Check if it's a Spending Report PDF vs regular statement
                if is_chase_spending_report(contents):
                    print("Detected Chase Spending Report PDF")
                    transactions = parse_chase_report_pdf(contents, file_hash)
                else:
                    transactions = parse_chase_pdf(contents, file_hash)
            else:
                transactions = parse_chase_pdf(contents, file_hash)
        elif source == TransactionSource.AMEX:
            if filename_lower.endswith(".pdf"):
                print("Detected Amex Year-End Summary PDF")
                transactions = parse_amex_year_end_pdf(contents, file_hash)
            else:
                transactions = parse_amex_csv(contents, file_hash)
        elif source == TransactionSource.COINBASE:
            if filename_lower.endswith(".pdf"):
                print("Detected Coinbase Card PDF statement")
                transactions = parse_coinbase_pdf(contents, file_hash)
            else:
                transactions = parse_coinbase_csv(contents, file_hash)
        else:
            raise ValueError(f"Unsupported source: {source}")

    if not transactions:
        return UploadResponse(
            filename=filename,
            source=source,
            transactions_added=0,
            transactions_skipped=0,
            message="No transactions found in file",
            file_hash=file_hash,
        )

    print(f"Parsed {len(transactions)} transactions from {filename}")

    # Fast categorization: use raw_category from source, no LLM yet
    categorize_transactions_fast(transactions)

    # Fast tagging: use known merchant patterns, no LLM yet
    tag_transactions_fast(transactions)

    # Add transactions to database immediately (don't wait for LLM)
    added, skipped = db.add_transactions_batch(transactions)

    print(f"Added {added} transactions, skipped {skipped} duplicates")

    # Count how many still need LLM processing
    uncategorized = sum(1 for t in transactions if not t.category)
    untagged = sum(1 for t in transactions if not t.tags)
    needs_processing = uncategorized + untagged

    # Record the uploaded file
    if added > 0:
        uploaded_file = UploadedFile(
            filename=filename,
            file_hash=file_hash,
            source=source,
            transaction_count=added,
            uploaded_at=datetime.now().isoformat(),
        )
        db.add_uploaded_file(uploaded_file)

        # Schedule background tasks for LLM categorization, tagging, and vector store
        # This runs after we return the response to the user
        if needs_processing > 0:
            start_processing_job(file_hash, filename, needs_processing)
        asyncio.create_task(_background_processing(transactions, file_hash))

    message = f"Successfully processed {added} transactions"
    if skipped > 0:
        message += f" ({skipped} duplicates skipped)"
    if uncategorized > 0:
        message += f". {uncategorized} will be categorized by AI in the background."

    return UploadResponse(
        filename=filename,
        source=source,
        transactions_added=added,
        transactions_skipped=skipped,
        message=message,
        file_hash=file_hash,
    )


async def _background_generic_parsing(filename: str, contents: bytes, file_hash: str) -> None:
    """Background task to parse file with generic LLM parser and add transactions to database."""
    try:
        print(f"\n" + "=" * 80)
        print(f"🚀 BACKGROUND PROCESSING STARTED: {filename}")
        print("=" * 80)

        update_progress(file_hash, "processing", 0, f"Starting to parse {filename}...")

        # Parse with generic LLM parser (this may take 1-2 minutes for large files)
        print(f"📄 Parsing {filename} with LLM-based generic parser...")
        update_progress(file_hash, "processing", 10, "Analyzing document with LLM...")

        transactions = await parse_generic(filename, contents, file_hash)

        if not transactions:
            print(f"⚠️  No transactions extracted from {filename}")
            update_progress(file_hash, "error", 100, "No transactions found")
            complete_processing_job(file_hash, error="No transactions found")
            return

        # Infer source from first transaction
        source = transactions[0].source
        print(f"✅ Successfully extracted {len(transactions)} transactions from {source.value}")
        update_progress(file_hash, "processing", 60, f"Extracted {len(transactions)} transactions")

        # Fast categorization: use raw_category from source, no LLM yet
        print(f"🏷️  Running fast categorization...")
        update_progress(file_hash, "processing", 70, "Categorizing transactions...")
        categorize_transactions_fast(transactions)

        # Fast tagging: use known merchant patterns, no LLM yet
        print(f"🔖 Running fast tagging...")
        update_progress(file_hash, "processing", 75, "Tagging merchants...")
        tag_transactions_fast(transactions)

        # Add transactions to database
        print(f"💾 Adding {len(transactions)} transactions to database...")
        update_progress(file_hash, "processing", 80, "Saving to database...")
        added, skipped = db.add_transactions_batch(transactions)
        print(f"✅ Database updated: {added} added, {skipped} duplicates skipped")

        # Record the uploaded file
        if added > 0:
            uploaded_file = UploadedFile(
                filename=filename,
                file_hash=file_hash,
                source=source,
                transaction_count=added,
                uploaded_at=datetime.now().isoformat(),
            )
            db.add_uploaded_file(uploaded_file)
            print(f"📝 File record saved to database")

            # Count how many still need LLM processing
            uncategorized = sum(1 for t in transactions if not t.category)
            untagged = sum(1 for t in transactions if not t.tags)
            needs_processing = uncategorized + untagged

            # Schedule background LLM categorization and tagging
            if needs_processing > 0:
                print(f"🤖 Scheduling LLM processing for {needs_processing} items...")
                start_processing_job(file_hash, filename, needs_processing)

            # Continue with categorization, tagging, and vector store
            print(f"🔄 Starting background LLM categorization & tagging...")
            update_progress(file_hash, "processing", 90, "Running AI categorization...")
            await _background_processing(transactions, file_hash)

            print("=" * 80)
            print(f"✅ BACKGROUND PROCESSING COMPLETE: {filename}")
            print(f"   Total transactions added: {added}")
            print("=" * 80 + "\n")

            update_progress(file_hash, "complete", 100, f"✅ Complete! Added {added} transactions", {
                "transactions_added": added,
                "transactions_skipped": skipped,
            })

            # Clear progress after 30 seconds
            await asyncio.sleep(30)
            clear_progress(file_hash)
        else:
            print(f"ℹ️  All transactions from {filename} were duplicates - nothing added")
            update_progress(file_hash, "complete", 100, "All transactions were duplicates")
            await asyncio.sleep(30)
            clear_progress(file_hash)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ BACKGROUND PROCESSING FAILED: {filename}")
        print(f"   Error: {e}")
        print("=" * 80 + "\n")
        import traceback
        traceback.print_exc()

        update_progress(file_hash, "error", 100, f"Error: {str(e)}")
        complete_processing_job(file_hash, error=str(e))

        # Clear progress after 30 seconds
        await asyncio.sleep(30)
        clear_progress(file_hash)


async def _background_processing(transactions: list[Transaction], file_hash: str) -> None:
    """Background task to categorize and tag transactions with LLM, then add to vector store."""
    try:
        # Get IDs of transactions that need LLM categorization
        uncategorized_ids = [str(t.id) for t in transactions if not t.category]

        if uncategorized_ids:
            print(f"Background: Starting LLM categorization for {len(uncategorized_ids)} transactions...")
            await schedule_llm_categorization(uncategorized_ids, file_hash)
            print("Background: LLM categorization complete")

        # Get IDs of transactions that need LLM tagging
        untagged_ids = [str(t.id) for t in transactions if not t.tags]

        if untagged_ids:
            print(f"Background: Starting LLM tagging for {len(untagged_ids)} transactions...")
            await schedule_llm_tagging(untagged_ids, file_hash)
            print("Background: LLM tagging complete")

        # Refresh transactions from DB to get updated tags for vector store
        all_ids = [str(t.id) for t in transactions]
        updated_transactions = db.get_transactions_by_ids(all_ids)

        # Add to vector store with tags
        print(f"Background: Adding {len(updated_transactions)} transactions to vector store...")
        await vector_store.add_transactions_batch(updated_transactions)
        print("Background: Vector store update complete")

        # Mark processing as complete
        complete_processing_job(file_hash)

    except Exception as e:
        print(f"Background processing error: {e}")
        complete_processing_job(file_hash, error=str(e))
