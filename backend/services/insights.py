"""Spending insights service for auto-generated financial analysis."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from backend.db.sqlite import db
from backend.models import Transaction, TransactionCategory


@dataclass
class SpendingInsight:
    """A single spending insight."""

    type: str  # "increase", "decrease", "anomaly", "subscription", "merchant", "tip"
    title: str
    description: str
    amount: float | None = None
    percent_change: float | None = None
    category: str | None = None
    merchant: str | None = None
    severity: str = "info"  # "info", "warning", "positive"


@dataclass
class InsightsReport:
    """Collection of spending insights for a period."""

    period_start: date
    period_end: date
    total_spending: float
    total_transactions: int
    insights: list[SpendingInsight]
    top_categories: list[tuple[str, float]] = None  # type: ignore[assignment]
    monthly_trend: list[tuple[str, float]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.top_categories is None:
            self.top_categories = []
        if self.monthly_trend is None:
            self.monthly_trend = []


def generate_insights(year: int | None = None, compare_to_previous: bool = True) -> InsightsReport:
    """
    Generate spending insights for a given period.

    Args:
        year: Year to analyze. If None, analyzes current year to date.
        compare_to_previous: Whether to compare to the previous period.

    Returns:
        InsightsReport with all generated insights.
    """
    today = date.today()

    # Determine analysis period
    if year:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31) if year < today.year else today
    else:
        start_date = date(today.year, 1, 1)
        end_date = today

    # Get transactions for the period
    transactions = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=10000)

    if not transactions:
        return InsightsReport(
            period_start=start_date,
            period_end=end_date,
            total_spending=0,
            total_transactions=0,
            insights=[],
        )

    insights: list[SpendingInsight] = []

    # Calculate totals
    total_spending = sum(abs(t.amount) for t in transactions if t.amount < 0)
    total_transactions = len([t for t in transactions if t.amount < 0])

    # Generate various insights
    insights.extend(_compare_periods(transactions, start_date, end_date, compare_to_previous))
    insights.extend(_analyze_category_changes(transactions, start_date, end_date, compare_to_previous))
    insights.extend(_find_unusual_spending(transactions))
    insights.extend(_analyze_subscriptions(transactions))
    insights.extend(_find_top_merchant_changes(transactions, start_date, end_date, compare_to_previous))
    insights.extend(_generate_spending_tips(transactions, total_spending))

    # Sort insights by severity (warnings first, then info, then positive)
    severity_order = {"warning": 0, "info": 1, "positive": 2}
    insights.sort(key=lambda x: severity_order.get(x.severity, 1))

    return InsightsReport(
        period_start=start_date,
        period_end=end_date,
        total_spending=total_spending,
        total_transactions=total_transactions,
        insights=insights[:15],  # Limit to top 15 insights
    )


def generate_monthly_insights(year: int, month: int) -> InsightsReport:
    """Generate insights for a specific month compared to previous month."""
    # Current month period
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)

    # Get current month transactions
    current_txns = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=5000)

    # Previous month period
    if month == 1:
        prev_start = date(year - 1, 12, 1)
        prev_end = date(year - 1, 12, 31)
    else:
        prev_start = date(year, month - 1, 1)
        prev_end = start_date - timedelta(days=1)

    prev_txns = db.get_all_transactions(start_date=prev_start, end_date=prev_end, limit=5000)

    insights: list[SpendingInsight] = []

    if not current_txns:
        return InsightsReport(
            period_start=start_date,
            period_end=end_date,
            total_spending=0,
            total_transactions=0,
            insights=[],
        )

    total_spending = sum(abs(t.amount) for t in current_txns if t.amount < 0)
    total_transactions = len([t for t in current_txns if t.amount < 0])

    # Compare total spending
    if prev_txns:
        prev_spending = sum(abs(t.amount) for t in prev_txns if t.amount < 0)
        if prev_spending > 0:
            change = total_spending - prev_spending
            pct_change = (change / prev_spending) * 100

            if abs(pct_change) >= 10:
                if change > 0:
                    insights.append(
                        SpendingInsight(
                            type="increase",
                            title="Spending Increased",
                            description=f"You spent ${change:.2f} more this month ({pct_change:+.0f}%) compared to last month.",
                            amount=change,
                            percent_change=pct_change,
                            severity="warning" if pct_change > 25 else "info",
                        )
                    )
                else:
                    insights.append(
                        SpendingInsight(
                            type="decrease",
                            title="Spending Decreased",
                            description=f"You spent ${abs(change):.2f} less this month ({pct_change:.0f}%) compared to last month.",
                            amount=abs(change),
                            percent_change=pct_change,
                            severity="positive",
                        )
                    )

    # Category-level insights for the month
    insights.extend(_compare_category_months(current_txns, prev_txns))

    # Find unusual individual transactions
    insights.extend(_find_unusual_spending(current_txns))

    # Limit insights
    return InsightsReport(
        period_start=start_date,
        period_end=end_date,
        total_spending=total_spending,
        total_transactions=total_transactions,
        insights=insights[:10],
    )


def _compare_periods(
    transactions: list[Transaction], start_date: date, end_date: date, compare_to_previous: bool
) -> list[SpendingInsight]:
    """Compare current period to previous period."""
    insights = []

    if not compare_to_previous:
        return insights

    # Calculate previous period (same length)
    period_length = (end_date - start_date).days
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length)

    prev_txns = db.get_all_transactions(start_date=prev_start, end_date=prev_end, limit=10000)

    if not prev_txns:
        return insights

    current_spending = sum(abs(t.amount) for t in transactions if t.amount < 0)
    prev_spending = sum(abs(t.amount) for t in prev_txns if t.amount < 0)

    if prev_spending > 0:
        change = current_spending - prev_spending
        pct_change = (change / prev_spending) * 100

        if abs(pct_change) >= 15:
            if change > 0:
                insights.append(
                    SpendingInsight(
                        type="increase",
                        title="Overall Spending Up",
                        description=f"Your total spending increased by ${change:.2f} ({pct_change:+.0f}%) compared to the previous period.",
                        amount=change,
                        percent_change=pct_change,
                        severity="warning" if pct_change > 30 else "info",
                    )
                )
            else:
                insights.append(
                    SpendingInsight(
                        type="decrease",
                        title="Overall Spending Down",
                        description=f"Your total spending decreased by ${abs(change):.2f} ({pct_change:.0f}%) compared to the previous period.",
                        amount=abs(change),
                        percent_change=pct_change,
                        severity="positive",
                    )
                )

    return insights


def _analyze_category_changes(
    transactions: list[Transaction], start_date: date, end_date: date, compare_to_previous: bool
) -> list[SpendingInsight]:
    """Analyze spending changes by category."""
    insights = []

    if not compare_to_previous:
        return insights

    # Group current transactions by category
    current_by_cat: dict[str, float] = defaultdict(float)
    for t in transactions:
        if t.amount < 0 and t.category:
            current_by_cat[t.category.value] += abs(t.amount)

    # Get previous period
    period_length = (end_date - start_date).days
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length)

    prev_txns = db.get_all_transactions(start_date=prev_start, end_date=prev_end, limit=10000)

    prev_by_cat: dict[str, float] = defaultdict(float)
    for t in prev_txns:
        if t.amount < 0 and t.category:
            prev_by_cat[t.category.value] += abs(t.amount)

    # Find significant changes
    for cat, current_amt in current_by_cat.items():
        prev_amt = prev_by_cat.get(cat, 0)

        if prev_amt > 50:  # Only compare if previous had significant spending
            change = current_amt - prev_amt
            pct_change = (change / prev_amt) * 100

            if pct_change >= 30 and change >= 50:
                insights.append(
                    SpendingInsight(
                        type="increase",
                        title=f"{cat} Spending Up",
                        description=f"You spent {pct_change:.0f}% more on {cat} (${change:.2f} increase).",
                        amount=change,
                        percent_change=pct_change,
                        category=cat,
                        severity="warning" if pct_change > 50 else "info",
                    )
                )
            elif pct_change <= -25 and abs(change) >= 30:
                insights.append(
                    SpendingInsight(
                        type="decrease",
                        title=f"{cat} Spending Down",
                        description=f"You spent {abs(pct_change):.0f}% less on {cat} (${abs(change):.2f} saved).",
                        amount=abs(change),
                        percent_change=pct_change,
                        category=cat,
                        severity="positive",
                    )
                )

    return insights[:5]  # Limit category insights


def _compare_category_months(current_txns: list[Transaction], prev_txns: list[Transaction]) -> list[SpendingInsight]:
    """Compare categories between two months."""
    insights = []

    # Group by category
    current_by_cat: dict[str, float] = defaultdict(float)
    for t in current_txns:
        if t.amount < 0 and t.category:
            current_by_cat[t.category.value] += abs(t.amount)

    prev_by_cat: dict[str, float] = defaultdict(float)
    for t in prev_txns:
        if t.amount < 0 and t.category:
            prev_by_cat[t.category.value] += abs(t.amount)

    # Find biggest changes
    changes = []
    for cat, current_amt in current_by_cat.items():
        prev_amt = prev_by_cat.get(cat, 0)
        if prev_amt > 20:
            change = current_amt - prev_amt
            pct_change = (change / prev_amt) * 100
            changes.append((cat, change, pct_change))

    # Sort by absolute percentage change
    changes.sort(key=lambda x: abs(x[2]), reverse=True)

    for cat, change, pct_change in changes[:3]:
        if abs(pct_change) >= 25:
            if change > 0:
                insights.append(
                    SpendingInsight(
                        type="increase",
                        title=f"{cat} Increased",
                        description=f"{cat} spending up {pct_change:.0f}% this month.",
                        amount=change,
                        percent_change=pct_change,
                        category=cat,
                        severity="warning" if pct_change > 40 else "info",
                    )
                )
            else:
                insights.append(
                    SpendingInsight(
                        type="decrease",
                        title=f"{cat} Decreased",
                        description=f"{cat} spending down {abs(pct_change):.0f}% this month.",
                        amount=abs(change),
                        percent_change=pct_change,
                        category=cat,
                        severity="positive",
                    )
                )

    return insights


def _find_unusual_spending(transactions: list[Transaction]) -> list[SpendingInsight]:
    """Find unusually large individual transactions."""
    insights = []

    # Only look at expenses
    expenses = [t for t in transactions if t.amount < 0]
    if len(expenses) < 10:
        return insights

    amounts = [abs(t.amount) for t in expenses]
    avg = sum(amounts) / len(amounts)
    threshold = avg * 3  # 3x average is unusual

    # Find transactions above threshold
    unusual = [(t, abs(t.amount)) for t in expenses if abs(t.amount) > threshold and abs(t.amount) > 100]
    unusual.sort(key=lambda x: x[1], reverse=True)

    for txn, amount in unusual[:3]:
        insights.append(
            SpendingInsight(
                type="anomaly",
                title="Large Transaction",
                description=f"${amount:.2f} at {txn.description[:30]} on {txn.date.strftime('%b %d')} - {(amount / avg):.1f}x your average transaction.",
                amount=amount,
                merchant=txn.description[:30],
                severity="info",
            )
        )

    return insights


def _analyze_subscriptions(transactions: list[Transaction]) -> list[SpendingInsight]:
    """Analyze subscription spending and detect potential duplicates or price changes."""
    insights = []

    # Get subscription transactions
    subs = [t for t in transactions if t.category == TransactionCategory.SUBSCRIPTIONS and t.amount < 0]

    if not subs:
        return insights

    # Group by merchant (simplified)
    merchant_txns: dict[str, list[Transaction]] = defaultdict(list)
    for t in subs:
        # Extract first meaningful word as merchant name
        desc = t.description.lower()
        for word in desc.split():
            if len(word) > 3 and word.isalpha():
                merchant_txns[word].append(t)
                break

    # Analyze each merchant
    total_monthly = 0
    for merchant, txns in merchant_txns.items():
        if len(txns) >= 2:
            amounts = [abs(t.amount) for t in txns]
            # Check for price changes
            if len(set(amounts)) > 1:
                min_amt, max_amt = min(amounts), max(amounts)
                if max_amt > min_amt * 1.1:  # 10% price increase
                    insights.append(
                        SpendingInsight(
                            type="subscription",
                            title=f"Price Change: {merchant.title()}",
                            description=f"Your {merchant.title()} subscription changed from ${min_amt:.2f} to ${max_amt:.2f}.",
                            amount=max_amt - min_amt,
                            percent_change=((max_amt - min_amt) / min_amt) * 100,
                            merchant=merchant.title(),
                            severity="info",
                        )
                    )

        # Estimate monthly cost
        total_monthly += sum(abs(t.amount) for t in txns) / max(1, len(set(t.date.month for t in txns)))

    if total_monthly > 100:
        insights.append(
            SpendingInsight(
                type="subscription",
                title="Subscription Summary",
                description=f"You're spending approximately ${total_monthly:.2f}/month on subscriptions.",
                amount=total_monthly,
                severity="info",
            )
        )

    return insights[:3]


def _find_top_merchant_changes(
    transactions: list[Transaction], start_date: date, end_date: date, compare_to_previous: bool
) -> list[SpendingInsight]:
    """Find merchants where spending changed significantly."""
    insights = []

    if not compare_to_previous:
        return insights

    # Group current by merchant (simplified)
    current_merchants: dict[str, float] = defaultdict(float)
    for t in transactions:
        if t.amount < 0:
            # Use first word of description as merchant
            merchant = t.description.split()[0].lower() if t.description else "unknown"
            current_merchants[merchant] += abs(t.amount)

    # Get previous period
    period_length = (end_date - start_date).days
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length)

    prev_txns = db.get_all_transactions(start_date=prev_start, end_date=prev_end, limit=10000)

    prev_merchants: dict[str, float] = defaultdict(float)
    for t in prev_txns:
        if t.amount < 0:
            merchant = t.description.split()[0].lower() if t.description else "unknown"
            prev_merchants[merchant] += abs(t.amount)

    # Find biggest changes
    changes = []
    for merchant, current_amt in current_merchants.items():
        prev_amt = prev_merchants.get(merchant, 0)
        if prev_amt > 50:
            change = current_amt - prev_amt
            pct_change = (change / prev_amt) * 100
            if abs(pct_change) >= 40 and abs(change) >= 30:
                changes.append((merchant, change, pct_change))

    # Sort and take top changes
    changes.sort(key=lambda x: abs(x[2]), reverse=True)

    for merchant, change, pct_change in changes[:2]:
        merchant_display = merchant.title()[:15]
        if change > 0:
            insights.append(
                SpendingInsight(
                    type="merchant",
                    title=f"More at {merchant_display}",
                    description=f"You spent {pct_change:.0f}% more at {merchant_display} (+${change:.2f}).",
                    amount=change,
                    percent_change=pct_change,
                    merchant=merchant_display,
                    severity="info",
                )
            )
        else:
            insights.append(
                SpendingInsight(
                    type="merchant",
                    title=f"Less at {merchant_display}",
                    description=f"You spent {abs(pct_change):.0f}% less at {merchant_display} (-${abs(change):.2f}).",
                    amount=abs(change),
                    percent_change=pct_change,
                    merchant=merchant_display,
                    severity="positive",
                )
            )

    return insights


def _generate_spending_tips(transactions: list[Transaction], total_spending: float) -> list[SpendingInsight]:
    """Generate actionable spending tips based on patterns."""
    insights = []

    if total_spending == 0:
        return insights

    # Calculate category percentages
    by_cat: dict[str, float] = defaultdict(float)
    for t in transactions:
        if t.amount < 0 and t.category:
            by_cat[t.category.value] += abs(t.amount)

    # Check Food & Dining percentage
    food_pct = (by_cat.get("Food & Dining", 0) / total_spending) * 100 if total_spending > 0 else 0
    if food_pct > 20:
        insights.append(
            SpendingInsight(
                type="tip",
                title="Food Spending High",
                description=f"Food & Dining is {food_pct:.0f}% of your spending. Consider cooking more at home or meal prepping.",
                amount=by_cat.get("Food & Dining", 0),
                category="Food & Dining",
                severity="info",
            )
        )

    # Check Subscriptions
    sub_amt = by_cat.get("Subscriptions", 0)
    if sub_amt > 150:
        insights.append(
            SpendingInsight(
                type="tip",
                title="Review Subscriptions",
                description=f"You're spending ${sub_amt:.2f} on subscriptions. Consider auditing services you might not be using.",
                amount=sub_amt,
                category="Subscriptions",
                severity="info",
            )
        )

    # Check Shopping
    shopping_pct = (by_cat.get("Shopping", 0) / total_spending) * 100 if total_spending > 0 else 0
    if shopping_pct > 25:
        insights.append(
            SpendingInsight(
                type="tip",
                title="Shopping Spending High",
                description=f"Shopping is {shopping_pct:.0f}% of your spending. Try a 24-hour rule before non-essential purchases.",
                amount=by_cat.get("Shopping", 0),
                category="Shopping",
                severity="info",
            )
        )

    return insights[:2]


def get_quick_stats(year: int | None = None) -> dict:
    """Get quick spending statistics for the dashboard."""
    today = date.today()

    if year:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31) if year < today.year else today
    else:
        start_date = date(today.year, 1, 1)
        end_date = today

    transactions = db.get_all_transactions(start_date=start_date, end_date=end_date, limit=10000)

    if not transactions:
        return {
            "total_spending": 0,
            "total_income": 0,
            "transaction_count": 0,
            "avg_transaction": 0,
            "top_category": None,
            "top_merchant": None,
        }

    expenses = [t for t in transactions if t.amount < 0]
    income = [t for t in transactions if t.amount > 0]

    total_spending = sum(abs(t.amount) for t in expenses)
    total_income = sum(t.amount for t in income)

    # Find top category
    by_cat: dict[str, float] = defaultdict(float)
    for t in expenses:
        if t.category:
            by_cat[t.category.value] += abs(t.amount)

    top_category = max(by_cat.items(), key=lambda x: x[1])[0] if by_cat else None

    # Find top merchant
    by_merchant: dict[str, float] = defaultdict(float)
    for t in expenses:
        merchant = t.description.split()[0] if t.description else "Unknown"
        by_merchant[merchant] += abs(t.amount)

    top_merchant = max(by_merchant.items(), key=lambda x: x[1])[0] if by_merchant else None

    return {
        "total_spending": total_spending,
        "total_income": total_income,
        "transaction_count": len(expenses),
        "avg_transaction": total_spending / len(expenses) if expenses else 0,
        "top_category": top_category,
        "top_merchant": top_merchant,
    }
