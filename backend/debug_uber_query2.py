"""Debug script to find why filtering is failing."""

from backend.db.sqlite import db
from backend.services.query_engine import (
    _has_required_tags,
    _get_required_tags,
    _extract_brand_keywords,
)


def debug_filtering():
    """Debug the filtering issue."""
    print("=" * 60)
    print("DEBUGGING FILTERING")
    print("=" * 60)
    
    # Get all Uber transactions
    uber_txns = db.search_transactions("uber", limit=1000)
    uber_in_desc = [t for t in uber_txns if "uber" in t.description.lower()]
    
    print(f"\nTotal Uber transactions in DB: {len(uber_in_desc)}")
    
    # Test _has_required_tags on each
    required_tags = _get_required_tags("uber")
    print(f"Required tags for 'uber' query: {required_tags}")
    
    # Count how many pass the filter
    passing = []
    failing = []
    for txn in uber_in_desc:
        if _has_required_tags(txn, required_tags):
            passing.append(txn)
        else:
            failing.append(txn)
    
    print(f"\nPassing filter: {len(passing)}")
    print(f"Failing filter: {len(failing)}")
    
    # Show some failing ones
    if failing:
        print("\nSample FAILING transactions:")
        for txn in failing[:5]:
            print(f"  Description: {txn.description}")
            print(f"  Tags: {txn.tags}")
            print(f"  'uber' in description.lower(): {'uber' in txn.description.lower()}")
            print()
    
    # Test the _has_required_tags function directly
    print("\nDirect test of _has_required_tags:")
    if failing:
        txn = failing[0]
        print(f"Transaction: {txn.description}")
        print(f"Tags: {txn.tags}")
        print(f"Required tags: {required_tags}")
        
        # Manual check
        desc_lower = txn.description.lower()
        print(f"Description lower: {desc_lower}")
        for tag in required_tags:
            tag_lower = tag.lower()
            print(f"  Checking if '{tag_lower}' in '{desc_lower}': {tag_lower in desc_lower}")


if __name__ == "__main__":
    debug_filtering()

