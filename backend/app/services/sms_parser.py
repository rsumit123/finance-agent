"""Parse bank SMS messages into transaction data.

Handles SMS formats from major Indian banks:
- HDFC Bank (debit/credit alerts)
- Axis Bank (CC and bank alerts)
- SBI (debit alerts)
- Kotak Bank (debit alerts)
- Scapia/Federal Bank (CC alerts)
- ICICI Bank (CC and bank alerts)
"""

import re
from datetime import datetime
from typing import Optional

from ..schemas import ExpenseCreate
from ..parsers.categorizer import classify_category


def parse_sms(body: str, sender: str, sms_date: str = "", user_name: str = "") -> dict:
    """Parse a single bank SMS message.

    Returns: {
        "expense": ExpenseCreate or None,
        "balance": float or None,
        "account_hint": str (e.g. "8705", "1088"),
        "bank": str,
        "is_credit": bool,
    }
    """
    if not body:
        return {"expense": None, "balance": None, "account_hint": "", "bank": "", "is_credit": False}

    sender_upper = (sender or "").upper()
    body_text = body.strip()

    # Detect bank from sender ID
    bank = _detect_bank_from_sender(sender_upper)
    if not bank:
        return {"expense": None, "balance": None, "account_hint": "", "bank": "", "is_credit": False}

    # Skip OTP messages
    if re.search(r"\bOTP\b|\bone.time.password\b|\bverification.code\b", body_text, re.IGNORECASE):
        return {"expense": None, "balance": None, "account_hint": "", "bank": bank, "is_credit": False}

    # Extract amount
    amount = _extract_amount(body_text)
    if not amount:
        return {"expense": None, "balance": None, "account_hint": "", "bank": bank, "is_credit": False}

    # Detect credit vs debit
    is_credit = bool(re.search(r"\bcredited\b|\breceived\b|\bcredit\b|\brefund\b", body_text, re.IGNORECASE))
    is_debit = bool(re.search(r"\bdebited\b|\bspent\b|\bdebit\b|\bpurchase\b|\bpaid\b|\bwithdraw", body_text, re.IGNORECASE))

    if not is_debit and not is_credit:
        # Can't determine type, skip
        return {"expense": None, "balance": None, "account_hint": "", "bank": bank, "is_credit": False}

    # Extract date
    txn_date = _extract_date(body_text) or _parse_sms_date(sms_date) or datetime.now()

    # Extract account number hint
    account_hint = _extract_account(body_text)

    # Extract description/merchant
    description = _extract_description(body_text)

    # Extract balance
    balance = _extract_balance(body_text)

    # Extract reference ID
    ref_id = _extract_ref(body_text)

    # Determine payment method
    payment_method = "debit_card"
    if re.search(r"credit.card|CC\s|card.ending", body_text, re.IGNORECASE):
        payment_method = "credit_card"
    elif re.search(r"\bUPI\b|\bVPA\b", body_text, re.IGNORECASE):
        payment_method = "upi"
    elif re.search(r"\bNEFT\b", body_text, re.IGNORECASE):
        payment_method = "neft"
    elif re.search(r"\bIMPS\b", body_text, re.IGNORECASE):
        payment_method = "imps"
    elif re.search(r"\bATM\b|\bwithdraw", body_text, re.IGNORECASE):
        payment_method = "cash"

    # Build source tag
    is_cc = payment_method == "credit_card"
    source = f"sms_{bank}_{'cc' if is_cc else 'bank'}"

    expense = ExpenseCreate(
        amount=-amount if is_credit else amount,
        category=classify_category(description, source=source, user_name=user_name),
        payment_method=payment_method,
        description=description[:200],
        date=txn_date,
        source=source,
        reference_id=ref_id,
    )

    return {
        "expense": expense,
        "balance": balance,
        "account_hint": account_hint,
        "bank": bank,
        "is_credit": is_credit,
    }


def _detect_bank_from_sender(sender: str) -> str:
    """Detect bank from SMS sender ID."""
    s = sender.upper()
    bank_map = {
        "HDFC": ["HDFCBK", "HDFC", "HDFCBANK"],
        "axis": ["AXISBK", "AXIS", "AXISBNK"],
        "sbi": ["SBIBNK", "SBIETX", "SBIINB", "ATMSBI"],
        "kotak": ["KOTAKB", "KOTAK", "KOTAKM"],
        "scapia": ["SCAPIA", "FEDBK", "FEDBNK"],
        "icici": ["ICICIB", "ICICI", "ICICIB"],
        "bob": ["BOBTXN", "BARODA"],
        "pnb": ["PNBSMS"],
        "idfc": ["IDFCFB"],
        "yes_bank": ["YESBK"],
        "indusind": ["IDBIBK"],
    }
    for bank, senders in bank_map.items():
        if any(sid in s for sid in senders):
            return bank
    return ""


def _extract_amount(text: str) -> Optional[float]:
    """Extract transaction amount from SMS."""
    patterns = [
        r"(?:Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)",
        r"(?:₹)\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _extract_balance(text: str) -> Optional[float]:
    """Extract available balance from SMS."""
    patterns = [
        r"(?:Avl\.?\s*Bal\.?|Available\s*Balance|Bal\.?)\s*(?:is\s*)?(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)",
        r"(?:Avl\.?\s*Bal\.?|Balance)\s*[:=]\s*(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _extract_date(text: str) -> Optional[datetime]:
    """Extract transaction date from SMS."""
    patterns = [
        (r"(\d{2}-\d{2}-\d{2,4})", ["%d-%m-%y", "%d-%m-%Y"]),
        (r"(\d{2}/\d{2}/\d{2,4})", ["%d/%m/%y", "%d/%m/%Y"]),
        (r"(\d{2}\w{3}\d{2,4})", ["%d%b%y", "%d%b%Y"]),
        (r"(\d{2}\s\w{3}\s\d{2,4})", ["%d %b %y", "%d %b %Y"]),
    ]
    for pattern, fmts in patterns:
        m = re.search(pattern, text)
        if m:
            for fmt in fmts:
                try:
                    return datetime.strptime(m.group(1), fmt)
                except ValueError:
                    continue
    return None


def _parse_sms_date(date_str: str) -> Optional[datetime]:
    """Parse the SMS received date."""
    if not date_str:
        return None
    try:
        # Try ISO format
        return datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        pass
    try:
        # Try timestamp (milliseconds)
        return datetime.fromtimestamp(int(date_str) / 1000)
    except (ValueError, TypeError, OSError):
        pass
    return None


def _extract_account(text: str) -> str:
    """Extract account/card number hint."""
    patterns = [
        r"(?:a/c|account|acct)\s*\**\s*(\d{4})",
        r"(?:card\s*(?:ending|no\.?)\s*(?:in\s*)?)\s*(\d{4})",
        r"XX(\d{4})",
        r"\*+(\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def _extract_description(text: str) -> str:
    """Extract merchant/description from SMS."""
    patterns = [
        r"(?:at|to|towards|for)\s+(.+?)(?:\s+on\s|\s+Ref|\s+Avl|\s*\.\s|$)",
        r"(?:to VPA|VPA)\s+([\w.@]+)\s*(.+?)(?:\s+on\s|\s+Ref|\s*\.\s|$)",
        r"(?:from|by)\s+(.+?)(?:\s+on\s|\s+Ref|\s+Avl|\s*\.\s|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            desc = " ".join(m.groups()).strip()
            # Clean up
            desc = re.sub(r"\s+", " ", desc).strip()
            if len(desc) > 3:
                return desc
    return "Bank Transaction"


def _extract_ref(text: str) -> str:
    """Extract transaction reference ID."""
    patterns = [
        r"(?:UPI\s*Ref|Ref\s*(?:No\.?)?)\s*[:.]?\s*(\d{6,})",
        r"(?:IMPS\s*Ref|NEFT\s*Ref)\s*[:.]?\s*(\S{6,})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""
