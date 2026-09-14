# Transcription checks: mock the provider network while exercising SDK payloads and timestamp assembly.
from unittest.mock import AsyncMock

import httpx
import pytest
from groq import AsyncGroq
from pydantic import SecretStr

from app.core.config import settings
from app.providers.groq import (
    GroqProvider,
    TranscriptionProviderError,
    TranscriptionUnavailableError,
)
from app.schemas.audio import SpeechClip
from app.schemas.transcription import ClipTranscription
from app.services.transcription import TranscriptionService


@pytest.mark.asyncio
async def test_provider_request_and_response(tmp_path, monkeypatch):
    """Send a multipart WAV, selected language, and verbose timestamp options through the SDK."""
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("test-key"))
    path = tmp_path / "speech.wav"
    path.write_bytes(b"fake audio for transport test")

    def respond(request):
        """Inspect the encoded request and return a realistic verbose JSON response."""
        body = request.read()
        assert b"speech.wav" in body
        assert b"verbose_json" in body
        assert b"language" in body and b"en" in body
        return httpx.Response(
            200,
            json={
                "text": "Hello.",
                "language": "english",
                "segments": [{"start": 0, "end": 0.5, "text": "Hello."}],
            },
        )

    client = AsyncGroq(
        api_key="test-key",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    monkeypatch.setattr("app.core.utils.models.AsyncGroq", lambda **kwargs: client)
    result = await GroqProvider.transcribe(path, "en")
    assert result.text == "Hello."
    assert result.segments[0].end == 0.5
    assert client.is_closed()


@pytest.mark.parametrize(
    "status,payload",
    [(429, {"error": {"message": "private"}}), (200, {"text": "", "segments": []})],
)
@pytest.mark.asyncio
async def test_provider_failure_is_sanitized(tmp_path, monkeypatch, status, payload):
    """Convert rate limits and malformed/empty responses into safe errors."""
    monkeypatch.setattr(settings, "groq_api_key", SecretStr("test-key"))
    path = tmp_path / "clip.wav"
    path.write_bytes(b"audio")
    client = AsyncGroq(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json=payload)
            )
        ),
    )
    monkeypatch.setattr("app.core.utils.models.AsyncGroq", lambda **kwargs: client)
    with pytest.raises(TranscriptionProviderError) as error:
        await GroqProvider.transcribe(path)
    assert "private" not in str(error.value)


@pytest.mark.asyncio
async def test_missing_key_is_clear(tmp_path, monkeypatch):
    """Fail before attempting any network request when credentials are absent."""
    monkeypatch.setattr(settings, "groq_api_key", None)
    with pytest.raises(TranscriptionUnavailableError, match="GROQ_API_KEY"):
        await GroqProvider.transcribe(tmp_path / "clip.wav")


@pytest.mark.asyncio
async def test_clips_combine_with_original_offsets(tmp_path, monkeypatch):
    """Restore original timing and combine text in clip order without including silence."""
    clips = [
        SpeechClip(
            filename=f"{start}.wav", start=start, end=start + 2, duration=2, size_mb=0.1
        )
        for start in [3, 10]
    ]
    responses = [
        ClipTranscription(
            text=text,
            language="english",
            segments=[{"start": 0.2, "end": 2.1, "text": text}],
        )
        for text in ["Hello.", "Goodbye."]
    ]
    provider = AsyncMock(side_effect=responses)
    monkeypatch.setattr(GroqProvider, "transcribe", provider)
    result = await TranscriptionService.transcribe_clips(tmp_path, clips, "en")
    assert result.text == "Hello. Goodbye."
    assert result.detected_languages == ["english"]
    assert [(s.start, s.end) for s in result.segments] == [(3.2, 5), (10.2, 12)]
    assert result.processing_time_ms >= 0
    assert provider.await_count == 2


@pytest.mark.asyncio
async def test_no_speech_skips_provider(tmp_path, monkeypatch):
    """Silence succeeds with an empty transcript and no external calls."""
    provider = AsyncMock()
    monkeypatch.setattr(GroqProvider, "transcribe", provider)
    result = await TranscriptionService.transcribe_clips(tmp_path, [])
    assert result.text == "" and result.segments == []
    provider.assert_not_awaited()
