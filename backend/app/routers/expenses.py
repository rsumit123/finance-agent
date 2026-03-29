"""Expense management endpoints."""

import json
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from collections import defaultdict

from ..auth import get_current_user
from ..database import get_db
from ..models import CategoryRule, Expense, User, UserPreference
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


def _get_excluded_banks(db: Session, user_id: int) -> list[str]:
    """Get user's excluded banks list."""
    pref = db.query(UserPreference).filter(
        UserPreference.user_id == user_id,
        UserPreference.key == "excluded_banks",
    ).first()
    if pref and pref.value:
        return json.loads(pref.value)
    return []

# Categories excluded from spending calculations (not real expenses)
EXCLUDED_SPEND_CATEGORIES = {"transfer", "lent", "borrowed"}

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


@router.post("/", response_model=ExpenseOut)
def add_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_expense(db, data, user_id=current_user.id)


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
    current_user: User = Depends(get_current_user),
):
    if period == "week":
        start_date, end_date = get_current_week_range()
    elif period == "month":
        start_date, end_date = get_current_month_range()

    return list_expenses(db, start_date, end_date, category, payment_method, source, limit, offset, user_id=current_user.id)


@router.get("/summary", response_model=ExpenseSummary)
def expense_summary(
    period: Optional[str] = Query(None, pattern="^(week|month)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if start_date and end_date:
        start, end = start_date, end_date
    elif period == "week":
        start, end = get_current_week_range()
    else:
        start, end = get_current_month_range()
    result = summarize_period(db, start, end, user_id=current_user.id)

    # Filter out excluded banks from category breakdown
    excluded = _get_excluded_banks(db, current_user.id)
    if excluded:
        # Re-calculate from filtered expenses
        all_in_range = db.query(Expense).filter(
            Expense.user_id == current_user.id,
            Expense.date >= start, Expense.date <= end,
        ).all()
        filtered = [e for e in all_in_range if _source_to_bank(e.source or "").lower() not in excluded]
        result.income = sum(abs(e.amount) for e in filtered if e.category == "salary")
        result.expense = sum(e.amount for e in filtered if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES)
        result.total = result.expense
        result.count = len(filtered)
        # Recalculate category breakdown
        cat = {}
        for e in filtered:
            if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES:
                cat[e.category] = cat.get(e.category, 0) + e.amount
        result.by_category = cat

    return result


@router.get("/sources")
def get_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all transaction sources grouped by bank and month.

    Returns a list of source groups with transaction count, total amount,
    date range, and bank identification.
    """
    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == current_user.id)
        .order_by(Expense.date.desc())
        .all()
    )

    # Group by (bank, account_type, month) — merge all source types (sms, email, stmt)
    groups: dict[tuple, list] = defaultdict(list)
    for e in expenses:
        source = e.source or "unknown"
        bank = _source_to_bank(source)
        is_cc = _is_cc_source(source)
        account_type = "Credit Card" if is_cc else "Bank Account"
        month_key = e.date.strftime("%Y-%m") if e.date else "unknown"
        groups[(bank, account_type, month_key)].append(e)

    result = []
    for (bank, account_type, month), txns in sorted(groups.items(), key=lambda x: x[0][2], reverse=True):
        amounts = [t.amount for t in txns]
        dates = [t.date for t in txns if t.date]
        debits = sum(a for a in amounts if a > 0)
        neg_total = abs(sum(a for a in amounts if a < 0))

        # Collect all unique source types and source values
        source_types = list(set(_source_to_type(t.source or "") for t in txns))
        source_values = list(set(t.source for t in txns if t.source))

        is_cc = account_type == "Credit Card"
        result.append({
            "bank": bank,
            "account_type": account_type,
            "source_type": source_types[0] if len(source_types) == 1 else "mixed",
            "source_types": source_types,
            "source_filter": source_values[0] if len(source_values) == 1 else "",
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
    s = source.lower()
    if "hdfc" in s:
        return "HDFC"
    if "axis" in s:
        return "Axis"
    if "scapia" in s:
        return "Scapia"
    if "icici" in s:
        return "ICICI"
    if "sbi" in s:
        return "SBI"
    if "kotak" in s:
        return "Kotak"
    if s.startswith("stmt_") or s.startswith("sms_"):
        prefix = "stmt_" if s.startswith("stmt_") else "sms_"
        name = s.replace(prefix, "")
        for suffix in ("_cc", "_bank"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name.upper()
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
    # Explicit bank sources
    if any(kw in s for kw in ["_bank", "bank_pdf", "upi_pdf", "email_hdfc_bank"]):
        return False
    # Explicit CC sources
    if any(kw in s for kw in ["_cc", "credit_card", "email_scapia", "email_hdfc_cc", "email_axis_cc", "email_icici_cc"]):
        return True
    # Old-style stmt_ without _cc/_bank suffix — treat as CC (legacy)
    if s.startswith("stmt_") and "_cc" not in s and "_bank" not in s:
        return True
    return False


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
def get_networth(
    period: Optional[str] = Query(None, pattern="^(week|month)$"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate financial summary for a period. CC outstanding is always all-time."""
    if start_date and end_date:
        q = db.query(Expense).filter(Expense.user_id == current_user.id, Expense.date >= start_date, Expense.date <= end_date)
    elif period == "week":
        start, end = get_current_week_range()
        q = db.query(Expense).filter(Expense.user_id == current_user.id, Expense.date >= start, Expense.date <= end)
    elif period == "month":
        start, end = get_current_month_range()
        q = db.query(Expense).filter(Expense.user_id == current_user.id, Expense.date >= start, Expense.date <= end)
    else:
        q = db.query(Expense).filter(Expense.user_id == current_user.id)

    all_expenses = q.all()

    # Filter out excluded banks
    excluded = _get_excluded_banks(db, current_user.id)
    if excluded:
        expenses = [e for e in all_expenses if _source_to_bank(e.source or "").lower() not in excluded]
    else:
        expenses = all_expenses

    if not expenses:
        return {"total_income": 0, "total_spent": 0, "net_cashflow": 0, "cc_outstanding": {}, "total_cc_debt": 0}

    total_income = 0  # bank credits only
    total_spent = 0   # all debits

    # Per-card CC tracking
    cc_charges: dict[str, float] = defaultdict(float)  # bank -> total charges
    cc_payments: dict[str, float] = defaultdict(float)  # bank -> total payments

    total_transfers = 0
    for e in expenses:
        is_cc = _is_cc_source(e.source or "")
        bank = _source_to_bank(e.source or "")
        is_transfer = (e.category in EXCLUDED_SPEND_CATEGORIES)

        # Income = salary only
        if e.category == "salary":
            total_income += abs(e.amount)

        if is_transfer:
            total_transfers += abs(e.amount)
            if is_cc:
                if e.amount > 0:
                    cc_charges[bank] += e.amount
                else:
                    cc_payments[bank] += abs(e.amount)
            continue

        if e.amount > 0:
            total_spent += e.amount
            if is_cc:
                cc_charges[bank] += e.amount
        elif e.amount < 0:
            if is_cc:
                cc_payments[bank] += abs(e.amount)

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

    # CC outstanding is always calculated from ALL data (debt persists)
    all_cc_query = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    all_cc_expenses = [e for e in all_cc_query if _source_to_bank(e.source or "").lower() not in excluded] if excluded else all_cc_query
    cc_charges_all: dict[str, float] = defaultdict(float)
    cc_payments_all: dict[str, float] = defaultdict(float)
    for e in all_cc_expenses:
        if _is_cc_source(e.source or ""):
            bank = _source_to_bank(e.source or "")
            if e.amount > 0:
                cc_charges_all[bank] += e.amount
            elif e.amount < 0:
                cc_payments_all[bank] += abs(e.amount)

    cc_outstanding_all = {}
    total_cc_debt_all = 0
    for bank in sorted(set(cc_charges_all) | set(cc_payments_all)):
        outstanding = cc_charges_all.get(bank, 0) - cc_payments_all.get(bank, 0)
        cc_outstanding_all[bank] = {
            "charges": round(cc_charges_all.get(bank, 0), 2),
            "payments": round(cc_payments_all.get(bank, 0), 2),
            "outstanding": round(max(outstanding, 0), 2),
        }
        total_cc_debt_all += max(outstanding, 0)

    return {
        "period": period or "all",
        "total_income": round(total_income, 2),
        "total_spent": round(total_spent, 2),
        "total_transfers": round(total_transfers, 2),
        "net_cashflow": round(total_income - total_spent, 2),
        "cc_outstanding": cc_outstanding_all,
        "total_cc_debt": round(total_cc_debt_all, 2),
    }


@router.get("/insights")
def get_insights(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    period: Optional[str] = Query(None, pattern="^(week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate spending insights for a period."""
    from collections import Counter

    if start_date and end_date:
        s, e = start_date, end_date
    elif period == "week":
        s, e = get_current_week_range()
    else:
        s, e = get_current_month_range()

    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == current_user.id, Expense.date >= s, Expense.date <= e, Expense.amount > 0)
        .all()
    )

    # Filter excluded banks
    excluded = _get_excluded_banks(db, current_user.id)
    if excluded:
        expenses = [x for x in expenses if _source_to_bank(x.source or "").lower() not in excluded]

    # Exclude transfers from insights
    real = [x for x in expenses if x.category != "transfer"]
    if not real:
        return {"insights": [], "top_merchants": [], "top_categories": [], "by_account": []}

    # Top merchants/people by total spend
    merchant_spend: dict[str, float] = defaultdict(float)
    merchant_count: dict[str, int] = defaultdict(int)
    for x in real:
        name = (x.description or "Unknown")[:50]
        merchant_spend[name] += x.amount
        merchant_count[name] += 1

    top_merchants = sorted(
        [{"name": k, "total": round(v, 2), "count": merchant_count[k]} for k, v in merchant_spend.items()],
        key=lambda x: -x["total"],
    )[:10]

    # Biggest single transaction
    biggest = max(real, key=lambda x: x.amount)

    # Most frequent payee
    freq_counter = Counter((x.description or "Unknown")[:50] for x in real)
    most_frequent = freq_counter.most_common(1)[0] if freq_counter else None

    # Per-account spending
    account_spend: dict[str, float] = defaultdict(float)
    account_count: dict[str, int] = defaultdict(int)
    for x in real:
        bank = _source_to_bank(x.source or "")
        is_cc = _is_cc_source(x.source or "")
        label = f"{bank} {'CC' if is_cc else 'Bank'}"
        account_spend[label] += x.amount
        account_count[label] += 1

    by_account = sorted(
        [{"account": k, "total": round(v, 2), "count": account_count[k]} for k, v in account_spend.items()],
        key=lambda x: -x["total"],
    )

    # Day of week pattern
    day_spend: dict[str, float] = defaultdict(float)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for x in real:
        if x.date:
            day = day_names[x.date.weekday()]
            day_spend[day] += x.amount
    by_day = [{"day": d, "total": round(day_spend.get(d, 0), 2)} for d in day_names]

    # Previous period comparison
    period_days = (e - s).days + 1
    prev_s = s - timedelta(days=period_days)
    prev_e = s - timedelta(days=1)
    prev_total = float(
        db.query(func.coalesce(func.sum(Expense.amount), 0.0))
        .filter(Expense.user_id == current_user.id, Expense.date >= prev_s, Expense.date <= prev_e, Expense.amount > 0, Expense.category not in EXCLUDED_SPEND_CATEGORIES)
        .scalar()
    )
    current_total = sum(x.amount for x in real)
    if prev_total > 0:
        change_pct = round(((current_total - prev_total) / prev_total) * 100, 1)
    else:
        change_pct = None

    # Build insight sentences
    insights = []
    if top_merchants:
        insights.append(f"Highest spend: {top_merchants[0]['name']} ({_fmt(top_merchants[0]['total'])})")
    if biggest:
        insights.append(f"Biggest transaction: {(biggest.description or 'Unknown')[:30]} ({_fmt(biggest.amount)})")
    if most_frequent and most_frequent[1] > 1:
        insights.append(f"Most frequent: {most_frequent[0]} ({most_frequent[1]} transactions)")
    if by_account:
        insights.append(f"Most used account: {by_account[0]['account']} ({_fmt(by_account[0]['total'])})")
    if change_pct is not None:
        direction = "up" if change_pct > 0 else "down"
        insights.append(f"Spending {direction} {abs(change_pct)}% vs previous period ({_fmt(prev_total)})")
    if by_day:
        peak_day = max(by_day, key=lambda x: x["total"])
        if peak_day["total"] > 0:
            insights.append(f"Peak spending day: {peak_day['day']}s ({_fmt(peak_day['total'])})")

    return {
        "insights": insights,
        "top_merchants": top_merchants,
        "by_account": by_account,
        "by_day": by_day,
        "vs_previous": {"current": round(current_total, 2), "previous": round(prev_total, 2), "change_pct": change_pct},
    }


def _fmt(n):
    """Format INR for insight strings."""
    if n >= 100000:
        return f"₹{n/100000:.1f}L"
    if n >= 1000:
        return f"₹{n/1000:.1f}K"
    return f"₹{n:.0f}"


@router.get("/subscriptions", response_model=list[Subscription])
def get_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detect recurring/subscription payments from expense history."""
    return detect_subscriptions(db, user_id=current_user.id)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    updates: dict,
    learn: bool = Query(True, description="Learn this category for future imports"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update specific fields on an expense. If category changes, learns the pattern."""
    expense = get_expense(db, expense_id, user_id=current_user.id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    old_category = expense.category

    allowed = {"category", "description", "payment_method"}
    for key, value in updates.items():
        if key in allowed:
            setattr(expense, key, value)

    # Learn category rule if category was changed
    new_category = updates.get("category")
    if learn and new_category and new_category != old_category and expense.description:
        _learn_category_rule(db, current_user.id, expense.description, new_category)

    db.commit()
    db.refresh(expense)
    return expense


def _learn_category_rule(db, user_id: int, description: str, category: str):
    """Extract a keyword from description and save as a category rule."""
    import re
    # Normalize: lowercase, strip refs/ids, take meaningful words
    desc = description.lower().strip()
    desc = re.sub(r"\(.*?\)", "", desc)  # remove parenthetical
    desc = re.sub(r"ref#?\s*\S+", "", desc)  # remove ref numbers
    desc = re.sub(r"\d{6,}", "", desc)  # remove long numbers
    desc = re.sub(r"[^a-z\s]", "", desc)
    desc = re.sub(r"\s+", " ", desc).strip()

    # Take first 3 significant words as the keyword
    words = [w for w in desc.split() if len(w) > 2]
    if not words:
        return

    keyword = " ".join(words[:3])
    if len(keyword) < 4:
        return

    # Check if rule already exists for this keyword
    existing = db.query(CategoryRule).filter(
        CategoryRule.user_id == user_id,
        CategoryRule.keyword == keyword,
    ).first()

    if existing:
        existing.category = category  # Update
    else:
        db.add(CategoryRule(user_id=user_id, keyword=keyword, category=category))


@router.post("/apply-category")
def apply_category_to_similar(
    expense_id: int = Query(...),
    category: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a category to all transactions with similar descriptions."""
    import re
    expense = get_expense(db, expense_id, user_id=current_user.id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Normalize description for matching
    desc = (expense.description or "").lower()
    desc = re.sub(r"\(.*?\)", "", desc)
    desc = re.sub(r"\d{6,}", "", desc)
    desc = re.sub(r"[^a-z\s]", "", desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    words = [w for w in desc.split() if len(w) > 2]
    keyword = " ".join(words[:3])

    if len(keyword) < 4:
        return {"updated": 0, "keyword": ""}

    # Find and update all matching expenses
    all_expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()
    updated = 0
    for e in all_expenses:
        e_desc = (e.description or "").lower()
        e_desc = re.sub(r"[^a-z\s]", "", e_desc)
        if keyword in e_desc and e.category != category:
            e.category = category
            updated += 1

    # Also save as a learned rule
    from ..models import CategoryRule
    existing_rule = db.query(CategoryRule).filter(
        CategoryRule.user_id == current_user.id, CategoryRule.keyword == keyword,
    ).first()
    if existing_rule:
        existing_rule.category = category
    else:
        db.add(CategoryRule(user_id=current_user.id, keyword=keyword, category=category))

    db.commit()
    return {"updated": updated, "keyword": keyword, "category": category}


@router.delete("/{expense_id}")
def remove_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not delete_expense(db, expense_id, user_id=current_user.id):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"message": "Expense deleted"}
