"""Auto-detect statement type and parse accordingly."""

import pdfplumber

from ..schemas import ExpenseCreate
from .bank_parser import parse_bank_statement
from .credit_card_parser import parse_credit_card_statement
from .upi_parser import parse_upi_statement


def detect_statement_type(pdf_path: str, password: str = None) -> str:
    """Detect whether a PDF is a bank statement, credit card statement, or UPI export."""
    from .ocr_fallback import is_garbled, ocr_page

    with pdfplumber.open(pdf_path, password=password) as pdf:
        text = ""
        for page in pdf.pages[:3]:  # Check first 3 pages
            page_text = page.extract_text() or ""
            if is_garbled(page_text):
                page_text = ocr_page(page)
            text += page_text + "\n"

    text_lower = text.lower()

    # Credit card indicators
    cc_keywords = [
        "credit card", "card number", "card no", "statement of account",
        "minimum amount due", "total amount due", "payment due date",
        "credit limit", "available credit", "reward points",
    ]
    cc_score = sum(1 for kw in cc_keywords if kw in text_lower)

    # UPI indicators
    upi_keywords = [
        "upi", "utr", "phonepe", "google pay", "gpay", "paytm",
        "upi id", "upi ref", "vpa", "@ybl", "@paytm", "@okaxis",
        "@oksbi", "@okhdfcbank",
    ]
    upi_score = sum(1 for kw in upi_keywords if kw in text_lower)

    # Bank statement indicators
    bank_keywords = [
        "account statement", "bank statement", "savings account",
        "current account", "opening balance", "closing balance",
        "withdrawal", "deposit", "ifsc",
    ]
    bank_score = sum(1 for kw in bank_keywords if kw in text_lower)

    scores = {
        "credit_card": cc_score,
        "upi": upi_score,
        "bank_statement": bank_score,
    }

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "bank_statement"  # Default fallback
    return best


def detect_and_parse(pdf_path: str, password: str = None) -> tuple[str, list[ExpenseCreate]]:
    """Auto-detect statement type and parse it. Returns (type, transactions)."""
    file_type = detect_statement_type(pdf_path, password=password)

    if file_type == "credit_card":
        transactions = parse_credit_card_statement(pdf_path, password=password)
    elif file_type == "upi":
        transactions = parse_upi_statement(pdf_path, password=password)
    else:
        transactions = parse_bank_statement(pdf_path, password=password)

    return file_type, transactions
