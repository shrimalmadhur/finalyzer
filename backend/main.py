"""FastAPI application for Finalyzer."""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db.sqlite import db
from backend.models import (
    QueryRequest,
    QueryResponse,
    SettingsResponse,
    SettingsUpdate,
    Transaction,
    UploadResponse,
)
from backend.services.query_engine import query_transactions
from backend.services.upload import process_upload

app = FastAPI(
    title="FINalyzer",
    description="Personal finance analyzer with LLM-powered categorization",
    version="0.1.0",
)

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    settings.ensure_directories()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "transaction_count": db.get_transaction_count()}


@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a financial statement (PDF or CSV)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Check file extension
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".pdf") or filename_lower.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Only PDF and CSV files are supported")

    # Read file contents
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        result = await process_upload(file.filename, contents)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.get("/transactions", response_model=list[Transaction])
async def get_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    source: str | None = None,
    limit: int = 100,
):
    """Get transactions with optional filters."""
    from datetime import date as date_type

    from backend.models import TransactionCategory, TransactionSource

    start = date_type.fromisoformat(start_date) if start_date else None
    end = date_type.fromisoformat(end_date) if end_date else None
    cat = TransactionCategory(category) if category else None
    src = TransactionSource(source) if source else None

    return db.get_all_transactions(start_date=start, end_date=end, category=cat, source=src, limit=limit)


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Query transactions using natural language."""
    try:
        result = await query_transactions(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@app.get("/summary")
async def get_summary(start_date: str | None = None, end_date: str | None = None):
    """Get spending summary by category."""
    from datetime import date as date_type

    start = date_type.fromisoformat(start_date) if start_date else None
    end = date_type.fromisoformat(end_date) if end_date else None

    summary = db.get_spending_summary(start_date=start, end_date=end)
    total = sum(summary.values())
    return {"by_category": summary, "total": total}


@app.get("/files")
async def get_uploaded_files():
    """Get list of uploaded files."""
    files = db.get_uploaded_files()
    return {"files": files}


@app.get("/processing-status")
async def get_processing_status():
    """Get status of background processing jobs."""
    from backend.services.categorizer import get_processing_status

    jobs = get_processing_status()
    return {"jobs": jobs, "has_active": any(j["status"] == "processing" for j in jobs)}


@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    return SettingsResponse(
        llm_provider=settings.llm_provider,
        ollama_host=settings.ollama_host,
        has_openai_key=bool(settings.openai_api_key),
    )


@app.put("/settings")
async def update_settings(update: SettingsUpdate):
    """Update settings (runtime only, doesn't persist to .env)."""
    if update.llm_provider:
        settings.llm_provider = update.llm_provider  # type: ignore
    if update.openai_api_key:
        settings.openai_api_key = update.openai_api_key
    if update.ollama_host:
        settings.ollama_host = update.ollama_host
    return {"status": "updated"}


@app.post("/recategorize")
async def recategorize_subscriptions():
    """
    Re-categorize transactions to fix subscription detection.
    This updates existing transactions that should be subscriptions.
    """
    from backend.models import TransactionCategory
    from backend.services.categorizer import _check_known_subscription

    # Get all transactions
    all_transactions = db.get_all_transactions(limit=10000)

    updated = 0
    for txn in all_transactions:
        # Check if this should be a subscription
        if _check_known_subscription(txn.description):
            if txn.category != TransactionCategory.SUBSCRIPTIONS:
                db.update_transaction_category(txn.id, TransactionCategory.SUBSCRIPTIONS)
                updated += 1

    return {
        "status": "complete",
        "transactions_checked": len(all_transactions),
        "subscriptions_fixed": updated,
    }


@app.post("/retag")
async def retag_transactions(reembed: bool = True):
    """
    Re-tag all transactions using the tagging service.
    Useful for applying tags to existing transactions.

    Args:
        reembed: If True, also re-embed transactions in vector store for better search
    """
    import asyncio

    from backend.db.vector import vector_store
    from backend.services.tagger import schedule_llm_tagging, tag_transactions_fast

    # Get all transactions
    all_transactions = db.get_all_transactions(limit=10000)

    # Fast tag first
    tag_transactions_fast(all_transactions)

    # Update DB with fast tags
    fast_tagged = 0
    for txn in all_transactions:
        if txn.tags:
            db.update_transaction_tags(txn.id, txn.tags)
            fast_tagged += 1

    # Re-embed tagged transactions in vector store for better semantic search
    reembedded = 0
    if reembed:
        # Get updated transactions from DB (with tags)
        updated_transactions = db.get_all_transactions(limit=10000)
        tagged_txns = [txn for txn in updated_transactions if txn.tags]

        if tagged_txns:
            # Re-embed in batches
            batch_size = 50
            for i in range(0, len(tagged_txns), batch_size):
                batch = tagged_txns[i : i + batch_size]
                try:
                    await vector_store.add_transactions_batch(batch)
                    reembedded += len(batch)
                except Exception as e:
                    print(f"Re-embed batch failed: {e}")

    # Get untagged for LLM
    untagged_ids = [str(txn.id) for txn in all_transactions if not txn.tags]

    if untagged_ids:
        asyncio.create_task(schedule_llm_tagging(untagged_ids))
        return {
            "status": "scheduled",
            "transactions_checked": len(all_transactions),
            "fast_tagged": fast_tagged,
            "reembedded": reembedded,
            "llm_tagging_scheduled": len(untagged_ids),
        }

    return {
        "status": "complete",
        "transactions_checked": len(all_transactions),
        "fast_tagged": fast_tagged,
        "reembedded": reembedded,
        "llm_tagging_scheduled": 0,
    }


# ==================== DASHBOARD ENDPOINTS ====================


@app.get("/dashboard/overview")
async def get_dashboard_overview(year: int | None = None):
    """Get overall dashboard statistics."""
    from datetime import date as date_type

    # Filter by year if specified
    if year:
        start_date = date_type(year, 1, 1)
        end_date = date_type(year, 12, 31)
        all_transactions = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=10000)
    else:
        all_transactions = db.get_all_transactions(limit=10000)

    if not all_transactions:
        return {
            "total_transactions": 0,
            "total_spending": 0,
            "total_income": 0,
            "date_range": None,
            "categories_count": 0,
            "sources_count": 0,
            "year": year,
        }

    total_spending = sum(abs(t.amount) for t in all_transactions if t.amount < 0)
    total_income = sum(t.amount for t in all_transactions if t.amount > 0)
    dates = [t.date for t in all_transactions]
    categories = set(t.category.value if t.category else "Uncategorized" for t in all_transactions)
    sources = set(t.source.value for t in all_transactions)

    return {
        "total_transactions": len(all_transactions),
        "total_spending": round(total_spending, 2),
        "total_income": round(total_income, 2),
        "date_range": {
            "start": min(dates).isoformat(),
            "end": max(dates).isoformat(),
        },
        "categories_count": len(categories),
        "sources_count": len(sources),
        "year": year,
    }


@app.get("/dashboard/spending-by-category")
async def get_spending_by_category(year: int | None = None):
    """Get spending breakdown by category."""
    from datetime import date as date_type

    # Filter by year if specified
    if year:
        start_date = date_type(year, 1, 1)
        end_date = date_type(year, 12, 31)
        transactions = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=10000)
    else:
        transactions = db.get_all_transactions(limit=10000)

    # Group by category
    by_category: dict[str, float] = {}
    for t in transactions:
        if t.amount < 0:  # Only spending
            cat = t.category.value if t.category else "Uncategorized"
            by_category[cat] = by_category.get(cat, 0) + abs(t.amount)

    # Sort by amount descending
    sorted_categories = sorted(by_category.items(), key=lambda x: x[1], reverse=True)

    return {
        "data": [{"category": cat, "amount": round(amt, 2)} for cat, amt in sorted_categories],
        "total": round(sum(by_category.values()), 2),
    }


@app.get("/dashboard/monthly-spending")
async def get_monthly_spending(year: int | None = None):
    """Get monthly spending for trend analysis."""
    from collections import defaultdict

    transactions = db.get_all_transactions(limit=10000)

    # Group by year-month
    monthly: dict[str, dict] = defaultdict(lambda: {"spending": 0.0, "income": 0.0, "count": 0})

    for t in transactions:
        if year and t.date.year != year:
            continue
        month_key = t.date.strftime("%Y-%m")
        monthly[month_key]["count"] += 1
        if t.amount < 0:
            monthly[month_key]["spending"] += abs(t.amount)
        else:
            monthly[month_key]["income"] += t.amount

    # Sort by month
    sorted_months = sorted(monthly.items())

    return {
        "data": [
            {
                "month": month,
                "spending": round(data["spending"], 2),
                "income": round(data["income"], 2),
                "net": round(data["income"] - data["spending"], 2),
                "count": data["count"],
            }
            for month, data in sorted_months
        ]
    }


@app.get("/dashboard/monthly-by-category")
async def get_monthly_by_category(year: int | None = None):
    """Get monthly spending broken down by category."""
    from collections import defaultdict

    transactions = db.get_all_transactions(limit=10000)

    # Group by year-month and category
    monthly_cat: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for t in transactions:
        if year and t.date.year != year:
            continue
        if t.amount < 0:  # Only spending
            month_key = t.date.strftime("%Y-%m")
            cat = t.category.value if t.category else "Uncategorized"
            monthly_cat[month_key][cat] += abs(t.amount)

    # Get all categories
    all_categories = set()
    for cats in monthly_cat.values():
        all_categories.update(cats.keys())

    # Sort by month
    sorted_months = sorted(monthly_cat.items())

    return {
        "data": [
            {"month": month, **{cat: round(cats.get(cat, 0), 2) for cat in all_categories}}
            for month, cats in sorted_months
        ],
        "categories": sorted(all_categories),
    }


@app.get("/dashboard/year-comparison")
async def get_year_comparison():
    """Get year-over-year spending comparison."""
    from collections import defaultdict

    transactions = db.get_all_transactions(limit=10000)

    # Group by year
    yearly: dict[int, dict] = defaultdict(lambda: {"spending": 0.0, "income": 0.0, "count": 0})

    for t in transactions:
        year = t.date.year
        yearly[year]["count"] += 1
        if t.amount < 0:
            yearly[year]["spending"] += abs(t.amount)
        else:
            yearly[year]["income"] += t.amount

    # Sort by year
    sorted_years = sorted(yearly.items(), reverse=True)

    result = []
    for i, (year, data) in enumerate(sorted_years):
        entry = {
            "year": year,
            "spending": round(data["spending"], 2),
            "income": round(data["income"], 2),
            "count": data["count"],
        }
        # Calculate YoY change
        if i < len(sorted_years) - 1:
            prev_year_data = sorted_years[i + 1][1]
            if prev_year_data["spending"] > 0:
                change = ((data["spending"] - prev_year_data["spending"]) / prev_year_data["spending"]) * 100
                entry["yoy_change"] = round(change, 1)
        result.append(entry)

    return {"data": result}


@app.get("/dashboard/top-merchants")
async def get_top_merchants(
    limit: int = 10,
    year: int | None = None,
):
    """Get top merchants by spending."""
    import re
    from collections import defaultdict
    from datetime import date as date_type

    # Filter by year if specified
    if year:
        start_date = date_type(year, 1, 1)
        end_date = date_type(year, 12, 31)
        transactions = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=10000)
    else:
        transactions = db.get_all_transactions(limit=10000)

    # Group by merchant (simplified name)
    merchants: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})

    for t in transactions:
        if t.amount < 0:  # Only spending
            # Simplify merchant name (remove numbers, codes, etc.)
            name = t.description.upper()
            # Remove common suffixes/prefixes
            name = re.sub(r"\s*#\d+.*$", "", name)
            name = re.sub(r"\s*\d{5,}.*$", "", name)
            name = re.sub(r"^\s*(SQ\s*\*|TST\s*\*|PP\s*\*)", "", name)
            name = name.strip()[:30]  # Limit length

            if name:
                merchants[name]["amount"] += abs(t.amount)
                merchants[name]["count"] += 1

    # Sort by amount and get top N
    sorted_merchants = sorted(merchants.items(), key=lambda x: x[1]["amount"], reverse=True)[:limit]

    return {
        "data": [
            {"merchant": name, "amount": round(data["amount"], 2), "count": data["count"]}
            for name, data in sorted_merchants
        ]
    }


@app.get("/dashboard/spending-by-source")
async def get_spending_by_source(year: int | None = None):
    """Get spending breakdown by card/source."""
    from datetime import date as date_type

    # Filter by year if specified
    if year:
        start_date = date_type(year, 1, 1)
        end_date = date_type(year, 12, 31)
        transactions = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=10000)
    else:
        transactions = db.get_all_transactions(limit=10000)

    # Group by source
    by_source: dict[str, dict] = {}
    source_labels = {"chase_credit": "Chase", "amex": "Amex", "coinbase": "Coinbase"}

    for t in transactions:
        if t.amount < 0:  # Only spending
            src = t.source.value
            label = source_labels.get(src, src)
            if label not in by_source:
                by_source[label] = {"amount": 0.0, "count": 0}
            by_source[label]["amount"] += abs(t.amount)
            by_source[label]["count"] += 1

    return {
        "data": [
            {"source": src, "amount": round(data["amount"], 2), "count": data["count"]}
            for src, data in sorted(by_source.items(), key=lambda x: x[1]["amount"], reverse=True)
        ]
    }


@app.get("/dashboard/daily-spending")
async def get_daily_spending(days: int = 30, year: int | None = None):
    """Get daily spending for the last N days, or for a specific year."""
    from collections import defaultdict
    from datetime import date as date_type
    from datetime import timedelta

    if year:
        # Show daily spending for the specified year
        start_date = date_type(year, 1, 1)
        end_date = min(date_type(year, 12, 31), date_type.today())
    else:
        # Show last N days
        end_date = date_type.today()
        start_date = end_date - timedelta(days=days)

    transactions = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=10000)

    # Group by day
    daily: dict[str, float] = defaultdict(float)

    for t in transactions:
        if t.amount < 0:
            day_key = t.date.isoformat()
            daily[day_key] += abs(t.amount)

    # Fill in missing days with 0
    result = []
    current = start_date
    while current <= end_date:
        day_key = current.isoformat()
        result.append(
            {
                "date": day_key,
                "amount": round(daily.get(day_key, 0), 2),
            }
        )
        current += timedelta(days=1)

    return {"data": result}


# ==================== INSIGHTS ENDPOINTS ====================


@app.get("/insights")
async def get_insights(year: int | None = None):
    """
    Get auto-generated spending insights.

    Returns a comprehensive insights report with spending patterns,
    anomalies, subscription analysis, and actionable tips.
    """
    from backend.services.insights import generate_insights

    report = generate_insights(year=year)
    return {
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "total_spending": round(report.total_spending, 2),
        "total_transactions": report.total_transactions,
        "insights": [
            {
                "type": i.type,
                "title": i.title,
                "description": i.description,
                "amount": round(i.amount, 2) if i.amount else None,
                "percent_change": round(i.percent_change, 1) if i.percent_change else None,
                "category": i.category,
                "merchant": i.merchant,
                "severity": i.severity,
            }
            for i in report.insights
        ],
        "top_categories": [{"category": cat, "amount": round(amt, 2)} for cat, amt in report.top_categories],
        "monthly_trend": [{"month": month, "amount": round(amt, 2)} for month, amt in report.monthly_trend],
    }


@app.get("/insights/monthly")
async def get_monthly_insights(year: int, month: int):
    """
    Get monthly spending insights compared to previous month.

    Returns detailed analysis for a specific month including
    month-over-month comparisons and specific recommendations.
    """
    from backend.services.insights import generate_monthly_insights

    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    report = generate_monthly_insights(year, month)
    return {
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "total_spending": round(report.total_spending, 2),
        "total_transactions": report.total_transactions,
        "insights": [
            {
                "type": i.type,
                "title": i.title,
                "description": i.description,
                "amount": round(i.amount, 2) if i.amount else None,
                "percent_change": round(i.percent_change, 1) if i.percent_change else None,
                "category": i.category,
                "merchant": i.merchant,
                "severity": i.severity,
            }
            for i in report.insights
        ],
        "top_categories": [{"category": cat, "amount": round(amt, 2)} for cat, amt in report.top_categories],
        "monthly_trend": [{"month": month, "amount": round(amt, 2)} for month, amt in report.monthly_trend],
    }


@app.get("/insights/quick-stats")
async def get_quick_stats():
    """
    Get quick stats for dashboard display.

    Returns high-level spending stats for the current period
    and comparison to previous period.
    """
    from backend.services.insights import get_quick_stats

    stats = get_quick_stats()
    return {
        "current_month_spending": round(stats["current_month_spending"], 2),
        "previous_month_spending": round(stats["previous_month_spending"], 2),
        "month_change_percent": round(stats["month_change_percent"], 1) if stats["month_change_percent"] else None,
        "ytd_spending": round(stats["ytd_spending"], 2),
        "previous_ytd_spending": round(stats["previous_ytd_spending"], 2),
        "ytd_change_percent": round(stats["ytd_change_percent"], 1) if stats["ytd_change_percent"] else None,
        "top_category_this_month": stats["top_category_this_month"],
        "subscription_total": round(stats["subscription_total"], 2),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.dev_mode,
    )
