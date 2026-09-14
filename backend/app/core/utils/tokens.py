# Refresh-token utilities: generate opaque tokens, hash them, and calculate expiry.
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import settings


def generate_refresh_token() -> str:
    """Return a cryptographically random opaque token for a refresh cookie.

    Persist only its hash; the raw value is the browser session credential.
    """
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Return the hexadecimal SHA-256 digest of a raw refresh token.

    Use the same digest to store new sessions and look up incoming cookies.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_refresh_token_expiry() -> datetime:
    """Return a timezone-aware UTC expiry using the configured refresh lifetime."""
    return datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
