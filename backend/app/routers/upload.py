"""PDF statement upload and parsing endpoints."""

import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import CategoryRule, UploadHistory, User
from ..parsers import (
    detect_and_parse,
    parse_bank_statement,
    parse_credit_card_statement,
    parse_upi_statement,
)
from ..parsers.categorizer import classify_category
from ..schemas import ExpenseOut, UploadResult
from ..services.tracker import create_expenses_bulk_dedup

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
    current_user: User = Depends(get_current_user),
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

    # Save transactions to DB with dedup
    if parsed:
        expenses, duplicates = create_expenses_bulk_dedup(db, parsed, user_id=current_user.id)
        # Auto-recategorize with user's name and learned rules
        user_name = current_user.name or ""
        rules = [(r.keyword, r.category) for r in db.query(CategoryRule).filter(CategoryRule.user_id == current_user.id).all()]
        for e in expenses:
            if e.category == "other":
                new_cat = classify_category(e.description or "", source=e.source or "", user_name=user_name, user_rules=rules)
                if new_cat != "other":
                    e.category = new_cat
        db.commit()
    else:
        expenses, duplicates = [], []

    # Build duplicate ExpenseOut-like objects for response
    dup_out = []
    for d in duplicates:
        dup_out.append(ExpenseOut(
            id=0,
            amount=d.amount,
            category=d.category,
            payment_method=d.payment_method,
            description=d.description,
            date=d.date,
            source=d.source,
            reference_id=d.reference_id,
        ))

    # Record upload history
    history = UploadHistory(
        filename=file.filename,
        file_type=detected_type,
        transactions_found=len(expenses),
        user_id=current_user.id,
    )
    db.add(history)
    db.commit()

    return UploadResult(
        filename=file.filename,
        file_type=detected_type,
        transactions_found=len(expenses),
        transactions=[ExpenseOut.model_validate(e) for e in expenses],
        duplicates_skipped=len(duplicates),
        duplicate_transactions=dup_out,
    )


@router.post("/debug")
async def debug_pdf(
    file: UploadFile = File(...),
    password: str = Query(""),
    current_user: User = Depends(get_current_user),
):
    """Debug endpoint: returns raw extracted text and tables from a PDF."""
    import pdfplumber

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    pwd = password or None
    result = {"pages": []}
    try:
        with pdfplumber.open(tmp_path, password=pwd) as pdf:
            for i, page in enumerate(pdf.pages[:5]):
                page_data = {"page": i + 1, "tables": [], "text": ""}
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        page_data["tables"].append(table[:15])
                page_data["text"] = (page.extract_text() or "")[:3000]
                result["pages"].append(page_data)
    finally:
        os.unlink(tmp_path)

    return result


@router.get("/history")
def upload_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get list of previously uploaded statements."""
    return (
        db.query(UploadHistory)
        .filter(UploadHistory.user_id == current_user.id)
        .order_by(UploadHistory.uploaded_at.desc())
        .limit(50)
        .all()
    )
