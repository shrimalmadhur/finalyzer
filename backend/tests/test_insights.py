"""Tests for the spending insights service."""

import uuid
from datetime import date
from unittest.mock import patch

import pytest

from backend.models import Transaction, TransactionCategory, TransactionSource
from backend.services.insights import (
    InsightsReport,
    SpendingInsight,
    generate_insights,
    generate_monthly_insights,
    get_quick_stats,
)


def create_mock_transaction(
    amount: float,
    txn_date: date,
    description: str = "TEST MERCHANT",
    category: TransactionCategory = TransactionCategory.SHOPPING,
    txn_id: int = 1,
) -> Transaction:
    """Create a mock transaction for testing."""
    # Generate a deterministic UUID based on txn_id
    txn_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"test-txn-{txn_id}")
    return Transaction(
        id=txn_uuid,
        source=TransactionSource.CHASE_CREDIT,
        source_file_hash="test-hash",
        transaction_hash=f"txn-{txn_id}-{amount}-{txn_date}",
        date=txn_date,
        description=description,
        amount=amount,
        category=category,
    )


class TestSpendingInsight:
    """Test SpendingInsight dataclass."""

    def test_creates_insight_with_required_fields(self):
        """Should create insight with required fields."""
        insight = SpendingInsight(
            type="increase",
            title="Spending Up",
            description="Your spending increased",
        )
        assert insight.type == "increase"
        assert insight.title == "Spending Up"
        assert insight.description == "Your spending increased"

    def test_creates_insight_with_optional_fields(self):
        """Should create insight with optional fields."""
        insight = SpendingInsight(
            type="anomaly",
            title="Large Purchase",
            description="Unusually large purchase detected",
            amount=500.0,
            percent_change=150.0,
            category="Shopping",
            merchant="AMAZON",
            severity="warning",
        )
        assert insight.amount == 500.0
        assert insight.percent_change == 150.0
        assert insight.category == "Shopping"
        assert insight.merchant == "AMAZON"
        assert insight.severity == "warning"

    def test_default_severity(self):
        """Should default to 'info' severity."""
        insight = SpendingInsight(
            type="tip",
            title="Spending Tip",
            description="A helpful tip",
        )
        assert insight.severity == "info"


class TestInsightsReport:
    """Test InsightsReport dataclass."""

    def test_creates_report_with_all_fields(self):
        """Should create report with all fields."""
        insights = [
            SpendingInsight(
                type="tip",
                title="Test",
                description="Test description",
            )
        ]
        report = InsightsReport(
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
            total_spending=5000.0,
            total_transactions=100,
            insights=insights,
        )
        assert report.total_spending == 5000.0
        assert report.total_transactions == 100
        assert report.period_start == date(2024, 1, 1)
        assert report.period_end == date(2024, 12, 31)
        assert len(report.insights) == 1


class TestGenerateInsights:
    """Test main insights generation function."""

    @patch("backend.services.insights.db")
    def test_generates_insights_for_year(self, mock_db):
        """Should generate insights for a specific year."""
        mock_db.get_all_transactions.return_value = [
            create_mock_transaction(-100.0, date(2024, 1, 15), txn_id=1),
            create_mock_transaction(-200.0, date(2024, 2, 15), txn_id=2),
            create_mock_transaction(-150.0, date(2024, 3, 15), txn_id=3),
        ]

        report = generate_insights(year=2024)

        assert isinstance(report, InsightsReport)
        assert report.period_start == date(2024, 1, 1)
        assert report.period_end == date(2024, 12, 31)
        assert report.total_spending > 0
        assert report.total_transactions == 3

    @patch("backend.services.insights.db")
    def test_handles_no_transactions(self, mock_db):
        """Should handle case with no transactions."""
        mock_db.get_all_transactions.return_value = []

        report = generate_insights()

        assert isinstance(report, InsightsReport)
        assert report.total_spending == 0
        assert report.total_transactions == 0

    @patch("backend.services.insights.db")
    def test_generates_insights_list(self, mock_db):
        """Should generate a list of insights."""
        mock_db.get_all_transactions.return_value = [
            create_mock_transaction(-500.0, date(2024, 1, 15), category=TransactionCategory.SHOPPING, txn_id=1),
            create_mock_transaction(-300.0, date(2024, 2, 15), category=TransactionCategory.FOOD_DINING, txn_id=2),
            create_mock_transaction(-200.0, date(2024, 3, 15), category=TransactionCategory.TRAVEL, txn_id=3),
        ]

        report = generate_insights(year=2024)

        assert isinstance(report.insights, list)
        # All insights should be SpendingInsight objects
        for insight in report.insights:
            assert isinstance(insight, SpendingInsight)


class TestGenerateMonthlyInsights:
    """Test monthly insights generation."""

    @patch("backend.services.insights.db")
    def test_generates_monthly_insights(self, mock_db):
        """Should generate insights for a specific month."""
        mock_db.get_all_transactions.return_value = [
            create_mock_transaction(-100.0, date(2024, 2, 5), txn_id=1),
            create_mock_transaction(-200.0, date(2024, 2, 15), txn_id=2),
            create_mock_transaction(-150.0, date(2024, 2, 25), txn_id=3),
            # Previous month for comparison
            create_mock_transaction(-50.0, date(2024, 1, 10), txn_id=4),
        ]

        report = generate_monthly_insights(2024, 2)

        assert isinstance(report, InsightsReport)
        assert report.period_start.month == 2
        assert report.period_start.year == 2024

    @patch("backend.services.insights.db")
    def test_handles_first_month_of_year(self, mock_db):
        """Should handle January which compares to December of previous year."""
        mock_db.get_all_transactions.return_value = [
            create_mock_transaction(-100.0, date(2024, 1, 15), txn_id=1),
        ]

        report = generate_monthly_insights(2024, 1)

        assert isinstance(report, InsightsReport)
        assert report.period_start.month == 1


class TestGetQuickStats:
    """Test quick stats function."""

    @patch("backend.services.insights.db")
    def test_returns_quick_stats_keys(self, mock_db):
        """Should return quick stats with expected keys."""
        today = date.today()
        mock_db.get_all_transactions.return_value = [
            create_mock_transaction(-100.0, today, txn_id=1),
            create_mock_transaction(-50.0, today, category=TransactionCategory.SUBSCRIPTIONS, txn_id=2),
        ]

        stats = get_quick_stats()

        # Verify the function returns a dict with expected structure
        assert isinstance(stats, dict)
        assert "total_spending" in stats
        assert "total_income" in stats
        assert "transaction_count" in stats
        assert "avg_transaction" in stats
        assert "top_category" in stats
        assert "top_merchant" in stats

    @patch("backend.services.insights.db")
    def test_handles_empty_data(self, mock_db):
        """Should handle case with no transactions."""
        mock_db.get_all_transactions.return_value = []

        stats = get_quick_stats()

        assert stats["total_spending"] == 0
        assert stats["total_income"] == 0
        assert stats["transaction_count"] == 0


class TestInsightsIntegration:
    """Integration tests for insights generation."""

    @patch("backend.services.insights.db")
    def test_insights_include_category_analysis(self, mock_db):
        """Should include category-based insights."""
        mock_db.get_all_transactions.return_value = [
            create_mock_transaction(-100.0, date(2024, 2, 1), category=TransactionCategory.SHOPPING, txn_id=1),
            create_mock_transaction(-100.0, date(2024, 2, 15), category=TransactionCategory.SHOPPING, txn_id=2),
            create_mock_transaction(-50.0, date(2024, 1, 15), category=TransactionCategory.SHOPPING, txn_id=3),
        ]

        report = generate_insights(year=2024)

        # Should include insights about category trends
        assert isinstance(report.insights, list)

    @patch("backend.services.insights.db")
    def test_calculates_total_spending_correctly(self, mock_db):
        """Should calculate total spending correctly."""
        mock_db.get_all_transactions.return_value = [
            create_mock_transaction(-100.0, date(2024, 1, 15), txn_id=1),
            create_mock_transaction(-200.0, date(2024, 2, 15), txn_id=2),
            create_mock_transaction(-150.0, date(2024, 3, 15), txn_id=3),
        ]

        report = generate_insights(year=2024)

        # Total spending should be sum of absolute values of negative amounts
        assert report.total_spending == 450.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
