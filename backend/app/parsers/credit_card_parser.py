"""Parser for credit card statement PDFs.

Handles common Indian credit card statement formats (HDFC, ICICI, SBI, Axis, etc.).
Credit card statements typically have: date, description, amount, and sometimes reward points.
"""

import re
from datetime import datetime
from typing import Optional

import pdfplumber

from ..schemas import ExpenseCreate

DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d %b %y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%b %d, %Y",
]

DATE_PATTERNS = [
    r"\d{2}/\d{2}/\d{4}",
    r"\d{2}-\d{2}-\d{4}",
    r"\d{2}\s\w{3}\s\d{4}",
    r"\d{2}\s\w{3}\s\d{2}",
    r"\d{2}/\d{2}/\d{2}",
    r"\w{3}\s\d{2},\s\d{4}",
]


def _parse_date(date_str: str) -> Optional[datetime]:
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _parse_amount(amount_str: str) -> Optional[float]:
    if not amount_str:
        return None
    cleaned = amount_str.replace(",", "").replace(" ", "").strip()
    cleaned = re.sub(r"[CcDd][Rr]\.?$", "", cleaned).strip()
    # Handle negative sign or parentheses (credits/refunds)
    is_credit = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
        is_credit = True
    if cleaned.startswith("-"):
        cleaned = cleaned[1:]
        is_credit = True
    try:
        val = float(cleaned)
        return -val if is_credit else val
    except ValueError:
        return None


def _classify_category(description: str) -> str:
    desc_lower = description.lower()
    mapping = {
        "food": ["swiggy", "zomato", "restaurant", "food", "cafe", "pizza", "mcdonald", "domino", "kfc", "starbucks"],
        "shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho", "shopping", "mall", "reliance"],
        "entertainment": ["netflix", "hotstar", "spotify", "movie", "pvr", "inox", "bookmyshow", "prime video"],
        "bills": ["electricity", "water", "gas", "broadband", "jio", "airtel", "vi ", "bsnl", "tata play"],
        "transport": ["uber", "ola", "metro", "fuel", "petrol", "irctc", "makemytrip", "cleartrip"],
        "health": ["hospital", "medical", "pharmacy", "doctor", "apollo", "1mg", "pharmeasy"],
        "groceries": ["bigbasket", "dmart", "blinkit", "zepto", "instamart", "grocery", "supermarket"],
        "education": ["school", "college", "course", "udemy", "coursera", "unacademy"],
        "emi": ["emi", "loan", "instalment"],
    }
    for category, keywords in mapping.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "other"


def parse_credit_card_statement(pdf_path: str, password: str = None) -> list[ExpenseCreate]:
    """Parse a credit card statement PDF and extract transactions."""
    from .ocr_fallback import extract_tables_with_ocr_fallback, is_garbled

    transactions = []

    with pdfplumber.open(pdf_path, password=password) as pdf:
        for page in pdf.pages:
            tables, ocr_text = extract_tables_with_ocr_fallback(page)
            if tables:
                for table in tables:
                    transactions.extend(_parse_cc_table(table))
            elif ocr_text:
                # OCR fallback — parse the OCR text
                transactions.extend(_parse_cc_text(ocr_text))
            else:
                text = page.extract_text() or ""
                if not is_garbled(text):
                    transactions.extend(_parse_cc_text(text))

    return transactions


def _parse_cc_table(table: list[list]) -> list[ExpenseCreate]:
    transactions = []
    if not table or len(table) < 2:
        return transactions

    header = [str(cell).lower().strip() if cell else "" for cell in table[0]]
    date_col = _find_col(header, ["date", "transaction date", "txn date"])
    desc_col = _find_col(header, ["description", "details", "particulars", "merchant"])
    amount_col = _find_col(header, ["amount", "txn amount", "transaction amount", "inr"])

    if date_col is None:
        date_col = 0
    if desc_col is None:
        desc_col = 1
    if amount_col is None:
        amount_col = len(header) - 1  # Usually last column

    for row in table[1:]:
        if not row or all(not cell for cell in row):
            continue

        row_str = [str(cell).strip() if cell else "" for cell in row]

        date_str = row_str[date_col] if date_col < len(row_str) else ""
        parsed_date = _parse_date(date_str)
        if not parsed_date:
            continue

        description = row_str[desc_col] if desc_col < len(row_str) else ""
        amount_str = row_str[amount_col] if amount_col < len(row_str) else ""
        amount = _parse_amount(amount_str)

        if amount is None or amount <= 0:
            continue  # Skip credits/refunds

        transactions.append(
            ExpenseCreate(
                amount=amount,
                category=_classify_category(description),
                payment_method="credit_card",
                description=description[:200],
                date=parsed_date.date(),
                source="credit_card_pdf",
            )
        )

    return transactions


def _parse_cc_text(text: str) -> list[ExpenseCreate]:
    transactions = []
    lines = text.split("\n")

    combined_pattern = re.compile(r"(" + "|".join(DATE_PATTERNS) + r")")

    for line in lines:
        match = combined_pattern.search(line)
        if not match:
            continue

        parsed_date = _parse_date(match.group(1))
        if not parsed_date:
            continue

        amounts = re.findall(r"[\d,]+\.\d{2}", line)
        if not amounts:
            continue

        rest = line[match.end():].strip()
        desc_match = re.match(r"(.+?)[\d,]+\.\d{2}", rest)
        description = desc_match.group(1).strip() if desc_match else rest[:100]

        amount = _parse_amount(amounts[-1])  # Last amount is usually the INR amount
        if amount is None or amount <= 0:
            continue

        transactions.append(
            ExpenseCreate(
                amount=amount,
                category=_classify_category(description),
                payment_method="credit_card",
                description=description[:200],
                date=parsed_date.date(),
                source="credit_card_pdf",
            )
        )

    return transactions


def _find_col(header: list[str], keywords: list[str]) -> Optional[int]:
    for i, cell in enumerate(header):
        for kw in keywords:
            if kw in cell:
                return i
    return None
