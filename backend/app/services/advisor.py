"""Purchase advisor — analyzes whether you can afford a purchase right now."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..schemas import PurchaseVerdict
from .tracker import (
    get_budget,
    get_budget_status,
    get_category_limits,
    get_current_month_range,
    get_current_week_range,
    get_period_total,
    get_period_total_by_category,
)


def analyze_purchase(
    db: Session,
    amount: float,
    category: str | None = None,
) -> PurchaseVerdict:
    """Analyze whether a purchase is affordable given current spending."""
    budget = get_budget(db)
    reasons = []
    warnings = []
    can_buy = True

    if not budget:
        return PurchaseVerdict(
            can_buy=True,
            amount=amount,
            reasons=["No budget set — cannot evaluate spending limits."],
            warnings=["Set a budget first to get proper purchase advice."],
            weekly_remaining_after=0,
            monthly_remaining_after=0,
            suggestion="Set up a budget first to get meaningful purchase advice.",
        )

    week_start, week_end = get_current_week_range()
    month_start, month_end = get_current_month_range()

    week_spent = get_period_total(db, week_start, week_end)
    month_spent = get_period_total(db, month_start, month_end)

    week_remaining = budget.weekly_limit - week_spent
    month_remaining = budget.monthly_limit - month_spent

    week_after = week_remaining - amount
    month_after = month_remaining - amount

    # Weekly budget check
    if amount > week_remaining:
        can_buy = False
        reasons.append(
            f"Exceeds weekly budget: you have ₹{week_remaining:,.0f} left this week, "
            f"but the purchase costs ₹{amount:,.0f}."
        )
    elif week_remaining > 0 and amount > week_remaining * 0.8:
        warnings.append(
            f"This will use {amount / week_remaining * 100:.0f}% of your remaining "
            f"weekly budget (₹{week_remaining:,.0f} left)."
        )

    # Monthly budget check
    if amount > month_remaining:
        can_buy = False
        reasons.append(
            f"Exceeds monthly budget: you have ₹{month_remaining:,.0f} left this month, "
            f"but the purchase costs ₹{amount:,.0f}."
        )
    elif month_remaining > 0 and amount > month_remaining * 0.5:
        warnings.append(
            f"This will use {amount / month_remaining * 100:.0f}% of your remaining "
            f"monthly budget (₹{month_remaining:,.0f} left)."
        )

    # Category limit check
    if category:
        cat_limits = get_category_limits(db, budget.id)
        cat_limit_map = {cl.category: cl.limit_amount for cl in cat_limits}
        if category in cat_limit_map:
            cat_limit = cat_limit_map[category]
            month_by_cat = get_period_total_by_category(db, month_start, month_end)
            cat_spent = month_by_cat.get(category, 0.0)
            cat_remaining = cat_limit - cat_spent
            if amount > cat_remaining:
                can_buy = False
                reasons.append(
                    f"Exceeds '{category}' category budget: ₹{cat_remaining:,.0f} "
                    f"remaining out of ₹{cat_limit:,.0f}."
                )

    # Spending velocity warning
    today = date.today()
    days_into_month = today.day
    if days_into_month > 0 and month_spent > 0:
        daily_avg = month_spent / days_into_month
        projected = daily_avg * 30
        if projected > budget.monthly_limit * 0.9:
            warnings.append(
                f"Spending trend alert: at ₹{daily_avg:,.0f}/day, you're projected "
                f"to spend ₹{projected:,.0f} this month (limit: ₹{budget.monthly_limit:,.0f})."
            )

    # Build suggestion
    if can_buy and not warnings:
        suggestion = "Looks good! This purchase fits comfortably within your budget."
    elif can_buy and warnings:
        suggestion = (
            "You can make this purchase, but be cautious — you're approaching "
            "your spending limits. Consider if this is a need or a want."
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
