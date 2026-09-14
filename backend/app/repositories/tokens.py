# Access tokens: create signed JWTs and verify incoming access credentials.
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(user_id: uuid.UUID) -> str:
    """Return a signed access JWT for the supplied user UUID.

    Include the access token type, issued-at time, and configured expiry.
    This function neither persists the token nor sets browser cookies.
    """
    now = datetime.now(UTC)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """Verify a JWT signature and claims, then return its decoded payload.

    Reject an expired exp claim when present and require type to be access.
    Raise ValueError for JWT validation failures or an incorrect token type;
    AuthService separately validates the subject UUID and user existence.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc

    if payload.get("type") != "access":
        raise ValueError("Invalid token type")

    return payload
