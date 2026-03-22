"""Gmail OAuth and sync endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from ..config import FRONTEND_URL, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REDIRECT_URI
from ..database import get_db
from ..models import GmailAccount
from ..services.gmail_sync import sync_emails

router = APIRouter(prefix="/api/gmail", tags=["gmail"])

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _create_flow() -> Flow:
    """Create OAuth flow from env-based credentials."""
    if not GMAIL_CLIENT_ID or not GMAIL_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Gmail OAuth not configured")

    client_config = {
        "web": {
            "client_id": GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GMAIL_REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = GMAIL_REDIRECT_URI
    return flow


@router.get("/auth")
def gmail_auth():
    """Get Google OAuth URL to connect Gmail."""
    flow = _create_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return {"auth_url": auth_url}


@router.get("/callback")
def gmail_callback(code: str = Query(...), db: Session = Depends(get_db)):
    """OAuth callback — exchange code for tokens and save."""
    flow = _create_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Get user email
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "unknown")

    # Upsert gmail account (single user — replace existing)
    existing = db.query(GmailAccount).first()
    if existing:
        existing.email = email
        existing.access_token = creds.token
        existing.refresh_token = creds.refresh_token or existing.refresh_token
        existing.token_expiry = creds.expiry
    else:
        account = GmailAccount(
            email=email,
            access_token=creds.token,
            refresh_token=creds.refresh_token or "",
            token_expiry=creds.expiry,
        )
        db.add(account)

    db.commit()

    # Redirect back to frontend upload page
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


@router.post("/disconnect")
def gmail_disconnect(db: Session = Depends(get_db)):
    """Disconnect Gmail — remove stored tokens."""
    db.query(GmailAccount).delete()
    db.commit()
    return {"message": "Gmail disconnected"}
