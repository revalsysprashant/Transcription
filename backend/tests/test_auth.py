# Auth regression tests: exercise HTTP routes against isolated SQLite storage with async DB adapters.
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.utils.tokens import hash_refresh_token
from app.main import app
from app.models import RefreshSession, User
from app.repositories.tokens import decode_access_token


@pytest_asyncio.fixture
async def auth_client():
    """Yield an HTTP client, isolated SQLite session, async DB adapter, and test user.

    Override get_db so tests never access the configured application database.
    SQLite exercises transaction behavior but does not verify PostgreSQL concurrency.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    User.__table__.create(engine)
    RefreshSession.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = User(id=uuid.uuid4(), google_id="google-id", email="test@example.com")
        session.add(user)
        session.add(
            RefreshSession(
                user_id=user.id,
                token_hash=hash_refresh_token("original"),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.commit()
        db = AsyncMock()
        db.add = session.add
        for method in ("execute", "commit", "flush", "refresh", "rollback"):
            getattr(db, method).side_effect = getattr(session, method)

        async def override_db():
            """Provide the fixture database adapter to FastAPI requests."""
            yield db

        app.dependency_overrides[get_db] = override_db
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, session, db, user
        app.dependency_overrides.clear()
    engine.dispose()


@pytest.mark.asyncio
async def test_refresh_rotates_and_rejects_replay(auth_client):
    """Verify replacement cookies and stored hashes, then reject reuse of the old token."""
    client, session, _, user = auth_client
    client.cookies.set("refresh_token", "original", path="/auth")
    response = await client.post("/auth/refresh")
    assert response.status_code == 200
    assert decode_access_token(response.cookies["access_token"])["sub"] == str(user.id)
    replacement = response.cookies["refresh_token"]
    assert replacement != "original"
    rows = session.scalars(select(RefreshSession)).all()
    assert len(rows) == 2
    assert next(
        r for r in rows if r.token_hash == hash_refresh_token("original")
    ).revoked_at
    assert (
        next(
            r for r in rows if r.token_hash == hash_refresh_token(replacement)
        ).revoked_at
        is None
    )
    cookies = response.headers.get_list("set-cookie")
    assert all("HttpOnly" in c and "SameSite=" in c for c in cookies)
    assert "Path=/auth" in cookies[1]
    client.cookies.clear()
    client.cookies.set("refresh_token", "original", path="/auth")
    assert (await client.post("/auth/refresh")).status_code == 401


@pytest.mark.parametrize("kind", ["missing", "unknown", "expired", "revoked"])
@pytest.mark.asyncio
async def test_invalid_refresh(auth_client, kind):
    """Reject missing, unknown, expired, and revoked cookies without issuing a session."""
    client, session, _, _ = auth_client
    row = session.scalar(select(RefreshSession))
    if kind == "expired":
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif kind == "revoked":
        row.revoked_at = datetime.now(UTC)
    session.commit()
    if kind != "missing":
        client.cookies.set(
            "refresh_token",
            "unknown" if kind == "unknown" else "original",
            path="/auth",
        )
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert not response.headers.get_list("set-cookie")
    assert len(session.scalars(select(RefreshSession)).all()) == 1


@pytest.mark.parametrize("token", [None, "unknown", "original"])
@pytest.mark.asyncio
async def test_logout_is_idempotent_and_clears_cookies(auth_client, token):
    """Verify repeated logout succeeds, cookies expire, and revoked tokens cannot refresh."""
    client, session, _, _ = auth_client
    if token:
        client.cookies.set("refresh_token", token, path="/auth")
    response = await client.post("/auth/logout")
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert all("Max-Age=0" in c for c in cookies)
    assert "Path=/;" in cookies[0]
    assert "Path=/auth;" in cookies[1]
    if token == "original":
        assert session.scalar(select(RefreshSession)).revoked_at is not None
        client.cookies.clear()
        client.cookies.set("refresh_token", token, path="/auth")
        assert (await client.post("/auth/refresh")).status_code == 401
    assert (await client.post("/auth/logout")).status_code == 200


@pytest.mark.parametrize("failure_at", ["flush", "commit"])
@pytest.mark.asyncio
async def test_failed_rotation_rolls_back_revocation(auth_client, failure_at):
    """Preserve the original session when replacement flush or commit fails."""
    client, session, db, _ = auth_client
    getattr(db, failure_at).side_effect = RuntimeError("Database failure")
    client.cookies.set("refresh_token", "original", path="/auth")
    with pytest.raises(RuntimeError, match="Database failure"):
        await client.post("/auth/refresh")
    db.rollback.assert_awaited_once()
    assert session.scalar(select(RefreshSession)).revoked_at is None
    assert len(session.scalars(select(RefreshSession)).all()) == 1


@pytest.mark.asyncio
async def test_invalid_google_login_returns_401(auth_client, monkeypatch):
    """Return a sanitized 401 for Google verification failure without DB writes or cookies."""
    client, _, db, _ = auth_client

    def reject_token(*args, **kwargs):
        """Simulate a Google verification failure containing private error details."""
        raise ValueError("Sensitive verification details")

    monkeypatch.setattr("app.services.auth.id_token.verify_oauth2_token", reject_token)
    response = await client.post("/auth/google", json={"credential": "invalid"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid Google token"}
    assert not response.headers.get_list("set-cookie")
    db.execute.assert_not_awaited()
    db.commit.assert_not_awaited()
