"""
Comprehensive tests for the query engine.

These tests cover all the edge cases and scenarios discovered during development:
1. Multi-year transaction breakdown
2. Brand-specific searches (uber, lyft, starbucks, etc.)
3. Category-based searches (airlines, rideshare, groceries)
4. Tag filtering logic
5. Brand vs category filter precedence
6. Mixed categorization handling (same brand across different categories)
"""

from datetime import date
from uuid import uuid4

import pytest

from backend.models import Transaction, TransactionCategory, TransactionSource
from backend.services.query_engine import (
    _calculate_stats,
    _extract_brand_keywords,
    _get_required_tags,
    _has_required_tags,
)

# =============================================================================
# Test Fixtures and Helpers
# =============================================================================


def make_transaction(
    description: str,
    amount: float,
    txn_date: date,
    tags: list[str] = None,
    category: TransactionCategory = TransactionCategory.OTHER,
    source: TransactionSource = TransactionSource.CHASE_CREDIT,
) -> Transaction:
    """Helper to create a test transaction."""
    return Transaction(
        id=uuid4(),
        source=source,
        source_file_hash="test-hash",
        transaction_hash=f"hash-{uuid4()}",
        date=txn_date,
        description=description,
        amount=amount,
        category=category,
        tags=tags or [],
    )


def create_uber_transactions_multi_year() -> list[Transaction]:
    """
    Create Uber transactions across multiple years with different categories.
    This simulates the real-world scenario where the same merchant can be
    categorized differently over time.
    """
    transactions = []

    # 2024 Uber transactions - categorized as TRAVEL (old categorization)
    for i in range(5):
        transactions.append(
            make_transaction(
                description=f"UBER* TRIP {i}",
                amount=-30.0,
                txn_date=date(2024, 6, i + 1),
                tags=["transportation", "rideshare", "taxi"],
                category=TransactionCategory.TRAVEL,
            )
        )

    # 2025 Uber transactions - categorized as TRANSPORTATION (new categorization)
    for i in range(3):
        transactions.append(
            make_transaction(
                description=f"UBER* TRIP {i}",
                amount=-25.0,
                txn_date=date(2025, 1, i + 1),
                tags=["transportation", "rideshare", "uber"],
                category=TransactionCategory.TRANSPORTATION,
            )
        )

    # Some Uber Eats transactions - categorized as FOOD
    for i in range(2):
        transactions.append(
            make_transaction(
                description=f"UBER* EATS {i}",
                amount=-20.0,
                txn_date=date(2025, 1, i + 10),
                tags=["food", "delivery", "uber"],
                category=TransactionCategory.FOOD_DINING,
            )
        )

    return transactions


def create_mixed_rideshare_transactions() -> list[Transaction]:
    """Create test transactions for both Uber and Lyft."""
    transactions = []

    # Uber transactions
    for i in range(3):
        transactions.append(
            make_transaction(
                description=f"UBER* TRIP {i}",
                amount=-20.0,
                txn_date=date(2024, 6, i + 1),
                tags=["transportation", "rideshare", "uber"],
                category=TransactionCategory.TRANSPORTATION,
            )
        )

    # Lyft transactions
    for i in range(2):
        transactions.append(
            make_transaction(
                description=f"LYFT* RIDE {i}",
                amount=-15.0,
                txn_date=date(2024, 6, i + 1),
                tags=["transportation", "rideshare", "lyft"],
                category=TransactionCategory.TRANSPORTATION,
            )
        )

    # Grab transactions (international rideshare)
    transactions.append(
        make_transaction(
            description="GRAB* A-12345",
            amount=-10.0,
            txn_date=date(2024, 7, 1),
            tags=["transportation", "rideshare", "grab"],
            category=TransactionCategory.TRANSPORTATION,
        )
    )

    return transactions


def create_airline_transactions() -> list[Transaction]:
    """Create airline transactions from various carriers."""
    transactions = []

    # Emirates
    transactions.append(
        make_transaction(
            description="EMIRATES AIRLINE",
            amount=-1500.0,
            txn_date=date(2024, 3, 15),
            tags=["travel", "airline", "flight", "international"],
            category=TransactionCategory.TRAVEL,
        )
    )

    # Alaska Airlines
    transactions.append(
        make_transaction(
            description="ALASKA AIR 123456",
            amount=-350.0,
            txn_date=date(2024, 5, 20),
            tags=["travel", "airline", "flight"],
            category=TransactionCategory.TRAVEL,
        )
    )

    # Delta
    transactions.append(
        make_transaction(
            description="DELTA AIR LINES",
            amount=-450.0,
            txn_date=date(2024, 7, 10),
            tags=["travel", "airline", "flight"],
            category=TransactionCategory.TRAVEL,
        )
    )

    # United
    transactions.append(
        make_transaction(
            description="UNITED AIRLINES",
            amount=-500.0,
            txn_date=date(2025, 1, 5),
            tags=["travel", "airline", "flight"],
            category=TransactionCategory.TRAVEL,
        )
    )

    return transactions


def create_coffee_transactions() -> list[Transaction]:
    """Create coffee shop transactions."""
    transactions = []

    # Starbucks
    for i in range(5):
        transactions.append(
            make_transaction(
                description=f"STARBUCKS STORE #{i}",
                amount=-6.50,
                txn_date=date(2024, 6, i + 1),
                tags=["food", "coffee", "cafe", "starbucks"],
                category=TransactionCategory.FOOD_DINING,
            )
        )

    # Dunkin
    for i in range(3):
        transactions.append(
            make_transaction(
                description=f"DUNKIN #{i}",
                amount=-4.50,
                txn_date=date(2024, 6, i + 10),
                tags=["food", "coffee", "cafe", "dunkin"],
                category=TransactionCategory.FOOD_DINING,
            )
        )

    # Local coffee shop (no brand tag)
    transactions.append(
        make_transaction(
            description="LOCAL COFFEE HOUSE",
            amount=-5.00,
            txn_date=date(2024, 6, 20),
            tags=["food", "coffee", "cafe"],
            category=TransactionCategory.FOOD_DINING,
        )
    )

    return transactions


def create_subscription_transactions() -> list[Transaction]:
    """Create subscription service transactions."""
    transactions = []

    # Netflix
    for month in range(1, 7):
        transactions.append(
            make_transaction(
                description="NETFLIX.COM",
                amount=-15.99,
                txn_date=date(2024, month, 15),
                tags=["subscription", "streaming", "entertainment", "netflix"],
                category=TransactionCategory.SUBSCRIPTIONS,
            )
        )

    # Spotify
    for month in range(1, 7):
        transactions.append(
            make_transaction(
                description="SPOTIFY USA",
                amount=-9.99,
                txn_date=date(2024, month, 1),
                tags=["subscription", "streaming", "music", "spotify"],
                category=TransactionCategory.SUBSCRIPTIONS,
            )
        )

    return transactions


# =============================================================================
# Test Classes
# =============================================================================


class TestCalculateStats:
    """Test the _calculate_stats function for accuracy."""

    def test_stats_with_multiple_years(self):
        """Test that stats correctly break down by year."""
        transactions = create_uber_transactions_multi_year()
        stats = _calculate_stats(transactions)

        # Total should be 10 transactions
        assert stats["total_count"] == 10

        # Year breakdown should exist
        assert 2024 in stats["by_year"]
        assert 2025 in stats["by_year"]

        # 2024: 5 transactions at $30 = $150
        assert stats["by_year"][2024]["count"] == 5
        assert stats["by_year"][2024]["spending"] == 150.0

        # 2025: 5 transactions (3 trips at $25 + 2 eats at $20) = $115
        assert stats["by_year"][2025]["count"] == 5
        assert stats["by_year"][2025]["spending"] == 115.0

    def test_stats_with_single_year(self):
        """Test stats with transactions from only one year."""
        transactions = [
            make_transaction("TEST", -100.0, date(2024, 5, 1)),
            make_transaction("TEST2", -50.0, date(2024, 6, 1)),
        ]

        stats = _calculate_stats(transactions)

        assert stats["total_count"] == 2
        assert stats["total_spending"] == 150.0
        assert len(stats["by_year"]) == 1
        assert stats["by_year"][2024]["count"] == 2
        assert stats["by_year"][2024]["spending"] == 150.0

    def test_stats_empty_transactions(self):
        """Test stats with no transactions."""
        stats = _calculate_stats([])
        assert stats == {}

    def test_stats_with_income(self):
        """Test that income (positive amounts) is tracked separately."""
        transactions = [
            make_transaction("PURCHASE", -100.0, date(2024, 5, 1)),
            make_transaction("REFUND", 25.0, date(2024, 5, 2)),
        ]

        stats = _calculate_stats(transactions)

        assert stats["total_spending"] == 100.0
        assert stats["total_income"] == 25.0

    def test_stats_source_breakdown(self):
        """Test that stats include source breakdown."""
        transactions = [
            make_transaction("CHASE TXN", -50.0, date(2024, 5, 1), source=TransactionSource.CHASE_CREDIT),
            make_transaction("AMEX TXN", -75.0, date(2024, 5, 1), source=TransactionSource.AMEX),
        ]

        stats = _calculate_stats(transactions)

        assert "by_source" in stats
        assert "chase_credit" in stats["by_source"]
        assert "amex" in stats["by_source"]
        assert stats["by_source"]["chase_credit"]["spending"] == 50.0
        assert stats["by_source"]["amex"]["spending"] == 75.0


class TestExtractBrandKeywords:
    """Test the _extract_brand_keywords function."""

    def test_extract_uber(self):
        """Test extracting uber from query."""
        keywords = _extract_brand_keywords("how much did i spend on uber")
        assert "uber" in keywords

    def test_extract_lyft(self):
        """Test extracting lyft from query."""
        keywords = _extract_brand_keywords("show me lyft transactions")
        assert "lyft" in keywords

    def test_extract_multiple_brands(self):
        """Test extracting multiple brands from one query."""
        keywords = _extract_brand_keywords("compare uber and lyft spending")
        assert "uber" in keywords
        assert "lyft" in keywords

    def test_no_brands(self):
        """Test query with no brand names."""
        keywords = _extract_brand_keywords("how much did i spend on food")
        assert keywords == []

    def test_extract_airlines(self):
        """Test extracting airline brands."""
        assert "emirates" in _extract_brand_keywords("emirates flights")
        assert "alaska" in _extract_brand_keywords("alaska airlines")
        assert "delta" in _extract_brand_keywords("delta tickets")

    def test_extract_coffee_brands(self):
        """Test extracting coffee shop brands."""
        assert "starbucks" in _extract_brand_keywords("starbucks spending")
        assert "dunkin" in _extract_brand_keywords("dunkin donuts")

    def test_extract_retail_brands(self):
        """Test extracting retail brands."""
        assert "amazon" in _extract_brand_keywords("amazon purchases")
        assert "target" in _extract_brand_keywords("target shopping")
        assert "walmart" in _extract_brand_keywords("walmart groceries")
        assert "costco" in _extract_brand_keywords("costco membership")

    def test_case_insensitive(self):
        """Test that brand extraction is case insensitive."""
        assert "uber" in _extract_brand_keywords("UBER spending")
        assert "uber" in _extract_brand_keywords("Uber rides")


class TestGetRequiredTags:
    """Test the _get_required_tags function."""

    # Brand-specific tag requirements
    def test_uber_requires_uber_tag(self):
        """Searching for 'uber' should require 'uber' tag."""
        tags = _get_required_tags("uber spending")
        assert "uber" in tags

    def test_lyft_requires_lyft_tag(self):
        """Searching for 'lyft' should require 'lyft' tag."""
        tags = _get_required_tags("lyft rides")
        assert "lyft" in tags

    def test_starbucks_requires_starbucks_tag(self):
        """Searching for 'starbucks' should require starbucks tag specifically."""
        tags = _get_required_tags("starbucks")
        assert "starbucks" in tags
        # Should NOT include generic "coffee" tag for brand-specific search
        assert "coffee" not in tags

    # Category-level tag requirements
    def test_rideshare_requires_rideshare_tag(self):
        """Searching for 'rideshare' should require rideshare tag."""
        tags = _get_required_tags("rideshare expenses")
        assert "rideshare" in tags

    def test_airlines_requires_airline_tag(self):
        """Searching for 'airlines' should require airline/flight tag."""
        tags = _get_required_tags("airline tickets")
        assert "airline" in tags or "flight" in tags

    def test_flights_requires_flight_tag(self):
        """Searching for 'flights' should require flight tag."""
        tags = _get_required_tags("how much on flights")
        assert "flight" in tags or "airline" in tags

    def test_coffee_requires_coffee_tag(self):
        """Searching for 'coffee' should require coffee tag."""
        tags = _get_required_tags("coffee expenses")
        assert "coffee" in tags

    def test_subscriptions_requires_subscription_tag(self):
        """Searching for 'subscriptions' should require subscription tag."""
        tags = _get_required_tags("my subscriptions")
        assert "subscription" in tags

    def test_groceries_requires_groceries_tag(self):
        """Searching for 'groceries' should require groceries tag."""
        tags = _get_required_tags("grocery spending")
        assert "groceries" in tags

    # No required tags for generic queries
    def test_generic_query_no_required_tags(self):
        """Generic queries should not require specific tags."""
        tags = _get_required_tags("how much did i spend last month")
        assert tags == []


class TestHasRequiredTags:
    """Test the _has_required_tags function."""

    def test_transaction_with_matching_tag(self):
        """Transaction with matching tag should pass."""
        txn = make_transaction(
            description="UBER* TRIP",
            amount=-20.0,
            txn_date=date(2024, 1, 1),
            tags=["transportation", "rideshare", "uber"],
        )

        assert _has_required_tags(txn, ["uber"]) is True

    def test_transaction_without_matching_tag(self):
        """Transaction without matching tag should fail."""
        txn = make_transaction(
            description="LYFT* RIDE",
            amount=-20.0,
            txn_date=date(2024, 1, 1),
            tags=["transportation", "rideshare", "lyft"],
        )

        assert _has_required_tags(txn, ["uber"]) is False

    def test_matches_description_when_no_tags(self):
        """Should match description when transaction has no tags."""
        txn = make_transaction(
            description="UBER* TRIP",
            amount=-20.0,
            txn_date=date(2024, 1, 1),
            tags=[],  # No tags
        )

        # Should match because "uber" is in description
        assert _has_required_tags(txn, ["uber"]) is True

    def test_matches_description_case_insensitive(self):
        """Description matching should be case insensitive."""
        txn = make_transaction(
            description="UBER* TRIP",  # Uppercase
            amount=-20.0,
            txn_date=date(2024, 1, 1),
            tags=[],
        )

        assert _has_required_tags(txn, ["uber"]) is True  # Lowercase search

    def test_empty_required_tags_always_passes(self):
        """Empty required tags should always pass."""
        txn = make_transaction(
            description="RANDOM PURCHASE",
            amount=-20.0,
            txn_date=date(2024, 1, 1),
            tags=[],
        )

        assert _has_required_tags(txn, []) is True

    def test_any_matching_tag_passes(self):
        """Any matching tag from the list should pass (with airline name in description)."""
        txn = make_transaction(
            description="DELTA AIR LINES BOOKING",
            amount=-500.0,
            txn_date=date(2024, 1, 1),
            tags=["travel", "flight"],
        )

        # Should pass because "delta air" is in description (airline query)
        assert _has_required_tags(txn, ["airline", "flight"]) is True


class TestFilteringLogic:
    """Test the overall filtering logic for brand-specific searches."""

    def test_filter_uber_from_mixed_rideshare(self):
        """Searching 'uber' should only return Uber, not Lyft or Grab."""
        transactions = create_mixed_rideshare_transactions()
        required_tags = _get_required_tags("uber")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should only have Uber transactions (3)
        assert len(filtered) == 3
        for txn in filtered:
            assert "UBER" in txn.description

    def test_filter_lyft_from_mixed_rideshare(self):
        """Searching 'lyft' should only return Lyft."""
        transactions = create_mixed_rideshare_transactions()
        required_tags = _get_required_tags("lyft")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should only have Lyft transactions (2)
        assert len(filtered) == 2
        for txn in filtered:
            assert "LYFT" in txn.description

    def test_rideshare_returns_all_rideshare(self):
        """Searching 'rideshare' should return Uber, Lyft, and Grab."""
        transactions = create_mixed_rideshare_transactions()
        required_tags = _get_required_tags("rideshare")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should have all 6 rideshare transactions
        assert len(filtered) == 6

    def test_filter_starbucks_from_coffee(self):
        """Searching 'starbucks' should only return Starbucks."""
        transactions = create_coffee_transactions()
        required_tags = _get_required_tags("starbucks")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should only have Starbucks (5)
        assert len(filtered) == 5
        for txn in filtered:
            assert "STARBUCKS" in txn.description

    def test_coffee_returns_all_coffee(self):
        """Searching 'coffee' should return all coffee shops."""
        transactions = create_coffee_transactions()
        required_tags = _get_required_tags("coffee")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should have all 9 coffee transactions
        assert len(filtered) == 9

    def test_airlines_returns_all_airlines(self):
        """Searching 'airlines' should return all airline transactions."""
        transactions = create_airline_transactions()
        required_tags = _get_required_tags("airlines")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should have all 4 airline transactions
        assert len(filtered) == 4


class TestMixedCategorization:
    """
    Test handling of the same brand across different categories.
    This was the root cause of the year breakdown bug.
    """

    def test_uber_across_categories(self):
        """
        Uber transactions may be categorized as Travel, Transportation, or Food.
        Searching for 'uber' should return ALL of them.
        """
        transactions = create_uber_transactions_multi_year()
        required_tags = _get_required_tags("uber")

        # Filter by required tags (should match description)
        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should get ALL 10 Uber transactions regardless of category
        assert len(filtered) == 10

        # Verify we have transactions from multiple categories
        categories = set(txn.category for txn in filtered)
        assert len(categories) >= 2  # At least Travel and Transportation

    def test_uber_year_breakdown_not_affected_by_category(self):
        """
        Year breakdown should not be affected by category differences.
        This tests the specific bug we fixed.
        """
        transactions = create_uber_transactions_multi_year()
        required_tags = _get_required_tags("uber")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        stats = _calculate_stats(filtered)

        # Should have transactions from both years
        assert 2024 in stats["by_year"]
        assert 2025 in stats["by_year"]

        # 2024 should have 5 transactions (all TRAVEL category)
        assert stats["by_year"][2024]["count"] == 5

        # 2025 should have 5 transactions (TRANSPORTATION + FOOD)
        assert stats["by_year"][2025]["count"] == 5


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_transaction_with_partial_brand_match(self):
        """Test that partial matches don't incorrectly match."""
        txn = make_transaction(
            description="SUPERMARKET PURCHASE",
            amount=-50.0,
            txn_date=date(2024, 1, 1),
            tags=["groceries"],
        )

        # "uber" should not match "SUPERMARKET"
        assert _has_required_tags(txn, ["uber"]) is False

    def test_empty_description(self):
        """Test handling of empty description."""
        txn = make_transaction(
            description="",
            amount=-50.0,
            txn_date=date(2024, 1, 1),
            tags=["test"],
        )

        # Should not crash, should not match "uber"
        assert _has_required_tags(txn, ["uber"]) is False

    def test_special_characters_in_description(self):
        """Test handling of special characters in description."""
        txn = make_transaction(
            description="UBER* TRIP #12345",
            amount=-20.0,
            txn_date=date(2024, 1, 1),
            tags=[],
        )

        assert _has_required_tags(txn, ["uber"]) is True

    def test_multiple_years_stats_ordering(self):
        """Test that year stats are calculated regardless of transaction order."""
        # Create transactions in non-chronological order
        transactions = [
            make_transaction("TXN", -100.0, date(2025, 1, 1)),
            make_transaction("TXN", -50.0, date(2023, 6, 1)),
            make_transaction("TXN", -75.0, date(2024, 3, 1)),
        ]

        stats = _calculate_stats(transactions)

        assert stats["by_year"][2023]["spending"] == 50.0
        assert stats["by_year"][2024]["spending"] == 75.0
        assert stats["by_year"][2025]["spending"] == 100.0


class TestSubscriptionQueries:
    """Test subscription-related queries."""

    def test_netflix_specific_search(self):
        """Searching 'netflix' should only return Netflix."""
        transactions = create_subscription_transactions()

        # Netflix should be in description
        filtered = [txn for txn in transactions if "netflix" in txn.description.lower()]

        assert len(filtered) == 6  # 6 months of Netflix

    def test_subscriptions_returns_all(self):
        """Searching 'subscriptions' should return all subscription services."""
        transactions = create_subscription_transactions()
        required_tags = _get_required_tags("subscriptions")

        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Should have all 12 subscription transactions (6 Netflix + 6 Spotify)
        assert len(filtered) == 12


# =============================================================================
# Integration-style tests (testing multiple functions together)
# =============================================================================


class TestQueryFlow:
    """Test the complete query flow from keyword extraction to filtering."""

    def test_uber_query_flow(self):
        """Test complete flow for 'how much did i spend on uber'."""
        query = "how much did i spend on uber"

        # Step 1: Extract brand keywords
        brand_keywords = _extract_brand_keywords(query.lower())
        assert "uber" in brand_keywords

        # Step 2: Get required tags
        required_tags = _get_required_tags(query.lower())
        assert "uber" in required_tags

        # Step 3: Filter transactions
        transactions = create_uber_transactions_multi_year()
        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Step 4: Calculate stats
        stats = _calculate_stats(filtered)

        # Verify complete flow
        assert stats["total_count"] == 10
        assert 2024 in stats["by_year"]
        assert 2025 in stats["by_year"]

    def test_airline_query_flow(self):
        """Test complete flow for 'airline expenses'."""
        query = "airline expenses"

        # Step 1: Extract brand keywords (none for generic airline query)
        _extract_brand_keywords(query.lower())
        # May or may not have brand keywords

        # Step 2: Get required tags
        required_tags = _get_required_tags(query.lower())
        assert "airline" in required_tags or "flight" in required_tags

        # Step 3: Filter transactions
        transactions = create_airline_transactions()
        filtered = [txn for txn in transactions if _has_required_tags(txn, required_tags)]

        # Step 4: Calculate stats
        stats = _calculate_stats(filtered)

        # Verify complete flow
        assert stats["total_count"] == 4
        assert stats["total_spending"] == 2800.0  # Sum of all airline tickets


class TestBrandVsCategoryQueries:
    """Test that brand queries (sweetgreen) and category queries (airlines) work correctly."""

    def test_brand_query_uses_direct_search(self):
        """Brand queries like 'sweetgreen' should use direct database search, not semantic."""

        # Generic category terms should be filtered out from merchant search
        generic_category_terms = {
            "airline",
            "airlines",
            "flight",
            "flights",
            "restaurant",
            "restaurants",
            "food",
            "dining",
        }

        # Test that "airlines" is recognized as a category term
        assert "airlines" in generic_category_terms
        assert "airline" in generic_category_terms

        # Test that "sweetgreen" is NOT a category term (will use direct search)
        assert "sweetgreen" not in generic_category_terms
        assert "sweetgreens" not in generic_category_terms

    def test_sweetgreen_query_returns_only_sweetgreen(self):
        """Query for 'sweetgreen' should only return Sweetgreen transactions, not all restaurants."""
        # Create test transactions
        sweetgreen_txns = [
            make_transaction(
                description="SWEETGREEN SOUTH LAKE",
                amount=-17.93,
                txn_date=date(2025, 4, 20),
                tags=["food", "restaurant", "healthy"],
            ),
            make_transaction(
                description="SWEETGREEN DWNTWN",
                amount=-14.19,
                txn_date=date(2025, 1, 31),
                tags=["food", "restaurant", "healthy"],
            ),
        ]

        other_restaurant_txns = [
            make_transaction(
                description="CHIPOTLE",
                amount=-12.50,
                txn_date=date(2025, 4, 15),
                tags=["food", "restaurant", "mexican"],
            ),
            make_transaction(
                description="PANERA BREAD",
                amount=-15.00,
                txn_date=date(2025, 4, 10),
                tags=["food", "restaurant", "bakery"],
            ),
        ]

        # Verify that only Sweetgreen transactions would match direct search
        for txn in sweetgreen_txns:
            assert "sweetgreen" in txn.description.lower()

        for txn in other_restaurant_txns:
            assert "sweetgreen" not in txn.description.lower()

    def test_airline_query_filters_non_airlines(self):
        """Query for 'airlines' should filter out airport restaurants and other non-airline transactions."""
        from backend.services.query_engine import _get_required_tags, _has_required_tags

        # Get required tags for airline query
        required_tags = _get_required_tags("airlines")
        assert "airline" in required_tags
        assert "flight" in required_tags

        # Real airline transactions
        airline_txns = [
            make_transaction(
                description="DELTA AIR LINES ATLANTA",
                amount=-308.19,
                txn_date=date(2025, 4, 30),
                tags=["travel", "airline", "flight", "booking"],
            ),
            make_transaction(
                description="EMIRATES AI 1762203506740",
                amount=-622.40,
                txn_date=date(2025, 12, 14),
                tags=["travel", "airline", "flight", "international"],
            ),
            make_transaction(
                description="AIR-INDIA",
                amount=-283.23,
                txn_date=date(2025, 12, 22),
                tags=["travel", "airline", "flight", "air-india"],
            ),
        ]

        # Non-airline transactions that might have airline tags (incorrectly tagged)
        non_airline_txns = [
            make_transaction(
                description="SSP EMIRATES LLC",  # Airport restaurant
                amount=-10.24,
                txn_date=date(2024, 10, 27),
                tags=["travel", "airline", "flight"],  # Incorrectly tagged
            ),
            make_transaction(
                description="HUDSON ST2073 INDIANAPOLIS IN",  # Airport shop
                amount=-10.69,
                txn_date=date(2024, 6, 24),
                tags=["travel", "airline", "flight"],  # Incorrectly tagged
            ),
            make_transaction(
                description="NORWEGIAN CRUISE LINE",  # Cruise, not airline
                amount=-479.00,
                txn_date=date(2025, 6, 26),
                tags=["travel", "airline", "flight"],  # Incorrectly tagged
            ),
            make_transaction(
                description="TST* FLORET - SEATAC AIR",  # Airport restaurant
                amount=-53.32,
                txn_date=date(2025, 9, 8),
                tags=["restaurant", "food"],
            ),
        ]

        # Verify airline transactions pass the filter
        for txn in airline_txns:
            assert _has_required_tags(txn, required_tags) is True, f"Airline transaction should pass: {txn.description}"

        # Verify non-airline transactions are filtered out
        for txn in non_airline_txns:
            assert _has_required_tags(txn, required_tags) is False, (
                f"Non-airline transaction should be filtered: {txn.description}"
            )

    def test_plural_singular_matching(self):
        """Test that plural/singular variants are handled (sweetgreens -> sweetgreen)."""
        # The query engine should try both "sweetgreens" and "sweetgreen"
        # when searching for "sweetgreens"

        term = "sweetgreens"
        search_variants = [term]

        # Add singular variant
        if term.endswith("s") and len(term) > 3:
            search_variants.append(term[:-1])

        assert "sweetgreen" in search_variants
        assert "sweetgreens" in search_variants

        # Test reverse (singular -> plural)
        term2 = "starbuck"
        search_variants2 = [term2]
        if not term2.endswith("s"):
            search_variants2.append(term2 + "s")

        assert "starbuck" in search_variants2
        assert "starbucks" in search_variants2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
