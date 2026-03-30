"""LLM-powered finance chat endpoint with tool use and SSE streaming."""

import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

import asyncio
import anthropic
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Expense, User, UserPreference, CategoryRule
from ..services.subscriptions import detect_subscriptions
from ..parsers.categorizer import classify_category

router = APIRouter(prefix="/api/chat", tags=["chat"])

EXCLUDED_SPEND_CATEGORIES = {"transfer", "lent", "borrowed"}

SYSTEM_PROMPT = """You are MoneyFlow AI — a personal finance assistant with full access to the user's transaction data.

DATA CONVENTIONS:
- Transactions with type "debit (spent)" = money the user SPENT (outgoing)
- Transactions with type "credit (received/refund)" = money the user RECEIVED (incoming)
- The "amount" field is always positive. The "type" field tells direction.
- When reporting: "spent ₹X" for debits, "received ₹X" for credits
- Salary/income = credit transactions in "salary" category

CAPABILITIES:
- Search and find transactions (by keyword, category, date, amount, bank)
- Spending summaries and category breakdowns
- Compare spending between periods
- Update transaction categories (single or bulk with auto-rule)
- Delete transactions
- Detect recurring subscriptions
- Net worth and CC outstanding
- Day-by-day spending patterns

GUIDELINES:
- Always use tools first — never guess amounts
- Use ₹ and Indian number formatting (1,00,000)
- Be concise — no filler
- Confirm before updating/deleting, then briefly confirm what was done
- Ask clarifying questions if needed
- Today's date is {today}

MONEYFLOW PLATFORM GUIDE (share when users ask how-to questions):
- **Import transactions**: Go to Import tab → Sync SMS (reads bank messages), Connect Gmail (reads bank emails + downloads statement PDFs), or upload PDF manually
- **Hide a bank**: Account tab → "Hide Banks" section → tap the bank to exclude it from all calculations
- **Change category**: Tap any transaction in Expenses → tap Category → pick new one. Choose "Apply to all similar" to bulk-update + save rule for future imports.
- **Self Transfer**: Change category to "Self Transfer" → optionally link the matching opposite transaction from another bank
- **Lent/Borrowed**: Categories for tracking money lent to others or borrowed — excluded from spending calculations
- **Supported banks**: HDFC, Axis, ICICI, SBI, Kotak, Scapia, Bank of Baroda, Karnataka Bank, Canara Bank, and more via SMS
- **PDF statements**: Upload password-protected PDFs. Save passwords in Import → Statement Passwords section.
- **Budget**: Set weekly/monthly spending limits in the Budget tab
- **Cards page**: See all cards/accounts with monthly transaction breakdown
- **Ask AI (this chat)**: You can search transactions, recategorize, compare periods, and manage expenses through natural language
"""

TOOLS = [
    {
        "name": "search_transactions",
        "description": (
            "Search and find transactions by keyword, category, date range, bank, or amount range. "
            "Use this for any question about specific transactions. Returns up to 20 results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Search in descriptions (e.g. 'blinkit', 'amazon', 'salary')"},
                "category": {"type": "string", "description": "Category filter: food, transport, shopping, entertainment, bills, subscriptions, health, education, groceries, rent, home, personal care, investment, emi, transfer, lent, borrowed, atm, salary, other"},
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                "bank": {"type": "string", "description": "Bank name (hdfc, axis, icici, sbi, kotak, scapia, etc.)"},
                "min_amount": {"type": "number", "description": "Minimum absolute amount"},
                "max_amount": {"type": "number", "description": "Maximum absolute amount"},
                "type": {"type": "string", "enum": ["debit", "credit"], "description": "debit (spent) or credit (received)"},
                "limit": {"type": "integer", "description": "Max results (default 20, max 50)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_spending_summary",
        "description": "Get total spent, income, and category breakdown for a period. Use for 'how much did I spend' questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
                "period": {"type": "string", "enum": ["month", "week"], "description": "Shorthand: current month or week"},
            },
            "required": [],
        },
    },
    {
        "name": "get_networth",
        "description": "Get income, spending, net cashflow, and CC outstanding. Use for net worth / financial overview questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["month", "week"]},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": [],
        },
    },
    {
        "name": "compare_periods",
        "description": "Compare spending between two date ranges. Use when user asks to compare months or weeks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period1_start": {"type": "string", "description": "YYYY-MM-DD"},
                "period1_end": {"type": "string", "description": "YYYY-MM-DD"},
                "period2_start": {"type": "string", "description": "YYYY-MM-DD"},
                "period2_end": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["period1_start", "period1_end", "period2_start", "period2_end"],
        },
    },
    {
        "name": "get_subscriptions",
        "description": "Detect and list recurring payments/subscriptions from transaction history.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_transaction_category",
        "description": (
            "Change the category of a specific transaction by ID. "
            "Always search for the transaction first and confirm with the user before updating. "
            "Valid categories: food, transport, shopping, entertainment, bills, subscriptions, health, education, "
            "groceries, rent, home, personal care, investment, emi, transfer, lent, borrowed, atm, salary, other"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer", "description": "The transaction ID to update"},
                "new_category": {"type": "string", "description": "New category name"},
            },
            "required": ["transaction_id", "new_category"],
        },
    },
    {
        "name": "bulk_recategorize",
        "description": (
            "Recategorize all transactions matching a keyword to a new category. "
            "Also saves a rule so future imports auto-categorize. "
            "Always confirm with the user first — show how many will be affected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Description keyword to match (e.g. 'blinkit', 'swiggy')"},
                "new_category": {"type": "string", "description": "New category to apply"},
            },
            "required": ["keyword", "new_category"],
        },
    },
    {
        "name": "delete_transaction",
        "description": (
            "Delete a transaction by ID. Always search and confirm with the user before deleting. "
            "Show the transaction details so the user can verify."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "integer", "description": "The transaction ID to delete"},
            },
            "required": ["transaction_id"],
        },
    },
    {
        "name": "get_daily_spending",
        "description": "Get day-by-day spending breakdown for a period. Useful for finding spending patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"],
        },
    },
]


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


def _get_excluded_banks(db: Session, user_id: int) -> list[str]:
    pref = db.query(UserPreference).filter(
        UserPreference.user_id == user_id,
        UserPreference.key == "excluded_banks",
    ).first()
    if pref and pref.value:
        return json.loads(pref.value)
    return []


def _source_to_bank(source: str) -> str:
    s = source.lower()
    for name in ["hdfc", "axis", "scapia", "icici", "sbi", "kotak", "karnataka", "canara", "bob"]:
        if name in s:
            return name.upper() if name not in ("scapia",) else "Scapia"
    return source.replace("_", " ").title()


def _is_cc_source(source: str) -> bool:
    s = source.lower()
    if any(kw in s for kw in ["_bank", "bank_pdf", "upi_pdf"]):
        return False
    if any(kw in s for kw in ["_cc", "credit_card", "email_scapia"]):
        return True
    if s.startswith("stmt_") and "_cc" not in s and "_bank" not in s:
        return True
    return False


def _parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _get_month_range():
    today = date.today()
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return start, end


def _get_week_range():
    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start, end


# ── Tool implementations ──────────────────────────────────────

def _exec_search_transactions(db: Session, user_id: int, params: dict) -> str:
    q = db.query(Expense).filter(Expense.user_id == user_id)

    keyword = params.get("keyword")
    category = params.get("category")
    start = _parse_date(params.get("start_date", ""))
    end = _parse_date(params.get("end_date", ""))
    bank = params.get("bank", "")
    min_amt = params.get("min_amount")
    max_amt = params.get("max_amount")
    txn_type = params.get("type")
    limit = min(params.get("limit", 20), 50)

    if start:
        q = q.filter(Expense.date >= datetime.combine(start, datetime.min.time()))
    if end:
        q = q.filter(Expense.date <= datetime.combine(end, datetime.max.time()))
    if category:
        q = q.filter(Expense.category == category.lower())
    if keyword:
        q = q.filter(Expense.description.ilike(f"%{keyword}%"))
    if bank:
        q = q.filter(Expense.source.ilike(f"%{bank.lower()}%"))
    if txn_type == "debit":
        q = q.filter(Expense.amount > 0)
    elif txn_type == "credit":
        q = q.filter(Expense.amount < 0)
    if min_amt is not None:
        q = q.filter(func.abs(Expense.amount) >= min_amt)
    if max_amt is not None:
        q = q.filter(func.abs(Expense.amount) <= max_amt)

    results = q.order_by(Expense.date.desc()).limit(limit).all()

    if not results:
        return json.dumps({"count": 0, "transactions": [], "message": "No matching transactions found."})

    txns = []
    for e in results:
        is_credit = e.amount < 0
        txns.append({
            "id": e.id,
            "amount": abs(e.amount),
            "type": "credit (received/refund)" if is_credit else "debit (spent)",
            "category": e.category,
            "description": e.description or "",
            "date": e.date.strftime("%Y-%m-%d") if e.date else "",
            "source": _source_to_bank(e.source or ""),
            "payment_method": e.payment_method or "",
        })

    total_spent = sum(t["amount"] for t in txns if "debit" in t["type"])
    total_received = sum(t["amount"] for t in txns if "credit" in t["type"])
    return json.dumps({"count": len(txns), "total_spent": round(total_spent, 2), "total_received": round(total_received, 2), "transactions": txns})


def _exec_spending_summary(db: Session, user_id: int, params: dict) -> str:
    period = params.get("period")
    if period == "month":
        start, end = _get_month_range()
    elif period == "week":
        start, end = _get_week_range()
    else:
        start = _parse_date(params.get("start_date", ""))
        end = _parse_date(params.get("end_date", ""))
        if not start or not end:
            start, end = _get_month_range()

    expenses = (
        db.query(Expense)
        .filter(Expense.user_id == user_id,
                Expense.date >= datetime.combine(start, datetime.min.time()),
                Expense.date <= datetime.combine(end, datetime.max.time()))
        .all()
    )

    excluded = _get_excluded_banks(db, user_id)
    if excluded:
        expenses = [e for e in expenses if _source_to_bank(e.source or "").lower() not in [b.lower() for b in excluded]]

    total_income = sum(abs(e.amount) for e in expenses if e.category == "salary")
    total_spent = sum(e.amount for e in expenses if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES)
    total_credits = sum(abs(e.amount) for e in expenses if e.amount < 0 and e.category != "salary")

    by_category = defaultdict(float)
    for e in expenses:
        if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES:
            by_category[e.category] += e.amount

    sorted_cats = sorted(by_category.items(), key=lambda x: -x[1])
    num_debits = sum(1 for e in expenses if e.amount > 0)
    num_credits = sum(1 for e in expenses if e.amount < 0)

    return json.dumps({
        "period": f"{start} to {end}",
        "total_spent_debits": round(total_spent, 2),
        "total_salary_income": round(total_income, 2),
        "total_credits_received": round(total_credits, 2),
        "transaction_count": len(expenses),
        "debit_count": num_debits,
        "credit_count": num_credits,
        "note": "Positive amounts = money spent (debits). Salary = income received. Credits = refunds/transfers received.",
        "by_category": {k: round(v, 2) for k, v in sorted_cats},
    })


def _exec_networth(db: Session, user_id: int, params: dict) -> str:
    period = params.get("period")
    start = _parse_date(params.get("start_date", ""))
    end = _parse_date(params.get("end_date", ""))

    if start and end:
        q = db.query(Expense).filter(Expense.user_id == user_id,
                                      Expense.date >= datetime.combine(start, datetime.min.time()),
                                      Expense.date <= datetime.combine(end, datetime.max.time()))
    elif period == "month":
        s, e = _get_month_range()
        q = db.query(Expense).filter(Expense.user_id == user_id,
                                      Expense.date >= datetime.combine(s, datetime.min.time()),
                                      Expense.date <= datetime.combine(e, datetime.max.time()))
    elif period == "week":
        s, e = _get_week_range()
        q = db.query(Expense).filter(Expense.user_id == user_id,
                                      Expense.date >= datetime.combine(s, datetime.min.time()),
                                      Expense.date <= datetime.combine(e, datetime.max.time()))
    else:
        q = db.query(Expense).filter(Expense.user_id == user_id)

    expenses = q.all()
    excluded = _get_excluded_banks(db, user_id)
    if excluded:
        expenses = [e for e in expenses if _source_to_bank(e.source or "").lower() not in [b.lower() for b in excluded]]

    total_income = sum(abs(e.amount) for e in expenses if e.category == "salary")
    total_spent = sum(e.amount for e in expenses if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES)

    # CC outstanding all-time
    all_expenses = db.query(Expense).filter(Expense.user_id == user_id).all()
    if excluded:
        all_expenses = [e for e in all_expenses if _source_to_bank(e.source or "").lower() not in [b.lower() for b in excluded]]

    cc_charges: dict[str, float] = defaultdict(float)
    cc_payments: dict[str, float] = defaultdict(float)
    for e in all_expenses:
        if _is_cc_source(e.source or ""):
            bank = _source_to_bank(e.source or "")
            if e.amount > 0:
                cc_charges[bank] += e.amount
            else:
                cc_payments[bank] += abs(e.amount)

    cc_outstanding = {}
    total_cc_debt = 0.0
    for bank in sorted(set(cc_charges) | set(cc_payments)):
        outstanding = max(cc_charges.get(bank, 0) - cc_payments.get(bank, 0), 0)
        cc_outstanding[bank] = round(outstanding, 2)
        total_cc_debt += outstanding

    return json.dumps({
        "total_salary_income_received": round(total_income, 2),
        "total_spent_debits": round(total_spent, 2),
        "net_cashflow": round(total_income - total_spent, 2),
        "cc_outstanding_by_bank": cc_outstanding,
        "total_cc_debt": round(total_cc_debt, 2),
        "note": "Income = salary received. Spent = all debits excluding self-transfers. CC outstanding = charges minus payments, all-time.",
    })


def _exec_compare_periods(db: Session, user_id: int, params: dict) -> str:
    p1_start = _parse_date(params.get("period1_start", ""))
    p1_end = _parse_date(params.get("period1_end", ""))
    p2_start = _parse_date(params.get("period2_start", ""))
    p2_end = _parse_date(params.get("period2_end", ""))

    if not all([p1_start, p1_end, p2_start, p2_end]):
        return json.dumps({"error": "All four dates are required."})

    excluded = _get_excluded_banks(db, user_id)

    def _summarize(s, e):
        expenses = db.query(Expense).filter(
            Expense.user_id == user_id,
            Expense.date >= datetime.combine(s, datetime.min.time()),
            Expense.date <= datetime.combine(e, datetime.max.time()),
        ).all()
        if excluded:
            expenses = [x for x in expenses if _source_to_bank(x.source or "").lower() not in [b.lower() for b in excluded]]
        total = sum(x.amount for x in expenses if x.amount > 0 and x.category not in EXCLUDED_SPEND_CATEGORIES)
        by_cat = defaultdict(float)
        for x in expenses:
            if x.amount > 0 and x.category not in EXCLUDED_SPEND_CATEGORIES:
                by_cat[x.category] += x.amount
        return {"period": f"{s} to {e}", "total_spent": round(total, 2), "by_category": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda x: -x[1])}}

    p1 = _summarize(p1_start, p1_end)
    p2 = _summarize(p2_start, p2_end)
    diff = p2["total_spent"] - p1["total_spent"]
    pct = round((diff / p1["total_spent"]) * 100, 1) if p1["total_spent"] > 0 else None

    return json.dumps({"period1": p1, "period2": p2, "difference": round(diff, 2), "change_percent": pct})


def _exec_subscriptions(db: Session, user_id: int, params: dict) -> str:
    subs = detect_subscriptions(db, user_id=user_id)
    result = []
    for s in subs:
        result.append({
            "name": s.name, "amount": s.amount, "frequency": s.frequency,
            "last_charged": s.last_charged.isoformat() if s.last_charged else None,
            "next_expected": s.next_expected.isoformat() if s.next_expected else None,
            "total_spent": s.total_spent, "occurrence_count": s.occurrence_count,
        })
    return json.dumps({"subscriptions": result, "count": len(result), "total_monthly": round(sum(s.amount for s in subs), 2)})


def _exec_update_category(db: Session, user_id: int, params: dict) -> str:
    txn_id = params.get("transaction_id")
    new_cat = params.get("new_category", "").lower()

    valid_cats = {"food", "transport", "shopping", "entertainment", "bills", "subscriptions",
                  "health", "education", "groceries", "rent", "home", "personal care",
                  "investment", "emi", "transfer", "lent", "borrowed", "atm", "salary", "other"}
    if new_cat not in valid_cats:
        return json.dumps({"error": f"Invalid category '{new_cat}'. Valid: {', '.join(sorted(valid_cats))}"})

    expense = db.query(Expense).filter(Expense.id == txn_id, Expense.user_id == user_id).first()
    if not expense:
        return json.dumps({"error": f"Transaction {txn_id} not found."})

    old_cat = expense.category
    expense.category = new_cat
    db.commit()

    return json.dumps({
        "success": True,
        "transaction_id": txn_id,
        "old_category": old_cat,
        "new_category": new_cat,
        "description": expense.description,
        "amount": expense.amount,
    })


def _exec_bulk_recategorize(db: Session, user_id: int, params: dict) -> str:
    keyword = params.get("keyword", "").strip()
    new_cat = params.get("new_category", "").lower()

    if not keyword:
        return json.dumps({"error": "Keyword is required."})

    valid_cats = {"food", "transport", "shopping", "entertainment", "bills", "subscriptions",
                  "health", "education", "groceries", "rent", "home", "personal care",
                  "investment", "emi", "transfer", "lent", "borrowed", "atm", "salary", "other"}
    if new_cat not in valid_cats:
        return json.dumps({"error": f"Invalid category '{new_cat}'."})

    matches = db.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.description.ilike(f"%{keyword}%"),
    ).all()

    if not matches:
        return json.dumps({"updated": 0, "message": f"No transactions matching '{keyword}'."})

    updated = 0
    for e in matches:
        if e.category != new_cat:
            e.category = new_cat
            updated += 1

    # Save rule for future auto-categorization
    existing_rule = db.query(CategoryRule).filter(
        CategoryRule.user_id == user_id,
        CategoryRule.keyword == keyword.lower(),
    ).first()
    if existing_rule:
        existing_rule.category = new_cat
    else:
        db.add(CategoryRule(user_id=user_id, keyword=keyword.lower(), category=new_cat))

    db.commit()

    return json.dumps({
        "updated": updated,
        "total_matches": len(matches),
        "keyword": keyword,
        "new_category": new_cat,
        "rule_saved": True,
        "message": f"Updated {updated} transactions and saved rule: '{keyword}' → {new_cat}",
    })


def _exec_delete_transaction(db: Session, user_id: int, params: dict) -> str:
    txn_id = params.get("transaction_id")

    expense = db.query(Expense).filter(Expense.id == txn_id, Expense.user_id == user_id).first()
    if not expense:
        return json.dumps({"error": f"Transaction {txn_id} not found."})

    details = {
        "id": expense.id,
        "amount": expense.amount,
        "description": expense.description,
        "date": expense.date.strftime("%Y-%m-%d") if expense.date else "",
        "category": expense.category,
    }

    # Unlink if it was a linked transfer
    if expense.linked_transaction_id:
        other = db.query(Expense).filter(Expense.id == expense.linked_transaction_id).first()
        if other:
            other.linked_transaction_id = None

    db.delete(expense)
    db.commit()

    return json.dumps({"success": True, "deleted": details})


def _exec_daily_spending(db: Session, user_id: int, params: dict) -> str:
    start = _parse_date(params.get("start_date", ""))
    end = _parse_date(params.get("end_date", ""))
    if not start or not end:
        start, end = _get_month_range()

    expenses = db.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.date >= datetime.combine(start, datetime.min.time()),
        Expense.date <= datetime.combine(end, datetime.max.time()),
        Expense.amount > 0,
    ).all()

    excluded = _get_excluded_banks(db, user_id)
    if excluded:
        expenses = [e for e in expenses if _source_to_bank(e.source or "").lower() not in [b.lower() for b in excluded]]

    expenses = [e for e in expenses if e.category not in EXCLUDED_SPEND_CATEGORIES]

    by_day = defaultdict(float)
    by_day_count = defaultdict(int)
    for e in expenses:
        d = e.date.strftime("%Y-%m-%d") if e.date else "unknown"
        by_day[d] += e.amount
        by_day_count[d] += 1

    days = sorted(by_day.keys())
    daily = [{"date": d, "amount": round(by_day[d], 2), "transactions": by_day_count[d]} for d in days]
    total = sum(by_day.values())
    avg = total / len(days) if days else 0

    return json.dumps({
        "period": f"{start} to {end}",
        "days": daily,
        "total": round(total, 2),
        "daily_average": round(avg, 2),
        "highest_day": max(daily, key=lambda x: x["amount"]) if daily else None,
        "lowest_day": min(daily, key=lambda x: x["amount"]) if daily else None,
    })


TOOL_EXECUTORS = {
    "search_transactions": _exec_search_transactions,
    "get_spending_summary": _exec_spending_summary,
    "get_networth": _exec_networth,
    "compare_periods": _exec_compare_periods,
    "get_subscriptions": _exec_subscriptions,
    "update_transaction_category": _exec_update_category,
    "bulk_recategorize": _exec_bulk_recategorize,
    "delete_transaction": _exec_delete_transaction,
    "get_daily_spending": _exec_daily_spending,
}


# ── Chat logging ──────────────────────────────────────────────

CHAT_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

def _log_chat(user_id: int, entry: str):
    """Append a log entry to the chat debug log."""
    try:
        os.makedirs(CHAT_LOG_DIR, exist_ok=True)
        log_path = os.path.join(CHAT_LOG_DIR, f"chat_log_{user_id}.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] {entry}\n")
    except Exception:
        pass


# ── OpenRouter (OpenAI-compatible) provider ───────────────────

def _convert_tools_to_openai_format():
    """Convert Anthropic tool format to OpenAI function-calling format."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}} for t in TOOLS]


def _run_openrouter(api_key: str, model: str, system: str, messages: list, chunk_queue, db, user_id: int):
    """Run chat via OpenRouter (OpenAI-compatible API) with tool use."""
    import httpx

    openai_tools = _convert_tools_to_openai_format()
    openai_messages = [{"role": "system", "content": system}] + messages

    try:
        max_iterations = 8
        for iteration in range(max_iterations):
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": openai_messages, "tools": openai_tools, "max_tokens": 2048, "stream": False},
                timeout=60,
            )
            if resp.status_code != 200:
                _log_chat(user_id, f"[OpenRouter error] {resp.status_code}: {resp.text[:500]}")
                chunk_queue.put(f"data: {json.dumps({'type': 'text', 'content': f'OpenRouter error: {resp.status_code}'})}\n\n")
                break

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            msg = choice.get("message", {})
            finish = choice.get("finish_reason", "stop")

            _log_chat(user_id, f"[OpenRouter iter {iteration}] finish={finish}, content={bool(msg.get('content'))}, tool_calls={len(msg.get('tool_calls', []))}")

            # Stream the text content
            if msg.get("content"):
                words = msg["content"].split(" ")
                for i, word in enumerate(words):
                    chunk = word if i == 0 else " " + word
                    chunk_queue.put(f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n")

            # Handle tool calls
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                # Build the assistant message exactly as OpenAI expects
                assistant_msg = {"role": "assistant", "content": msg.get("content") or None, "tool_calls": []}
                for tc in tool_calls:
                    assistant_msg["tool_calls"].append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]},
                    })
                openai_messages.append(assistant_msg)

                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    try:
                        tool_input = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_input = {}

                    chunk_queue.put(f"data: {json.dumps({'type': 'tool_use', 'name': tool_name})}\n\n")
                    _log_chat(user_id, f"[Tool call] {tool_name}({json.dumps(tool_input)})")

                    executor = TOOL_EXECUTORS.get(tool_name)
                    result = executor(db, user_id, tool_input) if executor else json.dumps({"error": f"Unknown tool: {tool_name}"})
                    _log_chat(user_id, f"[Tool result] {result[:300]}")

                    openai_messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                continue
            else:
                break

    except Exception as e:
        _log_chat(user_id, f"[OpenRouter exception] {str(e)}")
        chunk_queue.put(f"data: {json.dumps({'type': 'text', 'content': f'Error: {str(e)}'})}\n\n")
    finally:
        chunk_queue.put(None)


# ── Anthropic provider ────────────────────────────────────────

def _run_anthropic(api_key: str, model: str, system: str, messages: list, chunk_queue, db, user_id: int):
    """Run chat via Anthropic API with streaming + tool use."""
    client = anthropic.Anthropic(api_key=api_key)

    try:
        max_iterations = 8
        for _ in range(max_iterations):
            collected_text = ""
            tool_uses = []
            stop_reason = None

            with client.messages.stream(
                model=model, max_tokens=2048, system=system,
                messages=messages, tools=TOOLS,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        if hasattr(event.content_block, "type") and event.content_block.type == "tool_use":
                            tool_uses.append({"id": event.content_block.id, "name": event.content_block.name, "input_json": ""})
                            chunk_queue.put(f"data: {json.dumps({'type': 'tool_use', 'name': event.content_block.name})}\n\n")
                    elif event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            collected_text += event.delta.text
                            chunk_queue.put(f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n")
                        elif hasattr(event.delta, "partial_json") and tool_uses:
                            tool_uses[-1]["input_json"] += event.delta.partial_json

                final_message = stream.get_final_message()
                stop_reason = final_message.stop_reason

            if stop_reason == "tool_use" and tool_uses:
                assistant_content = []
                if collected_text:
                    assistant_content.append({"type": "text", "text": collected_text})
                for tu in tool_uses:
                    try:
                        tool_input = json.loads(tu["input_json"]) if tu["input_json"] else {}
                    except json.JSONDecodeError:
                        tool_input = {}
                    assistant_content.append({"type": "tool_use", "id": tu["id"], "name": tu["name"], "input": tool_input})

                messages.append({"role": "assistant", "content": assistant_content})

                tool_results = []
                for tu in tool_uses:
                    try:
                        tool_input = json.loads(tu["input_json"]) if tu["input_json"] else {}
                    except json.JSONDecodeError:
                        tool_input = {}
                    executor = TOOL_EXECUTORS.get(tu["name"])
                    result = executor(db, user_id, tool_input) if executor else json.dumps({"error": f"Unknown tool: {tu['name']}"})
                    tool_results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": result})

                messages.append({"role": "user", "content": tool_results})
                continue
            else:
                break

    except anthropic.APIError as e:
        error_msg = str(e).lower()
        if "credit" in error_msg or "balance" in error_msg or "billing" in error_msg:
            # Credit exhausted — signal fallback
            chunk_queue.put("__FALLBACK__")
            return
        chunk_queue.put(f"data: {json.dumps({'type': 'text', 'content': f'API error: {str(e)}'})}\n\n")
    except Exception as e:
        chunk_queue.put(f"data: {json.dumps({'type': 'text', 'content': f'Error: {str(e)}'})}\n\n")
    finally:
        chunk_queue.put(None)


@router.post("")
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat with the LLM finance assistant. Returns SSE stream."""
    anthropic_key = os.getenv("LLM_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    provider = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic", "openrouter", or "auto"
    anthropic_model = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
    openrouter_model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4-5-20251001")

    if not anthropic_key and not openrouter_key:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'text', 'content': 'No LLM API key configured.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    messages = []
    for msg in req.history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": req.message})

    _log_chat(current_user.id, f"[User] {req.message}")

    system = SYSTEM_PROMPT.format(today=date.today().isoformat())

    import queue
    chunk_queue: queue.Queue = queue.Queue()

    def _run():
        use_anthropic = provider in ("anthropic", "auto") and anthropic_key
        use_openrouter = provider == "openrouter" or (not anthropic_key and openrouter_key)

        if use_anthropic and not use_openrouter:
            _run_anthropic(anthropic_key, anthropic_model, system, messages, chunk_queue, db, current_user.id)

            # Check if Anthropic signaled fallback (credit exhausted)
            # The sentinel None is already in the queue; check if __FALLBACK__ was sent
        elif use_openrouter:
            _run_openrouter(openrouter_key, openrouter_model, system, messages, chunk_queue, db, current_user.id)
        else:
            # Auto mode: try Anthropic first, fallback to OpenRouter
            _run_anthropic(anthropic_key, anthropic_model, system, messages, chunk_queue, db, current_user.id)

    async def event_stream():
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _run)

        fallback_needed = False
        while True:
            try:
                chunk = await asyncio.to_thread(chunk_queue.get, timeout=60)
            except Exception:
                break
            if chunk is None:
                break
            if chunk == "__FALLBACK__":
                fallback_needed = True
                # Drain the sentinel
                try:
                    await asyncio.to_thread(chunk_queue.get, timeout=2)
                except Exception:
                    pass
                break
            yield chunk

        # Fallback to OpenRouter if Anthropic credit exhausted
        if fallback_needed and openrouter_key:
            fallback_queue: queue.Queue = queue.Queue()
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, lambda: _run_openrouter(
                openrouter_key, openrouter_model, system, messages, fallback_queue, db, current_user.id
            ))
            while True:
                try:
                    chunk = await asyncio.to_thread(fallback_queue.get, timeout=60)
                except Exception:
                    break
                if chunk is None:
                    break
                yield chunk
        elif fallback_needed:
            yield f"data: {json.dumps({'type': 'text', 'content': 'Anthropic credits exhausted and no backup configured. Set OPENROUTER_API_KEY.'})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
