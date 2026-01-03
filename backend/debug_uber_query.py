"""Debug script to test Uber query and find the issue."""

import asyncio

from backend.db.sqlite import db
from backend.services.query_engine import (
    _calculate_stats,
    _extract_brand_keywords,
    _get_required_tags,
    query_transactions,
)


def debug_uber_transactions():
    """Debug Uber transactions in the database."""
    print("=" * 60)
    print("DEBUGGING UBER TRANSACTIONS")
    print("=" * 60)

    # Step 1: Search for all Uber transactions in the database
    print("\n1. Direct database search for 'uber':")
    uber_txns = db.search_transactions("uber", limit=1000)
    print(f"   Found {len(uber_txns)} transactions with 'uber' in description/tags")

    # Step 2: Filter to only those with UBER in description
    uber_in_desc = [t for t in uber_txns if "uber" in t.description.lower()]
    print(f"   Of those, {len(uber_in_desc)} have 'uber' in description")

    # Step 3: Show year breakdown
    print("\n2. Year breakdown of Uber transactions:")
    year_counts = {}
    year_amounts = {}
    for txn in uber_in_desc:
        year = txn.date.year
        if year not in year_counts:
            year_counts[year] = 0
            year_amounts[year] = 0.0
        year_counts[year] += 1
        if txn.amount < 0:
            year_amounts[year] += abs(txn.amount)

    for year in sorted(year_counts.keys()):
        print(f"   {year}: {year_counts[year]} transactions, ${year_amounts[year]:.2f}")

    # Step 4: Test _calculate_stats
    print("\n3. Testing _calculate_stats on these transactions:")
    stats = _calculate_stats(uber_in_desc)
    print(f"   Total count: {stats.get('total_count', 0)}")
    print(f"   Total spending: ${stats.get('total_spending', 0):.2f}")
    print(f"   By year: {stats.get('by_year', {})}")

    # Step 5: Check what brand keywords are extracted
    print("\n4. Testing _extract_brand_keywords:")
    test_queries = [
        "uber",
        "how much did i spend on uber",
        "compare my uber transactions",
        "uber spending in 2024",
    ]
    for q in test_queries:
        keywords = _extract_brand_keywords(q)
        print(f"   '{q}' -> {keywords}")

    # Step 6: Check required tags
    print("\n5. Testing _get_required_tags:")
    for q in test_queries:
        tags = _get_required_tags(q)
        print(f"   '{q}' -> {tags}")

    # Step 7: Sample some transactions
    print("\n6. Sample Uber transactions (first 5):")
    for txn in uber_in_desc[:5]:
        print(f"   {txn.date} | {txn.description[:40]} | ${abs(txn.amount):.2f} | tags: {txn.tags}")

    print("\n7. Sample Uber transactions (last 5):")
    for txn in uber_in_desc[-5:]:
        print(f"   {txn.date} | {txn.description[:40]} | ${abs(txn.amount):.2f} | tags: {txn.tags}")

    return uber_in_desc


async def debug_full_query():
    """Debug the full query flow."""
    print("\n" + "=" * 60)
    print("DEBUGGING FULL QUERY FLOW")
    print("=" * 60)

    # Run the actual query
    print("\n8. Running actual query 'how much did i spend on uber':")
    result = await query_transactions("how much did i spend on uber")

    print(f"   Summary: {result.summary}")
    print(f"   Total amount: {result.total_amount}")
    print(f"   Transaction count: {len(result.transactions)}")

    if result.transactions:
        # Check year breakdown of returned transactions
        year_counts = {}
        year_amounts = {}
        for txn in result.transactions:
            year = txn.date.year
            if year not in year_counts:
                year_counts[year] = 0
                year_amounts[year] = 0.0
            year_counts[year] += 1
            if txn.amount < 0:
                year_amounts[year] += abs(txn.amount)

        print("\n   Year breakdown of returned transactions:")
        for year in sorted(year_counts.keys()):
            print(f"      {year}: {year_counts[year]} transactions, ${year_amounts[year]:.2f}")


if __name__ == "__main__":
    # Run sync debug first
    uber_txns = debug_uber_transactions()

    # Run async debug
    asyncio.run(debug_full_query())
