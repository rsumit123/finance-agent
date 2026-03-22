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
from ..models import GmailAccount
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
    """Extract plain text body from Gmail message payload."""
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                body += base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
            elif "parts" in part:
                # Nested multipart
                body += _extract_email_body(part)
    elif "body" in payload and "data" in payload["body"]:
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    return body


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
        "error": None,
    }
