"""Google Sign-In authentication endpoints."""

import base64
import hashlib
import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user
from ..config import FRONTEND_URL, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GOOGLE_LOGIN_REDIRECT_URI
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_SCOPES = ["openid", "email", "profile"]

# In-memory PKCE store (single server)
_login_verifiers: dict[str, str] = {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@router.get("/google")
def google_login(redirect_to: str = Query("")):
    """Get Google OAuth URL for sign-in."""
    if not GMAIL_CLIENT_ID:
        raise HTTPException(status_code=500, detail="OAuth not configured")

    code_verifier = _b64url(os.urandom(32))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    state = _b64url(os.urandom(16))
    _login_verifiers[state] = {"verifier": code_verifier, "redirect_to": redirect_to}

    params = {
        "client_id": GMAIL_CLIENT_ID,
        "redirect_uri": GOOGLE_LOGIN_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(LOGIN_SCOPES),
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return {"auth_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    """Google OAuth callback: exchange code, create/find user, issue JWT."""
    stored = _login_verifiers.pop(state, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    code_verifier = stored["verifier"] if isinstance(stored, dict) else stored
    redirect_to = stored.get("redirect_to", "") if isinstance(stored, dict) else ""

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GMAIL_CLIENT_ID,
                "client_secret": GMAIL_CLIENT_SECRET,
                "redirect_uri": GOOGLE_LOGIN_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {resp.text}")

    token_data = resp.json()
    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="No id_token in response")

    # Decode ID token to get user info (Google's public keys verify it, but for simplicity we trust it from Google's token endpoint)
    import jwt as pyjwt
    user_info = pyjwt.decode(id_token, options={"verify_signature": False})

    google_id = user_info.get("sub")
    email = user_info.get("email", "")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Could not get user info from Google")

    # Find or create user
    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        # Update profile
        user.name = name
        user.picture = picture
        user.email = email
    else:
        user = User(google_id=google_id, email=email, name=name, picture=picture)
        db.add(user)

    db.commit()
    db.refresh(user)

    # Issue JWT
    token = create_token(user.id)

    # Redirect back — use provided redirect_to or default FRONTEND_URL
    base = redirect_to if redirect_to else FRONTEND_URL
    return RedirectResponse(url=f"{base}/login/callback?token={token}")


@router.post("/google/token")
async def google_token_login(
    body: dict,
    db: Session = Depends(get_db),
):
    """Login with a Google ID token (from native mobile app).

    Accepts: { "id_token": "..." }
    Returns: { "token": "jwt...", "user": {...} }
    """
    id_token = body.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="id_token required")

    import jwt as pyjwt
    try:
        user_info = pyjwt.decode(id_token, options={"verify_signature": False})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id_token")

    google_id = user_info.get("sub")
    email = user_info.get("email", "")
    name = user_info.get("name", "")
    picture = user_info.get("picture", "")

    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Could not get user info")

    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        user.name = name
        user.picture = picture
        user.email = email
    else:
        user = User(google_id=google_id, email=email, name=name, picture=picture)
        db.add(user)

    db.commit()
    db.refresh(user)

    token = create_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "picture": current_user.picture,
    }
