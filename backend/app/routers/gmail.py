"""Gmail OAuth and sync endpoints."""

import hashlib
import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from ..config import FRONTEND_URL, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REDIRECT_URI
from ..database import get_db
from ..models import GmailAccount
from ..services.gmail_sync import sync_emails

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# In-memory store for code_verifier (single-user app, single server)
_pending_verifiers: dict[str, str] = {}


@router.get("/auth")
def gmail_auth():
    """Get Google OAuth URL to connect Gmail."""
    if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Gmail OAuth not configured")

    # Generate PKCE code verifier and challenge
    code_verifier = base64url_encode(os.urandom(32))
    code_challenge = base64url_encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    )

    # Use a simple state token to link auth and callback
    state = base64url_encode(os.urandom(16))
    _pending_verifiers[state] = code_verifier

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

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"auth_url": auth_url}


@router.get("/callback")
async def gmail_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    """OAuth callback — exchange code for tokens and save."""
    if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Gmail OAuth not configured")

    # Retrieve code verifier
    code_verifier = _pending_verifiers.pop(state, None)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    # Exchange code for tokens
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

    # Get user email
    creds = Credentials(token=access_token)
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "unknown")

    # Upsert gmail account (single user — replace existing)
    existing = db.query(GmailAccount).first()
    if existing:
        existing.email = email
        existing.access_token = access_token
        existing.refresh_token = refresh_token or existing.refresh_token
        existing.token_expiry = None
    else:
        account = GmailAccount(
            email=email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=None,
        )
        db.add(account)

    db.commit()

    return RedirectResponse(url=f"{FRONTEND_URL}/upload?gmail=connected")


@router.get("/status")
def gmail_status(db: Session = Depends(get_db)):
    """Check if Gmail is connected."""
    account = db.query(GmailAccount).first()
    if not account:
        return {"connected": False, "email": None, "last_sync": None}

    return {
        "connected": True,
        "email": account.email,
        "last_sync": account.last_sync_at.isoformat() if account.last_sync_at else None,
    }


@router.post("/sync")
def gmail_sync(db: Session = Depends(get_db)):
    """Sync bank alert emails from Gmail."""
    account = db.query(GmailAccount).first()
    if not account:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    result = sync_emails(db)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/debug")
def gmail_debug(db: Session = Depends(get_db)):
    """Debug: show raw email subjects/senders/body snippets from last sync query."""
    import base64
    import re
    from datetime import datetime, timedelta

    from google.auth.transport.requests import Request

    account = db.query(GmailAccount).first()
    if not account:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GMAIL_CLIENT_ID,
        client_secret=GMAIL_CLIENT_SECRET,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        account.access_token = creds.token
        db.commit()

    service = build("gmail", "v1", credentials=creds)

    from ..services.gmail_sync import GMAIL_QUERY_SENDERS
    after_date = (datetime.now() - timedelta(days=90)).strftime("%Y/%m/%d")
    query = f"({GMAIL_QUERY_SENDERS}) after:{after_date}"

    results = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
    messages = results.get("messages", [])

    debug_data = {"query": query, "total_results": results.get("resultSizeEstimate", 0), "emails": []}

    for msg_meta in messages:
        msg = service.users().messages().get(userId="me", id=msg_meta["id"], format="full").execute()
        headers = msg.get("payload", {}).get("headers", [])

        subject = ""
        sender = ""
        date_val = ""
        for h in headers:
            if h["name"].lower() == "subject":
                subject = h["value"]
            elif h["name"].lower() == "from":
                sender = h["value"]
            elif h["name"].lower() == "date":
                date_val = h["value"]

        # Extract body
        from ..services.gmail_sync import _extract_email_body
        body = _extract_email_body(msg.get("payload", {}))
        body_clean = re.sub(r"<[^>]+>", " ", body)
        body_clean = re.sub(r"\s+", " ", body_clean).strip()

        debug_data["emails"].append({
            "subject": subject,
            "from": sender,
            "date": date_val,
            "body_preview": body_clean[:500],
            "body_length": len(body),
        })

    return debug_data


@router.post("/disconnect")
def gmail_disconnect(db: Session = Depends(get_db)):
    """Disconnect Gmail — remove stored tokens."""
    db.query(GmailAccount).delete()
    db.commit()
    return {"message": "Gmail disconnected"}


def base64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
