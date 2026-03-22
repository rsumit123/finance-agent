"""Parser for UPI transaction statement PDFs.

Handles UPI transaction exports from apps like PhonePe, Google Pay, Paytm,
and bank-generated UPI transaction reports.
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
    "%Y-%m-%d",
    "%b %d, %Y",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%d %b %Y %H:%M",
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
    cleaned = amount_str.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    cleaned = re.sub(r"[CcDd][Rr]\.?$", "", cleaned).strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _classify_category(description: str) -> str:
    desc_lower = description.lower()
    mapping = {
        "food": ["swiggy", "zomato", "restaurant", "food", "cafe", "dominos", "pizza", "kfc", "mcdonald"],
        "shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho"],
        "groceries": ["bigbasket", "blinkit", "zepto", "instamart", "dmart", "grocery"],
        "transport": ["uber", "ola", "rapido", "metro", "irctc", "fuel", "petrol"],
        "bills": ["electricity", "water", "gas", "broadband", "jio", "airtel", "bsnl", "recharge"],
        "entertainment": ["netflix", "hotstar", "spotify", "bookmyshow"],
        "health": ["pharmacy", "medical", "hospital", "apollo", "1mg"],
        "rent": ["rent", "landlord"],
    }
    for category, keywords in mapping.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "other"


def _extract_upi_id(text: str) -> str:
    """Extract UPI ID from transaction text if present."""
    match = re.search(r"[\w.]+@[\w]+", text)
    return match.group(0) if match else ""


def parse_upi_statement(pdf_path: str, password: str = None) -> list[ExpenseCreate]:
    """Parse a UPI transaction statement PDF."""
    transactions = []

    with pdfplumber.open(pdf_path, password=password) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    transactions.extend(_parse_upi_table(table))
            else:
                text = page.extract_text() or ""
                transactions.extend(_parse_upi_text(text))

    return transactions


def _parse_upi_table(table: list[list]) -> list[ExpenseCreate]:
    transactions = []
    if not table or len(table) < 2:
        return transactions

    header = [str(cell).lower().strip() if cell else "" for cell in table[0]]
    date_col = _find_col(header, ["date", "transaction date", "txn date", "time"])
    desc_col = _find_col(header, ["description", "details", "to/from", "merchant", "paid to", "received from", "name"])
    amount_col = _find_col(header, ["amount", "txn amount", "value"])
    type_col = _find_col(header, ["type", "txn type", "debit/credit", "dr/cr", "status"])
    ref_col = _find_col(header, ["reference", "utr", "ref no", "transaction id"])

    if date_col is None:
        date_col = 0
    if desc_col is None:
        desc_col = 1

    for row in table[1:]:
        if not row or all(not cell for cell in row):
            continue

        row_str = [str(cell).strip() if cell else "" for cell in row]

        date_str = row_str[date_col] if date_col < len(row_str) else ""
        parsed_date = _parse_date(date_str)
        if not parsed_date:
            continue

        description = row_str[desc_col] if desc_col < len(row_str) else ""

        # Check transaction type — skip credits (received money)
        if type_col is not None and type_col < len(row_str):
            txn_type = row_str[type_col].lower()
            if any(kw in txn_type for kw in ["credit", "cr", "received"]):
                continue

        amount_str = row_str[amount_col] if amount_col and amount_col < len(row_str) else ""
        amount = _parse_amount(amount_str)
        if amount is None or amount <= 0:
            continue

        ref_id = row_str[ref_col] if ref_col and ref_col < len(row_str) else ""
        upi_id = _extract_upi_id(description)

        transactions.append(
            ExpenseCreate(
                amount=amount,
                category=_classify_category(description),
                payment_method="upi",
                description=description[:200],
                date=parsed_date.date(),
                source="upi_pdf",
                reference_id=ref_id or upi_id,
            )
        )

    return transactions


def _parse_upi_text(text: str) -> list[ExpenseCreate]:
    transactions = []
    lines = text.split("\n")

    date_patterns = [
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
        r"\d{2}\s\w{3}\s\d{4}",
        r"\d{4}-\d{2}-\d{2}",
    ]
    combined = re.compile(r"(" + "|".join(date_patterns) + r")")

    for line in lines:
        match = combined.search(line)
        if not match:
            continue

        parsed_date = _parse_date(match.group(1))
        if not parsed_date:
            continue

        # Skip lines that look like credits
        if re.search(r"\b(credited|received|credit|cr)\b", line, re.IGNORECASE):
            continue

        amounts = re.findall(r"₹?\s?[\d,]+\.\d{2}", line)
        if not amounts:
            continue

        rest = line[match.end():].strip()
        desc_match = re.match(r"(.+?)₹?\s?[\d,]+\.\d{2}", rest)
        description = desc_match.group(1).strip() if desc_match else rest[:100]

        amount = _parse_amount(amounts[0])
        if amount is None or amount <= 0:
            continue

        upi_id = _extract_upi_id(line)

        transactions.append(
            ExpenseCreate(
                amount=amount,
                category=_classify_category(description),
                payment_method="upi",
                description=description[:200],
                date=parsed_date.date(),
                source="upi_pdf",
                reference_id=upi_id,
            )
        )

    return transactions


def _find_col(header: list[str], keywords: list[str]) -> Optional[int]:
    for i, cell in enumerate(header):
        for kw in keywords:
            if kw in cell:
                return i
    return None
