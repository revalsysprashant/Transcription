# Test only file receipt and authentication; use the existing isolated auth fixture.
import io
import wave

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from test_auth import (
    auth_client as auth_client,  # noqa: PLC0414 -- shared pytest fixture
)

from app.core.config import settings
from app.models import Transcription
from app.repositories.tokens import create_access_token


@compiles(JSONB, "sqlite")
def compile_jsonb_for_storage_tests(element, compiler, **kwargs):
    """Use SQLite JSON in isolated tests while production retains PostgreSQL JSONB."""
    return "JSON"


@pytest_asyncio.fixture(autouse=True)
async def isolated_storage(auth_client, tmp_path, monkeypatch):
    """Create a test-only job table and keep saved audio in a temporary directory."""
    _, db_session, _, _ = auth_client
    Transcription.__table__.create(db_session.get_bind())
    monkeypatch.setattr(settings, "audio_storage_dir", tmp_path)
    yield tmp_path


@pytest.mark.asyncio
async def test_receive_file_metadata(auth_client):
    """Count multiple chunks accurately without creating a database record."""
    client, db_session, db, user = auth_client
    client.cookies.set("access_token", create_access_token(user.id))
    # A real three-second WAV exercises FFprobe and multiple read chunks.
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 48000)
    content = buffer.getvalue()
    response = await client.post(
        "/audio/upload", files={"file": ("sample.wav", content, "audio/wav")}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["normalized"]["transcription"].pop("processing_time_ms") >= 0
    job_id = body.pop("id")
    assert body.pop("status") == "COMPLETED"
    assert body == {
        "filename": "sample.wav",
        "content_type": "audio/wav",
        "size_mb": round(len(content) / 1_000_000, 2),
        "duration": 3.0,
        "sample_rate": 16000,
        "channels": 1,
        "bitrate": 256000,
        "codec": "pcm_s16le",
        "format": "wav",
        "normalized": {
            "speech_ranges": [],
            "speech_clips": [],
            "transcription": {"text": "", "detected_languages": [], "segments": []},
            "duration": 3.0,
            "sample_rate": 16000,
            "channels": 1,
            "bitrate": 256000,
            "codec": "pcm_s16le",
            "format": "wav",
        },
    }
    db.commit.assert_awaited_once()
    job = db_session.scalar(select(Transcription))
    assert str(job.id) == job_id and job.user_id == user.id
    assert job.file_size_bytes == len(content)
    assert (
        settings.audio_storage_dir / job.original_storage_key
    ).read_bytes() == content
    saved = await client.get(f"/audio/{job_id}")
    assert saved.status_code == 200
    assert saved.json()["transcript_text"] == ""
    assert saved.json()["segments"] == []
    assert saved.json()["size_mb"] == round(len(content) / 1_000_000, 2)
    assert "original_storage_key" not in saved.json()


@pytest.mark.asyncio
async def test_receive_requires_login(auth_client):
    """Reject a request with no access cookie before the service processes the file."""
    client, _, _, _ = auth_client
    response = await client.post(
        "/audio/upload", files={"file": ("sample.wav", b"abc", "audio/wav")}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_receive_requires_file(auth_client):
    """Require a multipart file field for authenticated requests."""
    client, _, _, user = auth_client
    client.cookies.set("access_token", create_access_token(user.id))
    response = await client.post("/audio/upload")
    assert response.status_code == 422


@pytest.mark.parametrize("provider_fails", [False, True])
@pytest.mark.asyncio
async def test_upload_transcription_response(auth_client, monkeypatch, provider_fails):
    """Exercise extraction through the HTTP response while replacing only VAD and Groq."""
    from app.providers.groq import TranscriptionProviderError
    from app.schemas.audio import SpeechRange
    from app.schemas.transcription import ClipTranscription

    client, _, _, user = auth_client
    client.cookies.set("access_token", create_access_token(user.id))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 48000)
    paths = []

    async def transcribe(path, language):
        """Confirm clips exist during the request and simulate a provider result."""
        assert path.exists()
        assert language == "en"
        paths.append(path)
        if provider_fails:
            raise TranscriptionProviderError(
                "Transcription provider request failed; please retry"
            )
        return ClipTranscription(
            text="Hello.",
            language="english",
            segments=[{"start": 0, "end": 0.5, "text": "Hello."}],
        )

    monkeypatch.setattr(
        "app.services.audio.detect_speech", lambda path: [SpeechRange(start=1, end=2)]
    )
    monkeypatch.setattr(
        "app.services.transcription.GroqProvider.transcribe", transcribe
    )
    response = await client.post(
        "/audio/upload",
        files={"file": ("sample.wav", buffer.getvalue(), "audio/wav")},
        data={"language": "en"},
    )
    assert response.status_code == (502 if provider_fails else 200)
    if not provider_fails:
        result = response.json()["normalized"]["transcription"]
        assert result["text"] == "Hello."
        assert result["segments"] == [{"start": 1.0, "end": 1.5, "text": "Hello."}]
    assert paths and all(not path.exists() for path in paths)
    if not provider_fails:
        saved = await client.get(f"/audio/{response.json()['id']}")
        assert saved.json()["transcript_text"] == "Hello."
        assert saved.json()["segments"] == result["segments"]
        assert saved.json()["requested_language"] == "en"
        assert saved.json()["detected_language"] == "english"
    else:
        assert not list(settings.audio_storage_dir.rglob("*.audio"))


@pytest.mark.parametrize("failure_at", ["flush", "commit", "file"])
@pytest.mark.asyncio
async def test_storage_failure_cleans_files(auth_client, monkeypatch, failure_at):
    """A failed file copy or DB write leaves no completed job or stored original."""
    client, db_session, db, user = auth_client
    client.cookies.set("access_token", create_access_token(user.id))
    if failure_at == "file":
        from unittest.mock import Mock

        monkeypatch.setattr(
            "app.repositories.storage.shutil.copyfileobj",
            Mock(side_effect=OSError("private path")),
        )
    else:
        getattr(db, failure_at).side_effect = RuntimeError("private database details")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)
    response = await client.post(
        "/audio/upload", files={"file": ("sample.wav", buffer.getvalue(), "audio/wav")}
    )
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to save audio and transcription"}
    assert db_session.scalar(select(Transcription)) is None
    assert not list(settings.audio_storage_dir.rglob("*.audio"))


@pytest.mark.asyncio
async def test_saved_job_is_owner_only(auth_client):
    """An authenticated user cannot retrieve another user's saved transcription."""
    import uuid

    from app.models import User

    client, db_session, _, user = auth_client
    other = User(id=uuid.uuid4(), google_id="other-google", email="other@example.com")
    db_session.add(other)
    job = Transcription(
        user_id=other.id,
        original_filename="private.wav",
        original_storage_key="private",
        mime_type="audio/wav",
        file_size_bytes=1,
    )
    db_session.add(job)
    db_session.commit()
    client.cookies.set("access_token", create_access_token(user.id))
    assert (await client.get(f"/audio/{job.id}")).status_code == 404
    assert (await client.get(f"/audio/{uuid.uuid4()}")).status_code == 404
    client.cookies.clear()
    assert (await client.get(f"/audio/{job.id}")).status_code == 401


@pytest.mark.asyncio
async def test_download_original_and_range(auth_client):
    """Download exact stored bytes, safely name the attachment, and support ranges."""
    from uuid import uuid4

    client, db_session, _, user = auth_client
    content = b"RIFFexample-original-audio-bytes"
    job_id = uuid4()
    key = f"{user.id}/{job_id}.audio"
    path = settings.audio_storage_dir / key
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    db_session.add(
        Transcription(
            id=job_id,
            user_id=user.id,
            original_filename="../recording.wav",
            original_storage_key=key,
            mime_type="audio/wav",
            file_size_bytes=len(content),
        )
    )
    db_session.commit()
    client.cookies.set("access_token", create_access_token(user.id))
    response = await client.get(f"/audio/{job_id}/download")
    assert response.status_code == 200
    assert response.content == content
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="recording.wav"'
    )
    assert response.headers["cache-control"] == "private, no-store"
    partial = await client.get(
        f"/audio/{job_id}/download", headers={"Range": "bytes=0-3"}
    )
    assert partial.status_code == 206
    assert partial.content == content[:4]
    assert path.read_bytes() == content
    path.unlink()
    assert (await client.get(f"/audio/{job_id}/download")).status_code == 404


@pytest.mark.asyncio
async def test_download_ownership(auth_client):
    """Reject missing/foreign jobs and unauthenticated download requests."""
    from uuid import uuid4

    from app.models import User

    client, db_session, _, user = auth_client
    other = User(id=uuid4(), google_id="download-other", email="download@example.com")
    db_session.add(other)
    job = Transcription(
        user_id=other.id,
        original_filename="private.wav",
        original_storage_key="private.audio",
        mime_type="audio/wav",
        file_size_bytes=1,
    )
    db_session.add(job)
    db_session.commit()
    client.cookies.set("access_token", create_access_token(user.id))
    assert (await client.get(f"/audio/{job.id}/download")).status_code == 404
    assert (await client.get(f"/audio/{uuid4()}/download")).status_code == 404
    client.cookies.clear()
    assert (await client.get(f"/audio/{job.id}/download")).status_code == 401


def test_storage_download_cannot_escape_root(tmp_path, monkeypatch):
    """Reject traversal and symlinks that reference files outside audio storage."""
    from app.repositories.storage import StorageRepository

    root = tmp_path / "audio"
    root.mkdir()
    secret = tmp_path / "private.txt"
    secret.write_text("private")
    monkeypatch.setattr(settings, "audio_storage_dir", root)
    assert StorageRepository.get_original_path("../private.txt") is None
    assert StorageRepository.get_original_path(str(secret)) is None
    (root / "link.audio").symlink_to(secret)
    assert StorageRepository.get_original_path("link.audio") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("limit_kind", ["size", "duration"])
async def test_upload_limits_before_processing(auth_client, monkeypatch, limit_kind):
    """Oversized files return 413 without normalization, storage, or provider calls."""
    from unittest.mock import AsyncMock

    client, db_session, _, user = auth_client
    client.cookies.set("access_token", create_access_token(user.id))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 32000)
    monkeypatch.setattr(
        settings, "max_audio_size_mb", 0.01 if limit_kind == "size" else 25
    )
    monkeypatch.setattr(
        settings, "max_audio_duration_seconds", 1 if limit_kind == "duration" else 3600
    )
    normalize = AsyncMock()
    monkeypatch.setattr(
        "app.services.audio.AudioService.get_normalized_metadata", normalize
    )
    response = await client.post(
        "/audio/upload", files={"file": ("test.wav", buffer.getvalue(), "audio/wav")}
    )
    assert response.status_code == 413
    assert "at most" in response.json()["detail"]
    normalize.assert_not_awaited()
    assert db_session.scalar(select(Transcription)) is None
    assert not list(settings.audio_storage_dir.rglob("*.audio"))


@pytest.mark.asyncio
async def test_transcript_exports_and_ownership(auth_client):
    """Export persisted Unicode text/timestamps and deny access to foreign jobs."""
    from uuid import uuid4

    client, db_session, _, user = auth_client
    job = Transcription(
        user_id=user.id,
        original_filename="sample.wav",
        original_storage_key="unused",
        mime_type="audio/wav",
        file_size_bytes=10,
        transcript_text="Hello café.",
        segments=[{"start": 59.9996, "end": 3601.123, "text": "Hello café."}],
    )
    db_session.add(job)
    db_session.commit()
    client.cookies.set("access_token", create_access_token(user.id))
    expected = {
        "txt": "Hello café.",
        "srt": "1\n00:01:00,000 --> 01:00:01,123\nHello café.\n\n",
        "vtt": "WEBVTT\n\n1\n00:01:00.000 --> 01:00:01.123\nHello café.\n\n",
    }
    for format, content in expected.items():
        response = await client.get(f"/audio/{job.id}/export/{format}")
        assert response.status_code == 200
        assert response.text == content
        assert f".{format}" in response.headers["content-disposition"]
        assert (
            await client.get(f"/audio/{uuid4()}/export/{format}")
        ).status_code == 404
    assert (await client.get(f"/audio/{job.id}/export/pdf")).status_code == 422
    from app.models import User

    other = User(id=uuid4(), google_id="export-other", email="export@example.com")
    db_session.add(other)
    db_session.commit()
    client.cookies.set("access_token", create_access_token(other.id))
    assert (await client.get(f"/audio/{job.id}/export/txt")).status_code == 404
    client.cookies.clear()
    assert (await client.get(f"/audio/{job.id}/export/txt")).status_code == 401
