"""Card management endpoints — auto-detect and manage credit cards/bank accounts."""

import re
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Card, Expense, User

router = APIRouter(prefix="/api/cards", tags=["cards"])


class CardOut(BaseModel):
    id: int
    bank_name: str
    card_type: str
    last_four: str
    nickname: str
    source_prefix: str

    model_config = {"from_attributes": True}


class CardUpdate(BaseModel):
    nickname: str = None
    last_four: str = None


@router.get("/", response_model=list[CardOut])
def list_cards(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List user's detected cards/accounts."""
    return db.query(Card).filter(Card.user_id == current_user.id).all()


@router.post("/detect")
def detect_cards(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Auto-detect cards from imported transactions' source fields."""
    expenses = db.query(Expense).filter(Expense.user_id == current_user.id).all()

    # Find unique source prefixes
    source_map = defaultdict(int)
    for e in expenses:
        source_map[e.source] += 1

    existing = {c.source_prefix: c for c in db.query(Card).filter(Card.user_id == current_user.id).all()}
    created = 0

    for source, count in source_map.items():
        if source in existing or source == "manual" or not source:
            continue

        bank_name = _source_to_bank(source)
        card_type = "credit_card" if _is_cc_source(source) else "bank_account"

        # Try to extract last four digits from descriptions
        last_four = _extract_last_four(db, current_user.id, source)

        card = Card(
            user_id=current_user.id,
            bank_name=bank_name,
            card_type=card_type,
            last_four=last_four,
            nickname="",
            source_prefix=source,
        )
        db.add(card)
        created += 1

    db.commit()

    cards = db.query(Card).filter(Card.user_id == current_user.id).all()
    return {"detected": created, "total": len(cards), "cards": [CardOut.model_validate(c) for c in cards]}


@router.patch("/{card_id}", response_model=CardOut)
def update_card(card_id: int, updates: CardUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update card nickname or last four digits."""
    card = db.query(Card).filter(Card.id == card_id, Card.user_id == current_user.id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    if updates.nickname is not None:
        card.nickname = updates.nickname
    if updates.last_four is not None:
        card.last_four = updates.last_four
    db.commit()
    db.refresh(card)
    return card


@router.post("/link-payment")
def link_card_payment(
    expense_id: int = Query(...),
    card_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a transaction as a card payment and link it to a specific card."""
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    card = db.query(Card).filter(Card.id == card_id, Card.user_id == current_user.id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    expense.card_id = card_id
    expense.category = "transfer"
    db.commit()

    return {"message": f"Linked to {card.bank_name} {card.card_type}", "expense_id": expense_id, "card_id": card_id}


@router.post("/unlink-payment")
def unlink_card_payment(
    expense_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove card payment link from a transaction."""
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.user_id == current_user.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense.card_id = None
    # Don't auto-change category back — user can do that manually
    db.commit()
    return {"message": "Unlinked", "expense_id": expense_id}


def _source_to_bank(source: str) -> str:
    s = source.lower()
    if "hdfc" in s: return "HDFC"
    if "axis" in s: return "Axis"
    if "scapia" in s: return "Scapia"
    if "icici" in s: return "ICICI"
    if "sbi" in s: return "SBI"
    if "kotak" in s: return "Kotak"
    if s.startswith("stmt_"):
        name = s.replace("stmt_", "")
        for suffix in ("_cc", "_bank"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name.upper()
    return source.replace("_", " ").title()


def _is_cc_source(source: str) -> bool:
    s = source.lower()
    if any(kw in s for kw in ["_bank", "bank_pdf", "upi_pdf", "email_hdfc_bank"]):
        return False
    if any(kw in s for kw in ["_cc", "credit_card", "email_scapia", "email_hdfc_cc", "email_axis_cc"]):
        return True
    if s.startswith("stmt_") and "_cc" not in s and "_bank" not in s:
        return True
    return False


def _extract_last_four(db: Session, user_id: int, source: str) -> str:
    """Try to extract card last four digits from transaction descriptions."""
    expenses = db.query(Expense).filter(
        Expense.user_id == user_id, Expense.source == source,
    ).limit(50).all()

    for e in expenses:
        desc = e.description or ""
        # Patterns: "ending 8705", "XX1088", "XXXX8705", "ending in 8921"
        m = re.search(r"(?:ending\s*(?:in\s*)?|XX+)(\d{4})", desc, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""
