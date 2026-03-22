"""Parser for bank account statement PDFs.

Handles common Indian bank statement formats (SBI, HDFC, ICICI, Axis, etc.).
Extracts transactions with date, description, debit/credit amounts, and balance.
"""

import re
from datetime import datetime
from typing import Optional

import pdfplumber

from ..schemas import ExpenseCreate

# Common date formats found in Indian bank statements
DATE_PATTERNS = [
    r"\d{2}/\d{2}/\d{4}",  # DD/MM/YYYY
    r"\d{2}-\d{2}-\d{4}",  # DD-MM-YYYY
    r"\d{2}\s\w{3}\s\d{4}",  # DD Mon YYYY
    r"\d{2}/\d{2}/\d{2}",  # DD/MM/YY
    r"\d{2}-\d{2}-\d{2}",  # DD-MM-YY
]

DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d %b %Y",
    "%d/%m/%y",
    "%d-%m-%y",
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
    # Remove trailing Cr/Dr markers
    cleaned = re.sub(r"[CcDd][Rr]\.?$", "", cleaned).strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _classify_payment_method(description: str) -> str:
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["upi", "phonepe", "gpay", "google pay", "paytm"]):
        return "upi"
    if any(kw in desc_lower for kw in ["neft", "rtgs"]):
        return "neft"
    if any(kw in desc_lower for kw in ["imps"]):
        return "imps"
    if any(kw in desc_lower for kw in ["atm", "cash withdrawal"]):
        return "cash"
    if any(kw in desc_lower for kw in ["pos", "swipe", "card"]):
        return "debit_card"
    return "debit_card"


def _classify_category(description: str) -> str:
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["swiggy", "zomato", "restaurant", "food", "cafe", "pizza", "burger"]):
        return "food"
    if any(kw in desc_lower for kw in ["uber", "ola", "metro", "fuel", "petrol", "diesel", "irctc", "railway"]):
        return "transport"
    if any(kw in desc_lower for kw in ["amazon", "flipkart", "myntra", "shopping", "mall"]):
        return "shopping"
    if any(kw in desc_lower for kw in ["netflix", "hotstar", "spotify", "movie", "pvr", "inox"]):
        return "entertainment"
    if any(kw in desc_lower for kw in ["electricity", "water", "gas", "broadband", "jio", "airtel", "vi ", "bsnl"]):
        return "bills"
    if any(kw in desc_lower for kw in ["hospital", "medical", "pharmacy", "doctor", "health", "apollo"]):
        return "health"
    if any(kw in desc_lower for kw in ["school", "college", "course", "udemy", "tuition"]):
        return "education"
    if any(kw in desc_lower for kw in ["grocery", "bigbasket", "dmart", "blinkit", "zepto", "instamart"]):
        return "groceries"
    if any(kw in desc_lower for kw in ["rent", "house rent", "landlord"]):
        return "rent"
    if any(kw in desc_lower for kw in ["salary", "sal credit"]):
        return "salary"
    if any(kw in desc_lower for kw in ["emi", "loan"]):
        return "emi"
    if any(kw in desc_lower for kw in ["atm", "cash withdrawal"]):
        return "atm"
    if any(kw in desc_lower for kw in ["transfer", "neft", "imps", "rtgs"]):
        return "transfer"
    return "other"


def parse_bank_statement(pdf_path: str) -> list[ExpenseCreate]:
    """Parse a bank statement PDF and extract transactions."""
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Try table extraction first (most bank statements are tabular)
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    transactions.extend(_parse_table_rows(table))
            else:
                # Fallback to text-based parsing
                text = page.extract_text() or ""
                transactions.extend(_parse_text_lines(text))

    return transactions


def _parse_table_rows(table: list[list]) -> list[ExpenseCreate]:
    """Parse rows from an extracted table."""
    transactions = []
    if not table or len(table) < 2:
        return transactions

    # Try to identify column indices from header row
    header = [str(cell).lower().strip() if cell else "" for cell in table[0]]
    date_col = _find_col(header, ["date", "txn date", "transaction date", "value date"])
    desc_col = _find_col(header, ["description", "narration", "particulars", "details", "remarks"])
    debit_col = _find_col(header, ["debit", "withdrawal", "dr", "debit amount"])
    credit_col = _find_col(header, ["credit", "deposit", "cr", "credit amount"])
    amount_col = _find_col(header, ["amount", "txn amount"])

    # If we can't find columns from header, try positional guessing
    if date_col is None:
        date_col = 0
    if desc_col is None:
        desc_col = 1 if len(header) > 1 else 0

    for row in table[1:]:
        if not row or all(not cell for cell in row):
            continue

        row_str = [str(cell).strip() if cell else "" for cell in row]

        # Extract date
        date_str = row_str[date_col] if date_col < len(row_str) else ""
        parsed_date = _parse_date(date_str)
        if not parsed_date:
            continue

        # Extract description
        description = row_str[desc_col] if desc_col < len(row_str) else ""

        # Extract amount (debit)
        amount = None
        if debit_col is not None and debit_col < len(row_str):
            amount = _parse_amount(row_str[debit_col])
        if amount is None and amount_col is not None and amount_col < len(row_str):
            amount = _parse_amount(row_str[amount_col])

        if amount is None or amount <= 0:
            # Skip credits (income) — we only track expenses
            continue

        transactions.append(
            ExpenseCreate(
                amount=amount,
                category=_classify_category(description),
                payment_method=_classify_payment_method(description),
                description=description[:200],
                date=parsed_date.date(),
                source="bank_pdf",
            )
        )

    return transactions


def _parse_text_lines(text: str) -> list[ExpenseCreate]:
    """Fallback: parse transactions from raw text lines."""
    transactions = []
    lines = text.split("\n")

    combined_date_pattern = re.compile(
        r"(" + "|".join(DATE_PATTERNS) + r")"
    )

    for line in lines:
        match = combined_date_pattern.search(line)
        if not match:
            continue

        date_str = match.group(1)
        parsed_date = _parse_date(date_str)
        if not parsed_date:
            continue

        # Find amounts in the line (numbers with optional commas and decimals)
        amounts = re.findall(r"[\d,]+\.\d{2}", line)
        if not amounts:
            continue

        # The description is the text between date and first amount
        rest = line[match.end():].strip()
        desc_match = re.match(r"(.+?)[\d,]+\.\d{2}", rest)
        description = desc_match.group(1).strip() if desc_match else rest[:100]

        # Use the first amount as the transaction amount (usually debit)
        amount = _parse_amount(amounts[0])
        if amount is None or amount <= 0:
            continue

        transactions.append(
            ExpenseCreate(
                amount=amount,
                category=_classify_category(description),
                payment_method=_classify_payment_method(description),
                description=description[:200],
                date=parsed_date.date(),
                source="bank_pdf",
            )
        )

    return transactions


def _find_col(header: list[str], keywords: list[str]) -> Optional[int]:
    for i, cell in enumerate(header):
        for kw in keywords:
            if kw in cell:
                return i
    return None
