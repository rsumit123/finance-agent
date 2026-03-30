"""Subscription/recurring payment detection service."""

import re
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import Expense
from ..schemas import Subscription


# Known subscription/merchant names to normalize
MERCHANT_ALIASES = {
    "netflix": "Netflix",
    "hotstar": "Hotstar",
    "spotify": "Spotify",
    "youtube": "YouTube Premium",
    "google play": "Google Play",
    "amazon prime": "Amazon Prime",
    "prime video": "Amazon Prime",
    "jio": "Jio Recharge",
    "airtel": "Airtel Recharge",
    "claude": "Claude AI",
    "openai": "OpenAI",
    "google cloud": "Google Cloud",
    "blinkit": "Blinkit",
    "swiggy": "Swiggy",
    "zomato": "Zomato",
}


def _normalize_merchant(description: str) -> str:
    """Extract a normalized merchant name from a transaction description."""
    desc_lower = description.lower().strip()

    # Check known aliases first
    for keyword, name in MERCHANT_ALIASES.items():
        if keyword in desc_lower:
            return name

    # Strip common suffixes/noise
    desc_lower = re.sub(r"\b(di si|mumbai|bangalore|gurgaon|delhi|chennai|hyderabad)\b", "", desc_lower)
    desc_lower = re.sub(r"\b(ref#?\s*\d+)\b", "", desc_lower)
    desc_lower = re.sub(r"\(.*?\)", "", desc_lower)  # remove parenthetical
    desc_lower = re.sub(r"[^a-z0-9\s]", "", desc_lower)
    desc_lower = re.sub(r"\s+", " ", desc_lower).strip()

    # Take first 3 significant words as merchant identifier
    words = [w for w in desc_lower.split() if len(w) > 2]
    return " ".join(words[:3]).title() if words else desc_lower.title()


def detect_subscriptions(db: Session, user_id: int) -> list[Subscription]:
    """Detect recurring/subscription payments from expense history.

    A subscription is defined as:
    - Same merchant appearing in 2+ different months
    - Amounts within 20% variance of each other

    Args:
        user_id: The ID of the user whose expenses to analyze.
    """
    # Get all expenses from the last 6 months
    cutoff = date.today() - timedelta(days=180)
    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == user_id)
        .filter(Expense.date >= cutoff)
        .order_by(Expense.date.desc())
        .all()
    )

    if not expenses:
        return []

    # Group by normalized merchant name
    merchant_groups: dict[str, list[Expense]] = defaultdict(list)
    for exp in expenses:
        if not exp.description:
            continue
        merchant = _normalize_merchant(exp.description)
        if merchant:
            merchant_groups[merchant].append(exp)

    subscriptions = []

    for merchant, txns in merchant_groups.items():
        if len(txns) < 2:
            continue

        # Check if they span multiple months
        months = set((t.date.year, t.date.month) for t in txns)
        if len(months) < 2:
            continue

        # Check amount consistency (within 20% of median)
        amounts = sorted(t.amount for t in txns)
        median_amount = amounts[len(amounts) // 2]
        consistent = all(
            abs(a - median_amount) / median_amount <= 0.20
            for a in amounts
        ) if median_amount > 0 else False

        if not consistent:
            continue

        # This looks like a subscription
        avg_amount = sum(amounts) / len(amounts)
        total_spent = sum(amounts)
        last_txn = max(txns, key=lambda t: t.date)

        # Estimate next expected date (roughly 30 days after last)
        last_date = last_txn.date.date() if hasattr(last_txn.date, 'date') else last_txn.date
        next_expected = last_date + timedelta(days=30)

        subscriptions.append(
            Subscription(
                name=merchant,
                amount=round(avg_amount, 2),
                frequency="monthly",
                last_charged=last_date,
                next_expected=next_expected if next_expected > date.today() else None,
                total_spent=round(total_spent, 2),
                occurrence_count=len(txns),
            )
        )

    # Sort by amount descending
    subscriptions.sort(key=lambda s: s.amount, reverse=True)
    return subscriptions
