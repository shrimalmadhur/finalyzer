"""Natural language query engine for transactions."""

import json
import re
from datetime import date, timedelta
from typing import Optional
import hashlib

from litellm import acompletion

from backend.config import settings
from backend.db.sqlite import db
from backend.db.vector import vector_store
from backend.models import QueryResponse, Transaction, TransactionCategory


def _get_model_name() -> str:
    """Get the appropriate model name based on provider."""
    if settings.llm_provider == "openai":
        return settings.openai_model
    else:
        return f"ollama/{settings.ollama_model}"


def _get_api_base() -> Optional[str]:
    """Get the API base URL for Ollama."""
    if settings.llm_provider == "ollama":
        return settings.ollama_host
    return None


# Simple in-memory cache for LLM intent analysis
_intent_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 3600  # 1 hour


def _get_cached_intent(query: str) -> Optional[dict]:
    """Get cached intent analysis if available and not expired."""
    import time
    cache_key = hashlib.md5(query.lower().strip().encode()).hexdigest()
    if cache_key in _intent_cache:
        intent, timestamp = _intent_cache[cache_key]
        if time.time() - timestamp < _CACHE_TTL:
            return intent
        else:
            del _intent_cache[cache_key]
    return None


def _cache_intent(query: str, intent: dict) -> None:
    """Cache intent analysis result."""
    import time
    cache_key = hashlib.md5(query.lower().strip().encode()).hexdigest()
    _intent_cache[cache_key] = (intent, time.time())
    # Limit cache size
    if len(_intent_cache) > 1000:
        # Remove oldest entries
        sorted_keys = sorted(_intent_cache.keys(), key=lambda k: _intent_cache[k][1])
        for k in sorted_keys[:100]:
            del _intent_cache[k]


def parse_relative_date(query: str) -> tuple[Optional[date], Optional[date]]:
    """
    Parse relative date expressions from the query.

    Supports:
    - "last month", "this month", "last year", "this year"
    - "last N days/weeks/months"
    - "past N days/weeks/months"
    - "yesterday", "today"
    - "last week", "this week"
    - Month names: "in January", "in December 2024"

    Returns (start_date, end_date) tuple, or (None, None) if no relative date found.
    """
    today = date.today()
    query_lower = query.lower()

    # Yesterday/today
    if "yesterday" in query_lower:
        yesterday = today - timedelta(days=1)
        return (yesterday, yesterday)
    if "today" in query_lower and "to date" not in query_lower:
        return (today, today)

    # This week / last week
    if "this week" in query_lower:
        start = today - timedelta(days=today.weekday())  # Monday
        return (start, today)
    if "last week" in query_lower:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return (start, end)

    # This month / last month
    if "this month" in query_lower:
        start = today.replace(day=1)
        return (start, today)
    if "last month" in query_lower:
        first_of_this_month = today.replace(day=1)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        start = last_of_prev_month.replace(day=1)
        return (start, last_of_prev_month)

    # This year / last year
    if "this year" in query_lower:
        start = today.replace(month=1, day=1)
        return (start, today)
    if "last year" in query_lower:
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(year=today.year - 1, month=12, day=31)
        return (start, end)

    # Year to date
    if "year to date" in query_lower or "ytd" in query_lower:
        start = today.replace(month=1, day=1)
        return (start, today)

    # Last N days/weeks/months pattern
    patterns = [
        (r"(?:last|past)\s+(\d+)\s+days?", "days"),
        (r"(?:last|past)\s+(\d+)\s+weeks?", "weeks"),
        (r"(?:last|past)\s+(\d+)\s+months?", "months"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, query_lower)
        if match:
            n = int(match.group(1))
            if unit == "days":
                start = today - timedelta(days=n)
            elif unit == "weeks":
                start = today - timedelta(weeks=n)
            elif unit == "months":
                # Approximate months as 30 days
                start = today - timedelta(days=n * 30)
            return (start, today)

    # Month names with optional year: "in January", "in December 2024"
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12
    }

    for month_name, month_num in month_names.items():
        # Pattern: "in January 2024" or "in January"
        pattern = rf"(?:in|during|for)\s+{month_name}(?:\s+(\d{{4}}))?"
        match = re.search(pattern, query_lower)
        if match:
            year = int(match.group(1)) if match.group(1) else today.year
            # If the month is in the future this year, assume last year
            if not match.group(1) and month_num > today.month:
                year = today.year - 1

            start = date(year, month_num, 1)
            # Get last day of month
            if month_num == 12:
                end = date(year, 12, 31)
            else:
                end = date(year, month_num + 1, 1) - timedelta(days=1)
            return (start, end)

    return (None, None)


async def query_transactions(query: str) -> QueryResponse:
    """
    Process a natural language query about transactions.

    Uses a combination of:
    1. Relative date parsing for common date expressions
    2. Semantic search via ChromaDB to find relevant transactions
    3. LLM to interpret the query and generate a response
    """
    # First, try to parse relative dates directly (faster than LLM)
    rel_start, rel_end = parse_relative_date(query)

    # Check cache for intent analysis
    cached_intent = _get_cached_intent(query)

    if cached_intent:
        intent = cached_intent
        # Override with parsed relative dates if found
        if rel_start:
            intent["start_date"] = rel_start.isoformat()
        if rel_end:
            intent["end_date"] = rel_end.isoformat()
    else:
        # Use LLM to understand the query intent
        intent = await _analyze_query_intent(query)

        # Override with parsed relative dates if found (more reliable)
        if rel_start:
            intent["start_date"] = rel_start.isoformat()
        if rel_end:
            intent["end_date"] = rel_end.isoformat()

        # Cache the intent
        _cache_intent(query, intent)

    # Get relevant transactions based on intent
    transactions = await _get_relevant_transactions(query, intent)

    # Calculate stats from actual data
    stats = _calculate_stats(transactions)

    # Generate natural language summary using LLM with pre-calculated stats
    summary = await _generate_summary(query, transactions, stats)

    # Return the calculated total
    total_amount = stats.get("total_spending") if transactions else None

    return QueryResponse(
        summary=summary,
        transactions=transactions,
        total_amount=-total_amount if total_amount else None,  # Negative for spending
    )


async def _analyze_query_intent(query: str) -> dict:
    """
    Use LLM to analyze the query and extract structured intent.

    Returns a dict with:
    - category: Optional category filter
    - start_date: Optional start date
    - end_date: Optional end date
    - search_terms: Keywords to search for
    - calculate_total: Whether to sum amounts
    - query_type: "spending", "search", "summary", etc.
    """
    today = date.today()

    prompt = f"""Analyze this financial query and extract the intent as JSON.

Query: "{query}"

Today's date is {today.isoformat()}.

Return a JSON object with these fields:
- category: One of [Food & Dining, Shopping, Transportation, Entertainment, Bills & Utilities, Travel, Health, Groceries, Gas, Subscriptions, Income, Transfer, Other] or null
- start_date: Start date in YYYY-MM-DD format or null (use the EARLIEST year mentioned)
- end_date: End date in YYYY-MM-DD format or null (use the LATEST year mentioned)
- search_terms: Array of keywords to search for (merchant names, product types), or empty array
- calculate_total: true if the user wants to know total spending/amount
- query_type: One of ["spending", "search", "summary", "list", "compare"]

IMPORTANT for date handling:
- For relative dates like "last month", "this year", convert to actual dates
- For comparison queries (e.g., "compare 2025 to 2024"), set start_date to Jan 1 of the EARLIER year and end_date to Dec 31 of the LATER year
- For "last N days/weeks/months", calculate from today's date

Examples:
- "How much did I spend on food in December 2024?" -> {{"category": "Food & Dining", "start_date": "2024-12-01", "end_date": "2024-12-31", "search_terms": [], "calculate_total": true, "query_type": "spending"}}
- "Show me my Amazon purchases" -> {{"category": null, "start_date": null, "end_date": null, "search_terms": ["amazon"], "calculate_total": false, "query_type": "search"}}
- "Compare my coffee expenses from 2025 to 2024" -> {{"category": null, "start_date": "2024-01-01", "end_date": "2025-12-31", "search_terms": ["coffee"], "calculate_total": true, "query_type": "compare"}}
- "What did I spend last month?" -> {{"category": null, "start_date": "{(today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()}", "end_date": "{(today.replace(day=1) - timedelta(days=1)).isoformat()}", "search_terms": [], "calculate_total": true, "query_type": "spending"}}
- "Spending in the past 30 days" -> {{"category": null, "start_date": "{(today - timedelta(days=30)).isoformat()}", "end_date": "{today.isoformat()}", "search_terms": [], "calculate_total": true, "query_type": "spending"}}

Only respond with the JSON object, nothing else."""

    try:
        response = await acompletion(
            model=_get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            api_base=_get_api_base(),
            api_key=settings.openai_api_key if settings.llm_provider == "openai" else None,
            temperature=0.1,
            timeout=20.0,
        )

        content = response.choices[0].message.content.strip()

        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        return json.loads(content)

    except Exception as e:
        print(f"Intent analysis failed: {e}")
        # Return default intent
        return {
            "category": None,
            "start_date": None,
            "end_date": None,
            "search_terms": [],
            "calculate_total": True,
            "query_type": "search",
        }


async def _get_relevant_transactions(query: str, intent: dict) -> list[Transaction]:
    """Get transactions relevant to the query using both semantic search and filters."""
    # Parse dates from intent
    start_date = None
    end_date = None
    if intent.get("start_date"):
        try:
            start_date = date.fromisoformat(intent["start_date"])
        except ValueError:
            pass
    if intent.get("end_date"):
        try:
            end_date = date.fromisoformat(intent["end_date"])
        except ValueError:
            pass

    # Parse category
    category = None
    if intent.get("category"):
        try:
            category = TransactionCategory(intent["category"])
        except ValueError:
            pass

    search_terms = intent.get("search_terms", [])
    transactions = []
    seen_ids = set()

    # Detect if this is a specific type query that needs tag filtering
    query_lower = query.lower()
    required_tags = _get_required_tags(query_lower)

    # Extract brand names from query for direct database search
    brand_keywords = _extract_brand_keywords(query_lower)

    # FIRST: Do direct database search for brand keywords (most reliable)
    # This ensures we get ALL transactions matching the brand
    if brand_keywords:
        for keyword in brand_keywords:
            matches = db.search_transactions(keyword, limit=1000)
            for txn in matches:
                if str(txn.id) not in seen_ids:
                    # Verify the keyword is actually in the description
                    if keyword.lower() in txn.description.lower():
                        seen_ids.add(str(txn.id))
                        transactions.append(txn)

    # SECOND: ONLY use direct search for LLM search_terms if they look like specific merchants
    # (i.e., not generic category terms like "airlines", "restaurants", etc.)
    # This prevents category queries from being treated as brand queries
    generic_category_terms = {
        'airline', 'airlines', 'flight', 'flights',
        'restaurant', 'restaurants', 'food', 'dining',
        'hotel', 'hotels', 'lodging', 'accommodation',
        'grocery', 'groceries', 'supermarket',
        'gas', 'fuel', 'transportation', 'rideshare',
        'coffee', 'cafe', 'subscription', 'subscriptions'
    }

    merchant_search_terms = [t for t in search_terms if t.lower() not in generic_category_terms]
    search_terms_with_matches = []

    if merchant_search_terms:
        for term in merchant_search_terms:
            # Try exact term first
            search_variants = [term]

            # Add singular/plural variants for better matching
            # e.g., "sweetgreens" -> also try "sweetgreen"
            if term.endswith('s') and len(term) > 3:
                search_variants.append(term[:-1])  # Remove trailing 's'
            else:
                search_variants.append(term + 's')  # Add trailing 's'

            term_found_matches = False
            for variant in search_variants:
                matches = db.search_transactions(variant, limit=500)
                for txn in matches:
                    if str(txn.id) not in seen_ids:
                        # For specific search terms, verify the term (or variant) is in the description
                        if variant.lower() in txn.description.lower():
                            term_found_matches = True
                            if required_tags:
                                if _has_required_tags(txn, required_tags):
                                    seen_ids.add(str(txn.id))
                                    transactions.append(txn)
                            else:
                                seen_ids.add(str(txn.id))
                                transactions.append(txn)

            if term_found_matches:
                search_terms_with_matches.append(term)

    # THIRD: Use semantic search ONLY if we don't have direct brand/merchant matches
    # This helps find related items (e.g., "airlines" -> "EMIRATES") but can be noisy
    # Skip semantic search if we have specific brand/merchant matches (not category queries)
    has_brand_search = bool(brand_keywords)
    has_merchant_matches = bool(search_terms_with_matches)

    # Use semantic search if:
    # 1. No brand keywords AND no merchant matches from search terms
    # 2. This allows "airlines" (category, no direct matches) to use semantic search
    # 3. But "sweetgreen" (brand, has direct matches) skips semantic search
    should_use_semantic = not has_brand_search and not has_merchant_matches

    if should_use_semantic:
        # IMPORTANT: When we have required_tags, skip the category filter from LLM intent
        # because the LLM might categorize "airlines" as "Transportation" when they're
        # actually tagged as "Travel". We'll filter by tags instead which is more reliable.
        use_category_filter = None if required_tags else intent.get("category")

        search_results = await vector_store.search(
            query=query,
            n_results=200,
            category_filter=use_category_filter,
        )

        if search_results:
            txn_ids = [result["id"] for result in search_results]
            semantic_matches = db.get_transactions_by_ids(txn_ids)
            for txn in semantic_matches:
                if str(txn.id) not in seen_ids:
                    # If we have required tags, filter by them
                    if required_tags:
                        if _has_required_tags(txn, required_tags):
                            seen_ids.add(str(txn.id))
                            transactions.append(txn)
                    else:
                        seen_ids.add(str(txn.id))
                        transactions.append(txn)

    # FOURTH: If we have a category filter but few results and NO specific brand/merchant matches,
    # get more transactions by category. Skip this if we have brand/merchant matches.
    if category and len(transactions) < 50 and not has_merchant_matches:
        db_transactions = db.get_all_transactions(
            start_date=start_date,
            end_date=end_date,
            category=category,
            limit=500,
        )
        for txn in db_transactions:
            if str(txn.id) not in seen_ids:
                if required_tags:
                    if _has_required_tags(txn, required_tags):
                        seen_ids.add(str(txn.id))
                        transactions.append(txn)
                else:
                    seen_ids.add(str(txn.id))
                    transactions.append(txn)

    # Apply date filters
    if start_date:
        transactions = [txn for txn in transactions if txn.date >= start_date]
    if end_date:
        transactions = [txn for txn in transactions if txn.date <= end_date]

    # Apply category filter ONLY if we don't have brand-specific search or tag-based filtering
    # Brand searches (uber, starbucks, etc.) and tag-based searches (airlines, rideshare)
    # should return all matching transactions regardless of how they were categorized
    # because the LLM might return wrong category (e.g., "airlines" -> "Transportation" instead of "Travel")
    if category and not brand_keywords and not required_tags:
        transactions = [txn for txn in transactions if txn.category == category]

    # Sort by date descending
    transactions.sort(key=lambda x: x.date, reverse=True)

    # Limit results
    return transactions[:200]


def _extract_brand_keywords(query: str) -> list[str]:
    """
    Extract specific brand/merchant names from the query for direct database search.
    Returns keywords that should be searched directly in transaction descriptions.
    """
    # Known brands to look for in queries (expanded list)
    brands = [
        # Rideshare
        "uber", "lyft", "grab", "bolt", "gojek",
        # Food delivery
        "doordash", "grubhub", "postmates", "ubereats", "instacart",
        # Coffee & food
        "starbucks", "dunkin", "chipotle", "mcdonald", "chick-fil-a", "sweetgreen",
        "panera", "subway", "wendy", "taco bell", "panda express",
        # Retail & shopping
        "amazon", "target", "walmart", "costco", "whole foods", "trader joe",
        "best buy", "home depot", "lowes", "ikea", "nordstrom", "macys",
        "sephora", "ulta", "cvs", "walgreens",
        # Streaming & subscriptions
        "netflix", "spotify", "hulu", "disney", "hbo", "apple tv", "peacock",
        "youtube", "audible", "kindle",
        # Travel & lodging
        "airbnb", "vrbo", "marriott", "hilton", "hyatt", "expedia", "booking.com",
        # Airlines
        "emirates", "alaska", "delta", "united", "southwest", "american airlines",
        "jetblue", "spirit", "frontier", "hawaiian", "air canada", "british airways",
        # Gas stations
        "shell", "chevron", "exxon", "tesla", "bp", "arco",
        # Tech & software
        "apple", "google", "microsoft", "adobe", "github", "openai", "chatgpt",
        "dropbox", "zoom", "slack",
        # Health
        "peloton", "planet fitness", "equinox",
        # Telecom
        "at&t", "verizon", "t-mobile", "comcast", "xfinity",
    ]

    found = []
    query_lower = query.lower()
    for brand in brands:
        if brand in query_lower:
            found.append(brand)

    return found


def _get_required_tags(query: str) -> list[str]:
    """
    Determine if the query requires specific tags to filter results.
    This prevents "airlines" from matching "uber" just because both are "travel".

    For specific brand searches (uber, lyft, starbucks), we require the brand tag.
    For category searches (rideshare, airlines), we require the category tag.
    """
    # First check for specific brand names - these should match exactly
    # Order matters - check more specific patterns first
    brand_tags = {
        # Specific rideshare brands
        "uber eats": ["uber"],  # Uber Eats specifically
        "uber": ["uber"],
        "lyft": ["lyft"],
        "grab": ["grab"],

        # Specific airlines
        "emirates": ["airline"],
        "alaska air": ["airline"],
        "delta": ["airline"],
        "united": ["airline"],
        "southwest": ["airline"],
        "american airlines": ["airline"],
        "jetblue": ["airline"],

        # Specific coffee shops - use brand tag only for brand-specific searches
        "starbucks": ["starbucks"],
        "dunkin": ["dunkin"],
        "peets": ["peets"],

        # Specific stores
        "amazon": ["amazon"],
        "target": ["target"],
        "walmart": ["walmart"],
        "costco": ["costco"],
    }

    # Check brand-specific tags first (exact brand match)
    for brand, tags in brand_tags.items():
        if brand in query:
            return tags

    # Category-level tags for broader queries
    category_tags = {
        # Airlines category
        "airline": ["airline", "flight"],
        "airlines": ["airline", "flight"],
        "flight": ["airline", "flight"],
        "flights": ["airline", "flight"],
        "plane": ["airline", "flight"],

        # Rideshare category (only when asking about rideshare in general)
        "rideshare": ["rideshare"],
        "ride share": ["rideshare"],
        "taxi": ["rideshare"],

        # Hotels category
        "hotel": ["hotel", "lodging", "accommodation"],
        "hotels": ["hotel", "lodging", "accommodation"],
        "lodging": ["hotel", "lodging", "accommodation"],
        "accommodation": ["hotel", "lodging", "accommodation"],
        "airbnb": ["airbnb", "accommodation"],

        # Coffee category
        "coffee": ["coffee"],

        # Subscriptions
        "subscription": ["subscription"],
        "subscriptions": ["subscription"],

        # Streaming
        "streaming": ["streaming"],

        # Groceries
        "grocery": ["groceries"],
        "groceries": ["groceries"],
        "supermarket": ["groceries", "supermarket"],

        # Food delivery
        "food delivery": ["delivery"],
        "delivery": ["delivery"],
        "doordash": ["doordash", "delivery"],
        "grubhub": ["grubhub", "delivery"],
    }

    for keyword, tags in category_tags.items():
        if keyword in query:
            return tags

    return []


def _has_required_tags(txn: Transaction, required_tags: list[str]) -> bool:
    """Check if transaction has at least one of the required tags or matches in description."""
    if not required_tags:
        return True

    desc_lower = txn.description.lower()
    txn_tags_lower = [t.lower() for t in txn.tags] if txn.tags else []

    # Special handling for airline queries - require airline-specific patterns
    # This is more reliable than trusting tags alone, which can be incorrectly assigned
    if "airline" in required_tags and "flight" in required_tags:
        # Check for explicit airline indicators
        # Pattern 1: "AIRLINE" or "AIRLINES" or "AIRWAYS" or "AIR LINES" in description
        if any(term in desc_lower for term in ["airline", "airways", " air lines"]):
            return True

        # Pattern 2: Specific airline name followed by " AIR" or " AI" (common in statements)
        # e.g., "DELTA AIR LINES", "EMIRATES AI", "ALASKA AIR", "AIR-INDIA"
        airline_with_air = [
            "delta air", "united air", "american air", "southwest air",
            "alaska air", "emirates ai", "etihad air", "qatar air",
            "air canada", "air france", "air india", "air-india", "air china",
            "british air", "virgin air", "hawaiian air", "spirit air",
            "frontier air", "norwegian air"
        ]
        if any(pattern in desc_lower for pattern in airline_with_air):
            return True

        # Pattern 3: Budget airlines with unique names
        budget_airlines = ["jetblue", "ryanair", "easyjet", "airasia"]
        if any(airline in desc_lower for airline in budget_airlines):
            return True

        return False

    # Check description for the required tag/brand
    for tag in required_tags:
        tag_lower = tag.lower()
        if tag_lower in desc_lower:
            return True

    # Check tags - any match is sufficient
    if txn_tags_lower:
        if any(tag.lower() in txn_tags_lower for tag in required_tags):
            return True

    return False


def _calculate_stats(transactions: list[Transaction]) -> dict:
    """Calculate statistics from transactions - done in Python for accuracy."""
    if not transactions:
        return {}

    total_spending = sum(abs(txn.amount) for txn in transactions if txn.amount < 0)
    total_income = sum(txn.amount for txn in transactions if txn.amount > 0)

    # Year breakdown
    year_data: dict[int, dict] = {}
    for txn in transactions:
        year = txn.date.year
        if year not in year_data:
            year_data[year] = {"count": 0, "spending": 0.0, "income": 0.0}
        year_data[year]["count"] += 1
        if txn.amount < 0:
            year_data[year]["spending"] += abs(txn.amount)
        else:
            year_data[year]["income"] += txn.amount

    # Source breakdown
    source_data: dict[str, dict] = {}
    for txn in transactions:
        src = txn.source.value if txn.source else "unknown"
        if src not in source_data:
            source_data[src] = {"count": 0, "spending": 0.0}
        source_data[src]["count"] += 1
        if txn.amount < 0:
            source_data[src]["spending"] += abs(txn.amount)

    # Month breakdown (for current year)
    month_data: dict[str, dict] = {}
    for txn in transactions:
        month_key = txn.date.strftime("%Y-%m")
        if month_key not in month_data:
            month_data[month_key] = {"count": 0, "spending": 0.0}
        month_data[month_key]["count"] += 1
        if txn.amount < 0:
            month_data[month_key]["spending"] += abs(txn.amount)

    # Category breakdown
    category_data: dict[str, dict] = {}
    for txn in transactions:
        cat = txn.category.value if txn.category else "Uncategorized"
        if cat not in category_data:
            category_data[cat] = {"count": 0, "spending": 0.0}
        category_data[cat]["count"] += 1
        if txn.amount < 0:
            category_data[cat]["spending"] += abs(txn.amount)

    return {
        "total_count": len(transactions),
        "total_spending": total_spending,
        "total_income": total_income,
        "by_year": year_data,
        "by_source": source_data,
        "by_month": month_data,
        "by_category": category_data,
    }


async def _generate_summary(query: str, transactions: list[Transaction], stats: dict) -> str:
    """
    Generate a natural language summary using LLM, but with pre-calculated stats
    embedded as facts that MUST be used verbatim.
    """
    if not transactions:
        return "I couldn't find any transactions matching your query."

    total_count = stats.get("total_count", 0)
    total_spending = stats.get("total_spending", 0)
    total_income = stats.get("total_income", 0)
    by_year = stats.get("by_year", {})
    by_source = stats.get("by_source", {})
    by_category = stats.get("by_category", {})

    # Detect query type to customize facts
    query_lower = query.lower()
    is_biggest_query = any(word in query_lower for word in ["biggest", "largest", "top", "most", "highest"])
    is_category_query = "category" in query_lower or "categories" in query_lower
    is_source_query = any(word in query_lower for word in ["card", "chase", "amex", "coinbase", "source"])

    # Build a structured facts section with exact numbers
    facts = []
    facts.append(f"TOTAL: {total_count} transactions, ${total_spending:.2f} spent")

    if total_income > 0:
        facts.append(f"CREDITS: ${total_income:.2f} in refunds/credits")

    # Year breakdown with exact numbers
    for year in sorted(by_year.keys(), reverse=True):
        data = by_year[year]
        facts.append(f"YEAR {year}: {data['count']} transactions, ${data['spending']:.2f} spent")

    # Calculate comparison if multiple years
    if len(by_year) >= 2:
        years = sorted(by_year.keys(), reverse=True)
        newer_year, older_year = years[0], years[1]
        newer_spending = by_year[newer_year]["spending"]
        older_spending = by_year[older_year]["spending"]
        if older_spending > 0:
            change_pct = ((newer_spending - older_spending) / older_spending) * 100
            diff = newer_spending - older_spending
            if diff > 0:
                facts.append(f"CHANGE: +${diff:.2f} (+{change_pct:.0f}%) from {older_year} to {newer_year}")
            else:
                facts.append(f"CHANGE: -${abs(diff):.2f} ({change_pct:.0f}%) from {older_year} to {newer_year}")

    # Category breakdown - prioritize for "biggest expenses" type queries
    if by_category and (is_biggest_query or is_category_query or not is_source_query):
        # Sort categories by spending (highest first)
        sorted_categories = sorted(
            by_category.items(),
            key=lambda x: x[1]["spending"],
            reverse=True
        )
        # Include top categories
        for cat, data in sorted_categories[:5]:
            if data["spending"] > 0:
                facts.append(f"CATEGORY {cat}: {data['count']} transactions, ${data['spending']:.2f}")

    # Top individual transactions for "biggest" queries
    if is_biggest_query:
        # Get top 5 largest individual transactions (by amount)
        spending_txns = [t for t in transactions if t.amount < 0]
        top_txns = sorted(spending_txns, key=lambda t: t.amount)[:5]  # Most negative = largest
        if top_txns:
            facts.append("TOP INDIVIDUAL TRANSACTIONS:")
            for txn in top_txns:
                facts.append(f"  - ${abs(txn.amount):.2f}: {txn.description[:50]} ({txn.date})")

    # Source breakdown - only include if specifically asked or as secondary info
    if is_source_query or (not is_biggest_query and not is_category_query):
        source_labels = {"chase_credit": "Chase", "amex": "Amex", "coinbase": "Coinbase"}
        for src, data in by_source.items():
            label = source_labels.get(src, src)
            facts.append(f"CARD {label}: {data['count']} transactions, ${data['spending']:.2f}")

    facts_text = "\n".join(f"• {f}" for f in facts)

    # Build context-aware prompt guidance
    if is_biggest_query:
        guidance = """Focus on the CATEGORY breakdown and TOP INDIVIDUAL TRANSACTIONS to answer about biggest/largest expenses.
List the top spending categories by amount. If individual transactions are provided, mention the largest ones."""
    elif is_category_query:
        guidance = "Focus on the CATEGORY breakdown to answer the question."
    elif is_source_query:
        guidance = "Focus on the CARD breakdown to answer the question."
    else:
        guidance = "Answer the question using the most relevant facts."

    prompt = f"""User question: "{query}"

EXACT FACTS (you MUST use these exact numbers - do not change, round, or recalculate them):
{facts_text}

{guidance}

Write a natural, conversational 2-4 sentence response that answers the user's question.
You MUST include the exact dollar amounts and transaction counts from the facts above.
Do not say "based on the data" or similar - just answer naturally.
Keep it concise and friendly."""

    try:
        response = await acompletion(
            model=_get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            api_base=_get_api_base(),
            api_key=settings.openai_api_key if settings.llm_provider == "openai" else None,
            temperature=0.4,
            timeout=15.0,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Summary generation failed: {e}")
        # Fallback to basic template
        if len(by_year) > 1:
            year_parts = [f"{y}: {d['count']} transactions, ${d['spending']:.2f}"
                         for y, d in sorted(by_year.items(), reverse=True)]
            return f"Here's the breakdown: " + " | ".join(year_parts)
        return f"Found {total_count} transactions totaling ${total_spending:.2f} in spending."
