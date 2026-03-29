#!/usr/bin/env python3
"""Test SMS parser locally against a dump file.

Usage:
  python test_sms_parser.py <sms_dump.json>
  python test_sms_parser.py <sms_dump.json> --imported   # show only imported
  python test_sms_parser.py <sms_dump.json> --skipped    # show only skipped
  python test_sms_parser.py <sms_dump.json> --verbose    # show full SMS body
"""

import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.sms_parser import parse_sms

# Inline the skip logic to avoid importing the router (which needs jwt, sqlalchemy, etc.)
import re

class _FakeParsed:
    def __init__(self, d):
        self.type = d.get("type", "")
        self.amount = d.get("amount", 0)
        self.merchant = d.get("merchant", "")
        self.reference_id = d.get("reference_id", "")
        self.account_type = d.get("account_type", "")
        self.account_number = d.get("account_number", "")
        self.account_name = d.get("account_name", "")
        self.balance = d.get("balance")

class _FakeMsg:
    def __init__(self, body, sender, date, parsed):
        self.body = body
        self.sender = sender
        self.date = date
        self.parsed = _FakeParsed(parsed) if parsed else None

def _should_skip_library_parsed(msg):
    body = (msg.body or "").lower()
    sender = (msg.sender or "").upper()
    skip_patterns = [
        r"\bwill be auto.?debited\b",
        r"\bauto debit\b.*\bunsuccessful\b",
        r"\brenewal premium\b.*\bis due\b",
        r"\bpayment of\b.*\bis due on\b",
        r"\bdue on\b.*\bminimum amount\b",
        r"\bupcoming mandate\b",
        r"\bfor the upcoming mandate\b",
        r"\bmandate\b.*\bcreated\b",
        r"\bmandate\b.*\brevoke\b",
        r"\bfund your\b",
        r"\bclaim\b.*\bcashback\b",
        r"\bcashback\b.*\bon\b.*\bspends\b",
        r"\bexpir\w*\b.*\brecharge\b",
        r"\brecharge\b.*\bexpir\w*\b",
        r"\bplan\b.*\bexpir\w*\b",
        r"\bwe have received a payment\b",
        r"\bpayment is updated\b",
        r"\bpayment received of\b",
        r"\bpolicy\b.*\bpremium\b",
        r"\bpremium\b.*\bpolicy\b",
        r"\bkotak life\b",
    ]
    if any(re.search(pat, body) for pat in skip_patterns):
        return True
    non_bank_senders = [
        "AIRTEL", "AIRBIL", "BSNLED", "JUSPAY", "BILLBK",
        "CREDIN", "JIOPAY", "JIOINF", "ARTLTV",
    ]
    if any(s in sender for s in non_bank_senders):
        return True
    if re.search(r"\bspent\s+USD\b", msg.body or "", re.IGNORECASE):
        return True
    return False


def test_file(path, show_imported=True, show_skipped=True, verbose=False):
    with open(path) as f:
        messages = json.load(f)

    imported = []
    skipped = []
    library_parsed = []

    for i, msg in enumerate(messages):
        body = msg.get("body", "")
        sender = msg.get("sender", "")
        date = msg.get("date", "")
        pre_parsed = msg.get("parsed")

        # Check if frontend library already parsed it
        if pre_parsed and pre_parsed.get("amount", 0) > 0:
            # Test the skip validation
            sms_msg = _FakeMsg(body=body, sender=sender, date=date, parsed=pre_parsed)
            if _should_skip_library_parsed(sms_msg):
                skipped.append({
                    "index": i,
                    "sender": sender,
                    "body": body if verbose else body[:120],
                    "bank": "",
                    "reason": "library-skip-filter",
                })
                continue

            library_parsed.append({
                "index": i,
                "sender": sender,
                "body": body[:120],
                "type": pre_parsed.get("type"),
                "amount": pre_parsed.get("amount"),
                "merchant": pre_parsed.get("merchant"),
                "account_type": pre_parsed.get("account_type"),
            })
            # Also test backend parser to compare
            result = parse_sms(body, sender, date, user_name="")
            if not result["expense"]:
                library_parsed[-1]["backend_would_skip"] = True
        else:
            # Backend parser
            result = parse_sms(body, sender, date, user_name="")
            entry = {
                "index": i,
                "sender": sender,
                "body": body if verbose else body[:120],
            }
            if result["expense"]:
                entry["type"] = "credit" if result["is_credit"] else "debit"
                entry["amount"] = abs(result["expense"].amount)
                entry["description"] = result["expense"].description
                entry["category"] = result["expense"].category
                entry["bank"] = result["bank"]
                entry["balance"] = result["balance"]
                imported.append(entry)
            else:
                entry["bank"] = result["bank"]
                skipped.append(entry)

    # Print summary
    print(f"\n{'='*70}")
    print(f"Total SMS: {len(messages)}")
    print(f"Library-parsed (frontend): {len(library_parsed)}")
    print(f"Backend-imported: {len(imported)}")
    print(f"Skipped: {len(skipped)}")
    print(f"{'='*70}\n")

    if show_imported and library_parsed:
        print(f"\n--- LIBRARY-PARSED ({len(library_parsed)}) ---")
        for e in library_parsed:
            flag = " ⚠️ BACKEND WOULD SKIP" if e.get("backend_would_skip") else ""
            print(f"  [{e['index']}] {e['type']:6s} ₹{e['amount']:>10,.2f}  {e.get('merchant','')[:40]:40s}  ({e['sender'][:20]}){flag}")

    if show_imported and imported:
        print(f"\n--- BACKEND-IMPORTED ({len(imported)}) ---")
        for e in imported:
            print(f"  [{e['index']}] {e['type']:6s} ₹{e['amount']:>10,.2f}  {e['description'][:40]:40s}  [{e['category']:15s}] ({e['bank']})")
            if verbose:
                print(f"         SMS: {e['body'][:200]}")

    if show_skipped and skipped:
        print(f"\n--- SKIPPED ({len(skipped)}) ---")
        for e in skipped:
            print(f"  [{e['index']}] {e['sender'][:25]:25s}  {e['body'][:100]}")

    # Flag potential false positives (library parsed but look suspicious)
    suspicious = [e for e in library_parsed if e.get("amount", 0) > 0 and not e.get("merchant")]
    if suspicious:
        print(f"\n--- ⚠️  SUSPICIOUS (no merchant) ---")
        for e in suspicious:
            print(f"  [{e['index']}] {e['type']:6s} ₹{e['amount']:>10,.2f}  ({e['sender'][:20]})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    flags = sys.argv[2:]

    show_imported = "--skipped" not in flags
    show_skipped = "--imported" not in flags
    verbose = "--verbose" in flags

    test_file(path, show_imported, show_skipped, verbose)
