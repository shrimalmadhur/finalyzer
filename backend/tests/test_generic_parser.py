"""Tests for the generic LLM-based transaction parser."""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from backend.models import TransactionCategory, TransactionSource
from backend.parsers.document_types import DocumentMetadata, RawTransaction
from backend.parsers.generic import (
    _create_transaction,
    _deduplicate_within_file,
    _detect_file_type,
    _validate_transactions,
    parse_generic,
)
from backend.parsers.llm_client import ParsingError
from backend.services.dedup import compute_file_hash

# Test constants
TEST_HASH = "a" * 64  # Valid SHA256 hash (64 hex chars)


class TestDetectFileType:
    """Test file type detection."""

    def test_detects_pdf(self):
        """Should detect PDF files."""
        assert _detect_file_type("statement.pdf") == "pdf"
        assert _detect_file_type("Statement.PDF") == "pdf"

    def test_detects_csv(self):
        """Should detect CSV files."""
        assert _detect_file_type("statement.csv") == "csv"
        assert _detect_file_type("Statement.CSV") == "csv"

    def test_defaults_to_csv(self):
        """Should default to CSV for unknown extensions."""
        assert _detect_file_type("statement.txt") == "csv"
        assert _detect_file_type("statement") == "csv"


class TestCreateTransaction:
    """Test Transaction object creation from RawTransaction."""

    def test_creates_transaction_with_all_required_fields(self):
        """Should populate all required fields."""
        raw_txn = RawTransaction(
            date=date(2024, 12, 1),
            description="STARBUCKS",
            amount=-5.50,
            raw_category="Food & Dining",
        )

        txn = _create_transaction(raw_txn=raw_txn, source=TransactionSource.CHASE_CREDIT, file_hash=TEST_HASH)

        # Required fields
        assert isinstance(txn.id, UUID)
        assert txn.source == TransactionSource.CHASE_CREDIT
        assert txn.source_file_hash == TEST_HASH
        assert isinstance(txn.transaction_hash, str)
        assert len(txn.transaction_hash) == 64  # SHA256 hex
        assert txn.date == date(2024, 12, 1)
        assert txn.description == "STARBUCKS"
        assert txn.amount == -5.50

        # Optional fields
        assert txn.category is None  # Set by categorizer later
        assert txn.raw_category == "Food & Dining"
        assert txn.tags == []  # Set by tagger later

    def test_transaction_hash_is_deterministic(self):
        """Same transaction should produce same hash."""
        raw_txn = RawTransaction(date=date(2024, 12, 1), description="TEST", amount=-10.0, raw_category=None)

        txn1 = _create_transaction(raw_txn, TransactionSource.AMEX, TEST_HASH)
        txn2 = _create_transaction(raw_txn, TransactionSource.AMEX, TEST_HASH)

        assert txn1.transaction_hash == txn2.transaction_hash

    def test_different_transactions_have_different_hashes(self):
        """Different transactions should have different hashes."""
        raw_txn1 = RawTransaction(date=date(2024, 12, 1), description="TEST1", amount=-10.0, raw_category=None)
        raw_txn2 = RawTransaction(date=date(2024, 12, 2), description="TEST2", amount=-20.0, raw_category=None)

        txn1 = _create_transaction(raw_txn1, TransactionSource.AMEX, TEST_HASH)
        txn2 = _create_transaction(raw_txn2, TransactionSource.AMEX, TEST_HASH)

        assert txn1.transaction_hash != txn2.transaction_hash

    def test_handles_unknown_source(self):
        """Should handle UNKNOWN source enum."""
        raw_txn = RawTransaction(date=date(2024, 12, 1), description="TEST", amount=-10.0, raw_category=None)

        txn = _create_transaction(raw_txn, TransactionSource.UNKNOWN, TEST_HASH)

        assert txn.source == TransactionSource.UNKNOWN

    def test_strips_description_whitespace(self):
        """Should strip whitespace from description."""
        raw_txn = RawTransaction(date=date(2024, 12, 1), description="  STARBUCKS  ", amount=-5.50, raw_category=None)

        txn = _create_transaction(raw_txn, TransactionSource.CHASE_CREDIT, TEST_HASH)

        assert txn.description == "STARBUCKS"


class TestDeduplicateWithinFile:
    """Test deduplication logic."""

    def test_removes_exact_duplicates(self):
        """Should remove transactions with same hash."""
        raw_txn = RawTransaction(date=date(2024, 12, 1), description="DUP", amount=-10.0, raw_category=None)

        txn1 = _create_transaction(raw_txn, TransactionSource.CHASE_CREDIT, TEST_HASH)
        txn2 = _create_transaction(raw_txn, TransactionSource.CHASE_CREDIT, TEST_HASH)

        # Force same transaction hash
        txn2.transaction_hash = txn1.transaction_hash

        result = _deduplicate_within_file([txn1, txn2])

        assert len(result) == 1
        assert result[0].transaction_hash == txn1.transaction_hash

    def test_keeps_unique_transactions(self):
        """Should keep transactions with different hashes."""
        raw_txn1 = RawTransaction(date=date(2024, 12, 1), description="TXN1", amount=-10.0, raw_category=None)
        raw_txn2 = RawTransaction(date=date(2024, 12, 2), description="TXN2", amount=-20.0, raw_category=None)

        txn1 = _create_transaction(raw_txn1, TransactionSource.CHASE_CREDIT, TEST_HASH)
        txn2 = _create_transaction(raw_txn2, TransactionSource.CHASE_CREDIT, TEST_HASH)

        result = _deduplicate_within_file([txn1, txn2])

        assert len(result) == 2

    def test_handles_empty_list(self):
        """Should handle empty transaction list."""
        result = _deduplicate_within_file([])
        assert len(result) == 0


class TestValidateTransactions:
    """Test transaction validation."""

    def test_validates_all_required_fields(self):
        """Should validate all required fields are present."""
        raw_txn = RawTransaction(date=date(2024, 12, 1), description="VALID", amount=-10.0, raw_category=None)

        txn = _create_transaction(raw_txn, TransactionSource.CHASE_CREDIT, TEST_HASH)

        # Should not raise
        _validate_transactions([txn], TEST_HASH)

    def test_fails_if_invalid_date_year(self):
        """Should fail if date year is invalid."""
        raw_txn = RawTransaction(
            date=date(1999, 12, 1),  # Before 2000
            description="TEST",
            amount=-10.0,
            raw_category=None,
        )

        txn = _create_transaction(raw_txn, TransactionSource.CHASE_CREDIT, TEST_HASH)

        with pytest.raises(ParsingError, match="Invalid date year"):
            _validate_transactions([txn], TEST_HASH)

    def test_fails_if_empty_description(self):
        """Should fail if description is empty."""
        raw_txn = RawTransaction(date=date(2024, 12, 1), description="X", amount=-10.0, raw_category=None)

        txn = _create_transaction(raw_txn, TransactionSource.CHASE_CREDIT, TEST_HASH)
        txn.description = ""  # Force empty after creation

        with pytest.raises(ParsingError, match="Missing description"):
            _validate_transactions([txn], TEST_HASH)

    def test_accepts_empty_list(self):
        """Should accept empty transaction list."""
        _validate_transactions([], TEST_HASH)  # Should not raise


@pytest.mark.asyncio
class TestParseGeneric:
    """Integration tests for parse_generic function."""

    async def test_parses_simple_csv(self):
        """Should parse a simple CSV file with mocked LLM."""
        csv_content = b"""Date,Description,Amount
12/01/2024,STARBUCKS,-5.50
12/02/2024,REFUND FROM AMAZON,25.00
12/03/2024,UBER RIDE,-15.30"""

        file_hash = compute_file_hash(csv_content)

        # Mock LLM responses
        mock_metadata = DocumentMetadata(
            source=TransactionSource.CHASE_CREDIT,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        mock_transactions = [
            RawTransaction(date=date(2024, 12, 1), description="STARBUCKS", amount=-5.50, raw_category=None),
            RawTransaction(
                date=date(2024, 12, 2),
                description="REFUND FROM AMAZON",
                amount=25.00,
                raw_category=None,
            ),
            RawTransaction(date=date(2024, 12, 3), description="UBER RIDE", amount=-15.30, raw_category=None),
        ]

        with patch("backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                transactions = await parse_generic("test.csv", csv_content, file_hash)

        # Verify results
        assert len(transactions) == 3

        # Check first transaction
        assert transactions[0].source == TransactionSource.CHASE_CREDIT
        assert transactions[0].date == date(2024, 12, 1)
        assert transactions[0].description == "STARBUCKS"
        assert transactions[0].amount == -5.50
        assert transactions[0].source_file_hash == file_hash

        # Check second transaction (credit)
        assert transactions[1].amount == 25.00

        # All should have required fields
        for txn in transactions:
            assert isinstance(txn.id, UUID)
            assert txn.transaction_hash
            assert txn.tags == []
            assert txn.category is None

    async def test_handles_unknown_source(self):
        """Should handle unknown source gracefully."""
        csv_content = b"""Date,Description,Amount
12/01/2024,MYSTERY MERCHANT,-10.00"""

        file_hash = compute_file_hash(csv_content)

        mock_metadata = DocumentMetadata(
            source="UNKNOWN",  # type: ignore
            statement_year=2024,
            statement_period="December 2024",
            document_type="transaction_export",
        )

        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1),
                description="MYSTERY MERCHANT",
                amount=-10.00,
                raw_category=None,
            ),
        ]

        with patch("backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                transactions = await parse_generic("unknown.csv", csv_content, file_hash)

        assert len(transactions) == 1
        assert transactions[0].source == TransactionSource.UNKNOWN

    async def test_deduplicates_within_file(self):
        """Should remove duplicate transactions within same file."""
        csv_content = b"""Date,Description,Amount
12/01/2024,DUPLICATE TXN,-10.00
12/01/2024,DUPLICATE TXN,-10.00
12/02/2024,UNIQUE TXN,-20.00"""

        file_hash = compute_file_hash(csv_content)

        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        # LLM returns duplicates
        mock_transactions = [
            RawTransaction(date=date(2024, 12, 1), description="DUPLICATE TXN", amount=-10.00, raw_category=None),
            RawTransaction(date=date(2024, 12, 1), description="DUPLICATE TXN", amount=-10.00, raw_category=None),
            RawTransaction(date=date(2024, 12, 2), description="UNIQUE TXN", amount=-20.00, raw_category=None),
        ]

        with patch("backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                transactions = await parse_generic("test.csv", csv_content, file_hash)

        # Should only have 2 transactions (duplicate removed)
        assert len(transactions) == 2

    async def test_returns_empty_list_if_no_transactions(self):
        """Should return empty list if LLM finds no transactions."""
        csv_content = b"""Date,Description,Amount
# Just a header, no data"""

        file_hash = compute_file_hash(csv_content)

        mock_metadata = DocumentMetadata(
            source=TransactionSource.CHASE_CREDIT,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        with patch("backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=[]),  # No transactions
            ):
                transactions = await parse_generic("empty.csv", csv_content, file_hash)

        assert len(transactions) == 0

    async def test_handles_parsing_error(self):
        """Should raise ParsingError if LLM fails."""
        csv_content = b"""Invalid CSV content"""

        file_hash = compute_file_hash(csv_content)

        with patch(
            "backend.parsers.generic._analyze_document",
            side_effect=Exception("LLM failed"),
        ):
            with pytest.raises(ParsingError, match="Failed to parse"):
                await parse_generic("bad.csv", csv_content, file_hash)

    async def test_validates_all_fields_populated(self):
        """Should validate all required fields are populated."""
        csv_content = b"""Date,Description,Amount
12/01/2024,VALID TXN,-10.00"""

        file_hash = compute_file_hash(csv_content)

        mock_metadata = DocumentMetadata(
            source=TransactionSource.COINBASE,
            statement_year=2024,
            statement_period="December 2024",
            document_type="transaction_export",
        )

        mock_transactions = [
            RawTransaction(date=date(2024, 12, 1), description="VALID TXN", amount=-10.00, raw_category=None),
        ]

        with patch("backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                transactions = await parse_generic("test.csv", csv_content, file_hash)

        # Comprehensive field validation
        txn = transactions[0]
        assert isinstance(txn.id, UUID)
        assert txn.source == TransactionSource.COINBASE
        assert isinstance(txn.source_file_hash, str)
        assert len(txn.source_file_hash) == 64
        assert txn.source_file_hash == file_hash
        assert isinstance(txn.transaction_hash, str)
        assert len(txn.transaction_hash) == 64
        assert isinstance(txn.date, date)
        assert txn.date.year >= 2000
        assert txn.date.year <= 2030
        assert isinstance(txn.description, str)
        assert len(txn.description) > 0
        assert isinstance(txn.amount, float)
        assert txn.tags == []
        assert txn.category is None or isinstance(txn.category, TransactionCategory)
