"""Gmail OAuth and sync endpoints."""

import base64
import hashlib
import json
import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import FRONTEND_URL, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REDIRECT_URI
from ..database import get_db
from ..models import Expense, GmailAccount, User
from ..services.gmail_sync import sync_emails, sync_statements

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

_pending_verifiers: dict[str, dict] = {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@router.get("/auth")
def gmail_auth(current_user: User = Depends(get_current_user)):
    """Get Google OAuth URL to connect Gmail."""
    if not GMAIL_CLIENT_ID:
        raise HTTPException(status_code=500, detail="OAuth not configured")

    code_verifier = _b64url(os.urandom(32))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    state = _b64url(os.urandom(16))
    _pending_verifiers[state] = {"verifier": code_verifier, "user_id": current_user.id}

    params = {
        "client_id": GMAIL_CLIENT_ID,
        "redirect_uri": GMAIL_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return {"auth_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


@router.get("/callback")
async def gmail_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    """OAuth callback — exchange code for tokens and save."""
    stored = _pending_verifiers.pop(state, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    code_verifier = stored["verifier"]
    user_id = stored["user_id"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GMAIL_CLIENT_ID,
                "client_secret": GMAIL_CLIENT_SECRET,
                "redirect_uri": GMAIL_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {resp.text}")

    token_data = resp.json()
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")

    creds = Credentials(token=access_token)
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "unknown")

    # Upsert gmail account for this user
    existing = db.query(GmailAccount).filter(GmailAccount.user_id == user_id).first()
    if existing:
        existing.email = email
        existing.access_token = access_token
        existing.refresh_token = refresh_token or existing.refresh_token
        existing.token_expiry = None
    else:
        db.add(GmailAccount(
            user_id=user_id,
            email=email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=None,
        ))

    db.commit()
    return RedirectResponse(url=f"{FRONTEND_URL}/upload?gmail=connected")


@router.get("/status")
def gmail_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if Gmail is connected + import summary."""
    account = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).first()
    if not account:
        return {"connected": False, "email": None, "last_sync": None, "import_summary": None}

    total = db.query(func.count(Expense.id)).filter(Expense.user_id == current_user.id).scalar() or 0
    min_date = db.query(func.min(Expense.date)).filter(Expense.user_id == current_user.id).scalar()
    max_date = db.query(func.max(Expense.date)).filter(Expense.user_id == current_user.id).scalar()

    source_counts = {}
    rows = db.query(Expense.source, func.count(Expense.id)).filter(Expense.user_id == current_user.id).group_by(Expense.source).all()
    for src, cnt in rows:
        source_counts[src] = cnt

    return {
        "connected": True,
        "email": account.email,
        "last_sync": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "import_summary": {
            "total_transactions": total,
            "earliest_date": min_date.isoformat() if min_date else None,
            "latest_date": max_date.isoformat() if max_date else None,
            "by_source": source_counts,
        },
    }


@router.post("/sync")
def gmail_sync(
    full: bool = Query(False),
    after: str = Query(""),
    before: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync bank alert emails from Gmail."""
    account = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    if full:
        account.last_sync_at = None
        db.commit()

    result = sync_emails(db, user_id=current_user.id, after_date=after or None, before_date=before or None)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.post("/sync-statements")
def gmail_sync_statements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find and parse CC/bank statement PDFs from Gmail attachments."""
    account = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    result = sync_statements(db, user_id=current_user.id)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.get("/debug")
def gmail_debug(
    q: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Debug: show raw email subjects/senders/body snippets."""
    from datetime import datetime, timedelta
    from google.auth.transport.requests import Request

    account = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    creds = Credentials(
        token=account.access_token, refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID, client_secret=GMAIL_CLIENT_SECRET,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        account.access_token = creds.token
        db.commit()

    service = build("gmail", "v1", credentials=creds)

    if q:
        query = q
    else:
        from ..services.gmail_sync import GMAIL_QUERY_SENDERS
        after_date = (datetime.now() - timedelta(days=90)).strftime("%Y/%m/%d")
        query = f"({GMAIL_QUERY_SENDERS}) after:{after_date}"

    results = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
    messages = results.get("messages", [])
    debug_data = {"query": query, "total_results": results.get("resultSizeEstimate", 0), "emails": []}

    from ..services.gmail_sync import _extract_email_body
    import re

    for msg_meta in messages:
        msg = service.users().messages().get(userId="me", id=msg_meta["id"], format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])
        subject = sender = date_val = ""
        for h in headers:
            if h["name"].lower() == "subject": subject = h["value"]
            elif h["name"].lower() == "from": sender = h["value"]
            elif h["name"].lower() == "date": date_val = h["value"]

        body = _extract_email_body(msg.get("payload", {}))
        body_clean = re.sub(r"<[^>]+>", " ", body)
        body_clean = re.sub(r"\s+", " ", body_clean).strip()
        debug_data["emails"].append({
            "subject": subject, "from": sender, "date": date_val,
            "body_preview": body_clean[:500], "body_length": len(body),
        })

    return debug_data


@router.post("/disconnect")
def gmail_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disconnect Gmail — remove stored tokens."""
    db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Gmail disconnected"}
