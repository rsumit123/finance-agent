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

import json as json_lib
import threading

from ..auth import get_current_user
from ..config import FRONTEND_URL, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REDIRECT_URI
from ..database import get_db, SessionLocal
from ..models import Expense, GmailAccount, SyncJob, User
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
    job_type: str = Query("all", pattern="^(alerts|statements|all)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a background sync job. Returns job_id immediately."""
    account = db.query(GmailAccount).filter(GmailAccount.user_id == current_user.id).first()
    if not account:
        raise HTTPException(status_code=400, detail="Gmail not connected")

    # Check for already running job
    running = db.query(SyncJob).filter(
        SyncJob.user_id == current_user.id,
        SyncJob.status.in_(["pending", "running"]),
    ).first()
    if running:
        return {"job_id": running.id, "status": running.status, "message": "Sync already in progress"}

    if full:
        account.last_sync_at = None
        db.commit()

    # Create job record
    job = SyncJob(user_id=current_user.id, job_type=job_type, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    user_id = current_user.id

    # Run in background thread
    def run_sync():
        from datetime import datetime
        db_bg = SessionLocal()
        try:
            bg_job = db_bg.query(SyncJob).filter(SyncJob.id == job_id).first()
            bg_job.status = "running"
            db_bg.commit()

            results = {}

            if job_type in ("alerts", "all"):
                alerts_result = sync_emails(db_bg, user_id=user_id, after_date=after or None, before_date=before or None)
                results["alerts"] = alerts_result

            if job_type in ("statements", "all"):
                stmts_result = sync_statements(db_bg, user_id=user_id)
                results["statements"] = stmts_result

            bg_job.result = json_lib.dumps(results, default=str)
            bg_job.status = "completed"
            bg_job.completed_at = datetime.now()
        except Exception as e:
            bg_job.status = "failed"
            bg_job.error = str(e)[:500]
            bg_job.completed_at = datetime.now()
        finally:
            db_bg.commit()
            db_bg.close()

    thread = threading.Thread(target=run_sync, daemon=True)
    thread.start()

    return {"job_id": job_id, "status": "pending", "message": "Sync started"}


@router.get("/sync/latest")
def get_latest_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the most recent sync job result."""
    job = db.query(SyncJob).filter(
        SyncJob.user_id == current_user.id,
    ).order_by(SyncJob.created_at.desc()).first()

    if not job:
        return {"job_id": None, "status": None}

    response = {
        "job_id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if job.status == "completed" and job.result:
        response["result"] = json_lib.loads(job.result)
    if job.status == "failed":
        response["error"] = job.error
    return response


@router.get("/sync/{job_id}")
def get_sync_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll sync job status."""
    job = db.query(SyncJob).filter(SyncJob.id == job_id, SyncJob.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        "job_id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }

    if job.status == "completed" and job.result:
        response["result"] = json_lib.loads(job.result)
    if job.status == "failed":
        response["error"] = job.error

    return response


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
