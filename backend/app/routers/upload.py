"""PDF statement upload and parsing endpoints."""

import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import UploadHistory
from ..parsers import (
    detect_and_parse,
    parse_bank_statement,
    parse_credit_card_statement,
    parse_upi_statement,
)
from ..schemas import ExpenseOut, UploadResult
from ..services.tracker import create_expenses_bulk

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/", response_model=UploadResult)
async def upload_statement(
    file: UploadFile = File(...),
    file_type: str = Query(
        "auto",
        pattern="^(auto|bank_statement|credit_card|upi)$",
        description="Statement type. Use 'auto' to auto-detect.",
    ),
    password: str = Query(
        "",
        description="PDF password (for password-protected statements)",
    ),
    db: Session = Depends(get_db),
):
    """Upload a bank/credit card/UPI statement PDF and parse transactions."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    pwd = password or None

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if file_type == "auto":
            detected_type, parsed = detect_and_parse(tmp_path, password=pwd)
        elif file_type == "bank_statement":
            detected_type = "bank_statement"
            parsed = parse_bank_statement(tmp_path, password=pwd)
        elif file_type == "credit_card":
            detected_type = "credit_card"
            parsed = parse_credit_card_statement(tmp_path, password=pwd)
        elif file_type == "upi":
            detected_type = "upi"
            parsed = parse_upi_statement(tmp_path, password=pwd)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown file type: {file_type}")
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse PDF: {str(e)}",
        )
    finally:
        os.unlink(tmp_path)

    # Save transactions to DB
    expenses = create_expenses_bulk(db, parsed) if parsed else []

    # Record upload history
    history = UploadHistory(
        filename=file.filename,
        file_type=detected_type,
        transactions_found=len(expenses),
    )
    db.add(history)
    db.commit()

    return UploadResult(
        filename=file.filename,
        file_type=detected_type,
        transactions_found=len(expenses),
        transactions=[ExpenseOut.model_validate(e) for e in expenses],
    )


@router.get("/history")
def upload_history(db: Session = Depends(get_db)):
    """Get list of previously uploaded statements."""
    return (
        db.query(UploadHistory)
        .order_by(UploadHistory.uploaded_at.desc())
        .limit(50)
        .all()
    )
