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

# HDFC single-column format: "21/02/2026| 10:03 AMAZON PAY INDIA PRIVATETBangalore C 302.00 l"
# Also handles: "21/02/2026| 00:00 PAYZAPPMUMBAI + C 2.00 l"
HDFC_ROW_PATTERN = re.compile(
    r"(\d{2}/\d{2}/\d{4})\|\s*\d{2}:\d{2}\s+"  # date|time
    r"(.+?)\s+"                                   # description (non-greedy)
    r"[C₹]\s*([\d,]+\.\d{2})\s*"                  # C or ₹ + amount
)


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
    cleaned = amount_str.strip()
    # Detect Cr (credit/refund) before stripping
    is_credit = False
    if re.search(r"\bCr\b", cleaned, re.IGNORECASE):
        is_credit = True
    # Strip currency symbols, Dr/Cr suffixes
    cleaned = cleaned.replace(",", "").replace(" ", "")
    cleaned = re.sub(r"[Dd][Rr]\.?$", "", cleaned).strip()
    cleaned = re.sub(r"[Cc][Rr]\.?$", "", cleaned).strip()
    cleaned = cleaned.lstrip("₹C").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
        is_credit = True
    if cleaned.startswith("-") or cleaned.startswith("+"):
        if cleaned.startswith("+"):
            is_credit = True
        cleaned = cleaned[1:]
    try:
        val = float(cleaned)
        return -val if is_credit else val
    except ValueError:
        return None


def _classify_category(description: str) -> str:
    desc_lower = description.lower()
    mapping = {
        "food": ["swiggy", "zomato", "restaurant", "food", "cafe", "pizza", "mcdonald", "domino", "kfc", "starbucks", "chai", "barista"],
        "shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho", "shopping", "mall", "reliance", "asspl"],
        "entertainment": ["netflix", "hotstar", "spotify", "movie", "pvr", "inox", "bookmyshow", "prime video", "cinepolis", "youtube", "google play"],
        "bills": ["electricity", "water", "gas", "broadband", "jio", "airtel", "vi ", "bsnl", "tata play", "recharge", "finance charges", "late fee"],
        "transport": ["uber", "ola", "metro", "fuel", "petrol", "irctc", "makemytrip", "cleartrip", "auto service"],
        "health": ["hospital", "medical", "pharmacy", "doctor", "apollo", "1mg", "pharmeasy"],
        "groceries": ["bigbasket", "dmart", "blinkit", "zepto", "instamart", "grocery", "supermarket", "smart bazaar", "flour mill"],
        "education": ["school", "college", "course", "udemy", "coursera", "unacademy"],
        "emi": ["emi", "loan", "instalment"],
    }
    for category, keywords in mapping.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "other"


def parse_credit_card_statement(pdf_path: str, password: str = None) -> list[ExpenseCreate]:
    """Parse a credit card statement PDF and extract transactions."""
    from .ocr_fallback import is_garbled

    transactions = []

    with pdfplumber.open(pdf_path, password=password) as pdf:
        for page in pdf.pages:
            # Try table extraction first
            tables = page.extract_tables()
            found_from_tables = False
            if tables:
                for table in tables:
                    parsed = _parse_cc_table(table)
                    if parsed:
                        transactions.extend(parsed)
                        found_from_tables = True

            # Also try text-based parsing (catches HDFC single-column format
            # and cases where tables don't parse cleanly)
            if not found_from_tables:
                text = page.extract_text() or ""
                if not is_garbled(text):
                    transactions.extend(_parse_cc_text(text))

    return transactions


def _parse_cc_table(table: list[list]) -> list[ExpenseCreate]:
    """Parse a credit card transaction table.

    Handles both multi-column tables and HDFC-style single-column tables
    where all data is crammed into one cell.
    """
    transactions = []
    if not table or len(table) < 2:
        return transactions

    # Find the actual header row (may not be row 0 — Axis puts summary in row 0)
    header_idx = None
    for idx, row in enumerate(table):
        row_text = " ".join(str(cell).lower() for cell in row if cell)
        if "date" in row_text and ("transaction" in row_text or "description" in row_text or "amount" in row_text):
            header_idx = idx
            break

    if header_idx is None:
        return transactions

    header = [str(cell).lower().strip() if cell else "" for cell in table[header_idx]]

    # Check if this is an HDFC-style single-column table
    # (header has all info in one cell like "DATE & TIME TRANSACTION DESCRIPTION AMOUNT")
    non_empty_header_cells = [c for c in header if c]
    if len(non_empty_header_cells) <= 2 and any("date" in c and "transaction" in c for c in header):
        for row in table[header_idx + 1:]:
            cell_text = "\n".join(str(cell) for cell in row if cell)
            parsed = _parse_hdfc_row(cell_text)
            if parsed:
                transactions.extend(parsed)
        return transactions

    # Standard multi-column table parsing
    date_col = _find_col(header, ["date", "transaction date", "txn date"])
    desc_col = _find_col(header, ["transaction details", "description", "details", "particulars", "merchant"])
    amount_col = _find_col(header, ["amount", "txn amount", "transaction amount", "inr"])

    if date_col is None:
        date_col = 0
    if desc_col is None:
        desc_col = 1
    if amount_col is None:
        amount_col = len(header) - 1

    for row in table[header_idx + 1:]:
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


def _parse_hdfc_row(cell_text: str) -> list[ExpenseCreate]:
    """Parse HDFC-style single-column rows.

    Format: "21/02/2026| 10:03 AMAZON PAY INDIA PRIVATETBangalore C 302.00 l"
    Also: "SUMIT KUMAR\n21/02/2026| 10:03 ..."
    """
    transactions = []
    for line in cell_text.split("\n"):
        match = HDFC_ROW_PATTERN.search(line)
        if not match:
            continue

        date_str = match.group(1)
        description = match.group(2).strip()
        amount_str = match.group(3)

        parsed_date = _parse_date(date_str)
        if not parsed_date:
            continue

        amount = _parse_amount(amount_str)
        if amount is None or amount <= 0:
            continue

        # Clean up description: remove trailing +, city names appended without space
        description = re.sub(r"\s*\+\s*$", "", description)

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
    """Parse credit card transactions from raw text."""
    transactions = []
    lines = text.split("\n")

    combined_pattern = re.compile(r"(" + "|".join(DATE_PATTERNS) + r")")

    for line in lines:
        # Try HDFC format first
        hdfc_match = HDFC_ROW_PATTERN.search(line)
        if hdfc_match:
            date_str = hdfc_match.group(1)
            description = hdfc_match.group(2).strip()
            amount_str = hdfc_match.group(3)

            parsed_date = _parse_date(date_str)
            amount = _parse_amount(amount_str)
            if parsed_date and amount and amount > 0:
                description = re.sub(r"\s*\+\s*$", "", description)
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
            continue

        # Generic text parsing
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

        amount = _parse_amount(amounts[-1])
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
