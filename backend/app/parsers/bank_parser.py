"""Parser for bank account statement PDFs.

Handles common Indian bank statement formats (SBI, HDFC, ICICI, Axis, etc.).
Extracts transactions with date, description, debit/credit amounts, and balance.
"""

import re
from datetime import datetime
from typing import Optional

import pdfplumber

from ..schemas import ExpenseCreate
from .categorizer import classify_category

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


def parse_bank_statement(pdf_path: str, password: str = None) -> list[ExpenseCreate]:
    """Parse a bank statement PDF and extract transactions."""
    from .ocr_fallback import extract_tables_with_ocr_fallback, is_garbled

    transactions = []

    with pdfplumber.open(pdf_path, password=password) as pdf:
        for page in pdf.pages:
            tables, ocr_text = extract_tables_with_ocr_fallback(page)
            if tables:
                # Merge fragmented tables (some banks like BOB split each row
                # into a separate table). Combine tables with same column count.
                merged = _merge_fragmented_tables(tables)
                for table in merged:
                    transactions.extend(_parse_table_rows(table))
                # Also try text parser — some rows may fall between table
                # boundaries (common with BOB, Canara). Dedup by date+amount.
                text = page.extract_text() or ""
                if text and not is_garbled(text):
                    text_txns = _parse_text_lines(text)
                    existing = {(t.date, t.amount) for t in transactions}
                    for tt in text_txns:
                        if (tt.date, tt.amount) not in existing:
                            transactions.append(tt)
                            existing.add((tt.date, tt.amount))
            elif ocr_text:
                transactions.extend(_parse_text_lines(ocr_text))
            else:
                text = page.extract_text() or ""
                if not is_garbled(text):
                    transactions.extend(_parse_text_lines(text))

    return transactions


def _parse_table_rows(table: list[list]) -> list[ExpenseCreate]:
    """Parse rows from an extracted table."""
    transactions = []
    if not table or len(table) < 2:
        return transactions

    # Clean (cid:X) artifacts from all cells
    def clean_cell(cell):
        if not cell:
            return ""
        return re.sub(r"\(cid:\d+\)", " ", str(cell)).strip()

    # Scan for the actual header row (may not be row 0)
    header_idx = 0
    for idx, row in enumerate(table):
        row_text = " ".join(clean_cell(c).lower() for c in row if c)
        if "date" in row_text and ("withdrawal" in row_text or "debit" in row_text or "amount" in row_text or "transaction" in row_text):
            header_idx = idx
            break

    header = [clean_cell(cell).lower() for cell in table[header_idx]]
    date_col = _find_col(header, ["date", "txn date", "transaction date", "value date"])
    desc_col = _find_col(header, ["description", "narration", "particulars", "details", "remarks", "transaction details"])
    debit_col = _find_col(header, ["debit", "withdrawal", "dr", "debit amount"])
    credit_col = _find_col(header, ["credit", "deposit", "deposits", "cr", "credit amount"])
    amount_col = _find_col(header, ["amount", "txn amount"])

    # If we can't find columns from header, try positional guessing
    if date_col is None:
        date_col = 0
    if desc_col is None:
        desc_col = 1 if len(header) > 1 else 0

    for row in table[header_idx + 1:]:
        if not row or all(not cell for cell in row):
            continue

        row_str = [clean_cell(cell) for cell in row]

        # Skip non-transaction rows (opening balance, totals, etc.)
        row_text = " ".join(row_str).lower()
        if any(kw in row_text for kw in ["opening balance", "closing balance", "total transactions", "abbreviations", "nominee", "base branch"]):
            continue

        # Extract date
        date_str = row_str[date_col] if date_col < len(row_str) else ""
        parsed_date = _parse_date(date_str)
        if not parsed_date:
            continue

        # Extract description
        description = row_str[desc_col] if desc_col < len(row_str) else ""

        # Extract amount — try debit first, then credit as negative
        amount = None
        is_credit = False
        if debit_col is not None and debit_col < len(row_str):
            amount = _parse_amount(row_str[debit_col])
        if amount is None and credit_col is not None and credit_col < len(row_str):
            amount = _parse_amount(row_str[credit_col])
            if amount:
                is_credit = True
        if amount is None and amount_col is not None and amount_col < len(row_str):
            amount = _parse_amount(row_str[amount_col])

        if amount is None or amount <= 0:
            continue

        transactions.append(
            ExpenseCreate(
                amount=-amount if is_credit else amount,
                category="salary" if is_credit and any(kw in description.lower() for kw in ["salary", "sal credit"]) else classify_category(description),
                payment_method=_classify_payment_method(description),
                description=description[:200],
                date=parsed_date,
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

        # Skip rows with very short/empty descriptions (likely parsing artifacts)
        clean_desc = re.sub(r"[^a-zA-Z]", "", description)
        if len(clean_desc) < 3:
            continue
        # Skip opening/closing balance lines
        if any(kw in description.lower() for kw in ["opening balance", "closing balance", "total"]):
            continue

        # Use the first amount as the transaction amount (usually debit)
        amount = _parse_amount(amounts[0])
        if amount is None or amount <= 0:
            continue

        transactions.append(
            ExpenseCreate(
                amount=amount,
                category=classify_category(description),
                payment_method=_classify_payment_method(description),
                description=description[:200],
                date=parsed_date,
                source="bank_pdf",
            )
        )

    return transactions


def _merge_fragmented_tables(tables: list[list]) -> list[list]:
    """Merge fragmented tables that share the same column structure.

    Some bank PDFs (Bank of Baroda, etc.) produce one table per row in
    pdfplumber. We detect tables with the same column count and merge
    them into a single table so the header-based parser can handle them.
    """
    if not tables:
        return tables

    # Group by column count
    groups: dict[int, list] = {}
    for table in tables:
        if not table:
            continue
        ncols = len(table[0]) if table else 0
        if ncols not in groups:
            groups[ncols] = []
        groups[ncols].append(table)

    merged = []
    for ncols, group_tables in groups.items():
        if len(group_tables) <= 1:
            merged.extend(group_tables)
            continue

        # Check if this looks like a fragmented transaction table
        # (multiple tables with same col count, most have 1-3 rows)
        total_rows = sum(len(t) for t in group_tables)
        avg_rows = total_rows / len(group_tables)

        if avg_rows <= 3 and len(group_tables) >= 3:
            # Likely fragmented — merge all rows into one table
            combined = []
            for t in group_tables:
                combined.extend(t)
            merged.append(combined)
        else:
            merged.extend(group_tables)

    return merged


def _find_col(header: list[str], keywords: list[str]) -> Optional[int]:
    for i, cell in enumerate(header):
        for kw in keywords:
            if kw in cell:
                return i
    return None
