"""Parse bank transaction alert emails into ExpenseCreate objects.

Supports:
- HDFC Bank UPI debit alerts
- HDFC Bank CC transaction alerts (OTP emails)
- Axis Bank Credit Card transaction alerts
"""

import re
from datetime import datetime
from typing import Optional

from ..schemas import ExpenseCreate


def _classify_category(description: str) -> str:
    desc_lower = description.lower()
    mapping = {
        "food": ["swiggy", "zomato", "restaurant", "food", "cafe", "pizza", "mcdonald", "domino", "kfc", "starbucks", "chai", "barista"],
        "shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho", "shopping", "mall", "reliance", "asspl"],
        "entertainment": ["netflix", "hotstar", "spotify", "movie", "pvr", "inox", "bookmyshow", "prime video", "cinepolis", "youtube", "google play"],
        "bills": ["electricity", "water", "gas", "broadband", "jio", "airtel", "vi ", "bsnl", "tata play", "recharge", "finance charges", "late fee"],
        "transport": ["uber", "ola", "metro", "fuel", "petrol", "irctc", "makemytrip", "cleartrip", "auto service", "rapido", "indian railways"],
        "health": ["hospital", "medical", "pharmacy", "doctor", "apollo", "1mg", "pharmeasy"],
        "groceries": ["bigbasket", "dmart", "blinkit", "zepto", "instamart", "grocery", "supermarket", "smart bazaar", "flour mill"],
        "education": ["school", "college", "course", "udemy", "coursera", "unacademy"],
        "emi": ["emi", "loan", "instalment"],
        "atm": ["atm", "cash withdrawal", "iccw atm"],
    }
    for category, keywords in mapping.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "other"


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from various formats found in bank emails."""
    date_str = date_str.strip()
    formats = [
        "%d-%m-%y",    # 06-02-26
        "%d-%m-%Y",    # 06-02-2026
        "%d/%m/%y",    # 06/02/26
        "%d/%m/%Y",    # 06/02/2026
        "%Y-%m-%d",    # 2026-02-06
        "%d %b %Y",    # 06 Feb 2026
        "%d %b %y",    # 06 Feb 26
        "%b %d, %Y",   # Feb 06, 2026
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


# HDFC UPI pattern:
# "Rs.10.00 has been debited from account 7247 to VPA 9234911014@axl ROHIT KUMAR SINGH on 06-02-26.
#  Your UPI transaction reference number is 581273702902."
HDFC_UPI_PATTERN = re.compile(
    r"Rs\.?\s?([\d,]+(?:\.\d{1,2})?)\s+has been debited from account\s+\w+\s+"
    r"to VPA\s+([\w.@]+)\s+(.+?)\s+on\s+(\d{2}-\d{2}-\d{2,4})\.\s*"
    r"Your UPI transaction reference number is\s+(\d+)",
    re.IGNORECASE,
)

# HDFC CC OTP pattern:
# "OTP is 160494 for txn of INR 804.00 at AMAZON PAY on HDFC Bank card ending 8705"
HDFC_CC_PATTERN = re.compile(
    r"(?:txn|transaction)\s+of\s+(?:INR|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)\s+"
    r"at\s+(.+?)\s+on\s+HDFC Bank card",
    re.IGNORECASE,
)

# HDFC credit (skip these):
# "Rs. 100000.00 is successfully credited to your account"
HDFC_CREDIT_PATTERN = re.compile(
    r"credited to your account",
    re.IGNORECASE,
)

# Axis CC pattern:
# "A transaction of INR 10,735.37 has been done on your Axis Bank Credit Card no. XX1088 at CLAUDE.AI on 26-02-2026"
# "INR 499.00 spent on Axis Bank Credit Card XX1088 at NETFLIX on 21-Feb-2026"
AXIS_CC_PATTERN = re.compile(
    r"(?:INR|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)\s+(?:has been done|spent)\s+on\s+.*?"
    r"(?:Axis Bank|axis bank).*?at\s+(.+?)\s+on\s+(\d{2}[-/]\d{2}[-/]\d{2,4}|\d{1,2}\s+\w{3}\s+\d{2,4})",
    re.IGNORECASE,
)


def parse_bank_email(subject: str, body: str, sender: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Route an email to the correct parser based on sender/subject."""
    sender_lower = sender.lower()

    if "hdfcbank" in sender_lower:
        return _parse_hdfc_email(subject, body, received_at)
    elif "axisbank" in sender_lower:
        return _parse_axis_email(subject, body, received_at)

    return None


def _parse_hdfc_email(subject: str, body: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Parse HDFC Bank email alerts (UPI debits and CC transactions)."""

    # Skip credit alerts
    if HDFC_CREDIT_PATTERN.search(body):
        return None

    # Try UPI debit pattern
    m = HDFC_UPI_PATTERN.search(body)
    if m:
        amount = float(m.group(1).replace(",", ""))
        vpa = m.group(2)
        name = m.group(3).strip()
        date_str = m.group(4)
        ref_id = m.group(5)

        txn_date = _parse_date(date_str) or received_at
        description = f"{name} ({vpa})" if name else vpa

        return ExpenseCreate(
            amount=amount,
            category=_classify_category(description),
            payment_method="upi",
            description=description[:200],
            date=txn_date,
            source="email_hdfc_bank",
            reference_id=ref_id,
        )

    # Try CC transaction pattern (from OTP emails)
    m = HDFC_CC_PATTERN.search(body)
    if m:
        amount = float(m.group(1).replace(",", ""))
        merchant = m.group(2).strip()

        return ExpenseCreate(
            amount=amount,
            category=_classify_category(merchant),
            payment_method="credit_card",
            description=merchant[:200],
            date=received_at,
            source="email_hdfc_cc",
            reference_id="",
        )

    return None


def _parse_axis_email(subject: str, body: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Parse Axis Bank CC transaction alerts."""

    # Skip credit/refund alerts
    if re.search(r"credited|refund", body, re.IGNORECASE):
        return None

    m = AXIS_CC_PATTERN.search(body)
    if m:
        amount = float(m.group(1).replace(",", ""))
        merchant = m.group(2).strip()
        date_str = m.group(3)
        txn_date = _parse_date(date_str) or received_at

        return ExpenseCreate(
            amount=amount,
            category=_classify_category(merchant),
            payment_method="credit_card",
            description=merchant[:200],
            date=txn_date,
            source="email_axis_cc",
            reference_id="",
        )

    return None
