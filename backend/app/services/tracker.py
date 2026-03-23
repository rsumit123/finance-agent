"""Expense tracking and budget management service."""

import re
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Budget, CategoryBudget, Expense
from ..schemas import BudgetCreate, BudgetStatus, ExpenseCreate, ExpenseSummary


def _normalize_desc(desc: str) -> str:
    """Normalize description for comparison."""
    s = desc.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _is_duplicate(new: ExpenseCreate, existing: Expense) -> bool:
    """Check if a new expense is a duplicate of an existing one."""
    # Must match on date (compare date portion only) and amount
    new_date = new.date.date() if hasattr(new.date, 'date') and callable(new.date.date) else new.date
    ex_date = existing.date.date() if hasattr(existing.date, 'date') and callable(existing.date.date) else existing.date
    if new_date != ex_date or abs(abs(new.amount) - abs(existing.amount)) > 0.01:
        return False

    # If both have reference_id (UTR), exact match = definite duplicate
    if new.reference_id and existing.reference_id:
        return new.reference_id == existing.reference_id

    # Fuzzy description match
    new_desc = _normalize_desc(new.description)
    existing_desc = _normalize_desc(existing.description)

    if not new_desc or not existing_desc:
        # If descriptions are empty, match on date+amount+payment_method
        return new.payment_method == existing.payment_method

    # Check if one contains the other, or they share significant overlap
    if new_desc in existing_desc or existing_desc in new_desc:
        return True

    # Check word overlap
    new_words = set(new_desc.split())
    existing_words = set(existing_desc.split())
    if len(new_words) > 0 and len(existing_words) > 0:
        overlap = len(new_words & existing_words)
        min_len = min(len(new_words), len(existing_words))
        if min_len > 0 and overlap / min_len >= 0.5:
            return True

    return False


def create_expenses_bulk_dedup(
    db: Session, items: list[ExpenseCreate]
) -> tuple[list[Expense], list[ExpenseCreate]]:
    """Create expenses in bulk, skipping duplicates.

    Returns (inserted_expenses, duplicate_items).
    """
    if not items:
        return [], []

    # Get date range of incoming items (use date portion for range query)
    dates = [item.date.date() if hasattr(item.date, 'date') and callable(item.date.date) else item.date for item in items]
    min_date = min(dates)
    max_date = max(dates) + timedelta(days=1)  # +1 day to include all times on max_date

    # Fetch existing expenses in that date range
    existing = (
        db.query(Expense)
        .filter(Expense.date >= min_date, Expense.date < max_date)
        .all()
    )

    new_items = []
    duplicates = []

    for item in items:
        # Check against existing DB records
        is_dup = any(_is_duplicate(item, ex) for ex in existing)
        if is_dup:
            duplicates.append(item)
        else:
            new_items.append(item)

    # Insert non-duplicates
    expenses = [Expense(**d.model_dump()) for d in new_items]
    if expenses:
        db.add_all(expenses)
        db.commit()
        for e in expenses:
            db.refresh(e)

    return expenses, duplicates


def create_expense(db: Session, data: ExpenseCreate) -> Expense:
    expense = Expense(**data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def create_expenses_bulk(db: Session, items: list[ExpenseCreate]) -> list[Expense]:
    expenses = [Expense(**d.model_dump()) for d in items]
    db.add_all(expenses)
    db.commit()
    for e in expenses:
        db.refresh(e)
    return expenses


def get_expense(db: Session, expense_id: int) -> Expense | None:
    return db.query(Expense).filter(Expense.id == expense_id).first()


def delete_expense(db: Session, expense_id: int) -> bool:
    expense = get_expense(db, expense_id)
    if not expense:
        return False
    db.delete(expense)
    db.commit()
    return True


def list_expenses(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    payment_method: str | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Expense]:
    q = db.query(Expense)
    if start_date:
        q = q.filter(Expense.date >= start_date)
    if end_date:
        q = q.filter(Expense.date <= end_date)
    if category:
        q = q.filter(Expense.category == category)
    if payment_method:
        q = q.filter(Expense.payment_method == payment_method)
    if source:
        # Support both exact match and prefix match (e.g. "stmt_axis_cc" or "email_scapia")
        if source.endswith("_cc") or source.endswith("_bank") or source in ("email_scapia", "email_hdfc_bank", "email_hdfc_cc", "manual", "upi_pdf", "credit_card_pdf", "bank_pdf"):
            q = q.filter(Expense.source == source)
        else:
            q = q.filter(Expense.source.like(f"{source}%"))
    return q.order_by(Expense.date.desc()).offset(offset).limit(limit).all()


def get_current_week_range() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    return start, today


def get_current_month_range() -> tuple[date, date]:
    today = date.today()
    start = today.replace(day=1)
    return start, today


def get_period_total(db: Session, start_date: date, end_date: date) -> float:
    result = (
        db.query(func.coalesce(func.sum(Expense.amount), 0.0))
        .filter(Expense.date >= start_date, Expense.date <= end_date)
        .scalar()
    )
    return float(result)


def get_period_total_by_category(
    db: Session, start_date: date, end_date: date
) -> dict[str, float]:
    rows = (
        db.query(Expense.category, func.sum(Expense.amount))
        .filter(Expense.date >= start_date, Expense.date <= end_date)
        .group_by(Expense.category)
        .all()
    )
    return {cat: float(total) for cat, total in rows}


def get_period_total_by_payment(
    db: Session, start_date: date, end_date: date
) -> dict[str, float]:
    rows = (
        db.query(Expense.payment_method, func.sum(Expense.amount))
        .filter(Expense.date >= start_date, Expense.date <= end_date)
        .group_by(Expense.payment_method)
        .all()
    )
    return {method: float(total) for method, total in rows}


def summarize_period(db: Session, start_date: date, end_date: date) -> ExpenseSummary:
    total = get_period_total(db, start_date, end_date)
    count = (
        db.query(func.count(Expense.id))
        .filter(Expense.date >= start_date, Expense.date <= end_date)
        .scalar()
    )

    # Split income vs expenses
    # Transfers (category="transfer") are excluded from both income and expense
    # CC credits (payments, refunds) are NOT income
    all_in_range = (
        db.query(Expense)
        .filter(Expense.date >= start_date, Expense.date <= end_date)
        .all()
    )
    # Income = salary category only (actual earnings)
    # Refunds, CC credits, transfers are NOT income
    income_amt = sum(abs(e.amount) for e in all_in_range if e.category == "salary")

    # Expense = positive amounts, excluding transfers
    expense_amt = sum(e.amount for e in all_in_range if e.amount > 0 and e.category != "transfer")

    # Transfers = both sides of self-transfers
    transfer_amt = sum(abs(e.amount) for e in all_in_range if e.category == "transfer")

    income = income_amt
    expense = expense_amt

    # For charts: only positive amounts, exclude transfers
    cat_data = get_period_total_by_category(db, start_date, end_date)
    payment_data = get_period_total_by_payment(db, start_date, end_date)

    cat_data = {k: v for k, v in cat_data.items() if v > 0}
    payment_data = {k: v for k, v in payment_data.items() if v > 0}

    return ExpenseSummary(
        total=total,
        count=count or 0,
        income=abs(income),
        expense=expense,
        transfers=transfer_amt,
        by_category=cat_data,
        by_payment_method=payment_data,
    )


# --- Budget ---


def set_budget(db: Session, data: BudgetCreate) -> Budget:
    # Replace existing budget (only one active budget)
    db.query(CategoryBudget).delete()
    db.query(Budget).delete()

    budget = Budget(monthly_limit=data.monthly_limit, weekly_limit=data.weekly_limit)
    db.add(budget)
    db.flush()

    for cl in data.category_limits:
        db.add(CategoryBudget(
            budget_id=budget.id,
            category=cl.category,
            limit_amount=cl.limit_amount,
        ))

    db.commit()
    db.refresh(budget)
    return budget


def get_budget(db: Session) -> Budget | None:
    return db.query(Budget).order_by(Budget.id.desc()).first()


def get_category_limits(db: Session, budget_id: int) -> list[CategoryBudget]:
    return db.query(CategoryBudget).filter(CategoryBudget.budget_id == budget_id).all()


def get_budget_status(db: Session) -> BudgetStatus | None:
    budget = get_budget(db)
    if not budget:
        return None

    week_start, week_end = get_current_week_range()
    month_start, month_end = get_current_month_range()

    week_spent = get_period_total(db, week_start, week_end)
    month_spent = get_period_total(db, month_start, month_end)

    cat_limits = get_category_limits(db, budget.id)
    month_by_cat = get_period_total_by_category(db, month_start, month_end)

    categories = {}
    for cl in cat_limits:
        spent = month_by_cat.get(cl.category, 0.0)
        categories[cl.category] = {
            "limit": cl.limit_amount,
            "spent": spent,
            "remaining": cl.limit_amount - spent,
            "percent_used": round((spent / cl.limit_amount) * 100, 1)
            if cl.limit_amount > 0
            else 0,
        }

    return BudgetStatus(
        weekly_limit=budget.weekly_limit,
        weekly_spent=week_spent,
        weekly_remaining=budget.weekly_limit - week_spent,
        weekly_percent=round((week_spent / budget.weekly_limit) * 100, 1)
        if budget.weekly_limit > 0
        else 0,
        monthly_limit=budget.monthly_limit,
        monthly_spent=month_spent,
        monthly_remaining=budget.monthly_limit - month_spent,
        monthly_percent=round((month_spent / budget.monthly_limit) * 100, 1)
        if budget.monthly_limit > 0
        else 0,
        categories=categories,
    )
