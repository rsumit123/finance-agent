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

    # Group by (bank, account_type, source_type, month)
    groups: dict[tuple, list] = defaultdict(list)
    for e in expenses:
        source = e.source or "unknown"
        bank = _source_to_bank(source)
        source_type = _source_to_type(source)
        is_cc = _is_cc_source(source)
        account_type = "Credit Card" if is_cc else "Bank Account"
        month_key = e.date.strftime("%Y-%m") if e.date else "unknown"
        groups[(bank, account_type, source_type, month_key)].append(e)

    result = []
    for (bank, account_type, source_type, month), txns in sorted(groups.items(), key=lambda x: x[0][3], reverse=True):
        amounts = [t.amount for t in txns]
        dates = [t.date for t in txns if t.date]
        debits = sum(a for a in amounts if a > 0)
        neg_total = abs(sum(a for a in amounts if a < 0))

        is_cc = account_type == "Credit Card"
        result.append({
            "bank": bank,
            "account_type": account_type,
            "source_type": source_type,
            "month": month,
            "month_label": _month_label(month),
            "transaction_count": len(txns),
            "total_amount": round(sum(amounts), 2),
            "total_debits": round(debits, 2),
            "total_credits": round(neg_total, 2) if not is_cc else 0,
            "total_payments": round(neg_total, 2) if is_cc else 0,
            "is_credit_card": is_cc,
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


def _is_cc_source(source: str) -> bool:
    """Check if a source is a credit card source (vs bank account)."""
    s = source.lower()
    cc_keywords = ["credit_card", "stmt_", "email_hdfc_cc", "email_axis_cc", "email_scapia", "email_icici_cc"]
    # email_hdfc_bank is bank, not CC
    if "email_hdfc_bank" in s or "bank_pdf" in s or "upi_pdf" in s:
        return False
    return any(kw in s for kw in cc_keywords)


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


@router.get("/networth")
def get_networth(db: Session = Depends(get_db)):
    """Calculate net worth summary from all transactions.

    Net worth = total income (bank credits) - total spending + CC payments made
    CC outstanding = CC charges - CC payments
    """
    expenses = db.query(Expense).all()
    if not expenses:
        return {"total_income": 0, "total_spent": 0, "net_cashflow": 0, "cc_outstanding": {}, "total_cc_debt": 0}

    total_income = 0  # bank credits only
    total_spent = 0   # all debits

    # Per-card CC tracking
    cc_charges: dict[str, float] = defaultdict(float)  # bank -> total charges
    cc_payments: dict[str, float] = defaultdict(float)  # bank -> total payments

    for e in expenses:
        is_cc = _is_cc_source(e.source or "")
        bank = _source_to_bank(e.source or "")

        if e.amount > 0:
            total_spent += e.amount
            if is_cc:
                cc_charges[bank] += e.amount
        elif e.amount < 0:
            if is_cc:
                cc_payments[bank] += abs(e.amount)
            else:
                total_income += abs(e.amount)

    # CC outstanding per bank
    cc_outstanding = {}
    total_cc_debt = 0
    all_cc_banks = set(cc_charges.keys()) | set(cc_payments.keys())
    for bank in sorted(all_cc_banks):
        outstanding = cc_charges.get(bank, 0) - cc_payments.get(bank, 0)
        cc_outstanding[bank] = {
            "charges": round(cc_charges.get(bank, 0), 2),
            "payments": round(cc_payments.get(bank, 0), 2),
            "outstanding": round(max(outstanding, 0), 2),
        }
        total_cc_debt += max(outstanding, 0)

    return {
        "total_income": round(total_income, 2),
        "total_spent": round(total_spent, 2),
        "net_cashflow": round(total_income - total_spent, 2),
        "cc_outstanding": cc_outstanding,
        "total_cc_debt": round(total_cc_debt, 2),
    }


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
