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

# PhonePe format: "Mar 22, 2026 Paid to Jetender Electricity DEBIT ₹150"
PHONEPE_PATTERN = re.compile(
    r"(\w{3}\s+\d{1,2},\s+\d{4})\s+"  # date: Mar 22, 2026
    r"Paid\s+to\s+(.+?)\s+"            # "Paid to <description>"
    r"(DEBIT|CREDIT)\s+"               # type
    r"₹([\d,]+(?:\.\d{1,2})?)"         # amount with ₹ symbol
)

# Generic UPI line: date + description + amount
GENERIC_UPI_PATTERN = re.compile(
    r"(\d{2}[/-]\d{2}[/-]\d{4})\s+"    # date
    r"(.+?)\s+"                         # description
    r"₹?\s?([\d,]+\.\d{2})"            # amount
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
    cleaned = amount_str.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    cleaned = re.sub(r"[CcDd][Rr]\.?$", "", cleaned).strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _classify_category(description: str) -> str:
    desc_lower = description.lower()
    mapping = {
        "food": ["swiggy", "zomato", "restaurant", "food", "cafe", "dominos", "pizza", "kfc", "mcdonald", "chai", "barista"],
        "shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho"],
        "groceries": ["bigbasket", "blinkit", "zepto", "instamart", "dmart", "grocery", "smart bazaar", "flour mill"],
        "transport": ["uber", "ola", "rapido", "metro", "irctc", "fuel", "petrol", "auto service"],
        "bills": ["electricity", "water", "gas", "broadband", "jio", "airtel", "bsnl", "recharge", "prepaid"],
        "entertainment": ["netflix", "hotstar", "spotify", "bookmyshow", "cinepolis", "pvr", "inox", "movie"],
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
    from .ocr_fallback import is_garbled

    transactions = []

    with pdfplumber.open(pdf_path, password=password) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not is_garbled(text):
                full_text += text + "\n"

        # Try PhonePe multi-line format first
        phonepe_txns = _parse_phonepe_text(full_text)
        if phonepe_txns:
            return phonepe_txns

        # Fall back to table-based or generic text parsing
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    transactions.extend(_parse_upi_table(table))
            else:
                text = page.extract_text() or ""
                if not is_garbled(text):
                    transactions.extend(_parse_upi_text_generic(text))

    return transactions


def _parse_phonepe_text(text: str) -> list[ExpenseCreate]:
    """Parse PhonePe statement format.

    Format (multi-line per transaction):
        Mar 22, 2026 Paid to Jetender Electricity DEBIT ₹150
        01:10 pm Transaction ID T2603221310340785561579
        UTR No. 498882856834
        Paid by XXXXXXXX134868
    """
    transactions = []
    lines = text.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = PHONEPE_PATTERN.search(line)
        if match:
            date_str = match.group(1)
            description = match.group(2).strip()
            txn_type = match.group(3)
            amount_str = match.group(4)

            # Skip credits (received money)
            if txn_type == "CREDIT":
                i += 1
                continue

            parsed_date = _parse_date(date_str)
            amount = _parse_amount(amount_str)

            if parsed_date and amount and amount > 0:
                # Look ahead for UTR number
                ref_id = ""
                for j in range(1, 4):
                    if i + j < len(lines):
                        utr_match = re.search(r"UTR\s+No\.\s*(\d+)", lines[i + j])
                        if utr_match:
                            ref_id = utr_match.group(1)
                            break

                transactions.append(
                    ExpenseCreate(
                        amount=amount,
                        category=_classify_category(description),
                        payment_method="upi",
                        description=description[:200],
                        date=parsed_date.date(),
                        source="upi_pdf",
                        reference_id=ref_id,
                    )
                )
        i += 1

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


def _parse_upi_text_generic(text: str) -> list[ExpenseCreate]:
    """Parse generic UPI text format with date + description + amount per line."""
    transactions = []
    lines = text.split("\n")

    date_patterns = [
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
        r"\d{2}\s\w{3}\s\d{4}",
        r"\d{4}-\d{2}-\d{2}",
        r"\w{3}\s\d{1,2},\s\d{4}",
    ]
    combined = re.compile(r"(" + "|".join(date_patterns) + r")")

    for line in lines:
        match = combined.search(line)
        if not match:
            continue

        parsed_date = _parse_date(match.group(1))
        if not parsed_date:
            continue

        if re.search(r"\b(credited|received|credit|cr)\b", line, re.IGNORECASE):
            continue

        # Match amounts: ₹150 or ₹1,091.89 or 150.00
        amounts = re.findall(r"₹([\d,]+(?:\.\d{1,2})?)", line)
        if not amounts:
            amounts = re.findall(r"([\d,]+\.\d{2})", line)
        if not amounts:
            continue

        rest = line[match.end():].strip()
        # Try to extract description before the amount
        desc_match = re.match(r"(.+?)₹", rest)
        if not desc_match:
            desc_match = re.match(r"(.+?)[\d,]+\.\d{2}", rest)
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
