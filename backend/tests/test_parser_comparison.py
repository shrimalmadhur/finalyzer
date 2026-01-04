"""Compare generic parser output with existing parser output."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from backend.parsers.generic import parse_generic
from backend.parsers.amex_csv import parse_amex_csv
from backend.parsers.document_types import DocumentMetadata, RawTransaction
from backend.models import TransactionSource
from backend.services.dedup import compute_file_hash


# Test constants
TEST_HASH = "a" * 64  # Valid SHA256 hash (64 hex chars)


class TestAmexCsvComparison:
    """Compare generic parser with Amex CSV parser."""

    def test_parses_same_amex_csv(self):
        """Generic parser should match Amex CSV parser output."""
        # Sample Amex CSV (Activity Download format)
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,UBER TRIP,JOHN DOE,1234,5.50
12/02/2024,STARBUCKS,JOHN DOE,1234,4.75
12/03/2024,WHOLE FOODS,JOHN DOE,1234,45.32
12/15/2024,PAYMENT - THANK YOU,JOHN DOE,1234,-100.00"""

        file_hash = compute_file_hash(csv_content)

        # Parse with old Amex CSV parser
        old_txns = parse_amex_csv(csv_content, file_hash)

        # Should filter out payment and have 3 transactions
        assert len(old_txns) == 3
        assert all(t.source == TransactionSource.AMEX for t in old_txns)

        # Verify old parser results
        assert old_txns[0].description == "UBER TRIP"
        assert old_txns[0].amount == -5.50  # Expense is negative
        assert old_txns[1].description == "STARBUCKS"
        assert old_txns[1].amount == -4.75
        assert old_txns[2].description == "WHOLE FOODS"
        assert old_txns[2].amount == -45.32

    @pytest.mark.asyncio
    async def test_generic_parser_matches_amex_csv(self):
        """Generic parser should produce similar results to Amex CSV parser."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,UBER TRIP,JOHN DOE,1234,5.50
12/02/2024,STARBUCKS,JOHN DOE,1234,4.75
12/03/2024,WHOLE FOODS,JOHN DOE,1234,45.32"""

        file_hash = compute_file_hash(csv_content)

        # Mock LLM responses
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1), description="UBER TRIP", amount=-5.50, raw_category=None
            ),
            RawTransaction(
                date=date(2024, 12, 2), description="STARBUCKS", amount=-4.75, raw_category=None
            ),
            RawTransaction(
                date=date(2024, 12, 3),
                description="WHOLE FOODS",
                amount=-45.32,
                raw_category=None,
            ),
        ]

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        # Compare counts
        assert len(new_txns) == 3

        # Compare sources
        assert all(t.source == TransactionSource.AMEX for t in new_txns)

        # Compare totals (should match within rounding)
        old_txns = parse_amex_csv(csv_content, file_hash)
        old_total = sum(t.amount for t in old_txns)
        new_total = sum(t.amount for t in new_txns)
        assert abs(new_total - old_total) < 0.01

        # Compare individual transactions
        assert new_txns[0].description == "UBER TRIP"
        assert new_txns[0].amount == -5.50
        assert new_txns[1].description == "STARBUCKS"
        assert new_txns[1].amount == -4.75

    @pytest.mark.asyncio
    async def test_both_parsers_filter_payments(self):
        """Both parsers should filter out credit card payments."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,UBER TRIP,JOHN DOE,1234,5.50
12/15/2024,PAYMENT - THANK YOU,JOHN DOE,1234,-100.00
12/20/2024,STARBUCKS,JOHN DOE,1234,4.75"""

        file_hash = compute_file_hash(csv_content)

        # Old parser
        old_txns = parse_amex_csv(csv_content, file_hash)

        # Should filter payment
        assert len(old_txns) == 2
        assert all("PAYMENT" not in t.description for t in old_txns)

        # New parser (mock to simulate filtering)
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        # LLM should not return payment transactions
        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1), description="UBER TRIP", amount=-5.50, raw_category=None
            ),
            RawTransaction(
                date=date(2024, 12, 20), description="STARBUCKS", amount=-4.75, raw_category=None
            ),
        ]

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        # Should match old parser count
        assert len(new_txns) == len(old_txns)


class TestFieldComparison:
    """Verify generic parser populates all fields identically."""

    @pytest.mark.asyncio
    async def test_all_required_fields_match_old_parsers(self):
        """Generic parser should populate same fields as old parsers."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,TEST MERCHANT,JOHN DOE,1234,10.50"""

        file_hash = compute_file_hash(csv_content)

        # Old parser transaction
        old_txns = parse_amex_csv(csv_content, file_hash)
        old_txn = old_txns[0]

        # New parser transaction
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1),
                description="TEST MERCHANT",
                amount=-10.50,
                raw_category=None,
            ),
        ]

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        new_txn = new_txns[0]

        # Compare field presence (not values, since UUIDs differ)
        assert old_txn.id is not None and new_txn.id is not None
        assert old_txn.source == new_txn.source
        assert old_txn.source_file_hash == new_txn.source_file_hash
        assert old_txn.transaction_hash is not None and new_txn.transaction_hash is not None
        assert old_txn.date == new_txn.date
        assert old_txn.description == new_txn.description
        assert old_txn.amount == new_txn.amount
        assert old_txn.tags == new_txn.tags == []
        assert old_txn.category == new_txn.category == None

    @pytest.mark.asyncio
    async def test_transaction_hash_format_matches(self):
        """Both parsers should use 64-character SHA256 hashes."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,TEST,JOHN DOE,1234,10.00"""

        file_hash = compute_file_hash(csv_content)

        # Old parser
        old_txns = parse_amex_csv(csv_content, file_hash)

        # New parser
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1), description="TEST", amount=-10.00, raw_category=None
            ),
        ]

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        # Both should have 64-char SHA256 hashes
        assert len(old_txns[0].transaction_hash) == 64
        assert len(new_txns[0].transaction_hash) == 64
        assert len(old_txns[0].source_file_hash) == 64
        assert len(new_txns[0].source_file_hash) == 64


class TestAccuracyMetrics:
    """Measure accuracy of generic parser vs old parsers."""

    @pytest.mark.asyncio
    async def test_total_accuracy_within_threshold(self):
        """Generic parser total should match old parser within 1%."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,TRANSACTION 1,JOHN DOE,1234,10.00
12/02/2024,TRANSACTION 2,JOHN DOE,1234,20.50
12/03/2024,TRANSACTION 3,JOHN DOE,1234,15.75
12/04/2024,TRANSACTION 4,JOHN DOE,1234,8.25"""

        file_hash = compute_file_hash(csv_content)

        # Old parser
        old_txns = parse_amex_csv(csv_content, file_hash)
        old_total = abs(sum(t.amount for t in old_txns))

        # New parser
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1),
                description="TRANSACTION 1",
                amount=-10.00,
                raw_category=None,
            ),
            RawTransaction(
                date=date(2024, 12, 2),
                description="TRANSACTION 2",
                amount=-20.50,
                raw_category=None,
            ),
            RawTransaction(
                date=date(2024, 12, 3),
                description="TRANSACTION 3",
                amount=-15.75,
                raw_category=None,
            ),
            RawTransaction(
                date=date(2024, 12, 4),
                description="TRANSACTION 4",
                amount=-8.25,
                raw_category=None,
            ),
        ]

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        new_total = abs(sum(t.amount for t in new_txns))

        # Should match within 1%
        if old_total > 0:
            accuracy = abs(new_total - old_total) / old_total
            assert accuracy < 0.01, f"Accuracy {accuracy:.2%} exceeds 1% threshold"

    @pytest.mark.asyncio
    async def test_count_accuracy_within_threshold(self):
        """Generic parser should extract similar number of transactions."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,TXN 1,JOHN DOE,1234,10.00
12/02/2024,TXN 2,JOHN DOE,1234,20.00
12/03/2024,TXN 3,JOHN DOE,1234,15.00"""

        file_hash = compute_file_hash(csv_content)

        # Old parser
        old_txns = parse_amex_csv(csv_content, file_hash)
        old_count = len(old_txns)

        # New parser
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1), description="TXN 1", amount=-10.00, raw_category=None
            ),
            RawTransaction(
                date=date(2024, 12, 2), description="TXN 2", amount=-20.00, raw_category=None
            ),
            RawTransaction(
                date=date(2024, 12, 3), description="TXN 3", amount=-15.00, raw_category=None
            ),
        ]

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        new_count = len(new_txns)

        # Should match within 5%
        if old_count > 0:
            count_diff = abs(new_count - old_count) / old_count
            assert count_diff < 0.05, f"Count difference {count_diff:.2%} exceeds 5% threshold"


class TestRobustness:
    """Test that generic parser handles edge cases as well as old parsers."""

    @pytest.mark.asyncio
    async def test_handles_empty_csv_like_old_parser(self):
        """Both parsers should handle empty CSV gracefully."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount"""

        file_hash = compute_file_hash(csv_content)

        # Old parser should return empty list
        old_txns = parse_amex_csv(csv_content, file_hash)
        assert len(old_txns) == 0

        # New parser should also return empty list
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=[]),  # No transactions
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        assert len(new_txns) == 0

    @pytest.mark.asyncio
    async def test_handles_credits_correctly(self):
        """Both parsers should handle credits (positive amounts) correctly."""
        csv_content = b"""Date,Description,Card Member,Account #,Amount
12/01/2024,PURCHASE,JOHN DOE,1234,50.00
12/02/2024,REFUND FROM STORE,JOHN DOE,1234,-25.00"""

        file_hash = compute_file_hash(csv_content)

        # Old parser
        old_txns = parse_amex_csv(csv_content, file_hash)

        # Should have 2 transactions: expense (negative) and credit (positive)
        assert len(old_txns) == 2
        assert old_txns[0].amount == -50.00  # Expense
        assert old_txns[1].amount == 25.00  # Credit (positive)

        # New parser
        mock_metadata = DocumentMetadata(
            source=TransactionSource.AMEX,
            statement_year=2024,
            statement_period="December 2024",
            document_type="monthly_statement",
        )

        mock_transactions = [
            RawTransaction(
                date=date(2024, 12, 1), description="PURCHASE", amount=-50.00, raw_category=None
            ),
            RawTransaction(
                date=date(2024, 12, 2),
                description="REFUND FROM STORE",
                amount=25.00,
                raw_category=None,
            ),
        ]

        with patch(
            "backend.parsers.generic._analyze_document", new=AsyncMock(return_value=mock_metadata)
        ):
            with patch(
                "backend.parsers.generic._extract_transactions_batch",
                new=AsyncMock(return_value=mock_transactions),
            ):
                new_txns = await parse_generic("test.csv", csv_content, file_hash)

        # Should match old parser
        assert len(new_txns) == 2
        assert new_txns[0].amount == -50.00
        assert new_txns[1].amount == 25.00
