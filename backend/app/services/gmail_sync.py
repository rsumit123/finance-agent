"""Gmail API sync service — fetches bank alert emails and parses transactions."""

import base64
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from ..config import GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET
from ..models import GmailAccount, PdfPassword
from ..parsers import detect_and_parse, parse_credit_card_statement, parse_bank_statement
from ..schemas import ExpenseCreate
from ..services.email_parser import parse_bank_email
from ..services.tracker import create_expenses_bulk_dedup


# Bank sender addresses to search
BANK_SENDERS = [
    "alerts@hdfcbank.net",
    "alerts@hdfcbank.com",
    "noreply@hdfcbank.net",
    "creditcards@hdfcbank.net",
    "alerts@axisbank.com",
    "alerts@axisbank.co.in",
    "credit-cards@axisbank.com",
    "scapiacards@federalbank.co.in",
]

# Gmail search query
GMAIL_QUERY_SENDERS = " OR ".join(f"from:{s}" for s in BANK_SENDERS)


def _get_credentials(account: GmailAccount) -> Credentials:
    """Build Google credentials from stored tokens, refreshing if needed."""
    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
    )

    if account.token_expiry:
        creds.expiry = account.token_expiry

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds


def _extract_email_body(payload: dict) -> str:
    """Extract text body from Gmail message payload.

    Tries text/plain first, falls back to text/html (stripped of tags).
    Many bank alert emails are HTML-only.
    """
    plain = ""
    html = ""

    def _walk(part: dict):
        nonlocal plain, html
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data", "")

        if mime == "text/plain" and data:
            plain += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime == "text/html" and data:
            html += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)

    if plain:
        return plain

    if html:
        # Strip HTML tags to get readable text
        text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&rsquo;|&lsquo;|&#39;", "'", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"&#\d+;", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    return ""


def _get_header(headers: list[dict], name: str) -> str:
    """Get a header value from Gmail message headers."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def sync_emails(db: Session) -> dict:
    """Fetch new bank alert emails from Gmail and parse into transactions.

    Returns: { imported: int, duplicates: int, emails_scanned: int, error: str|None }
    """
    account = db.query(GmailAccount).first()
    if not account:
        return {"imported": 0, "duplicates": 0, "emails_scanned": 0, "error": "Gmail not connected"}

    try:
        creds = _get_credentials(account)
    except Exception as e:
        return {"imported": 0, "duplicates": 0, "emails_scanned": 0, "error": f"Auth failed: {str(e)}"}

    # Update stored tokens if refreshed
    if creds.token != account.access_token:
        account.access_token = creds.token
        if creds.expiry:
            account.token_expiry = creds.expiry
        db.commit()

    service = build("gmail", "v1", credentials=creds)

    # Build search query
    query = f"({GMAIL_QUERY_SENDERS})"
    if account.last_sync_at:
        # Search from 1 day before last sync to catch any missed
        after_date = (account.last_sync_at - timedelta(days=1)).strftime("%Y/%m/%d")
        query += f" after:{after_date}"
    else:
        # First sync: go back 90 days
        after_date = (datetime.now() - timedelta(days=90)).strftime("%Y/%m/%d")
        query += f" after:{after_date}"

    # Fetch message IDs
    try:
        results = service.users().messages().list(
            userId="me", q=query, maxResults=200
        ).execute()
    except Exception as e:
        return {"imported": 0, "duplicates": 0, "emails_scanned": 0, "error": f"Gmail API error: {str(e)}"}

    messages = results.get("messages", [])
    if not messages:
        account.last_sync_at = datetime.now()
        db.commit()
        return {"imported": 0, "duplicates": 0, "emails_scanned": 0, "error": None}

    # Fetch and parse each message
    parsed_expenses: list[ExpenseCreate] = []
    emails_scanned = 0

    for msg_meta in messages:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_meta["id"], format="full"
            ).execute()
        except Exception:
            continue

        emails_scanned += 1
        headers = msg.get("payload", {}).get("headers", [])
        subject = _get_header(headers, "Subject")
        sender = _get_header(headers, "From")
        date_str = _get_header(headers, "Date")

        # Parse received date
        try:
            received_at = parsedate_to_datetime(date_str)
            # Make naive for consistency
            received_at = received_at.replace(tzinfo=None)
        except Exception:
            received_at = datetime.now()

        body = _extract_email_body(msg.get("payload", {}))
        if not body:
            continue

        # Clean body: remove HTML artifacts, extra whitespace
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()

        expense = parse_bank_email(subject, body, sender, received_at)
        if expense:
            parsed_expenses.append(expense)

    # Dedup and save
    if parsed_expenses:
        imported, duplicates = create_expenses_bulk_dedup(db, parsed_expenses)
        imported_count = len(imported)
        dup_count = len(duplicates)
    else:
        imported_count = 0
        dup_count = 0

    # Update last sync timestamp
    account.last_sync_at = datetime.now()
    db.commit()

    return {
        "imported": imported_count,
        "duplicates": dup_count,
        "emails_scanned": emails_scanned,
        "statements_found": 0,
        "statement_transactions": 0,
        "error": None,
    }


def sync_statements(db: Session) -> dict:
    """Find CC/bank statement PDF attachments in Gmail, download and parse them.

    Searches for emails with subjects like 'credit card statement', 'account statement'
    that have PDF attachments. Downloads each PDF, tries saved passwords, and parses.

    Returns: { statements_found, imported, duplicates, error }
    """
    import os
    import tempfile

    account = db.query(GmailAccount).first()
    if not account:
        return {"statements_found": 0, "imported": 0, "duplicates": 0, "error": "Gmail not connected"}

    try:
        creds = _get_credentials(account)
    except Exception as e:
        return {"statements_found": 0, "imported": 0, "duplicates": 0, "error": f"Auth failed: {str(e)}"}

    if creds.token != account.access_token:
        account.access_token = creds.token
        if creds.expiry:
            account.token_expiry = creds.expiry
        db.commit()

    service = build("gmail", "v1", credentials=creds)

    # Get saved passwords
    passwords = [pw.password for pw in db.query(PdfPassword).all()]
    # Always try None (no password) first
    passwords_to_try = [None] + passwords

    # Search for statement emails with PDF attachments
    query = (
        "(subject:\"credit card statement\" OR subject:\"card statement\" "
        "OR subject:\"account statement\" OR subject:\"bank statement\") "
        "has:attachment filename:pdf"
    )

    # Go back 180 days for statements
    after_date = (datetime.now() - timedelta(days=180)).strftime("%Y/%m/%d")
    query += f" after:{after_date}"

    try:
        results = service.users().messages().list(
            userId="me", q=query, maxResults=50
        ).execute()
    except Exception as e:
        return {"statements_found": 0, "imported": 0, "duplicates": 0, "error": f"Gmail API error: {str(e)}"}

    messages = results.get("messages", [])
    if not messages:
        return {"statements_found": 0, "imported": 0, "duplicates": 0, "error": None}

    all_parsed: list[ExpenseCreate] = []
    statements_found = 0

    statements_detail = []  # list of { bank, filename, transactions }

    for msg_meta in messages:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_meta["id"], format="full"
            ).execute()
        except Exception:
            continue

        headers = msg.get("payload", {}).get("headers", [])
        subject = _get_header(headers, "Subject")
        sender = _get_header(headers, "From")

        # Detect bank from sender/subject
        bank = _detect_bank(sender, subject)

        # Find PDF attachments
        pdf_parts = _find_pdf_attachments(msg.get("payload", {}))

        for part in pdf_parts:
            attachment_id = part.get("body", {}).get("attachmentId")
            filename = part.get("filename", "statement.pdf")
            if not attachment_id:
                continue

            # Download attachment
            try:
                att = service.users().messages().attachments().get(
                    userId="me", messageId=msg_meta["id"], id=attachment_id
                ).execute()
            except Exception:
                continue

            pdf_data = base64.urlsafe_b64decode(att["data"])

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_data)
                tmp_path = tmp.name

            # Try parsing with each password
            parsed = None
            try:
                for pwd in passwords_to_try:
                    try:
                        _, txns = detect_and_parse(tmp_path, password=pwd)
                        if txns:
                            parsed = txns
                            break
                    except Exception:
                        continue
            finally:
                os.unlink(tmp_path)

            if parsed:
                statements_found += 1
                # Tag each transaction with bank-specific source
                source_tag = f"stmt_{bank}" if bank else "credit_card_pdf"
                for txn in parsed:
                    txn.source = source_tag
                all_parsed.extend(parsed)
                statements_detail.append({
                    "bank": bank or "unknown",
                    "filename": filename,
                    "transactions": len(parsed),
                })

    # Dedup and save
    if all_parsed:
        imported, duplicates = create_expenses_bulk_dedup(db, all_parsed)
        return {
            "statements_found": statements_found,
            "imported": len(imported),
            "duplicates": len(duplicates),
            "statements": statements_detail,
            "error": None,
        }

    return {"statements_found": statements_found, "imported": 0, "duplicates": 0, "statements": [], "error": None}


def _detect_bank(sender: str, subject: str) -> str:
    """Detect bank name from email sender/subject."""
    text = (sender + " " + subject).lower()
    if "scapia" in text:
        return "scapia"
    if "hdfc" in text:
        return "hdfc"
    if "axis" in text:
        return "axis"
    if "icici" in text:
        return "icici"
    if "sbi" in text:
        return "sbi"
    if "kotak" in text:
        return "kotak"
    if "idfc" in text:
        return "idfc"
    if "yes bank" in text or "yesbank" in text:
        return "yes_bank"
    if "bob" in text or "bank of baroda" in text:
        return "bob"
    return "unknown"


def _find_pdf_attachments(payload: dict) -> list[dict]:
    """Recursively find all PDF attachment parts in a Gmail message payload."""
    results = []
    filename = payload.get("filename", "")
    if filename.lower().endswith(".pdf") and payload.get("body", {}).get("attachmentId"):
        results.append(payload)

    for part in payload.get("parts", []):
        results.extend(_find_pdf_attachments(part))

    return results
