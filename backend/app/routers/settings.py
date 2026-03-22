"""User settings endpoints — PDF passwords, etc."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PdfPassword

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
