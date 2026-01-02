"""Debug script to trace _get_relevant_transactions."""

import asyncio
from backend.db.sqlite import db
from backend.db.vector import vector_store
from backend.services.query_engine import (
    _analyze_query_intent,
    _extract_brand_keywords,
    _get_required_tags,
    _has_required_tags,
)


async def debug_get_relevant():
    """Debug the _get_relevant_transactions flow."""
    print("=" * 60)
    print("DEBUGGING _get_relevant_transactions FLOW")
    print("=" * 60)
    
    query = "how much did i spend on uber"
    query_lower = query.lower()
    
    # Step 1: Analyze intent
    print("\n1. Analyzing query intent:")
    intent = await _analyze_query_intent(query)
    print(f"   Intent: {intent}")
    
    # Step 2: Extract brand keywords
    print("\n2. Extracting brand keywords:")
    brand_keywords = _extract_brand_keywords(query_lower)
    print(f"   Brand keywords: {brand_keywords}")
    
    # Step 3: Get required tags
    print("\n3. Getting required tags:")
    required_tags = _get_required_tags(query_lower)
    print(f"   Required tags: {required_tags}")
    
    # Step 4: Direct database search for brand keywords
    print("\n4. Direct database search for brand keywords:")
    transactions = []
    seen_ids = set()
    
    if brand_keywords:
        for keyword in brand_keywords:
            matches = db.search_transactions(keyword, limit=1000)
            print(f"   db.search_transactions('{keyword}'): {len(matches)} results")
            
            for txn in matches:
                if str(txn.id) not in seen_ids:
                    # Check if keyword is in description
                    if keyword.lower() in txn.description.lower():
                        seen_ids.add(str(txn.id))
                        transactions.append(txn)
            
            print(f"   After filtering by description: {len(transactions)} transactions")
    
    print(f"\n   Total after brand search: {len(transactions)}")
    
    # Step 5: Check year breakdown
    print("\n5. Year breakdown of found transactions:")
    year_counts = {}
    for txn in transactions:
        year = txn.date.year
        year_counts[year] = year_counts.get(year, 0) + 1
    for year in sorted(year_counts.keys()):
        print(f"   {year}: {year_counts[year]} transactions")
    
    # Step 6: Check semantic search
    print("\n6. Checking semantic search:")
    search_results = await vector_store.search(
        query=query,
        n_results=200,
    )
    print(f"   Semantic search returned: {len(search_results)} results")
    
    if search_results:
        txn_ids = [result["id"] for result in search_results]
        semantic_matches = db.get_transactions_by_ids(txn_ids)
        print(f"   After fetching from DB: {len(semantic_matches)} transactions")
        
        # Check how many have uber in description
        uber_semantic = [t for t in semantic_matches if "uber" in t.description.lower()]
        print(f"   Of those, {len(uber_semantic)} have 'uber' in description")
        
        # Year breakdown
        year_counts_semantic = {}
        for txn in uber_semantic:
            year = txn.date.year
            year_counts_semantic[year] = year_counts_semantic.get(year, 0) + 1
        print(f"   Semantic search year breakdown: {year_counts_semantic}")


if __name__ == "__main__":
    asyncio.run(debug_get_relevant())

