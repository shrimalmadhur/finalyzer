"""LLM-powered transaction categorization service."""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from litellm import acompletion

from backend.config import settings
from backend.models import Transaction, TransactionCategory


# Track background processing status
@dataclass
class ProcessingJob:
    """Represents a background processing job."""
    file_hash: str
    filename: str
    total_transactions: int
    processed_transactions: int = 0
    status: str = "processing"  # processing, complete, error
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


# Global processing tracker (in production, use Redis or similar)
_processing_jobs: dict[str, ProcessingJob] = {}


def start_processing_job(file_hash: str, filename: str, total: int) -> ProcessingJob:
    """Start tracking a new processing job."""
    job = ProcessingJob(
        file_hash=file_hash,
        filename=filename,
        total_transactions=total,
    )
    _processing_jobs[file_hash] = job
    return job


def update_processing_job(file_hash: str, processed: int) -> None:
    """Update progress of a processing job."""
    if file_hash in _processing_jobs:
        _processing_jobs[file_hash].processed_transactions = processed


def complete_processing_job(file_hash: str, error: Optional[str] = None) -> None:
    """Mark a processing job as complete."""
    if file_hash in _processing_jobs:
        job = _processing_jobs[file_hash]
        job.status = "error" if error else "complete"
        job.completed_at = datetime.now()
        job.error_message = error
        # Clean up old jobs after 5 minutes
        asyncio.get_event_loop().call_later(300, lambda: _processing_jobs.pop(file_hash, None))


def get_processing_status() -> list[dict]:
    """Get status of all active processing jobs."""
    now = datetime.now()
    result = []
    for job in _processing_jobs.values():
        elapsed = (now - job.started_at).total_seconds()
        result.append({
            "file_hash": job.file_hash,
            "filename": job.filename,
            "total": job.total_transactions,
            "processed": job.processed_transactions,
            "status": job.status,
            "elapsed_seconds": round(elapsed, 1),
            "error": job.error_message,
        })
    return result


def get_job_for_file(file_hash: str) -> Optional[dict]:
    """Get processing status for a specific file."""
    if file_hash in _processing_jobs:
        job = _processing_jobs[file_hash]
        now = datetime.now()
        elapsed = (now - job.started_at).total_seconds()
        return {
            "file_hash": job.file_hash,
            "filename": job.filename,
            "total": job.total_transactions,
            "processed": job.processed_transactions,
            "status": job.status,
            "elapsed_seconds": round(elapsed, 1),
            "error": job.error_message,
        }
    return None


# Category descriptions for the LLM
CATEGORY_DESCRIPTIONS = """
Available categories:
- Food & Dining: Restaurants, cafes, fast food, food delivery (DoorDash, UberEats, etc.)
- Shopping: Retail stores, online shopping (Amazon, Target, etc.), clothing, electronics
- Transportation: Uber, Lyft, taxis, public transit, parking
- Entertainment: Movies, concerts, streaming services (Netflix, Spotify), games
- Bills & Utilities: Electric, water, gas, internet, phone bills
- Travel: Hotels, airlines, car rentals, vacation expenses
- Health: Pharmacies, doctors, hospitals, gym memberships, health insurance
- Groceries: Supermarkets, grocery stores (Whole Foods, Trader Joe's, Costco)
- Gas: Gas stations, fuel
- Subscriptions: Recurring monthly/yearly services, memberships
- Income: Salary, refunds, cashback, rewards
- Transfer: Bank transfers, payments to self, Venmo/PayPal transfers
- Other: Anything that doesn't fit above categories
"""


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


def categorize_transactions_fast(transactions: list[Transaction]) -> None:
    """
    Fast categorization using raw_category and known merchants.
    No LLM calls - just mapping known categories.
    Modifies transactions in place.
    """
    categorized_count = 0
    for txn in transactions:
        if not txn.category:
            # First check if it's a known subscription by merchant name
            subscription_cat = _check_known_subscription(txn.description)
            if subscription_cat:
                txn.category = subscription_cat
                categorized_count += 1
            # Check known merchants for category
            elif merchant_cat := _check_known_merchant(txn.description):
                txn.category = merchant_cat
                categorized_count += 1
            # Then try raw_category mapping
            elif txn.raw_category:
                mapped = _map_raw_category(txn.raw_category, txn.description)
                if mapped:
                    txn.category = mapped
                    categorized_count += 1

    print(f"Fast categorization: {categorized_count}/{len(transactions)} from raw_category/known merchants")


# Known subscription services - these should always be categorized as Subscriptions
KNOWN_SUBSCRIPTIONS = [
    # Streaming - Video
    "netflix", "hulu", "disney+", "disney plus", "disneyplus",
    "hbo max", "hbo", "max", "peacock", "paramount+", "paramount plus",
    "prime video", "amazon prime video", "apple tv+", "apple tv",
    "crunchyroll", "funimation", "showtime", "starz", "mubi", "criterion",
    "curiosity stream", "discovery+", "espn+", "dazn", "fubo", "sling",
    "youtube tv", "youtube premium",

    # Streaming - Music
    "spotify", "apple music", "amazon music", "youtube music", "tidal",
    "deezer", "pandora", "soundcloud", "audible", "podcasts",

    # Software/Cloud
    "adobe", "creative cloud", "microsoft 365", "office 365", "microsoft office",
    "dropbox", "google one", "google drive", "icloud", "box.com",
    "github", "gitlab", "bitbucket", "notion", "evernote", "obsidian",
    "slack", "zoom", "teams", "webex", "calendly",
    "canva", "figma", "sketch", "invision", "miro",
    "grammarly", "jasper", "copy.ai", "writesonic",
    "1password", "lastpass", "bitwarden", "dashlane",
    "nordvpn", "expressvpn", "surfshark", "protonvpn", "mullvad",
    "protonmail", "tutanota", "hey.com",
    "jetbrains", "webstorm", "intellij", "pycharm", "phpstorm",
    "sublime text", "vs code", "cursor",

    # News/Reading
    "new york times", "nytimes", "nyt", "washington post", "wapo",
    "wsj", "wall street journal", "financial times", "economist",
    "medium", "substack", "patreon", "kindle unlimited", "scribd",
    "apple news", "google news", "reuters", "bloomberg",

    # Fitness/Health
    "peloton", "strava", "zwift", "fitbod", "strong",
    "headspace", "calm", "ten percent", "waking up", "balance",
    "noom", "weight watchers", "ww", "myfitnesspal", "lose it",
    "whoop", "oura", "eight sleep",

    # Gaming
    "xbox game pass", "xbox live", "playstation plus", "ps plus", "ps now",
    "nintendo online", "nintendo switch online",
    "ea play", "ea access", "ubisoft+", "ubisoft plus", "humble bundle",
    "geforce now", "xbox cloud", "playstation now", "luna",
    "twitch", "discord nitro",

    # AI/Tech
    "openai", "chatgpt", "gpt plus", "claude", "anthropic",
    "midjourney", "dall-e", "stable diffusion", "runway",
    "copilot", "tabnine", "replit",

    # Education
    "duolingo", "babbel", "rosetta stone",
    "coursera", "udemy", "skillshare", "masterclass", "linkedin learning",
    "brilliant", "khan academy", "codecademy",

    # Storage/Backup
    "backblaze", "carbonite", "idrive", "crashplan",
    "wasabi", "b2 cloud",

    # Dating/Social
    "tinder", "bumble", "hinge", "match.com", "okcupid", "eharmony",

    # Productivity
    "todoist", "asana", "monday.com", "clickup", "linear", "jira",
    "trello", "airtable", "coda", "roam research",

    # Finance
    "mint", "ynab", "personal capital", "quicken", "quickbooks",

    # Domain/Hosting
    "godaddy", "namecheap", "cloudflare", "vercel", "netlify", "heroku",
    "digitalocean", "linode", "aws", "amazon web services",
    "google cloud", "azure",

    # Other recurring
    "costco membership", "amazon prime", "sam's club", "bj's",
    "aaa", "roadside",
]


# Known merchants with their categories (for fast categorization without LLM)
KNOWN_MERCHANT_CATEGORIES: dict[str, TransactionCategory] = {
    # Food & Dining - Fast Food
    "mcdonald": TransactionCategory.FOOD_DINING,
    "burger king": TransactionCategory.FOOD_DINING,
    "wendy": TransactionCategory.FOOD_DINING,
    "taco bell": TransactionCategory.FOOD_DINING,
    "chick-fil-a": TransactionCategory.FOOD_DINING,
    "popeyes": TransactionCategory.FOOD_DINING,
    "kfc": TransactionCategory.FOOD_DINING,
    "arby": TransactionCategory.FOOD_DINING,
    "sonic drive": TransactionCategory.FOOD_DINING,
    "dairy queen": TransactionCategory.FOOD_DINING,
    "five guys": TransactionCategory.FOOD_DINING,
    "in-n-out": TransactionCategory.FOOD_DINING,
    "shake shack": TransactionCategory.FOOD_DINING,
    "jack in the box": TransactionCategory.FOOD_DINING,

    # Food & Dining - Fast Casual
    "chipotle": TransactionCategory.FOOD_DINING,
    "panera": TransactionCategory.FOOD_DINING,
    "sweetgreen": TransactionCategory.FOOD_DINING,
    "cava": TransactionCategory.FOOD_DINING,
    "noodles": TransactionCategory.FOOD_DINING,
    "qdoba": TransactionCategory.FOOD_DINING,
    "panda express": TransactionCategory.FOOD_DINING,
    "wingstop": TransactionCategory.FOOD_DINING,
    "buffalo wild": TransactionCategory.FOOD_DINING,
    "jersey mike": TransactionCategory.FOOD_DINING,
    "jimmy john": TransactionCategory.FOOD_DINING,
    "firehouse sub": TransactionCategory.FOOD_DINING,
    "potbelly": TransactionCategory.FOOD_DINING,
    "zaxby": TransactionCategory.FOOD_DINING,
    "raising cane": TransactionCategory.FOOD_DINING,

    # Food & Dining - Coffee/Cafe
    "starbucks": TransactionCategory.FOOD_DINING,
    "dunkin": TransactionCategory.FOOD_DINING,
    "peet": TransactionCategory.FOOD_DINING,
    "blue bottle": TransactionCategory.FOOD_DINING,
    "philz": TransactionCategory.FOOD_DINING,
    "dutch bros": TransactionCategory.FOOD_DINING,
    "coffee bean": TransactionCategory.FOOD_DINING,
    "caribou coffee": TransactionCategory.FOOD_DINING,
    "tim horton": TransactionCategory.FOOD_DINING,

    # Food & Dining - Delivery
    "doordash": TransactionCategory.FOOD_DINING,
    "uber eats": TransactionCategory.FOOD_DINING,
    "grubhub": TransactionCategory.FOOD_DINING,
    "postmates": TransactionCategory.FOOD_DINING,
    "seamless": TransactionCategory.FOOD_DINING,
    "caviar": TransactionCategory.FOOD_DINING,
    "gopuff": TransactionCategory.FOOD_DINING,

    # Groceries
    "whole foods": TransactionCategory.GROCERIES,
    "trader joe": TransactionCategory.GROCERIES,
    "safeway": TransactionCategory.GROCERIES,
    "kroger": TransactionCategory.GROCERIES,
    "publix": TransactionCategory.GROCERIES,
    "aldi": TransactionCategory.GROCERIES,
    "lidl": TransactionCategory.GROCERIES,
    "food lion": TransactionCategory.GROCERIES,
    "stop & shop": TransactionCategory.GROCERIES,
    "giant": TransactionCategory.GROCERIES,
    "wegmans": TransactionCategory.GROCERIES,
    "heb": TransactionCategory.GROCERIES,
    "meijer": TransactionCategory.GROCERIES,
    "sprouts": TransactionCategory.GROCERIES,
    "fresh market": TransactionCategory.GROCERIES,
    "instacart": TransactionCategory.GROCERIES,

    # Transportation - Rideshare
    "uber": TransactionCategory.TRANSPORTATION,
    "lyft": TransactionCategory.TRANSPORTATION,
    "grab": TransactionCategory.TRANSPORTATION,
    "bolt": TransactionCategory.TRANSPORTATION,
    "gojek": TransactionCategory.TRANSPORTATION,
    "via": TransactionCategory.TRANSPORTATION,
    "curb": TransactionCategory.TRANSPORTATION,

    # Travel - Airlines
    "delta air": TransactionCategory.TRAVEL,
    "united air": TransactionCategory.TRAVEL,
    "american air": TransactionCategory.TRAVEL,
    "southwest air": TransactionCategory.TRAVEL,
    "alaska air": TransactionCategory.TRAVEL,
    "jetblue": TransactionCategory.TRAVEL,
    "spirit air": TransactionCategory.TRAVEL,
    "frontier air": TransactionCategory.TRAVEL,
    "hawaiian air": TransactionCategory.TRAVEL,
    "sun country": TransactionCategory.TRAVEL,
    "emirates": TransactionCategory.TRAVEL,
    "british air": TransactionCategory.TRAVEL,
    "lufthansa": TransactionCategory.TRAVEL,
    "air canada": TransactionCategory.TRAVEL,
    "air france": TransactionCategory.TRAVEL,
    "klm": TransactionCategory.TRAVEL,
    "qatar air": TransactionCategory.TRAVEL,
    "singapore air": TransactionCategory.TRAVEL,

    # Travel - Hotels
    "marriott": TransactionCategory.TRAVEL,
    "hilton": TransactionCategory.TRAVEL,
    "hyatt": TransactionCategory.TRAVEL,
    "ihg": TransactionCategory.TRAVEL,
    "wyndham": TransactionCategory.TRAVEL,
    "best western": TransactionCategory.TRAVEL,
    "motel 6": TransactionCategory.TRAVEL,
    "la quinta": TransactionCategory.TRAVEL,
    "airbnb": TransactionCategory.TRAVEL,
    "vrbo": TransactionCategory.TRAVEL,
    "booking.com": TransactionCategory.TRAVEL,
    "expedia": TransactionCategory.TRAVEL,
    "hotels.com": TransactionCategory.TRAVEL,

    # Travel - Car Rental
    "hertz": TransactionCategory.TRAVEL,
    "enterprise": TransactionCategory.TRAVEL,
    "national car": TransactionCategory.TRAVEL,
    "budget rent": TransactionCategory.TRAVEL,
    "avis": TransactionCategory.TRAVEL,
    "dollar rent": TransactionCategory.TRAVEL,
    "sixt": TransactionCategory.TRAVEL,
    "turo": TransactionCategory.TRAVEL,

    # Gas
    "shell": TransactionCategory.GAS,
    "chevron": TransactionCategory.GAS,
    "exxon": TransactionCategory.GAS,
    "mobil": TransactionCategory.GAS,
    "bp": TransactionCategory.GAS,
    "arco": TransactionCategory.GAS,
    "76 gas": TransactionCategory.GAS,
    "speedway": TransactionCategory.GAS,
    "wawa": TransactionCategory.GAS,
    "sheetz": TransactionCategory.GAS,
    "quiktrip": TransactionCategory.GAS,
    "circle k": TransactionCategory.GAS,
    "7-eleven": TransactionCategory.GAS,
    "racetrac": TransactionCategory.GAS,
    "murphy usa": TransactionCategory.GAS,
    "costco gas": TransactionCategory.GAS,
    "sam's gas": TransactionCategory.GAS,

    # EV Charging
    "tesla supercharger": TransactionCategory.GAS,
    "chargepoint": TransactionCategory.GAS,
    "electrify america": TransactionCategory.GAS,
    "evgo": TransactionCategory.GAS,

    # Shopping - General
    "amazon": TransactionCategory.SHOPPING,
    "target": TransactionCategory.SHOPPING,
    "walmart": TransactionCategory.SHOPPING,
    "costco": TransactionCategory.SHOPPING,
    "sam's club": TransactionCategory.SHOPPING,
    "bj's wholesale": TransactionCategory.SHOPPING,

    # Shopping - Electronics
    "best buy": TransactionCategory.SHOPPING,
    "apple store": TransactionCategory.SHOPPING,
    "micro center": TransactionCategory.SHOPPING,
    "b&h photo": TransactionCategory.SHOPPING,

    # Shopping - Home
    "home depot": TransactionCategory.SHOPPING,
    "lowes": TransactionCategory.SHOPPING,
    "ikea": TransactionCategory.SHOPPING,
    "wayfair": TransactionCategory.SHOPPING,
    "bed bath": TransactionCategory.SHOPPING,
    "crate and barrel": TransactionCategory.SHOPPING,
    "pottery barn": TransactionCategory.SHOPPING,
    "williams sonoma": TransactionCategory.SHOPPING,
    "restoration hardware": TransactionCategory.SHOPPING,
    "west elm": TransactionCategory.SHOPPING,

    # Shopping - Fashion
    "nordstrom": TransactionCategory.SHOPPING,
    "macys": TransactionCategory.SHOPPING,
    "bloomingdales": TransactionCategory.SHOPPING,
    "neiman marcus": TransactionCategory.SHOPPING,
    "saks": TransactionCategory.SHOPPING,
    "zara": TransactionCategory.SHOPPING,
    "h&m": TransactionCategory.SHOPPING,
    "uniqlo": TransactionCategory.SHOPPING,
    "gap": TransactionCategory.SHOPPING,
    "old navy": TransactionCategory.SHOPPING,
    "banana republic": TransactionCategory.SHOPPING,
    "j.crew": TransactionCategory.SHOPPING,
    "lululemon": TransactionCategory.SHOPPING,
    "nike": TransactionCategory.SHOPPING,
    "adidas": TransactionCategory.SHOPPING,
    "foot locker": TransactionCategory.SHOPPING,
    "finish line": TransactionCategory.SHOPPING,

    # Shopping - Beauty
    "sephora": TransactionCategory.SHOPPING,
    "ulta": TransactionCategory.SHOPPING,
    "bath & body": TransactionCategory.SHOPPING,

    # Health
    "cvs": TransactionCategory.HEALTH,
    "walgreens": TransactionCategory.HEALTH,
    "rite aid": TransactionCategory.HEALTH,
    "kaiser": TransactionCategory.HEALTH,
    "quest diagnostic": TransactionCategory.HEALTH,
    "labcorp": TransactionCategory.HEALTH,
    "zocdoc": TransactionCategory.HEALTH,

    # Fitness (not subscription-based)
    "planet fitness": TransactionCategory.HEALTH,
    "equinox": TransactionCategory.HEALTH,
    "orangetheory": TransactionCategory.HEALTH,
    "crossfit": TransactionCategory.HEALTH,
    "24 hour fitness": TransactionCategory.HEALTH,
    "la fitness": TransactionCategory.HEALTH,
    "ymca": TransactionCategory.HEALTH,

    # Bills & Utilities
    "at&t": TransactionCategory.BILLS_UTILITIES,
    "verizon": TransactionCategory.BILLS_UTILITIES,
    "t-mobile": TransactionCategory.BILLS_UTILITIES,
    "sprint": TransactionCategory.BILLS_UTILITIES,
    "comcast": TransactionCategory.BILLS_UTILITIES,
    "xfinity": TransactionCategory.BILLS_UTILITIES,
    "spectrum": TransactionCategory.BILLS_UTILITIES,
    "cox communication": TransactionCategory.BILLS_UTILITIES,
    "frontier comm": TransactionCategory.BILLS_UTILITIES,
    "centurylink": TransactionCategory.BILLS_UTILITIES,
    "pg&e": TransactionCategory.BILLS_UTILITIES,
    "con edison": TransactionCategory.BILLS_UTILITIES,
    "duke energy": TransactionCategory.BILLS_UTILITIES,
    "national grid": TransactionCategory.BILLS_UTILITIES,
    "water bill": TransactionCategory.BILLS_UTILITIES,
    "sewer bill": TransactionCategory.BILLS_UTILITIES,
    "geico": TransactionCategory.BILLS_UTILITIES,
    "state farm": TransactionCategory.BILLS_UTILITIES,
    "allstate": TransactionCategory.BILLS_UTILITIES,
    "progressive": TransactionCategory.BILLS_UTILITIES,

    # Transfer/Payment
    "venmo": TransactionCategory.TRANSFER,
    "paypal": TransactionCategory.TRANSFER,
    "zelle": TransactionCategory.TRANSFER,
    "cash app": TransactionCategory.TRANSFER,
    "wire transfer": TransactionCategory.TRANSFER,
    "ach transfer": TransactionCategory.TRANSFER,

    # Entertainment
    "amc theatre": TransactionCategory.ENTERTAINMENT,
    "regal cinema": TransactionCategory.ENTERTAINMENT,
    "cinemark": TransactionCategory.ENTERTAINMENT,
    "imax": TransactionCategory.ENTERTAINMENT,
    "ticketmaster": TransactionCategory.ENTERTAINMENT,
    "stubhub": TransactionCategory.ENTERTAINMENT,
    "vivid seats": TransactionCategory.ENTERTAINMENT,
    "seatgeek": TransactionCategory.ENTERTAINMENT,
    "eventbrite": TransactionCategory.ENTERTAINMENT,
    "bowlero": TransactionCategory.ENTERTAINMENT,
    "topgolf": TransactionCategory.ENTERTAINMENT,
    "dave and buster": TransactionCategory.ENTERTAINMENT,
    "escape room": TransactionCategory.ENTERTAINMENT,
    "axe throw": TransactionCategory.ENTERTAINMENT,
    "steam": TransactionCategory.ENTERTAINMENT,
    "playstation store": TransactionCategory.ENTERTAINMENT,
    "xbox": TransactionCategory.ENTERTAINMENT,
    "nintendo eshop": TransactionCategory.ENTERTAINMENT,
    "epic games": TransactionCategory.ENTERTAINMENT,
}


def _check_known_subscription(description: str) -> Optional[TransactionCategory]:
    """Check if the transaction is a known subscription service."""
    desc_lower = description.lower()

    for subscription in KNOWN_SUBSCRIPTIONS:
        if subscription in desc_lower:
            return TransactionCategory.SUBSCRIPTIONS

    return None


def _check_known_merchant(description: str) -> Optional[TransactionCategory]:
    """Check if the transaction is from a known merchant and return its category."""
    desc_lower = description.lower()

    for merchant, category in KNOWN_MERCHANT_CATEGORIES.items():
        if merchant in desc_lower:
            return category

    return None


async def schedule_llm_categorization(transaction_ids: list[str], file_hash: Optional[str] = None) -> None:
    """
    Categorize transactions by ID using LLM in batches.
    Updates the database directly.
    """
    from backend.db.sqlite import db

    if not transaction_ids:
        return

    # Get transactions from DB
    transactions = db.get_transactions_by_ids(transaction_ids)
    uncategorized = [t for t in transactions if not t.category]

    if not uncategorized:
        return

    print(f"LLM categorizing {len(uncategorized)} transactions in batches...")

    # Process in batches of 15 (increased from 10 for efficiency)
    batch_size = 15
    processed_count = 0

    for i in range(0, len(uncategorized), batch_size):
        batch = uncategorized[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(uncategorized) + batch_size - 1) // batch_size

        try:
            print(f"  Batch {batch_num}/{total_batches}...")
            await asyncio.wait_for(_categorize_batch(batch), timeout=30.0)

            # Update database with new categories
            for txn in batch:
                if txn.category:
                    db.update_transaction_category(txn.id, txn.category)

            processed_count += len(batch)

            # Update processing job progress
            if file_hash:
                update_processing_job(file_hash, processed_count)

        except asyncio.TimeoutError:
            print(f"  Batch {batch_num} timeout, skipping...")
            processed_count += len(batch)
            if file_hash:
                update_processing_job(file_hash, processed_count)
        except Exception as e:
            print(f"  Batch {batch_num} error: {e}")
            processed_count += len(batch)
            if file_hash:
                update_processing_job(file_hash, processed_count)

        # Small delay between batches to avoid rate limits
        if i + batch_size < len(uncategorized):
            await asyncio.sleep(0.3)

    print(f"LLM categorization complete")


async def categorize_transactions(transactions: list[Transaction]) -> list[Transaction]:
    """
    Categorize a list of transactions using LLM.

    Processes transactions in batches for efficiency.
    Falls back to raw_category or leaves uncategorized if LLM fails.
    """
    if not transactions:
        return transactions

    # First, try to use raw_category from the source if available
    categorize_transactions_fast(transactions)

    # Find transactions that still need categorization
    uncategorized = [txn for txn in transactions if not txn.category]

    if not uncategorized:
        return transactions

    print(f"Categorizing {len(uncategorized)} transactions via LLM...")

    # Process in batches of 15
    batch_size = 15

    for i in range(0, len(uncategorized), batch_size):
        batch = uncategorized[i : i + batch_size]
        try:
            # Add timeout to prevent hanging
            await asyncio.wait_for(_categorize_batch(batch), timeout=30.0)
        except asyncio.TimeoutError:
            print(f"Categorization timeout for batch {i//batch_size + 1}, skipping...")
        except Exception as e:
            # If LLM fails, keep transactions uncategorized
            print(f"Categorization error: {e}")

    return transactions


def _map_raw_category(raw_category: str, description: str = "") -> Optional[TransactionCategory]:
    """Map raw category from bank statement to our categories."""
    if not raw_category:
        return None

    raw_lower = raw_category.lower()
    desc_lower = description.lower() if description else ""

    # Special handling: "Entertainment" category but it's actually a subscription
    if "entertainment" in raw_lower:
        # Check if it's a known streaming/subscription service
        if _check_known_subscription(description):
            return TransactionCategory.SUBSCRIPTIONS
        # Otherwise it's entertainment (movies, concerts, etc.)
        return TransactionCategory.ENTERTAINMENT

    # Chase/Amex category mappings
    category_mappings = {
        "food & drink": TransactionCategory.FOOD_DINING,
        "food": TransactionCategory.FOOD_DINING,
        "dining": TransactionCategory.FOOD_DINING,
        "restaurants": TransactionCategory.FOOD_DINING,
        "restaurant": TransactionCategory.FOOD_DINING,
        "cafe": TransactionCategory.FOOD_DINING,
        "coffee shop": TransactionCategory.FOOD_DINING,
        "fast food": TransactionCategory.FOOD_DINING,
        "bakery": TransactionCategory.FOOD_DINING,
        "shopping": TransactionCategory.SHOPPING,
        "merchandise": TransactionCategory.SHOPPING,
        "retail": TransactionCategory.SHOPPING,
        "department store": TransactionCategory.SHOPPING,
        "electronics": TransactionCategory.SHOPPING,
        "clothing": TransactionCategory.SHOPPING,
        "home improvement": TransactionCategory.SHOPPING,
        "travel": TransactionCategory.TRAVEL,
        "airlines": TransactionCategory.TRAVEL,
        "airline": TransactionCategory.TRAVEL,
        "hotels": TransactionCategory.TRAVEL,
        "hotel": TransactionCategory.TRAVEL,
        "lodging": TransactionCategory.TRAVEL,
        "car rental": TransactionCategory.TRAVEL,
        "gas": TransactionCategory.GAS,
        "automotive": TransactionCategory.GAS,
        "fuel": TransactionCategory.GAS,
        "service station": TransactionCategory.GAS,
        "groceries": TransactionCategory.GROCERIES,
        "grocery": TransactionCategory.GROCERIES,
        "supermarket": TransactionCategory.GROCERIES,
        "health": TransactionCategory.HEALTH,
        "health & wellness": TransactionCategory.HEALTH,
        "medical": TransactionCategory.HEALTH,
        "pharmacy": TransactionCategory.HEALTH,
        "doctor": TransactionCategory.HEALTH,
        "dental": TransactionCategory.HEALTH,
        "vision": TransactionCategory.HEALTH,
        "fitness": TransactionCategory.HEALTH,
        "streaming": TransactionCategory.SUBSCRIPTIONS,
        "subscription": TransactionCategory.SUBSCRIPTIONS,
        "membership": TransactionCategory.SUBSCRIPTIONS,
        "bills & utilities": TransactionCategory.BILLS_UTILITIES,
        "bills": TransactionCategory.BILLS_UTILITIES,
        "utilities": TransactionCategory.BILLS_UTILITIES,
        "phone": TransactionCategory.BILLS_UTILITIES,
        "internet": TransactionCategory.BILLS_UTILITIES,
        "cable": TransactionCategory.BILLS_UTILITIES,
        "insurance": TransactionCategory.BILLS_UTILITIES,
        "professional services": TransactionCategory.OTHER,
        "personal": TransactionCategory.OTHER,
        "fees & adjustments": TransactionCategory.OTHER,
        "payment": TransactionCategory.TRANSFER,
        "transfer": TransactionCategory.TRANSFER,
        "atm": TransactionCategory.TRANSFER,
        "refund": TransactionCategory.INCOME,
        "reward": TransactionCategory.INCOME,
        "cashback": TransactionCategory.INCOME,
        "credit": TransactionCategory.INCOME,
    }

    for key, category in category_mappings.items():
        if key in raw_lower:
            return category

    return None


async def _categorize_batch(transactions: list[Transaction]) -> list[Transaction]:
    """Categorize a batch of transactions."""
    # Build the prompt
    transaction_list = "\n".join(
        f"{i+1}. {txn.description} (${abs(txn.amount):.2f})"
        for i, txn in enumerate(transactions)
    )

    prompt = f"""Categorize each of the following financial transactions into one of these categories:
{CATEGORY_DESCRIPTIONS}

Transactions to categorize:
{transaction_list}

Respond with a JSON array of category names in the same order as the transactions.
Example response: ["Food & Dining", "Shopping", "Transportation"]

Only respond with the JSON array, nothing else."""

    try:
        response = await acompletion(
            model=_get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            api_base=_get_api_base(),
            api_key=settings.openai_api_key if settings.llm_provider == "openai" else None,
            temperature=0.1,  # Low temperature for consistent categorization
            timeout=25.0,  # 25 second timeout
        )

        # Parse the response
        content = response.choices[0].message.content.strip()

        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        categories = json.loads(content)

        # Apply categories to transactions
        for i, txn in enumerate(transactions):
            if i < len(categories):
                category_str = categories[i]
                txn.category = _parse_category(category_str)

    except Exception as e:
        print(f"LLM categorization failed: {e}")
        # Leave transactions uncategorized

    return transactions


def _parse_category(category_str: str) -> TransactionCategory:
    """Parse a category string to TransactionCategory enum."""
    # Try exact match first
    try:
        return TransactionCategory(category_str)
    except ValueError:
        pass

    # Try case-insensitive match
    category_lower = category_str.lower()
    for cat in TransactionCategory:
        if cat.value.lower() == category_lower:
            return cat

    # Try partial match
    category_map = {
        "food": TransactionCategory.FOOD_DINING,
        "dining": TransactionCategory.FOOD_DINING,
        "restaurant": TransactionCategory.FOOD_DINING,
        "shop": TransactionCategory.SHOPPING,
        "retail": TransactionCategory.SHOPPING,
        "transport": TransactionCategory.TRANSPORTATION,
        "uber": TransactionCategory.TRANSPORTATION,
        "lyft": TransactionCategory.TRANSPORTATION,
        "entertain": TransactionCategory.ENTERTAINMENT,
        "movie": TransactionCategory.ENTERTAINMENT,
        "bill": TransactionCategory.BILLS_UTILITIES,
        "utility": TransactionCategory.BILLS_UTILITIES,
        "travel": TransactionCategory.TRAVEL,
        "hotel": TransactionCategory.TRAVEL,
        "flight": TransactionCategory.TRAVEL,
        "health": TransactionCategory.HEALTH,
        "medical": TransactionCategory.HEALTH,
        "pharmacy": TransactionCategory.HEALTH,
        "grocery": TransactionCategory.GROCERIES,
        "supermarket": TransactionCategory.GROCERIES,
        "gas": TransactionCategory.GAS,
        "fuel": TransactionCategory.GAS,
        "subscription": TransactionCategory.SUBSCRIPTIONS,
        "membership": TransactionCategory.SUBSCRIPTIONS,
        "income": TransactionCategory.INCOME,
        "salary": TransactionCategory.INCOME,
        "refund": TransactionCategory.INCOME,
        "transfer": TransactionCategory.TRANSFER,
        "payment": TransactionCategory.TRANSFER,
    }

    for keyword, cat in category_map.items():
        if keyword in category_lower:
            return cat

    return TransactionCategory.OTHER


async def categorize_single(description: str, amount: float) -> TransactionCategory:
    """Categorize a single transaction description."""
    prompt = f"""Categorize this financial transaction into one of these categories:
{CATEGORY_DESCRIPTIONS}

Transaction: {description} (${abs(amount):.2f})

Respond with only the category name, nothing else."""

    try:
        response = await acompletion(
            model=_get_model_name(),
            messages=[{"role": "user", "content": prompt}],
            api_base=_get_api_base(),
            api_key=settings.openai_api_key if settings.llm_provider == "openai" else None,
            temperature=0.1,
        )

        category_str = response.choices[0].message.content.strip()
        return _parse_category(category_str)

    except Exception as e:
        print(f"Single categorization failed: {e}")
        return TransactionCategory.OTHER
