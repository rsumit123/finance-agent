"""User settings endpoints — PDF passwords, etc."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Expense, PdfPassword, UploadHistory, User
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
def list_passwords(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(PdfPassword).filter(PdfPassword.user_id == current_user.id).all()


@router.post("/passwords", response_model=PasswordOut)
def add_password(data: PasswordIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not data.password:
        raise HTTPException(status_code=400, detail="Password cannot be empty")
    pw = PdfPassword(label=data.label, password=data.password, user_id=current_user.id)
    db.add(pw)
    db.commit()
    db.refresh(pw)
    return pw


@router.delete("/passwords/{password_id}")
def delete_password(password_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pw = db.query(PdfPassword).filter(PdfPassword.id == password_id, PdfPassword.user_id == current_user.id).first()
    if not pw:
        raise HTTPException(status_code=404, detail="Password not found")
    db.delete(pw)
    db.commit()
    return {"message": "Password deleted"}


@router.post("/recategorize")
def recategorize_expenses(
    user_name: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-categorize all 'other' transactions for current user."""
    # Use user's name from profile if not provided
    name = user_name or current_user.name or ""
    others = db.query(Expense).filter(Expense.user_id == current_user.id, Expense.category == "other").all()
    fixed = 0
    changes = {}
    for e in others:
        new_cat = classify_category(e.description or "", source=e.source or "", user_name=name)
        if new_cat != "other":
            e.category = new_cat
            fixed += 1
            changes[new_cat] = changes.get(new_cat, 0) + 1
    db.commit()
    return {"total_others": len(others), "recategorized": fixed, "remaining_other": len(others) - fixed, "changes": changes}


@router.post("/clear-data")
def clear_all_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete current user's expenses and upload history."""
    expense_count = db.query(Expense).filter(Expense.user_id == current_user.id).count()
    history_count = db.query(UploadHistory).filter(UploadHistory.user_id == current_user.id).count()
    db.query(Expense).filter(Expense.user_id == current_user.id).delete()
    db.query(UploadHistory).filter(UploadHistory.user_id == current_user.id).delete()
    db.commit()
    return {"message": "All data cleared", "expenses_deleted": expense_count, "history_deleted": history_count}
