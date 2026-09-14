"""Additional HTTP checks covering route gaps with isolated database storage."""

import uuid

import pytest
from sqlalchemy import select
from test_auth import (
    auth_client as auth_client,  # noqa: PLC0414 -- shared pytest fixture
)

from app.core.config import settings
from app.models import User
from app.repositories.tokens import create_access_token


@pytest.mark.asyncio
async def test_public_routes(auth_client):
    client, _, _, _ = auth_client
    assert (await client.get("/health")).json() == {"status": "ok"}
    response = await client.get("/audio/limits")
    assert response.status_code == 200
    assert response.json() == {
        "max_size_bytes": settings.max_audio_size_mb * 1_000_000,
        "max_duration_seconds": settings.max_audio_duration_seconds,
    }
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert (await client.get(path)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("new_user", [False, True])
async def test_google_login_and_profile(auth_client, monkeypatch, new_user):
    client, session, _, user = auth_client
    identity = {
        "sub": "new-google-id" if new_user else user.google_id,
        "email": "new@example.com" if new_user else user.email,
        "name": "Route Test",
        "picture": "https://example.com/avatar.png",
    }
    monkeypatch.setattr(
        "app.services.auth.id_token.verify_oauth2_token",
        lambda *args, **kwargs: identity,
    )
    response = await client.post("/auth/google", json={"credential": "test-credential"})
    assert response.status_code == 200
    assert {"access_token", "refresh_token"} <= set(response.cookies.keys())
    # Explicitly attach the token so this check also works with secure-cookie settings.
    client.cookies.clear()
    client.cookies.set("access_token", response.cookies["access_token"])
    profile = await client.get("/auth/me")
    assert profile.status_code == 200
    saved_user = session.scalar(select(User).where(User.google_id == identity["sub"]))
    assert profile.json() == {
        "id": str(saved_user.id),
        "email": saved_user.email,
        "name": saved_user.name,
        "avatar_url": saved_user.avatar_url,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("token_kind", ["missing", "malformed", "unknown_user"])
async def test_profile_rejects_invalid_auth(auth_client, token_kind):
    client, _, _, _ = auth_client
    if token_kind != "missing":
        client.cookies.set(
            "access_token",
            "invalid"
            if token_kind == "malformed"
            else create_access_token(uuid.uuid4()),
        )
    assert (await client.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"credential": None}])
async def test_google_requires_credential(auth_client, payload):
    client, _, _, _ = auth_client
    assert (await client.post("/auth/google", json=payload)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,expected",
    [
        ("invalid_audio", 400),
        ("tools_unavailable", 503),
        ("provider_unavailable", 503),
    ],
)
async def test_upload_error_mapping(auth_client, monkeypatch, failure, expected):
    from unittest.mock import AsyncMock

    from app.providers.groq import TranscriptionUnavailableError

    client, _, _, user = auth_client
    client.cookies.set("access_token", create_access_token(user.id))
    errors = {
        "invalid_audio": ValueError("private details"),
        "tools_unavailable": RuntimeError("private details"),
        "provider_unavailable": TranscriptionUnavailableError("Provider unavailable"),
    }
    monkeypatch.setattr(
        "app.services.audio.AudioService.receive_upload",
        AsyncMock(side_effect=errors[failure]),
    )
    response = await client.post(
        "/audio/upload", files={"file": ("bad.wav", b"invalid")}
    )
    assert response.status_code == expected
    assert "private details" not in response.text


@pytest.mark.asyncio
async def test_audio_request_validation(auth_client):
    client, _, _, user = auth_client
    client.cookies.set("access_token", create_access_token(user.id))
    for suffix in ("", "/download", "/export/txt"):
        assert (await client.get("/audio/not-a-uuid" + suffix)).status_code == 422
    response = await client.post(
        "/audio/upload",
        files={"file": ("a.wav", b"invalid")},
        data={"language": "english"},
    )
    assert response.status_code == 422
    response = await client.post("/audio/upload", files={"file": ("a.wav", b"invalid")})
    assert response.status_code == 400
