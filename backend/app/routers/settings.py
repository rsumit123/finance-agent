"""User settings endpoints — PDF passwords, etc."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Expense, PdfPassword, UploadHistory
from ..parsers.categorizer import classify_category

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PasswordIn(BaseModel):
    label: str = ""
    password: str


class PasswordOut(BaseModel):
    id: int
    label: str

    model_config = {"from_attributes": True}


@router.get("/passwords", response_model=list[PasswordOut])
def list_passwords(db: Session = Depends(get_db)):
    """List saved PDF passwords (labels only, not the actual passwords)."""
    return db.query(PdfPassword).all()


@router.post("/passwords", response_model=PasswordOut)
def add_password(data: PasswordIn, db: Session = Depends(get_db)):
    """Add a PDF password."""
    if not data.password:
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    pw = PdfPassword(label=data.label, password=data.password)
    db.add(pw)
    db.commit()
    db.refresh(pw)
    return pw


@router.delete("/passwords/{password_id}")
def delete_password(password_id: int, db: Session = Depends(get_db)):
    """Delete a saved PDF password."""
    pw = db.query(PdfPassword).filter(PdfPassword.id == password_id).first()
    if not pw:
        raise HTTPException(status_code=404, detail="Password not found")
    db.delete(pw)
    db.commit()
    return {"message": "Password deleted"}


@router.post("/recategorize")
def recategorize_expenses(
    user_name: str = Query("", description="User name for self-transfer detection"),
    db: Session = Depends(get_db),
):
    """Re-categorize all 'other' transactions using improved categorizer."""
    others = db.query(Expense).filter(Expense.category == "other").all()
    fixed = 0
    changes = {}
    for e in others:
        new_cat = classify_category(e.description or "", source=e.source or "", user_name=user_name)
        if new_cat != "other":
            e.category = new_cat
            fixed += 1
            changes[new_cat] = changes.get(new_cat, 0) + 1
    db.commit()
    return {
        "total_others": len(others),
        "recategorized": fixed,
        "remaining_other": len(others) - fixed,
        "changes": changes,
    }


@router.post("/clear-data")
def clear_all_data(db: Session = Depends(get_db)):
    """Delete all expenses and upload history. Keeps passwords and Gmail connection."""
    expense_count = db.query(Expense).count()
    history_count = db.query(UploadHistory).count()
    db.query(Expense).delete()
    db.query(UploadHistory).delete()
    db.commit()
    return {
        "message": "All data cleared",
        "expenses_deleted": expense_count,
        "history_deleted": history_count,
    }
