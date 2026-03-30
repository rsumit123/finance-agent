"""LLM-powered finance chat endpoint with tool use and SSE streaming."""

import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Expense, User, UserPreference
from ..services.subscriptions import detect_subscriptions

router = APIRouter(prefix="/api/chat", tags=["chat"])

EXCLUDED_SPEND_CATEGORIES = {"transfer", "lent", "borrowed"}

SYSTEM_PROMPT = (
    "You are a helpful personal finance assistant for MoneyFlow. "
    "You help users understand their spending, find transactions, and make better financial decisions. "
    "Be concise and use \u20b9 for amounts. Format numbers in Indian style (1,00,000). "
    "When asked about spending, always call the appropriate tool first rather than guessing."
)

TOOLS = [
    {
        "name": "search_transactions",
        "description": (
            "Search expenses by keyword, category, date range, or bank/source. "
            "Returns a list of matching transactions with amount, category, description, date, and source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Search keyword to match against transaction descriptions",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category (food, transport, shopping, entertainment, bills, health, education, groceries, rent, salary, transfer, atm, emi, other)",
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
                "bank": {
                    "type": "string",
                    "description": "Bank name to filter by (matches against source field, e.g. 'hdfc', 'axis', 'icici')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 20)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_spending_summary",
        "description": (
            "Get total spent, total income, and spending breakdown by category for a given period. "
            "Use this when the user asks about how much they spent, income, or category-wise breakdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
                "period": {
                    "type": "string",
                    "description": "Shorthand period: 'month' for current month, 'week' for current week. Overrides start/end dates.",
                    "enum": ["month", "week"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_networth",
        "description": (
            "Get financial overview: total income, total spent, net cashflow, and credit card outstanding amounts. "
            "Use this when the user asks about net worth, overall financial position, or CC debt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "Period: 'month', 'week', or omit for all-time",
                    "enum": ["month", "week"],
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
            },
            "required": [],
        },
    },
    {
        "name": "compare_periods",
        "description": (
            "Compare spending between two time periods. Returns total spent and by-category breakdown for each period. "
            "Use when user asks to compare months, weeks, or any two date ranges."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period1_start": {
                    "type": "string",
                    "description": "First period start date (YYYY-MM-DD)",
                },
                "period1_end": {
                    "type": "string",
                    "description": "First period end date (YYYY-MM-DD)",
                },
                "period2_start": {
                    "type": "string",
                    "description": "Second period start date (YYYY-MM-DD)",
                },
                "period2_end": {
                    "type": "string",
                    "description": "Second period end date (YYYY-MM-DD)",
                },
            },
            "required": ["period1_start", "period1_end", "period2_start", "period2_end"],
        },
    },
    {
        "name": "get_subscriptions",
        "description": (
            "List detected recurring/subscription payments based on expense history. "
            "Returns name, average amount, frequency, last charged date, and total spent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
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
    for name in ["hdfc", "axis", "scapia", "icici", "sbi", "kotak"]:
        if name in s:
            return name.upper() if name != "scapia" else "Scapia"
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


def _fmt_inr(n: float) -> str:
    """Format number in Indian style."""
    if n < 0:
        return "-" + _fmt_inr(abs(n))
    n = round(n, 2)
    s = f"{n:,.2f}"
    # Convert to Indian format
    parts = s.split(".")
    integer_part = parts[0].replace(",", "")
    decimal_part = parts[1]

    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:] if len(rest) >= 2 else rest)
            rest = rest[:-2]
        groups.reverse()
        formatted = ",".join(groups) + "," + last3

    return formatted + "." + decimal_part


# ── Tool implementations ──────────────────────────────────────


def _exec_search_transactions(db: Session, user_id: int, params: dict) -> str:
    q = db.query(Expense).filter(Expense.user_id == user_id)

    keyword = params.get("keyword")
    category = params.get("category")
    start = _parse_date(params.get("start_date", ""))
    end = _parse_date(params.get("end_date", ""))
    bank = params.get("bank", "")
    limit = min(params.get("limit", 20), 50)

    if start:
        q = q.filter(Expense.date >= start)
    if end:
        q = q.filter(Expense.date <= end)
    if category:
        q = q.filter(Expense.category == category.lower())
    if keyword:
        q = q.filter(Expense.description.ilike(f"%{keyword}%"))
    if bank:
        q = q.filter(Expense.source.ilike(f"%{bank.lower()}%"))

    results = q.order_by(Expense.date.desc()).limit(limit).all()

    if not results:
        return json.dumps({"count": 0, "transactions": [], "message": "No matching transactions found."})

    txns = []
    for e in results:
        txns.append({
            "amount": e.amount,
            "category": e.category,
            "description": e.description or "",
            "date": e.date.strftime("%Y-%m-%d") if e.date else "",
            "source": _source_to_bank(e.source or ""),
            "payment_method": e.payment_method or "",
        })

    return json.dumps({"count": len(txns), "transactions": txns})


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
        .filter(Expense.user_id == user_id, Expense.date >= start, Expense.date <= end)
        .all()
    )

    excluded = _get_excluded_banks(db, user_id)
    if excluded:
        expenses = [e for e in expenses if _source_to_bank(e.source or "").lower() not in [b.lower() for b in excluded]]

    total_income = sum(abs(e.amount) for e in expenses if e.category == "salary")
    total_spent = sum(e.amount for e in expenses if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES)

    by_category = defaultdict(float)
    for e in expenses:
        if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES:
            by_category[e.category] += e.amount

    # Sort by amount desc
    sorted_cats = sorted(by_category.items(), key=lambda x: -x[1])

    return json.dumps({
        "period": f"{start} to {end}",
        "total_spent": round(total_spent, 2),
        "total_income": round(total_income, 2),
        "transaction_count": len(expenses),
        "by_category": {k: round(v, 2) for k, v in sorted_cats},
    })


def _exec_networth(db: Session, user_id: int, params: dict) -> str:
    period = params.get("period")
    start = _parse_date(params.get("start_date", ""))
    end = _parse_date(params.get("end_date", ""))

    if start and end:
        q = db.query(Expense).filter(Expense.user_id == user_id, Expense.date >= start, Expense.date <= end)
    elif period == "month":
        s, e = _get_month_range()
        q = db.query(Expense).filter(Expense.user_id == user_id, Expense.date >= s, Expense.date <= e)
    elif period == "week":
        s, e = _get_week_range()
        q = db.query(Expense).filter(Expense.user_id == user_id, Expense.date >= s, Expense.date <= e)
    else:
        q = db.query(Expense).filter(Expense.user_id == user_id)

    expenses = q.all()
    excluded = _get_excluded_banks(db, user_id)
    if excluded:
        expenses = [e for e in expenses if _source_to_bank(e.source or "").lower() not in [b.lower() for b in excluded]]

    total_income = sum(abs(e.amount) for e in expenses if e.category == "salary")
    total_spent = sum(e.amount for e in expenses if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES)

    # CC outstanding from all-time data
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
        "total_income": round(total_income, 2),
        "total_spent": round(total_spent, 2),
        "net_cashflow": round(total_income - total_spent, 2),
        "cc_outstanding": cc_outstanding,
        "total_cc_debt": round(total_cc_debt, 2),
    })


def _exec_compare_periods(db: Session, user_id: int, params: dict) -> str:
    p1_start = _parse_date(params.get("period1_start", ""))
    p1_end = _parse_date(params.get("period1_end", ""))
    p2_start = _parse_date(params.get("period2_start", ""))
    p2_end = _parse_date(params.get("period2_end", ""))

    if not all([p1_start, p1_end, p2_start, p2_end]):
        return json.dumps({"error": "All four dates are required."})

    excluded = _get_excluded_banks(db, user_id)

    def _summarize(start, end):
        expenses = (
            db.query(Expense)
            .filter(Expense.user_id == user_id, Expense.date >= start, Expense.date <= end)
            .all()
        )
        if excluded:
            expenses = [e for e in expenses if _source_to_bank(e.source or "").lower() not in [b.lower() for b in excluded]]

        total = sum(e.amount for e in expenses if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES)
        by_cat = defaultdict(float)
        for e in expenses:
            if e.amount > 0 and e.category not in EXCLUDED_SPEND_CATEGORIES:
                by_cat[e.category] += e.amount
        return {
            "period": f"{start} to {end}",
            "total_spent": round(total, 2),
            "by_category": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda x: -x[1])},
        }

    p1 = _summarize(p1_start, p1_end)
    p2 = _summarize(p2_start, p2_end)

    diff = p2["total_spent"] - p1["total_spent"]
    pct = round((diff / p1["total_spent"]) * 100, 1) if p1["total_spent"] > 0 else None

    return json.dumps({
        "period1": p1,
        "period2": p2,
        "difference": round(diff, 2),
        "change_percent": pct,
    })


def _exec_subscriptions(db: Session, user_id: int, params: dict) -> str:
    subs = detect_subscriptions(db, user_id=user_id)
    result = []
    for s in subs:
        result.append({
            "name": s.name,
            "amount": s.amount,
            "frequency": s.frequency,
            "last_charged": s.last_charged.isoformat() if s.last_charged else None,
            "next_expected": s.next_expected.isoformat() if s.next_expected else None,
            "total_spent": s.total_spent,
            "occurrence_count": s.occurrence_count,
        })
    return json.dumps({"subscriptions": result, "count": len(result)})


TOOL_EXECUTORS = {
    "search_transactions": _exec_search_transactions,
    "get_spending_summary": _exec_spending_summary,
    "get_networth": _exec_networth,
    "compare_periods": _exec_compare_periods,
    "get_subscriptions": _exec_subscriptions,
}


@router.post("")
async def chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat with the LLM finance assistant. Returns SSE stream."""
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'text', 'content': 'LLM API key not configured. Please set LLM_API_KEY environment variable.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    client = anthropic.Anthropic(api_key=api_key)

    # Build messages from history + new message
    messages = []
    for msg in req.history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": req.message})

    async def event_stream():
        nonlocal messages
        try:
            # Loop to handle tool use -> response cycles
            max_iterations = 5
            for _ in range(max_iterations):
                # Make the API call with streaming
                collected_text = ""
                tool_uses = []
                stop_reason = None

                with client.messages.stream(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=TOOLS,
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_start":
                            if hasattr(event.content_block, "type"):
                                if event.content_block.type == "tool_use":
                                    tool_uses.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input_json": "",
                                    })
                                    # Send tool use indicator
                                    yield f"data: {json.dumps({'type': 'tool_use', 'name': event.content_block.name, 'input': {}})}\n\n"

                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                collected_text += event.delta.text
                                yield f"data: {json.dumps({'type': 'text', 'content': event.delta.text})}\n\n"
                            elif hasattr(event.delta, "partial_json"):
                                if tool_uses:
                                    tool_uses[-1]["input_json"] += event.delta.partial_json

                    # Get the final message to check stop reason
                    final_message = stream.get_final_message()
                    stop_reason = final_message.stop_reason

                # If the model wants to use tools, execute them
                if stop_reason == "tool_use" and tool_uses:
                    # Build the assistant message with all content blocks
                    assistant_content = []
                    if collected_text:
                        assistant_content.append({"type": "text", "text": collected_text})
                    for tu in tool_uses:
                        try:
                            tool_input = json.loads(tu["input_json"]) if tu["input_json"] else {}
                        except json.JSONDecodeError:
                            tool_input = {}
                        assistant_content.append({
                            "type": "tool_use",
                            "id": tu["id"],
                            "name": tu["name"],
                            "input": tool_input,
                        })

                    messages.append({"role": "assistant", "content": assistant_content})

                    # Execute each tool and build tool results
                    tool_results = []
                    for tu in tool_uses:
                        try:
                            tool_input = json.loads(tu["input_json"]) if tu["input_json"] else {}
                        except json.JSONDecodeError:
                            tool_input = {}

                        executor = TOOL_EXECUTORS.get(tu["name"])
                        if executor:
                            result = executor(db, current_user.id, tool_input)
                        else:
                            result = json.dumps({"error": f"Unknown tool: {tu['name']}"})

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": result,
                        })

                    messages.append({"role": "user", "content": tool_results})
                    # Continue the loop to get the final response
                    continue
                else:
                    # No more tool calls, we're done
                    break

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except anthropic.APIError as e:
            yield f"data: {json.dumps({'type': 'text', 'content': f'API error: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'text', 'content': f'Error: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
