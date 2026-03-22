"""Expense management endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ExpenseCreate, ExpenseOut, ExpenseSummary, Subscription
from ..services.subscriptions import detect_subscriptions
from ..services.tracker import (
    create_expense,
    delete_expense,
    get_current_month_range,
    get_current_week_range,
    get_expense,
    list_expenses,
    summarize_period,
)

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.post("/", response_model=ExpenseOut)
def add_expense(data: ExpenseCreate, db: Session = Depends(get_db)):
    return create_expense(db, data)


@router.get("/", response_model=list[ExpenseOut])
def get_expenses(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category: Optional[str] = Query(None),
    payment_method: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    period: Optional[str] = Query(None, pattern="^(week|month)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    if period == "week":
        start_date, end_date = get_current_week_range()
    elif period == "month":
        start_date, end_date = get_current_month_range()

    return list_expenses(db, start_date, end_date, category, payment_method, source, limit, offset)


@router.get("/summary", response_model=ExpenseSummary)
def expense_summary(
    period: str = Query("month", pattern="^(week|month)$"),
    db: Session = Depends(get_db),
):
    if period == "week":
        start, end = get_current_week_range()
    else:
        start, end = get_current_month_range()
    return summarize_period(db, start, end)


@router.get("/subscriptions", response_model=list[Subscription])
def get_subscriptions(db: Session = Depends(get_db)):
    """Detect recurring/subscription payments from expense history."""
    return detect_subscriptions(db)


@router.delete("/{expense_id}")
def remove_expense(expense_id: int, db: Session = Depends(get_db)):
    if not delete_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"message": "Expense deleted"}
