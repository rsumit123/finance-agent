"""Expense tracking and budget management service."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Budget, CategoryBudget, Expense
from ..schemas import BudgetCreate, BudgetStatus, ExpenseCreate, ExpenseSummary


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
        q = q.filter(Expense.source == source)
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
    return ExpenseSummary(
        total=total,
        count=count or 0,
        by_category=get_period_total_by_category(db, start_date, end_date),
        by_payment_method=get_period_total_by_payment(db, start_date, end_date),
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
