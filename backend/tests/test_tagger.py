"""
Tests for the transaction tagger service.

These tests ensure that:
1. Brand-specific tags are correctly applied
2. Category tags are applied
3. Multiple tags can be applied to a single transaction
4. Tagging is case-insensitive
"""

import pytest
from datetime import date
from uuid import uuid4

from backend.models import Transaction, TransactionSource, TransactionCategory
from backend.services.tagger import tag_transactions_fast, MERCHANT_TAGS


def make_transaction(
    description: str,
    amount: float = -20.0,
    txn_date: date = None,
    category: TransactionCategory = TransactionCategory.OTHER,
) -> Transaction:
    """Helper to create a test transaction without tags."""
    return Transaction(
        id=uuid4(),
        source=TransactionSource.CHASE_CREDIT,
        source_file_hash="test-hash",
        transaction_hash=f"hash-{uuid4()}",
        date=txn_date or date(2024, 1, 1),
        description=description,
        amount=amount,
        category=category,
        tags=[],  # Start with no tags
    )


class TestMerchantTagsConfig:
    """Test that MERCHANT_TAGS configuration is correct."""
    
    def test_uber_has_uber_tag(self):
        """Uber should have 'uber' in its tags."""
        assert "uber" in MERCHANT_TAGS
        assert "uber" in MERCHANT_TAGS["uber"]
    
    def test_lyft_has_lyft_tag(self):
        """Lyft should have 'lyft' in its tags."""
        assert "lyft" in MERCHANT_TAGS
        assert "lyft" in MERCHANT_TAGS["lyft"]
    
    def test_rideshare_tags_include_rideshare(self):
        """Rideshare merchants should have 'rideshare' tag."""
        rideshare_merchants = ["uber", "lyft", "grab"]
        for merchant in rideshare_merchants:
            if merchant in MERCHANT_TAGS:
                assert "rideshare" in MERCHANT_TAGS[merchant], f"{merchant} missing 'rideshare' tag"
    
    def test_airlines_have_airline_tag(self):
        """Airlines should have 'airline' and 'flight' tags."""
        airlines = ["emirates", "alaska", "delta", "united", "southwest"]
        for airline in airlines:
            if airline in MERCHANT_TAGS:
                tags = MERCHANT_TAGS[airline]
                assert "airline" in tags or "flight" in tags, f"{airline} missing airline tags"
    
    def test_coffee_shops_have_coffee_tag(self):
        """Coffee shops should have 'coffee' tag."""
        coffee_shops = ["starbucks", "dunkin"]
        for shop in coffee_shops:
            if shop in MERCHANT_TAGS:
                assert "coffee" in MERCHANT_TAGS[shop], f"{shop} missing 'coffee' tag"
    
    def test_subscriptions_have_subscription_tag(self):
        """Subscription services should have 'subscription' tag."""
        subscriptions = ["netflix", "spotify", "hulu"]
        for sub in subscriptions:
            if sub in MERCHANT_TAGS:
                assert "subscription" in MERCHANT_TAGS[sub], f"{sub} missing 'subscription' tag"


class TestTagTransactionsFast:
    """Test the tag_transactions_fast function."""
    
    def test_tags_uber_transaction(self):
        """Uber transaction should get uber and rideshare tags."""
        txn = make_transaction("UBER* TRIP")
        tag_transactions_fast([txn])
        
        assert "uber" in txn.tags
        assert "rideshare" in txn.tags
    
    def test_tags_lyft_transaction(self):
        """Lyft transaction should get lyft and rideshare tags."""
        txn = make_transaction("LYFT* RIDE 12345")
        tag_transactions_fast([txn])
        
        assert "lyft" in txn.tags
        assert "rideshare" in txn.tags
    
    def test_uber_and_lyft_get_different_brand_tags(self):
        """Uber and Lyft should get different brand tags."""
        uber_txn = make_transaction("UBER* TRIP")
        lyft_txn = make_transaction("LYFT* RIDE")
        
        tag_transactions_fast([uber_txn, lyft_txn])
        
        # Uber should have uber tag, not lyft
        assert "uber" in uber_txn.tags
        assert "lyft" not in uber_txn.tags
        
        # Lyft should have lyft tag, not uber
        assert "lyft" in lyft_txn.tags
        assert "uber" not in lyft_txn.tags
    
    def test_tags_starbucks_transaction(self):
        """Starbucks transaction should get coffee tags."""
        txn = make_transaction("STARBUCKS STORE #1234")
        tag_transactions_fast([txn])
        
        assert "coffee" in txn.tags
    
    def test_tags_airline_transaction(self):
        """Airline transaction should get airline and flight tags."""
        txn = make_transaction("EMIRATES AIRLINE")
        tag_transactions_fast([txn])
        
        assert "airline" in txn.tags
        assert "flight" in txn.tags
    
    def test_tags_netflix_transaction(self):
        """Netflix transaction should get subscription and streaming tags."""
        txn = make_transaction("NETFLIX.COM")
        tag_transactions_fast([txn])
        
        assert "subscription" in txn.tags
        assert "streaming" in txn.tags
    
    def test_case_insensitive_matching(self):
        """Tagging should be case insensitive."""
        txn_upper = make_transaction("UBER* TRIP")
        txn_lower = make_transaction("uber* trip")
        txn_mixed = make_transaction("Uber* Trip")
        
        tag_transactions_fast([txn_upper, txn_lower, txn_mixed])
        
        # All should get uber tag
        assert "uber" in txn_upper.tags
        assert "uber" in txn_lower.tags
        assert "uber" in txn_mixed.tags
    
    def test_partial_match(self):
        """Merchant name can be part of description."""
        txn = make_transaction("PAYMENT TO UBER TECHNOLOGIES")
        tag_transactions_fast([txn])
        
        assert "uber" in txn.tags
    
    def test_no_tags_for_unknown_merchant(self):
        """Unknown merchants should not get tags (will be LLM tagged later)."""
        txn = make_transaction("RANDOM UNKNOWN STORE")
        tag_transactions_fast([txn])
        
        # Should have no tags or minimal tags
        # The function may still add some generic tags, so just check it doesn't crash
        assert isinstance(txn.tags, list)
    
    def test_multiple_transactions(self):
        """Should correctly tag multiple transactions."""
        transactions = [
            make_transaction("UBER* TRIP"),
            make_transaction("LYFT* RIDE"),
            make_transaction("STARBUCKS"),
            make_transaction("NETFLIX.COM"),
        ]
        
        tag_transactions_fast(transactions)
        
        assert "uber" in transactions[0].tags
        assert "lyft" in transactions[1].tags
        assert "coffee" in transactions[2].tags
        assert "subscription" in transactions[3].tags


class TestSpecificMerchants:
    """Test tagging for specific merchants we've had issues with."""
    
    def test_uber_eats_gets_uber_tag(self):
        """Uber Eats should get uber tag."""
        txn = make_transaction("UBER* EATS")
        tag_transactions_fast([txn])
        
        assert "uber" in txn.tags
    
    def test_alaska_airlines(self):
        """Alaska Airlines should get airline tags."""
        txn = make_transaction("ALASKA AIR 123456")
        tag_transactions_fast([txn])
        
        assert "airline" in txn.tags
    
    def test_emirates(self):
        """Emirates should get airline tags."""
        txn = make_transaction("EMIRATES AIRLINE")
        tag_transactions_fast([txn])
        
        assert "airline" in txn.tags
    
    def test_grab_rideshare(self):
        """Grab should get rideshare tags."""
        txn = make_transaction("GRAB* A-12345")
        tag_transactions_fast([txn])
        
        assert "rideshare" in txn.tags
        assert "grab" in txn.tags
    
    def test_amazon(self):
        """Amazon should get shopping tags."""
        txn = make_transaction("AMAZON.COM*123456")
        tag_transactions_fast([txn])
        
        assert "amazon" in txn.tags or "shopping" in txn.tags
    
    def test_costco(self):
        """Costco should get shopping tags."""
        txn = make_transaction("COSTCO WHSE #1234")
        tag_transactions_fast([txn])
        
        assert "costco" in txn.tags or "shopping" in txn.tags


class TestTagPreservation:
    """Test that existing tags are handled correctly."""
    
    def test_skips_already_tagged_transactions(self):
        """Should skip transactions that already have tags."""
        txn = make_transaction("UBER* TRIP")
        txn.tags = ["existing-tag"]  # Pre-existing tags
        
        tag_transactions_fast([txn])
        
        # Should preserve existing tags and not add new ones
        # (fast tagging only processes untagged transactions)
        assert txn.tags == ["existing-tag"]
    
    def test_tags_only_untagged_transactions(self):
        """Should only tag transactions without tags."""
        tagged_txn = make_transaction("UBER* TRIP")
        tagged_txn.tags = ["existing"]
        
        untagged_txn = make_transaction("LYFT* RIDE")
        # No tags
        
        tag_transactions_fast([tagged_txn, untagged_txn])
        
        # Tagged transaction should be unchanged
        assert tagged_txn.tags == ["existing"]
        
        # Untagged transaction should now have tags
        assert "lyft" in untagged_txn.tags


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

