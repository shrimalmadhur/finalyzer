"""LLM-powered transaction tagging service."""

import asyncio
import json

from litellm import acompletion

from backend.config import settings
from backend.models import Transaction


def _get_model_name() -> str:
    """Get the appropriate model name based on provider."""
    if settings.llm_provider == "openai":
        return settings.openai_model
    else:
        return f"ollama/{settings.ollama_model}"


def _get_api_base() -> str | None:
    """Get the API base URL for Ollama."""
    if settings.llm_provider == "ollama":
        return settings.ollama_host
    return None


# Known merchant tags for fast tagging without LLM
MERCHANT_TAGS: dict[str, list[str]] = {
    # Travel & Accommodation
    "airbnb": ["travel", "accommodation", "lodging", "vacation", "rental"],
    "hotel": ["travel", "accommodation", "lodging", "hotel"],
    "marriott": ["travel", "accommodation", "lodging", "hotel"],
    "hilton": ["travel", "accommodation", "lodging", "hotel"],
    "hyatt": ["travel", "accommodation", "lodging", "hotel"],
    "vrbo": ["travel", "accommodation", "lodging", "vacation", "rental"],
    "booking.com": ["travel", "accommodation", "lodging"],
    "expedia": ["travel", "booking", "vacation"],
    "united": ["travel", "airline", "flight", "booking"],
    "delta": ["travel", "airline", "flight", "booking"],
    "american airlines": ["travel", "airline", "flight", "booking"],
    "southwest": ["travel", "airline", "flight", "booking"],
    "jetblue": ["travel", "airline", "flight", "booking"],
    "spirit": ["travel", "airline", "flight", "booking"],
    "frontier": ["travel", "airline", "flight", "booking"],
    "emirates": ["travel", "airline", "flight", "international", "booking"],
    "alaska": ["travel", "airline", "flight", "booking"],
    "alaska air": ["travel", "airline", "flight", "booking"],
    "air canada": ["travel", "airline", "flight", "international", "booking"],
    "british airways": ["travel", "airline", "flight", "international", "booking"],
    "lufthansa": ["travel", "airline", "flight", "international", "booking"],
    "qatar": ["travel", "airline", "flight", "international", "booking"],
    "singapore air": ["travel", "airline", "flight", "international", "booking"],
    "cathay": ["travel", "airline", "flight", "international", "booking"],
    "korean air": ["travel", "airline", "flight", "international", "booking"],
    "ana": ["travel", "airline", "flight", "international", "booking"],
    "jal": ["travel", "airline", "flight", "international", "booking"],
    "air france": ["travel", "airline", "flight", "international", "booking"],
    "klm": ["travel", "airline", "flight", "international", "booking"],
    "virgin": ["travel", "airline", "flight", "booking"],
    "hawaiian": ["travel", "airline", "flight", "booking"],
    "sun country": ["travel", "airline", "flight", "booking"],
    "allegiant": ["travel", "airline", "flight", "booking"],
    # Food & Dining
    "doordash": ["food", "delivery", "restaurant", "takeout"],
    "grubhub": ["food", "delivery", "restaurant", "takeout"],
    "postmates": ["food", "delivery", "restaurant", "takeout"],
    "instacart": ["groceries", "delivery", "food"],
    "chipotle": ["food", "restaurant", "mexican", "fast-casual"],
    "starbucks": ["food", "coffee", "cafe", "drinks"],
    "dunkin": ["food", "coffee", "cafe", "drinks"],
    "mcdonald": ["food", "restaurant", "fast-food"],
    "chick-fil-a": ["food", "restaurant", "fast-food"],
    "wendy": ["food", "restaurant", "fast-food"],
    "taco bell": ["food", "restaurant", "fast-food", "mexican"],
    "panera": ["food", "restaurant", "fast-casual", "bakery"],
    "sweetgreen": ["food", "restaurant", "healthy", "salad"],
    # Shopping
    "amazon": ["shopping", "online", "retail", "ecommerce"],
    "target": ["shopping", "retail", "department-store"],
    "walmart": ["shopping", "retail", "groceries", "department-store"],
    "costco": ["shopping", "wholesale", "groceries", "bulk"],
    "best buy": ["shopping", "electronics", "retail"],
    "apple": ["shopping", "electronics", "tech", "apple"],
    "ikea": ["shopping", "furniture", "home"],
    "home depot": ["shopping", "home-improvement", "hardware"],
    "lowes": ["shopping", "home-improvement", "hardware"],
    "nordstrom": ["shopping", "fashion", "clothing", "retail"],
    "macys": ["shopping", "fashion", "clothing", "department-store"],
    "sephora": ["shopping", "beauty", "cosmetics"],
    "ulta": ["shopping", "beauty", "cosmetics"],
    # Transportation - Rideshare (include brand name as tag for specific searches)
    "uber": ["transportation", "rideshare", "uber"],
    "uber eats": ["food", "delivery", "restaurant", "takeout", "uber"],  # Override for Uber Eats
    "lyft": ["transportation", "rideshare", "lyft"],
    "grab": ["transportation", "rideshare", "grab"],
    "bolt": ["transportation", "rideshare", "bolt"],
    "gojek": ["transportation", "rideshare", "gojek"],
    # Gas stations
    "shell": ["gas", "fuel", "automotive"],
    "chevron": ["gas", "fuel", "automotive"],
    "exxon": ["gas", "fuel", "automotive"],
    "bp": ["gas", "fuel", "automotive"],
    "mobil": ["gas", "fuel", "automotive"],
    "arco": ["gas", "fuel", "automotive"],
    "76": ["gas", "fuel", "automotive"],
    "speedway": ["gas", "fuel", "automotive"],
    "wawa": ["gas", "fuel", "automotive", "convenience"],
    "tesla": ["automotive", "electric", "charging"],
    "chargepoint": ["automotive", "electric", "charging"],
    "electrify": ["automotive", "electric", "charging"],
    # Subscriptions & Services
    "netflix": ["subscription", "streaming", "entertainment", "movies", "tv"],
    "spotify": ["subscription", "streaming", "music", "entertainment"],
    "hulu": ["subscription", "streaming", "entertainment", "tv"],
    "disney": ["subscription", "streaming", "entertainment", "movies"],
    "hbo": ["subscription", "streaming", "entertainment", "tv"],
    "amazon prime": ["subscription", "streaming", "shopping", "membership"],
    "apple music": ["subscription", "streaming", "music"],
    "youtube": ["subscription", "streaming", "video", "entertainment"],
    "openai": ["subscription", "ai", "software", "tech"],
    "chatgpt": ["subscription", "ai", "software", "tech"],
    "claude": ["subscription", "ai", "software", "tech"],
    "anthropic": ["subscription", "ai", "software", "tech"],
    "github": ["subscription", "software", "developer", "tech"],
    "dropbox": ["subscription", "storage", "cloud", "software"],
    "google one": ["subscription", "storage", "cloud", "google"],
    "icloud": ["subscription", "storage", "cloud", "apple"],
    "adobe": ["subscription", "software", "creative", "design"],
    "microsoft": ["subscription", "software", "office", "productivity"],
    "zoom": ["subscription", "software", "video", "meetings"],
    "slack": ["subscription", "software", "communication", "work"],
    # Groceries
    "whole foods": ["groceries", "organic", "food", "supermarket"],
    "trader joe": ["groceries", "food", "supermarket"],
    "safeway": ["groceries", "food", "supermarket"],
    "kroger": ["groceries", "food", "supermarket"],
    "publix": ["groceries", "food", "supermarket"],
    "aldi": ["groceries", "food", "supermarket", "discount"],
    # Health & Fitness
    "cvs": ["health", "pharmacy", "drugstore"],
    "walgreens": ["health", "pharmacy", "drugstore"],
    "rite aid": ["health", "pharmacy", "drugstore"],
    "peloton": ["fitness", "subscription", "exercise", "health"],
    "planet fitness": ["fitness", "gym", "health", "membership"],
    "equinox": ["fitness", "gym", "health", "membership"],
    "orangetheory": ["fitness", "gym", "health", "membership"],
    # Bills & Utilities
    "at&t": ["bills", "phone", "telecom", "utilities"],
    "verizon": ["bills", "phone", "telecom", "utilities"],
    "t-mobile": ["bills", "phone", "telecom", "utilities"],
    "comcast": ["bills", "internet", "cable", "utilities"],
    "xfinity": ["bills", "internet", "cable", "utilities"],
    "spectrum": ["bills", "internet", "cable", "utilities"],
    "pg&e": ["bills", "utilities", "electric", "gas"],
    "con edison": ["bills", "utilities", "electric"],
}


def tag_transactions_fast(transactions: list[Transaction]) -> None:
    """
    Fast tagging using known merchant patterns.
    No LLM calls - just pattern matching.
    Modifies transactions in place.
    """
    tagged_count = 0
    for txn in transactions:
        if not txn.tags:
            tags = _get_merchant_tags(txn.description)
            if tags:
                txn.tags = tags
                tagged_count += 1

    print(f"Fast tagging: {tagged_count}/{len(transactions)} from known merchants")


def _get_merchant_tags(description: str) -> list[str]:
    """Get tags for a transaction based on merchant name."""
    desc_lower = description.lower()

    for merchant, tags in MERCHANT_TAGS.items():
        if merchant in desc_lower:
            return tags

    return []


async def schedule_llm_tagging(transaction_ids: list[str], file_hash: str | None = None) -> None:
    """
    Tag transactions by ID using LLM in batches.
    Updates the database directly.
    """
    from backend.db.sqlite import db

    if not transaction_ids:
        return

    # Get transactions from DB
    transactions = db.get_transactions_by_ids(transaction_ids)
    untagged = [t for t in transactions if not t.tags]

    if not untagged:
        return

    print(f"LLM tagging {len(untagged)} transactions in batches...")

    # Process in batches of 10
    batch_size = 10

    for i in range(0, len(untagged), batch_size):
        batch = untagged[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(untagged) + batch_size - 1) // batch_size

        try:
            print(f"  Tagging batch {batch_num}/{total_batches}...")
            await asyncio.wait_for(_tag_batch(batch), timeout=30.0)

            # Update database with new tags
            for txn in batch:
                if txn.tags:
                    db.update_transaction_tags(txn.id, txn.tags)

        except TimeoutError:
            print(f"  Batch {batch_num} timeout, skipping...")
        except Exception as e:
            print(f"  Batch {batch_num} error: {e}")

        # Small delay between batches to avoid rate limits
        if i + batch_size < len(untagged):
            await asyncio.sleep(0.5)

    print("LLM tagging complete")


async def _tag_batch(transactions: list[Transaction]) -> list[Transaction]:
    """Tag a batch of transactions using LLM."""
    # Build the prompt
    transaction_list = "\n".join(
        f"{i + 1}. {txn.description} (${abs(txn.amount):.2f}, {txn.date})" for i, txn in enumerate(transactions)
    )

    prompt = f"""Generate search tags for each financial transaction. Tags should be lowercase keywords that would help find this transaction in a search.

Include tags for:
- Merchant type (restaurant, store, service, etc.)
- Purchase category (food, travel, entertainment, etc.)
- Specific attributes (online, delivery, subscription, etc.)
- Brand/company name variations

Transactions to tag:
{transaction_list}

Respond with a JSON array where each element is an array of 3-6 relevant tags.
Example: [["food", "delivery", "restaurant", "mexican"], ["travel", "airline", "flight", "vacation"]]

Only respond with the JSON array, nothing else."""

    try:
        response = await acompletion(
            model=_get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            api_base=_get_api_base(),
            api_key=settings.openai_api_key if settings.llm_provider == "openai" else None,
            temperature=0.1,
            timeout=25.0,
        )

        # Parse the response
        content = response.choices[0].message.content.strip()

        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        tags_list = json.loads(content)

        # Apply tags to transactions
        for i, txn in enumerate(transactions):
            if i < len(tags_list):
                tags = tags_list[i]
                if isinstance(tags, list):
                    # Ensure all tags are lowercase strings
                    txn.tags = [str(t).lower().strip() for t in tags if t]

    except Exception as e:
        print(f"LLM tagging failed: {e}")
        # Leave transactions untagged

    return transactions
