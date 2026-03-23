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
from ..parsers.categorizer import classify_category


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

    if "scapia" in sender_lower or "scapia" in subject.lower():
        return _parse_scapia_email(subject, body, received_at)
    elif "hdfcbank" in sender_lower:
        return _parse_hdfc_email(subject, body, received_at)
    elif "axisbank" in sender_lower:
        return _parse_axis_email(subject, body, received_at)

    return None


def _parse_hdfc_email(subject: str, body: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Parse HDFC Bank email alerts (UPI debits and CC transactions)."""

    # Check if it's a credit
    is_credit = bool(HDFC_CREDIT_PATTERN.search(body))

    # Try credit pattern first
    if is_credit:
        # Parse credit (money received)
        m = re.search(
            r"Rs\.?\s?([\d,]+(?:\.\d{1,2})?)\s+is\s+successfully\s+credited\s+to\s+your\s+account\s+\*\*\w+\s+"
            r"by\s+VPA\s+([\w.@]+)\s+(.+?)\s+on\s+(\d{2}-\d{2}-\d{2,4})\.",
            body, re.IGNORECASE,
        )
        if m:
            amount = float(m.group(1).replace(",", ""))
            vpa = m.group(2)
            name = m.group(3).strip()
            date_str = m.group(4)
            txn_date = _parse_date(date_str) or received_at
            ref_match = re.search(r"UPI\s+transaction\s+reference\s+number\s+is\s+(\d+)", body)
            ref_id = ref_match.group(1) if ref_match else ""
            return ExpenseCreate(
                amount=-amount,
                category="transfer",
                payment_method="upi",
                description=f"{name} ({vpa})"[:200],
                date=txn_date,
                source="email_hdfc_bank",
                reference_id=ref_id,
            )
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
            category=classify_category(description),
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
            category=classify_category(merchant),
            payment_method="credit_card",
            description=merchant[:200],
            date=received_at,
            source="email_hdfc_cc",
            reference_id="",
        )

    return None


# Scapia pattern:
# "Your payment on 22-03-2026 at 06:07 PM using your Scapia Federal RuPay Credit Card ending in 8921
#  has been successfully processed. Amount ₹30.00 Merchant Vijay Kumar Paswan"
SCAPIA_PATTERN = re.compile(
    r"payment on\s+(\d{2}-\d{2}-\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)\s+"
    r"using your Scapia.*?Amount\s*₹([\d,]+(?:\.\d{1,2})?)\s+"
    r"Merchant\s+(.+?)(?:\s+Not you\?|$)",
    re.IGNORECASE | re.DOTALL,
)


def _parse_scapia_email(subject: str, body: str, received_at: datetime) -> Optional[ExpenseCreate]:
    """Parse Scapia Federal Credit Card transaction alert."""
    # Skip non-transaction emails (promos, fuel surcharge waivers, etc.)
    if "transaction was successful" not in subject.lower():
        return None

    m = SCAPIA_PATTERN.search(body)
    if not m:
        return None

    date_str = m.group(1)  # 22-03-2026
    time_str = m.group(2).strip()  # 06:07 PM
    amount_str = m.group(3)  # 30.00
    merchant = m.group(4).strip()  # Vijay Kumar Paswan

    txn_date = _parse_date(date_str)
    if not txn_date:
        txn_date = received_at

    # Parse time
    try:
        t = datetime.strptime(time_str, "%I:%M %p")
        txn_date = txn_date.replace(hour=t.hour, minute=t.minute)
    except ValueError:
        pass

    amount = float(amount_str.replace(",", ""))

    return ExpenseCreate(
        amount=amount,
        category=classify_category(merchant),
        payment_method="credit_card",
        description=merchant[:200],
        date=txn_date,
        source="email_scapia",
        reference_id="",
    )


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
            category=classify_category(merchant),
            payment_method="credit_card",
            description=merchant[:200],
            date=txn_date,
            source="email_axis_cc",
            reference_id="",
        )

    return None
