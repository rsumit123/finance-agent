"""SMS sync endpoint — accepts bank SMS messages from mobile app."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import AccountBalance, User
from ..services.sms_parser import parse_sms
from ..services.tracker import create_expenses_bulk_dedup

router = APIRouter(prefix="/api/sms", tags=["sms"])


class SmsMessage(BaseModel):
    body: str
    sender: str = ""
    date: str = ""  # ISO string or timestamp


class SmsSyncRequest(BaseModel):
    messages: list[SmsMessage]


@router.post("/sync")
def sync_sms(
    request: SmsSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parse bank SMS messages and import transactions."""
    from ..parsers.categorizer import classify_category

    parsed_expenses = []
    balances_extracted = []
    skipped = 0

    for msg in request.messages:
        result = parse_sms(msg.body, msg.sender, msg.date, user_name=current_user.name or "")

        if result["expense"]:
            parsed_expenses.append(result["expense"])

        if result["balance"] is not None:
            balances_extracted.append({
                "bank": result["bank"],
                "account_hint": result["account_hint"],
                "balance": result["balance"],
                "date": result["expense"].date if result["expense"] else datetime.now(),
            })

        if not result["expense"] and result["balance"] is None:
            skipped += 1

    # Dedup and save transactions
    imported_count = 0
    dup_count = 0
    if parsed_expenses:
        imported, duplicates = create_expenses_bulk_dedup(db, parsed_expenses, user_id=current_user.id)
        imported_count = len(imported)
        dup_count = len(duplicates)

        # Auto-recategorize with user's name
        from ..services.gmail_sync import _recategorize_others
        _recategorize_others(db, imported, current_user.id)

    # Save balances
    balances_saved = 0
    for bal in balances_extracted:
        # Only save if newer than existing
        existing = db.query(AccountBalance).filter(
            AccountBalance.user_id == current_user.id,
            AccountBalance.bank_name == bal["bank"],
            AccountBalance.account_hint == bal["account_hint"],
        ).order_by(AccountBalance.balance_date.desc()).first()

        if not existing or bal["date"] > existing.balance_date:
            db.add(AccountBalance(
                user_id=current_user.id,
                bank_name=bal["bank"],
                account_hint=bal["account_hint"],
                balance=bal["balance"],
                balance_date=bal["date"],
                source="sms",
            ))
            balances_saved += 1

    db.commit()

    return {
        "imported": imported_count,
        "duplicates": dup_count,
        "skipped": skipped,
        "messages_processed": len(request.messages),
        "balances_extracted": balances_saved,
    }


@router.get("/balances")
def get_balances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest known balance per account."""
    from sqlalchemy import func

    # Get latest balance per bank+account combo
    subq = db.query(
        AccountBalance.bank_name,
        AccountBalance.account_hint,
        func.max(AccountBalance.balance_date).label("max_date"),
    ).filter(
        AccountBalance.user_id == current_user.id,
    ).group_by(
        AccountBalance.bank_name,
        AccountBalance.account_hint,
    ).subquery()

    latest = db.query(AccountBalance).join(
        subq,
        (AccountBalance.bank_name == subq.c.bank_name) &
        (AccountBalance.account_hint == subq.c.account_hint) &
        (AccountBalance.balance_date == subq.c.max_date) &
        (AccountBalance.user_id == current_user.id),
    ).all()

    accounts = []
    total_balance = 0
    for bal in latest:
        accounts.append({
            "bank": bal.bank_name,
            "account_hint": bal.account_hint,
            "balance": bal.balance,
            "as_of": bal.balance_date.isoformat(),
            "source": bal.source,
        })
        total_balance += bal.balance

    return {
        "accounts": accounts,
        "total_balance": round(total_balance, 2),
    }
