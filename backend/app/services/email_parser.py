"""Parse bank transaction alert emails into ExpenseCreate objects.

Supports:
- HDFC Bank debit/credit alerts
- HDFC Credit Card transaction alerts
- Axis Bank Credit Card transaction alerts
"""

import re
from datetime import datetime
from typing import Optional

from ..schemas import ExpenseCreate


# Category classification (reuse from parsers)
def _classify_category(description: str) -> str:
    desc_lower = description.lower()
    mapping = {
        "food": ["swiggy", "zomato", "restaurant", "food", "cafe", "pizza", "mcdonald", "domino", "kfc", "starbucks", "chai", "barista"],
        "shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho", "shopping", "mall", "reliance", "asspl"],
        "entertainment": ["netflix", "hotstar", "spotify", "movie", "pvr", "inox", "bookmyshow", "prime video", "cinepolis", "youtube", "google play"],
        "bills": ["electricity", "water", "gas", "broadband", "jio", "airtel", "vi ", "bsnl", "tata play", "recharge", "finance charges", "late fee"],
        "transport": ["uber", "ola", "metro", "fuel", "petrol", "irctc", "makemytrip", "cleartrip", "auto service", "rapido"],
        "health": ["hospital", "medical", "pharmacy", "doctor", "apollo", "1mg", "pharmeasy"],
        "groceries": ["bigbasket", "dmart", "blinkit", "zepto", "instamart", "grocery", "supermarket", "smart bazaar", "flour mill"],
        "education": ["school", "college", "course", "udemy", "coursera", "unacademy"],
        "emi": ["emi", "loan", "instalment"],
    }
    for category, keywords in mapping.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "other"


def _parse_amount(text: str) -> Optional[float]:
    """Extract amount from text like 'Rs.302.00' or 'INR 10,735.37'."""
    match = re.search(r"(?:Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_date_from_email(text: str) -> Optional[datetime]:
    """Try to extract a transaction date/time from email body."""
    patterns = [
        # 21-02-2026 or 21/02/2026
        (r"(\d{2}[-/]\d{2}[-/]\d{4})", ["%d-%m-%Y", "%d/%m/%Y"]),
        # 2026-02-21
        (r"(\d{4}-\d{2}-\d{2})", ["%Y-%m-%d"]),
        # 21 Feb 2026
        (r"(\d{1,2}\s+\w{3}\s+\d{4})", ["%d %b %Y"]),
        # Feb 21, 2026
        (r"(\w{3}\s+\d{1,2},?\s+\d{4})", ["%b %d, %Y", "%b %d %Y"]),
    ]
    for pattern, fmts in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            for fmt in fmts:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Try to find time nearby: HH:MM:SS or HH:MM
                    time_match = re.search(
                        pattern + r"[:\s]+(\d{2}:\d{2}(?::\d{2})?)",
                        text,
                    )
                    if time_match:
                        time_str = time_match.group(2)
                        parts = time_str.split(":")
                        dt = dt.replace(hour=int(parts[0]), minute=int(parts[1]))
                        if len(parts) == 3:
                            dt = dt.replace(second=int(parts[2]))
                    return dt
                except ValueError:
                    continue
    return None


def parse_hdfc_bank_alert(subject: str, body: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Parse HDFC Bank account debit alert.

    Example subjects:
    - "Alert : Update on your HDFC Bank A/c XXXX8705"
    - "You have done a UPI txn. Check details!"

    Example body patterns:
    - "Rs.302.00 has been debited from account **8705 to VPA sumit@upi on 21-02-26"
    - "Rs 1,500.00 debited from a/c **8705 on 22-03-26 by UPI ref 498882856834"
    - "Money Sent! Rs.150.00 sent to VPA merchant@upi from HDFC Bank A/C xx8705 on 22-03-2026"
    """
    if "credit" in body.lower() and "debit" not in body.lower():
        return None  # Skip credit alerts

    amount = _parse_amount(body)
    if not amount:
        return None

    # Extract date from body, fall back to email received date
    txn_date = _parse_date_from_email(body) or received_at

    # Extract merchant/description
    # Pattern: "to VPA merchant@upi" or "at MERCHANT_NAME" or "to MERCHANT"
    description = ""
    desc_patterns = [
        r"(?:to|at)\s+VPA\s+([\w.@]+)",
        r"(?:at|to)\s+([A-Z][\w\s,]+?)(?:\s+on\s|\s+from\s|\s*$)",
        r"Info:\s*(.+?)(?:\s*$|\.\s)",
    ]
    for pat in desc_patterns:
        match = re.search(pat, body, re.IGNORECASE)
        if match:
            description = match.group(1).strip()
            break

    if not description:
        description = "HDFC Bank Transaction"

    # Extract UPI ref if present
    ref_match = re.search(r"(?:UPI\s*(?:ref|Ref)\s*(?:No\.?)?\s*:?\s*)(\d{8,})", body)
    ref_id = ref_match.group(1) if ref_match else ""

    # Determine payment method
    payment_method = "debit_card"
    if "upi" in body.lower() or "vpa" in body.lower():
        payment_method = "upi"
    elif "neft" in body.lower():
        payment_method = "neft"
    elif "imps" in body.lower():
        payment_method = "imps"
    elif "atm" in body.lower():
        payment_method = "cash"

    return ExpenseCreate(
        amount=amount,
        category=_classify_category(description),
        payment_method=payment_method,
        description=description[:200],
        date=txn_date,
        source="email_hdfc_bank",
        reference_id=ref_id,
    )


def parse_hdfc_cc_alert(subject: str, body: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Parse HDFC Credit Card transaction alert.

    Example body:
    - "Rs.499.00 spent on your HDFC Bank Credit Card ending 8705 at NETFLIX DI SI on 2026-02-21:10:03:00"
    - "Thank you for using your HDFC Bank Credit Card ending 8705 for Rs.302.00 at AMAZON on 21-02-2026"
    """
    amount = _parse_amount(body)
    if not amount:
        return None

    txn_date = _parse_date_from_email(body) or received_at

    # Extract merchant: "at MERCHANT_NAME on" or "at MERCHANT_NAME."
    description = ""
    match = re.search(r"\bat\s+([A-Z][\w\s,.]+?)(?:\s+on\s|\s*\.|\s*$)", body)
    if match:
        description = match.group(1).strip()
    if not description:
        description = "HDFC CC Transaction"

    return ExpenseCreate(
        amount=amount,
        category=_classify_category(description),
        payment_method="credit_card",
        description=description[:200],
        date=txn_date,
        source="email_hdfc_cc",
        reference_id="",
    )


def parse_axis_cc_alert(subject: str, body: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Parse Axis Bank Credit Card transaction alert.

    Example body:
    - "A transaction of INR 10,735.37 has been done on your Axis Bank Credit Card no. XX1088 at CLAUDE.AI SUBSCRIPTION on 26-02-2026"
    - "INR 499.00 spent on Axis Bank Credit Card XX1088 at NETFLIX on 21-Feb-2026"
    """
    amount = _parse_amount(body)
    if not amount:
        return None

    txn_date = _parse_date_from_email(body) or received_at

    description = ""
    match = re.search(r"\bat\s+([A-Z][\w\s,.]+?)(?:\s+on\s|\s*\.|\s*$)", body)
    if match:
        description = match.group(1).strip()
    if not description:
        description = "Axis CC Transaction"

    return ExpenseCreate(
        amount=amount,
        category=_classify_category(description),
        payment_method="credit_card",
        description=description[:200],
        date=txn_date,
        source="email_axis_cc",
        reference_id="",
    )


def parse_bank_email(subject: str, body: str, sender: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Route an email to the correct parser based on sender/subject."""
    sender_lower = sender.lower()
    subject_lower = subject.lower()

    # HDFC Bank account alerts
    if "hdfcbank" in sender_lower or "hdfc bank" in subject_lower:
        if "credit card" in subject_lower or "credit card" in body.lower()[:200]:
            return parse_hdfc_cc_alert(subject, body, received_at)
        return parse_hdfc_bank_alert(subject, body, received_at)

    # Axis Bank alerts
    if "axisbank" in sender_lower or "axis bank" in subject_lower:
        return parse_axis_cc_alert(subject, body, received_at)

    return None
