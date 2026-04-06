"""SMS sync endpoint — accepts bank SMS messages from mobile app."""

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import re

from ..auth import get_current_user
from ..database import get_db
from ..models import AccountBalance, User
from ..schemas import ExpenseCreate
from ..services.sms_parser import parse_sms
from ..services.tracker import create_expenses_bulk_dedup

# Use /app/data which is mounted as a volume (persists across container rebuilds)
SMS_DUMP_DIR = "/app/data"
os.makedirs(SMS_DUMP_DIR, exist_ok=True)

router = APIRouter(prefix="/api/sms", tags=["sms"])


class ParsedInfo(BaseModel):
    type: str = ""  # debit or credit
    amount: float = 0
    merchant: str = ""
    reference_id: str = ""
    account_type: str = ""
    account_number: str = ""
    account_name: str = ""
    balance: Optional[float] = None


class SmsMessage(BaseModel):
    body: str
    sender: str = ""
    date: str = ""
    parsed: Optional[ParsedInfo] = None  # Pre-parsed by frontend library


class SmsSyncRequest(BaseModel):
    messages: list[SmsMessage]


@router.post("/sync")
def sync_sms(
    request: SmsSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import SMS transactions. Tries LLM parser first, falls back to regex."""
    from ..parsers.categorizer import classify_category

    # Dump raw incoming SMS for debugging
    try:
        dump_path = os.path.join(SMS_DUMP_DIR, f"sms_dump_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(dump_path, "w") as f:
            json.dump([m.model_dump() for m in request.messages], f, indent=2, default=str)
    except Exception as e:
        print(f"SMS dump error: {e}")

    parsed_expenses = []
    balances_extracted = []
    skipped = 0
    parse_method = "regex"

    # Try LLM parser first
    llm_results = _parse_sms_batch_llm(request.messages, user_name=current_user.name or "")

    if llm_results is not None:
        parse_method = "llm"
        parsed_expenses, balances_extracted, skipped = _build_expenses_from_llm(
            request.messages, llm_results, user_name=current_user.name or ""
        )
        # Debug: check if salary was built
        salary_exps = [e for e in parsed_expenses if e.category == "salary" or "WORKFORCE" in (e.description or "").upper()]
        if salary_exps:
            print(f"DEBUG: {len(salary_exps)} salary expenses built: {[(e.amount, e.description[:30]) for e in salary_exps]}")
        else:
            # Check if salary SMS was in the dump
            salary_indices = [i for i, m in enumerate(request.messages) if "225000" in (m.body or "") or "WORKFORCE" in (m.body or "").upper()]
            if salary_indices:
                print(f"DEBUG: Salary SMS at indices {salary_indices} but NO salary expense built!")
                for si in salary_indices:
                    print(f"  LLM result for [{si}]: {llm_results[si]}")
    else:
        # Fallback: regex-based parsing (per-message)
        for msg in request.messages:
            if msg.parsed and msg.parsed.amount > 0:
                if _should_skip_library_parsed(msg):
                    skipped += 1
                    continue

                is_credit = msg.parsed.type == "credit"
                amount = msg.parsed.amount
                bank = _detect_bank_from_sender(msg.sender)

                acct_type = msg.parsed.account_type.upper()
                if acct_type == "CARD":
                    payment_method = "credit_card"
                elif acct_type == "WALLET":
                    payment_method = "upi"
                else:
                    payment_method = "debit_card"

                is_cc = acct_type == "CARD"
                source = f"sms_{bank}_{'cc' if is_cc else 'bank'}" if bank else "sms_unknown"
                txn_date = _parse_sms_date(msg.date) or datetime.now()
                ref = msg.parsed.reference_id if msg.parsed.reference_id else f"sms:{msg.body[:150]}"

                description = msg.parsed.merchant or msg.parsed.account_name or ""
                if not description or description == "Bank Transaction":
                    description = _extract_merchant_from_body(msg.body) or "Bank Transaction"

                expense = ExpenseCreate(
                    amount=-amount if is_credit else amount,
                    category=classify_category(description, source=source, user_name=current_user.name or ""),
                    payment_method=payment_method,
                    description=description[:200],
                    date=txn_date,
                    source=source,
                    reference_id=ref,
                )
                parsed_expenses.append(expense)

                if msg.parsed.balance is not None:
                    balances_extracted.append({
                        "bank": bank or "unknown",
                        "account_hint": msg.parsed.account_number or "",
                        "balance": msg.parsed.balance,
                        "date": txn_date,
                    })
            else:
                result = parse_sms(msg.body, msg.sender, msg.date, user_name=current_user.name or "")
                if result["expense"]:
                    parsed_expenses.append(result["expense"])
                if result["balance"] is not None:
                    balances_extracted.append({
                        "bank": result["bank"],
                        "account_hint": result["account_hint"],
                        "balance": result["balance"],
                        "date": result["expense"].date if result["expense"] else datetime.now(),
                    })
                if not result["expense"] and result["balance"] is None:
                    skipped += 1

    # Dedup and save transactions
    imported_count = 0
    dup_count = 0
    if parsed_expenses:
        imported, duplicates = create_expenses_bulk_dedup(db, parsed_expenses, user_id=current_user.id)
        imported_count = len(imported)
        dup_count = len(duplicates)

        # Auto-recategorize with user's name
        from ..services.gmail_sync import _recategorize_others
        _recategorize_others(db, imported, current_user.id)

    # Save balances
    balances_saved = 0
    for bal in balances_extracted:
        # Only save if newer than existing
        existing = db.query(AccountBalance).filter(
            AccountBalance.user_id == current_user.id,
            AccountBalance.bank_name == bal["bank"],
            AccountBalance.account_hint == bal["account_hint"],
        ).order_by(AccountBalance.balance_date.desc()).first()

        if not existing or bal["date"] > existing.balance_date:
            db.add(AccountBalance(
                user_id=current_user.id,
                bank_name=bal["bank"],
                account_hint=bal["account_hint"],
                balance=bal["balance"],
                balance_date=bal["date"],
                source="sms",
            ))
            balances_saved += 1

    db.commit()

    return {
        "imported": imported_count,
        "duplicates": dup_count,
        "skipped": skipped,
        "messages_processed": len(request.messages),
        "balances_extracted": balances_saved,
        "parse_method": parse_method,
    }


@router.post("/test-parse")
def test_parse_sms(
    request: SmsSyncRequest,
    current_user: User = Depends(get_current_user),
):
    """Dry-run: show what the parser would do with each SMS. No DB writes."""
    from ..parsers.categorizer import classify_category

    results = []
    for msg in request.messages:
        entry = {
            "sender": msg.sender,
            "body": msg.body[:200],
            "date": msg.date,
        }

        # Check frontend library parse
        if msg.parsed and msg.parsed.amount > 0:
            bank = _detect_bank_from_sender(msg.sender)
            entry["source"] = "library"
            entry["action"] = "import"
            entry["parsed"] = {
                "type": msg.parsed.type,
                "amount": msg.parsed.amount,
                "merchant": msg.parsed.merchant,
                "bank": bank,
                "account_type": msg.parsed.account_type,
                "balance": msg.parsed.balance,
            }
        else:
            # Try backend parser
            result = parse_sms(msg.body, msg.sender, msg.date, user_name=current_user.name or "")
            if result["expense"]:
                entry["source"] = "backend"
                entry["action"] = "import"
                entry["parsed"] = {
                    "type": "credit" if result["is_credit"] else "debit",
                    "amount": abs(result["expense"].amount),
                    "merchant": result["expense"].description,
                    "bank": result["bank"],
                    "category": result["expense"].category,
                    "balance": result["balance"],
                }
            else:
                entry["source"] = "none"
                entry["action"] = "skip"
                entry["reason"] = "no parser matched"

        results.append(entry)

    imported = [r for r in results if r["action"] == "import"]
    skipped = [r for r in results if r["action"] == "skip"]
    return {
        "total": len(results),
        "would_import": len(imported),
        "would_skip": len(skipped),
        "results": results,
    }


@router.get("/balances")
def get_balances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest known balance per account."""
    from sqlalchemy import func

    # Get latest balance per bank+account combo
    subq = db.query(
        AccountBalance.bank_name,
        AccountBalance.account_hint,
        func.max(AccountBalance.balance_date).label("max_date"),
    ).filter(
        AccountBalance.user_id == current_user.id,
    ).group_by(
        AccountBalance.bank_name,
        AccountBalance.account_hint,
    ).subquery()

    latest = db.query(AccountBalance).join(
        subq,
        (AccountBalance.bank_name == subq.c.bank_name) &
        (AccountBalance.account_hint == subq.c.account_hint) &
        (AccountBalance.balance_date == subq.c.max_date) &
        (AccountBalance.user_id == current_user.id),
    ).all()

    accounts = []
    total_balance = 0
    for bal in latest:
        accounts.append({
            "bank": bal.bank_name,
            "account_hint": bal.account_hint,
            "balance": bal.balance,
            "as_of": bal.balance_date.isoformat(),
            "source": bal.source,
        })
        total_balance += bal.balance

    return {
        "accounts": accounts,
        "total_balance": round(total_balance, 2),
    }


def _should_skip_library_parsed(msg: SmsMessage) -> bool:
    """Validate library-parsed SMS — reject false positives the library picks up."""
    body = (msg.body or "").lower()
    sender = (msg.sender or "").upper()

    # Skip patterns: messages that contain amounts but are NOT actual transactions
    skip_patterns = [
        r"\bwill be auto.?debited\b",          # Future auto-debit notifications
        r"\bauto debit\b.*\bunsuccessful\b",    # Failed auto-debit
        r"\brenewal premium\b.*\bis due\b",     # Insurance premium due
        r"\bpayment of\b.*\bis due on\b",       # CC statement due
        r"\bdue on\b.*\bminimum amount\b",      # CC minimum due
        r"\bupcoming mandate\b",                # Mandate notifications
        r"\bfor the upcoming mandate\b",
        r"\bmandate\b.*\bcreated\b",            # Mandate created
        r"\bmandate\b.*\brevoke\b",             # Mandate revoked
        r"\bfund your\b",                       # Promotional (fund your account)
        r"\bclaim\b.*\bcashback\b",             # Cashback promo
        r"\bcashback\b.*\bon\b.*\bspends\b",    # Cashback on spends promo
        r"\bexpir\w*\b.*\brecharge\b",          # Airtel/Jio expiry + recharge
        r"\brecharge\b.*\bexpir\w*\b",
        r"\bplan\b.*\bexpir\w*\b",             # Plan expiry
        r"\bwe have received a payment\b",      # Payment receipt (not a spend)
        r"\bpayment is updated\b",              # Payment receipt
        r"\bpayment received of\b",             # Payment receipt
        r"\bpolicy\b.*\bpremium\b",             # Insurance
        r"\bpremium\b.*\bpolicy\b",
        r"\bkotak life\b",                      # Kotak Life insurance
        r"\bvouchers?\s+added\b",               # Voucher promos
        r"\bupto\s+rs\b.*\bvoucher",            # "Upto Rs.3550 Vouchers"
        r"\btransaction\s+reversed\b",           # Reversal notification (not a new txn)
        r"\bhas been received (?:towards|on) your\b.*\bcredit card\b",  # CC payment confirmation (dupes bank debit)
        r"\bsuccessfully credited towards your\b.*\bcredit card\b",  # Same
        r"\bpayment of rs\b.*\breceived on your\b.*\bcredit card\b",  # "Payment of Rs X has been received on your ICICI Bank Credit Card"
        r"\bbill\b.*\baccount\b.*\btel\b",      # BSNL landline bill notification
        r"\bincoming facility\b.*\bbarred\b",    # BSNL service barred
        r"\bamazon\s+voucher\b",                 # "Get an Amazon voucher worth INR 500"
        r"\brewards from\b.*\bspends\b",         # "rewards from Reliance, MakeMyTrip on spends"
        r"\bcashback\b.*\bcredited\b",           # "cashback of INR X has been credited"
        r"\bearn\b.*\bcashback\b",               # "Earn 1% cashback on..."
        r"\bbill dated\b",                       # "Your JioHome bill dated 16-Mar"
        r"\bbill has been sent\b",               # Bill notification
        r"\bnach debit towards\b",               # NACH debit notification (not a direct debit SMS)
        r"\bcongratulations\b.*\bcredited\b",    # "Congratulations! cashback credited"
    ]
    if any(re.search(pat, body) for pat in skip_patterns):
        return True

    # Skip non-bank senders that TRAI suffix caught
    non_bank_senders = [
        "AIRTEL", "AIRBIL", "BSNLED", "JUSPAY", "BILLBK",
        "CREDIN", "JIOPAY", "JIOINF", "ARTLTV",
    ]
    if any(s in sender for s in non_bank_senders):
        return True

    # Skip USD transactions where library parsed the INR available limit instead
    if re.search(r"\bspent\s+USD\b", msg.body or "", re.IGNORECASE):
        return True

    return False


def _extract_merchant_from_body(body: str) -> str:
    """Extract merchant/description from SMS body when library didn't."""
    if not body:
        return ""
    text = body.strip()

    patterns = [
        # "Spent INR 299\nAxis Bank Card no. XX1088\n29-03-26...\nYOUTUBEGOOG\n"
        # Merchant is the line after the date line in Axis "Spent" format
        r"Spent (?:INR|Rs\.?)\s*[\d,.]+\n.*Card.*XX\d{4}\n[\d-]+\s[\d:]+\s\w+\n(.+?)(?:\n|$)",
        # "Spent Rs.245 On HDFC Bank Card 8705 At ASSPL On 2026-"
        r"Spent Rs\.?[\d,.]+ (?:On|From) \w+ Bank Card \w+ At (.+?) On \d{4}",
        # "debited towards Google for INR 399.00"
        r"debited towards (.+?) for (?:INR|Rs)",
        # "INR 587.50 spent using ICICI Bank Card XX9009 on ... on BOOK MY SHOW"
        r"spent using .+? Card .+? on .+? on (.+?)(?:\.|,|\s+Avl)",
        # "A/c no. XX9570\n20-03-26...\nUPI/P2A/.../AJAY  GOPE"
        r"UPI/P2[AM]/\d+/(.+?)(?:\n|$)",
        # "Debit INR ...\nAxis Bank A/c XX9570\n...\nNBSM/.../BHARAT SANC"
        r"NBSM/\d+/(.+?)(?:\n|$)",
        # "trf to BINOD PANDIT" (Karnataka Bank)
        r"trf to (.+?)(?:\.|,|UPI:|\n|$)",
        # "Received Rs... from user@vpa"
        r"(?:Received|credited).*from\s+(\S+@\S+)\s",
        # "credited by Rs.60000 from SUMIT KUMAR on" (Karnataka Bank)
        r"credited by .+? from (.+?) on \d",
        # "credited.*Info APBS*HPCL LPG"
        r"credited.*Info\s+(.+?)(?:\.|$)",
        # "CreditCard Payment XX" (CC bill payment)
        r"(CreditCard Payment .+?)(?:\n|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            desc = m.group(1).strip()
            # Clean up
            desc = re.sub(r"\s+", " ", desc).strip()
            # Remove trailing "Not you?" etc
            desc = re.sub(r"\s*Not you\?.*$", "", desc, flags=re.IGNORECASE)
            if len(desc) >= 3:
                return desc
    return ""


def _detect_bank_from_sender(sender: str) -> str:
    s = (sender or "").upper()
    bank_map = {
        "hdfc": ["HDFC"], "axis": ["AXIS"], "sbi": ["SBI"],
        "kotak": ["KOTAK"], "scapia": ["SCAPIA", "FEDBK", "FED", "FEDSCP"],
        "icici": ["ICICI"], "bob": ["BOB", "BARODA"], "idfc": ["IDFC"],
        "yes_bank": ["YESBK"], "indusind": ["INDUS"],
        "citi": ["CITI"], "hsbc": ["HSBC"],
        "karnataka": ["KBLBNK"],
        "canara": ["CANBNK"],
    }
    for bank, patterns in bank_map.items():
        if any(p in s for p in patterns):
            return bank
    return ""


def _parse_sms_date(date_str: str):
    if not date_str:
        return None
    try:
        return datetime.fromtimestamp(int(date_str) / 1000)
    except (ValueError, TypeError, OSError):
        pass
    try:
        return datetime.fromisoformat(date_str.replace("Z", ""))
    except ValueError:
        pass
    return None


# ── LLM-based SMS Parser ──────────────────────────────────────

LLM_SMS_SYSTEM_PROMPT = """You are an Indian bank SMS parser. Today is {today}. The user's name is "{user_name}".

Analyze each SMS and determine if it is a REAL financial transaction (money actually debited or credited).

REAL transactions: actual debits, actual credits, UPI payments, card spends, NEFT/IMPS transfers, ATM withdrawals, salary credits, refunds.

NOT transactions (mark is_transaction=false):
- OTPs, verification codes
- Balance inquiries, available limit info
- Payment DUE reminders, upcoming auto-debit NOTIFICATIONS
- Promotional offers (vouchers, cashback offers, rewards)
- Card/account info updates, PIN generated, statement ready
- Failed/declined transactions
- Bill NOTIFICATIONS (bill generated, bill sent to email) vs actual bill PAYMENTS
- Mandate creation/revocation alerts
- Insurance/policy notifications
- Marketing SMS
- Credit limit changes

IMPORTANT:
- If the SMS contains the user's name "{user_name}" as the recipient, mark category as "transfer"
- CC bill payment confirmations (money received ON credit card) = mark category as "transfer"
- For "Sent Rs.X from Bank to VPA" format: this IS a real debit transaction
- Amount should always be positive. Use "type" field to indicate debit/credit.
- Extract merchant name from the SMS (clean up UPI IDs into readable names)

Return JSON: {{"results": [...]}}
Each result: {{"index": int, "is_transaction": bool, "type": "debit"|"credit", "amount": float, "merchant": "string", "category": "string", "ref_id": "string", "account_hint": "string", "balance": float|null, "payment_method": "string"}}

Valid categories: food, groceries, transport, entertainment, shopping, bills, subscriptions, health, education, rent, home, personal care, investment, emi, transfer, lent, borrowed, atm, salary, other
Valid payment_methods: credit_card, debit_card, upi, neft, imps, cash"""


def _parse_sms_batch_llm(messages: list[SmsMessage], user_name: str = "") -> list[dict] | None:
    """Parse SMS batch using LLM. Returns list of parsed results or None on failure."""
    import httpx

    if os.getenv("LLM_SMS_PARSER", "true").lower() == "false":
        return None

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return None

    model = os.getenv("LLM_SMS_PARSER_MODEL", "google/gemini-2.0-flash-001")
    today = datetime.now().strftime("%Y-%m-%d")
    system = LLM_SMS_SYSTEM_PROMPT.format(today=today, user_name=user_name)

    all_results = [None] * len(messages)
    batch_size = 50

    def _call_llm(indices_to_parse):
        """Send a batch of SMS indices to LLM. Returns number of results received."""
        sms_text = ""
        for idx in indices_to_parse:
            msg = messages[idx]
            sender = (msg.sender or "unknown")[:20]
            date_str = msg.date or ""
            try:
                ts = int(date_str) / 1000
                from datetime import datetime as dt
                date_fmt = dt.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError, OSError):
                date_fmt = date_str[:16] if date_str else "unknown"
            sms_text += f"\n[{idx}] Sender: {sender} | Date: {date_fmt}\n{(msg.body or '')[:300]}\n"

        try:
            resp = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": f"Parse these bank SMS messages:\n{sms_text}"},
                    ],
                    "max_tokens": 8192,
                    "response_format": {"type": "json_object"},
                },
                timeout=90,
            )

            if resp.status_code != 200:
                print(f"LLM SMS batch error: {resp.status_code} {resp.text[:200]}")
                return 0

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Try to fix common JSON issues (trailing commas, truncated)
            content = content.strip()
            if not content.endswith("}"):
                # Truncated — try to salvage
                last_brace = content.rfind("}")
                if last_brace > 0:
                    content = content[:last_brace + 1]
                    # Close the array if needed
                    if '"results"' in content and content.count("[") > content.count("]"):
                        content = content.rstrip().rstrip(",") + "]}"

            parsed = json.loads(content)
            results = parsed.get("results", [])

            matched = 0
            for r in results:
                idx = r.get("index", -1)
                if 0 <= idx < len(messages):
                    all_results[idx] = r
                    matched += 1
            return matched

        except Exception as e:
            print(f"LLM SMS batch exception: {e}")
            return 0

    # Pass 1: Process all SMS in batches
    for batch_start in range(0, len(messages), batch_size):
        batch_indices = list(range(batch_start, min(batch_start + batch_size, len(messages))))
        matched = _call_llm(batch_indices)
        print(f"LLM SMS pass 1 batch {batch_start}: {matched}/{len(batch_indices)}")

    # Pass 2: Retry any missed indices in smaller batches
    missed = [i for i in range(len(messages)) if all_results[i] is None]
    if missed:
        print(f"LLM SMS pass 2: retrying {len(missed)} missed SMS")
        retry_batch_size = 15  # Smaller batches for reliability
        for retry_start in range(0, len(missed), retry_batch_size):
            retry_indices = missed[retry_start:retry_start + retry_batch_size]
            matched = _call_llm(retry_indices)
            print(f"LLM SMS pass 2 retry: {matched}/{len(retry_indices)}")

    # Final stats
    filled = sum(1 for r in all_results if r is not None)
    still_missing = len(messages) - filled
    print(f"LLM SMS final: {filled}/{len(messages)} parsed, {still_missing} falling back to regex")

    return all_results


def _build_expenses_from_llm(
    messages: list[SmsMessage], llm_results: list[dict | None], user_name: str
) -> tuple[list[ExpenseCreate], list[dict], int]:
    """Convert LLM parse results into ExpenseCreate objects.
    For missing LLM results (None), falls back to regex parser.
    Returns (expenses, balances, skipped_count)."""
    from ..parsers.categorizer import classify_category

    expenses = []
    balances = []
    skipped = 0

    for i, result in enumerate(llm_results):
        # If LLM didn't return a result for this index, try regex fallback
        if result is None:
            msg = messages[i]
            fallback = parse_sms(msg.body, msg.sender, msg.date, user_name=user_name)
            if fallback["expense"]:
                expenses.append(fallback["expense"])
                if fallback["balance"] is not None:
                    balances.append({
                        "bank": fallback["bank"],
                        "account_hint": fallback["account_hint"],
                        "balance": fallback["balance"],
                        "date": fallback["expense"].date,
                    })
            else:
                skipped += 1
            continue

        if not result.get("is_transaction", False):
            skipped += 1
            continue

        try:
          msg = messages[i]
          amount = result.get("amount", 0)
          if not amount or amount <= 0:
            skipped += 1
            # Debug: log skipped transactions with large amounts in body
            if "225000" in (msg.body or "") or "WORKFORCE" in (msg.body or "").upper():
                print(f"DEBUG: Salary SMS at index {i} SKIPPED — amount={amount}, result={result}")
            continue

        is_credit = (result.get("type") or "debit") == "credit"
        bank = _detect_bank_from_sender(msg.sender)
        merchant = result.get("merchant") or ""

        # Determine source tag
        pm = result.get("payment_method") or "debit_card"
        is_cc = pm == "credit_card"
        source = f"sms_{bank}_{'cc' if is_cc else 'bank'}" if bank else "sms_unknown"

        # Parse date
        txn_date = _parse_sms_date(msg.date) or datetime.now()

        # Reference ID
        ref_id = result.get("ref_id") or ""
        ref = ref_id if ref_id else f"sms:{msg.body[:150]}"

        # Category — use LLM's category but let user rules override
        llm_cat = result.get("category") or "other"
        # Apply user-specific rules via categorizer (might override LLM)
        rule_cat = classify_category(merchant, source=source, user_name=user_name)
        category = rule_cat if rule_cat != "other" else llm_cat

        expenses.append(ExpenseCreate(
            amount=-amount if is_credit else amount,
            category=category,
            payment_method=pm,
            description=merchant[:200] if merchant else "Bank Transaction",
            date=txn_date,
            source=source,
            reference_id=ref,
        ))

        # Balance extraction
        balance = result.get("balance")
        if balance is not None:
            balances.append({
                "bank": bank or "unknown",
                "account_hint": result.get("account_hint") or "",
                "balance": balance,
                "date": txn_date,
            })
        except Exception as e:
            print(f"LLM build error at index {i}: {e}")
            # Try regex fallback for this message
            msg = messages[i]
            fallback = parse_sms(msg.body, msg.sender, msg.date, user_name=user_name)
            if fallback["expense"]:
                expenses.append(fallback["expense"])
            else:
                skipped += 1

    return expenses, balances, skipped
