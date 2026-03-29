"""SMS sync endpoint — accepts bank SMS messages from mobile app."""

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import re

from ..auth import get_current_user
from ..database import get_db
from ..models import AccountBalance, User
from ..schemas import ExpenseCreate
from ..services.sms_parser import parse_sms
from ..services.tracker import create_expenses_bulk_dedup

SMS_DUMP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
os.makedirs(SMS_DUMP_DIR, exist_ok=True)

router = APIRouter(prefix="/api/sms", tags=["sms"])


class ParsedInfo(BaseModel):
    type: str = ""  # debit or credit
    amount: float = 0
    merchant: str = ""
    reference_id: str = ""
    account_type: str = ""
    account_number: str = ""
    account_name: str = ""
    balance: Optional[float] = None


class SmsMessage(BaseModel):
    body: str
    sender: str = ""
    date: str = ""
    parsed: Optional[ParsedInfo] = None  # Pre-parsed by frontend library


class SmsSyncRequest(BaseModel):
    messages: list[SmsMessage]


@router.post("/sync")
def sync_sms(
    request: SmsSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import SMS transactions. Accepts pre-parsed data from frontend."""
    from ..parsers.categorizer import classify_category

    # Dump raw incoming SMS for debugging
    try:
        dump_path = os.path.join(SMS_DUMP_DIR, f"sms_dump_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(dump_path, "w") as f:
            json.dump([m.model_dump() for m in request.messages], f, indent=2, default=str)
    except Exception as e:
        print(f"SMS dump error: {e}")

    parsed_expenses = []
    balances_extracted = []
    skipped = 0

    for msg in request.messages:
        if msg.parsed and msg.parsed.amount > 0:
            # Use pre-parsed data from transaction-sms-parser (frontend)
            is_credit = msg.parsed.type == "credit"
            amount = msg.parsed.amount

            # Determine bank from sender
            bank = _detect_bank_from_sender(msg.sender)

            # Determine payment method
            acct_type = msg.parsed.account_type.upper()
            if acct_type == "CARD":
                payment_method = "credit_card"
            elif acct_type == "WALLET":
                payment_method = "upi"
            else:
                payment_method = "debit_card"

            # Build source tag
            is_cc = acct_type == "CARD"
            source = f"sms_{bank}_{'cc' if is_cc else 'bank'}" if bank else "sms_unknown"

            # Parse date
            txn_date = _parse_sms_date(msg.date) or datetime.now()

            # Store original SMS in reference_id
            ref = msg.parsed.reference_id if msg.parsed.reference_id else f"sms:{msg.body[:150]}"

            description = msg.parsed.merchant or msg.parsed.account_name or "Bank Transaction"

            expense = ExpenseCreate(
                amount=-amount if is_credit else amount,
                category=classify_category(description, source=source, user_name=current_user.name or ""),
                payment_method=payment_method,
                description=description[:200],
                date=txn_date,
                source=source,
                reference_id=ref,
            )
            parsed_expenses.append(expense)

            if msg.parsed.balance is not None:
                balances_extracted.append({
                    "bank": bank or "unknown",
                    "account_hint": msg.parsed.account_number or "",
                    "balance": msg.parsed.balance,
                    "date": txn_date,
                })
        else:
            # Fallback: use backend parser
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


@router.post("/test-parse")
def test_parse_sms(
    request: SmsSyncRequest,
    current_user: User = Depends(get_current_user),
):
    """Dry-run: show what the parser would do with each SMS. No DB writes."""
    from ..parsers.categorizer import classify_category

    results = []
    for msg in request.messages:
        entry = {
            "sender": msg.sender,
            "body": msg.body[:200],
            "date": msg.date,
        }

        # Check frontend library parse
        if msg.parsed and msg.parsed.amount > 0:
            bank = _detect_bank_from_sender(msg.sender)
            entry["source"] = "library"
            entry["action"] = "import"
            entry["parsed"] = {
                "type": msg.parsed.type,
                "amount": msg.parsed.amount,
                "merchant": msg.parsed.merchant,
                "bank": bank,
                "account_type": msg.parsed.account_type,
                "balance": msg.parsed.balance,
            }
        else:
            # Try backend parser
            result = parse_sms(msg.body, msg.sender, msg.date, user_name=current_user.name or "")
            if result["expense"]:
                entry["source"] = "backend"
                entry["action"] = "import"
                entry["parsed"] = {
                    "type": "credit" if result["is_credit"] else "debit",
                    "amount": abs(result["expense"].amount),
                    "merchant": result["expense"].description,
                    "bank": result["bank"],
                    "category": result["expense"].category,
                    "balance": result["balance"],
                }
            else:
                entry["source"] = "none"
                entry["action"] = "skip"
                entry["reason"] = "no parser matched"

        results.append(entry)

    imported = [r for r in results if r["action"] == "import"]
    skipped = [r for r in results if r["action"] == "skip"]
    return {
        "total": len(results),
        "would_import": len(imported),
        "would_skip": len(skipped),
        "results": results,
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


def _detect_bank_from_sender(sender: str) -> str:
    s = (sender or "").upper()
    bank_map = {
        "hdfc": ["HDFC"], "axis": ["AXIS"], "sbi": ["SBI"],
        "kotak": ["KOTAK"], "scapia": ["SCAPIA", "FEDBK", "FED", "FEDSCP"],
        "icici": ["ICICI"], "bob": ["BOB", "BARODA"], "idfc": ["IDFC"],
        "yes_bank": ["YESBK"], "indusind": ["INDUS"],
        "citi": ["CITI"], "hsbc": ["HSBC"],
    }
    for bank, patterns in bank_map.items():
        if any(p in s for p in patterns):
            return bank
    return ""


def _parse_sms_date(date_str: str):
    if not date_str:
        return None
    try:
        return datetime.fromtimestamp(int(date_str) / 1000)
    except (ValueError, TypeError, OSError):
        pass
    try:
        return datetime.fromisoformat(date_str.replace("Z", ""))
    except ValueError:
        pass
    return None
