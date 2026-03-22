"""Expense tracking and summarization logic."""

from datetime import date, datetime, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .models import Budget, Category, Expense, PaymentMethod
from .storage import (
    DEFAULT_DATA_FILE,
    delete_expense,
    load_budget,
    load_expenses,
    save_budget,
    save_expense,
)


def add_expense(
    amount: float,
    category: str,
    payment_method: str,
    description: str,
    expense_date: Optional[str] = None,
    data_file: Path = DEFAULT_DATA_FILE,
) -> Expense:
    expense = Expense(
        amount=amount,
        category=Category(category),
        payment_method=PaymentMethod(payment_method),
        description=description,
        date=expense_date or date.today().isoformat(),
    )
    save_expense(expense, data_file)
    return expense


def remove_expense(expense_id: str, data_file: Path = DEFAULT_DATA_FILE) -> bool:
    return delete_expense(expense_id, data_file)


def set_budget(
    monthly_limit: float,
    weekly_limit: float,
    category_limits: Optional[dict[str, float]] = None,
    data_file: Path = DEFAULT_DATA_FILE,
) -> Budget:
    budget = Budget(
        monthly_limit=monthly_limit,
        weekly_limit=weekly_limit,
        category_limits=category_limits or {},
    )
    save_budget(budget, data_file)
    return budget


def get_expenses_for_period(
    start_date: date,
    end_date: date,
    data_file: Path = DEFAULT_DATA_FILE,
) -> list[Expense]:
    expenses = load_expenses(data_file)
    return [
        e
        for e in expenses
        if start_date <= date.fromisoformat(e.date) <= end_date
    ]


def get_current_week_expenses(data_file: Path = DEFAULT_DATA_FILE) -> list[Expense]:
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    return get_expenses_for_period(start_of_week, today, data_file)


def get_current_month_expenses(data_file: Path = DEFAULT_DATA_FILE) -> list[Expense]:
    today = date.today()
    start_of_month = today.replace(day=1)
    return get_expenses_for_period(start_of_month, today, data_file)


def summarize_expenses(expenses: list[Expense]) -> dict:
    total = sum(e.amount for e in expenses)

    by_category = defaultdict(float)
    for e in expenses:
        by_category[e.category.value] += e.amount

    by_payment = defaultdict(float)
    for e in expenses:
        by_payment[e.payment_method.value] += e.amount

    return {
        "total": total,
        "count": len(expenses),
        "by_category": dict(by_category),
        "by_payment_method": dict(by_payment),
    }


def get_budget_status(data_file: Path = DEFAULT_DATA_FILE) -> Optional[dict]:
    budget = load_budget(data_file)
    if not budget:
        return None

    week_expenses = get_current_week_expenses(data_file)
    month_expenses = get_current_month_expenses(data_file)

    week_total = sum(e.amount for e in week_expenses)
    month_total = sum(e.amount for e in month_expenses)

    week_remaining = budget.weekly_limit - week_total
    month_remaining = budget.monthly_limit - month_total

    category_status = {}
    month_by_cat = defaultdict(float)
    for e in month_expenses:
        month_by_cat[e.category.value] += e.amount

    for cat, limit in budget.category_limits.items():
        spent = month_by_cat.get(cat, 0.0)
        category_status[cat] = {
            "limit": limit,
            "spent": spent,
            "remaining": limit - spent,
            "percent_used": round((spent / limit) * 100, 1) if limit > 0 else 0,
        }

    return {
        "weekly": {
            "limit": budget.weekly_limit,
            "spent": week_total,
            "remaining": week_remaining,
            "percent_used": round((week_total / budget.weekly_limit) * 100, 1)
            if budget.weekly_limit > 0
            else 0,
        },
        "monthly": {
            "limit": budget.monthly_limit,
            "spent": month_total,
            "remaining": month_remaining,
            "percent_used": round((month_total / budget.monthly_limit) * 100, 1)
            if budget.monthly_limit > 0
            else 0,
        },
        "categories": category_status,
    }
