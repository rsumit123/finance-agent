"""App configuration from environment variables."""

import os

GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET", "")
GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "http://localhost:8000/api/gmail/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
