"""Expense management endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from collections import defaultdict

from ..database import get_db
from ..models import Expense
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


@router.get("/sources")
def get_sources(db: Session = Depends(get_db)):
    """Get all transaction sources grouped by bank and month.

    Returns a list of source groups with transaction count, total amount,
    date range, and bank identification.
    """
    expenses = db.query(Expense).order_by(Expense.date.desc()).all()

    # Group by (source_type, month)
    groups: dict[tuple, list] = defaultdict(list)
    for e in expenses:
        # Determine bank from source
        source = e.source or "unknown"
        bank = _source_to_bank(source)
        source_type = _source_to_type(source)
        month_key = e.date.strftime("%Y-%m") if e.date else "unknown"
        groups[(bank, source_type, month_key)].append(e)

    result = []
    for (bank, source_type, month), txns in sorted(groups.items(), key=lambda x: x[0][2], reverse=True):
        amounts = [t.amount for t in txns]
        dates = [t.date for t in txns if t.date]
        result.append({
            "bank": bank,
            "source_type": source_type,
            "month": month,
            "month_label": _month_label(month),
            "transaction_count": len(txns),
            "total_amount": round(sum(amounts), 2),
            "min_date": min(dates).isoformat() if dates else None,
            "max_date": max(dates).isoformat() if dates else None,
        })

    return result


def _source_to_bank(source: str) -> str:
    if "hdfc" in source:
        return "HDFC"
    if "axis" in source:
        return "Axis"
    if "scapia" in source:
        return "Scapia"
    if "icici" in source:
        return "ICICI"
    if "sbi" in source:
        return "SBI"
    if source.startswith("stmt_"):
        return source.replace("stmt_", "").upper()
    if source == "upi_pdf":
        return "PhonePe/UPI"
    if source == "credit_card_pdf":
        return "Credit Card"
    if source == "bank_pdf":
        return "Bank"
    if source == "manual":
        return "Manual"
    return source.replace("_", " ").title()


def _source_to_type(source: str) -> str:
    if source.startswith("email"):
        return "gmail_alert"
    if source.startswith("stmt_"):
        return "gmail_statement"
    if source.endswith("_pdf"):
        return "pdf_upload"
    if source == "manual":
        return "manual"
    return "other"


def _month_label(month: str) -> str:
    try:
        from datetime import datetime
        dt = datetime.strptime(month, "%Y-%m")
        return dt.strftime("%b %Y")
    except ValueError:
        return month


@router.get("/subscriptions", response_model=list[Subscription])
def get_subscriptions(db: Session = Depends(get_db)):
    """Detect recurring/subscription payments from expense history."""
    return detect_subscriptions(db)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, updates: dict, db: Session = Depends(get_db)):
    """Update specific fields on an expense (e.g. category)."""
    expense = get_expense(db, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    allowed = {"category", "description", "payment_method"}
    for key, value in updates.items():
        if key in allowed:
            setattr(expense, key, value)

    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}")
def remove_expense(expense_id: int, db: Session = Depends(get_db)):
    if not delete_expense(db, expense_id):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"message": "Expense deleted"}
