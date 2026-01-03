"""Debug script to find the category filter issue."""

import asyncio

from backend.db.sqlite import db
from backend.models import TransactionCategory
from backend.services.query_engine import _analyze_query_intent


async def debug_category_filter():
    """Debug the category filter issue."""
    print("=" * 60)
    print("DEBUGGING CATEGORY FILTER")
    print("=" * 60)

    query = "how much did i spend on uber"

    # Step 1: Get intent
    print("\n1. Query intent:")
    intent = await _analyze_query_intent(query)
    print(f"   Intent category: {intent.get('category')}")

    # Step 2: Get all Uber transactions
    print("\n2. Uber transactions in DB:")
    uber_txns = db.search_transactions("uber", limit=1000)
    uber_in_desc = [t for t in uber_txns if "uber" in t.description.lower()]
    print(f"   Total: {len(uber_in_desc)}")

    # Step 3: Check categories of Uber transactions
    print("\n3. Categories of Uber transactions:")
    cat_counts = {}
    for txn in uber_in_desc:
        cat = txn.category.value if txn.category else "None"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for cat, count in sorted(cat_counts.items()):
        print(f"   {cat}: {count}")

    # Step 4: Try to parse the intent category
    print("\n4. Parsing intent category:")
    intent_cat_str = intent.get("category")
    print(f"   Intent category string: '{intent_cat_str}'")

    try:
        intent_cat = TransactionCategory(intent_cat_str)
        print(f"   Parsed as: {intent_cat}")
        print(f"   Enum value: {intent_cat.value}")
    except Exception as e:
        print(f"   Failed to parse: {e}")

    # Step 5: Filter by category
    print("\n5. Filtering by category:")
    if intent_cat_str:
        try:
            category = TransactionCategory(intent_cat_str)
            filtered = [t for t in uber_in_desc if t.category == category]
            print(f"   Transactions matching '{category.value}': {len(filtered)}")

            # Year breakdown
            year_counts = {}
            for txn in filtered:
                year = txn.date.year
                year_counts[year] = year_counts.get(year, 0) + 1
            print(f"   Year breakdown: {year_counts}")
        except Exception as e:
            print(f"   Error: {e}")

    # Step 6: Check what Travel category looks like
    print("\n6. Checking Travel vs Transportation:")
    print(f"   TransactionCategory.TRANSPORTATION.value = '{TransactionCategory.TRANSPORTATION.value}'")
    print(f"   TransactionCategory.TRAVEL.value = '{TransactionCategory.TRAVEL.value}'")

    # Check which Uber transactions are Travel vs Transportation
    travel_uber = [t for t in uber_in_desc if t.category == TransactionCategory.TRAVEL]
    transport_uber = [t for t in uber_in_desc if t.category == TransactionCategory.TRANSPORTATION]
    print(f"\n   Uber transactions with TRAVEL: {len(travel_uber)}")
    print(f"   Uber transactions with TRANSPORTATION: {len(transport_uber)}")


if __name__ == "__main__":
    asyncio.run(debug_category_filter())
