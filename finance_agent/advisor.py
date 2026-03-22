"""Purchase advisor — analyzes whether you can afford a purchase right now."""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from .models import Category
from .storage import DEFAULT_DATA_FILE, load_budget
from .tracker import (
    get_current_month_expenses,
    get_current_week_expenses,
    get_expenses_for_period,
    summarize_expenses,
)


@dataclass
class PurchaseVerdict:
    can_buy: bool
    amount: float
    reasons: list[str]
    warnings: list[str]
    weekly_remaining_after: float
    monthly_remaining_after: float
    suggestion: str


def analyze_purchase(
    amount: float,
    category: Optional[str] = None,
    data_file: Path = DEFAULT_DATA_FILE,
) -> PurchaseVerdict:
    """Analyze whether a purchase is affordable given current spending."""
    budget = load_budget(data_file)
    reasons = []
    warnings = []
    can_buy = True

    if not budget:
        return PurchaseVerdict(
            can_buy=True,
            amount=amount,
            reasons=["No budget set — cannot evaluate limits."],
            warnings=["Set a budget with `finance budget set` to get proper advice."],
            weekly_remaining_after=0,
            monthly_remaining_after=0,
            suggestion="Set up a budget first to get meaningful purchase advice.",
        )

    week_expenses = get_current_week_expenses(data_file)
    month_expenses = get_current_month_expenses(data_file)

    week_total = sum(e.amount for e in week_expenses)
    month_total = sum(e.amount for e in month_expenses)

    week_remaining = budget.weekly_limit - week_total
    month_remaining = budget.monthly_limit - month_total

    week_after = week_remaining - amount
    month_after = month_remaining - amount

    # Check weekly budget
    if amount > week_remaining:
        can_buy = False
        reasons.append(
            f"Exceeds weekly budget: you have ₹{week_remaining:,.0f} left this week, "
            f"but the purchase costs ₹{amount:,.0f}."
        )
    elif amount > week_remaining * 0.8:
        warnings.append(
            f"This will use {amount / week_remaining * 100:.0f}% of your remaining "
            f"weekly budget (₹{week_remaining:,.0f} left)."
        )

    # Check monthly budget
    if amount > month_remaining:
        can_buy = False
        reasons.append(
            f"Exceeds monthly budget: you have ₹{month_remaining:,.0f} left this month, "
            f"but the purchase costs ₹{amount:,.0f}."
        )
    elif amount > month_remaining * 0.5:
        warnings.append(
            f"This will use {amount / month_remaining * 100:.0f}% of your remaining "
            f"monthly budget (₹{month_remaining:,.0f} left)."
        )

    # Check category limit if specified
    if category and category in budget.category_limits:
        cat_limit = budget.category_limits[category]
        cat_spent = sum(
            e.amount for e in month_expenses if e.category.value == category
        )
        cat_remaining = cat_limit - cat_spent
        if amount > cat_remaining:
            can_buy = False
            reasons.append(
                f"Exceeds '{category}' category budget: ₹{cat_remaining:,.0f} "
                f"remaining out of ₹{cat_limit:,.0f}."
            )

    # Spending velocity check — are you spending faster than usual?
    today = date.today()
    days_into_month = today.day
    if days_into_month > 0:
        daily_avg = month_total / days_into_month
        days_in_month = 30
        projected_monthly = daily_avg * days_in_month
        if projected_monthly > budget.monthly_limit * 0.9:
            warnings.append(
                f"Spending trend alert: at your current pace (₹{daily_avg:,.0f}/day), "
                f"you're projected to spend ₹{projected_monthly:,.0f} this month "
                f"(limit: ₹{budget.monthly_limit:,.0f})."
            )

    # Build suggestion
    if can_buy and not warnings:
        suggestion = "Looks good! This purchase fits comfortably within your budget."
    elif can_buy and warnings:
        suggestion = (
            "You can make this purchase, but be cautious — you're getting close "
            "to your limits. Consider if this is a need or a want."
        )
    else:
        if week_remaining > 0 and amount > week_remaining:
            days_to_wait = 7 - today.weekday()
            suggestion = (
                f"Consider waiting {days_to_wait} days until next week when your "
                f"weekly budget resets."
            )
        else:
            suggestion = (
                "This purchase would break your budget. Consider postponing it "
                "or finding a cheaper alternative."
            )

    if not reasons and can_buy:
        reasons.append("Purchase fits within both weekly and monthly budgets.")

    return PurchaseVerdict(
        can_buy=can_buy,
        amount=amount,
        reasons=reasons,
        warnings=warnings,
        weekly_remaining_after=max(week_after, 0),
        monthly_remaining_after=max(month_after, 0),
        suggestion=suggestion,
    )
