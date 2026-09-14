# Provider boundary: temporary speech WAV → Groq Whisper → validated text and clip-relative timestamps.
from pathlib import Path

from groq import APIError
from pydantic import ValidationError

from app.core.config import settings
from app.core.utils.models import create_groq_client
from app.schemas.transcription import ClipTranscription


class TranscriptionUnavailableError(Exception):
    """Transcription cannot start because provider configuration is missing."""


class TranscriptionProviderError(Exception):
    """The provider failed or returned an unusable transcription."""


class GroqProvider:
    """Keep Groq-specific request options and response parsing out of services."""

    @staticmethod
    async def transcribe(
        file_path: Path, language: str | None = None
    ) -> ClipTranscription:
        """Send one WAV clip and return its words, language, and segment timestamps.

        Input: a temporary clip path and optional language code, such as en.
        Processing: request verbose JSON from Groq and validate its fields.
        Output: ClipTranscription; timestamps start at zero for this clip.

        Omit language for automatic detection. API errors are replaced with safe
        messages. The client and file handle are closed even if the request fails.
        """
        if not settings.groq_api_key:
            raise TranscriptionUnavailableError(
                "Set GROQ_API_KEY to enable transcription"
            )
        options = {"language": language} if language else {}
        try:
            async with create_groq_client(
                settings.groq_api_key.get_secret_value()
            ) as client:
                with file_path.open("rb") as audio:
                    response = await client.audio.transcriptions.create(
                        file=(file_path.name, audio, "audio/wav"),
                        model=settings.groq_transcription_model,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                        **options,
                    )
            return ClipTranscription.model_validate(response.model_dump())
        except APIError as exc:
            raise TranscriptionProviderError(
                "Transcription provider request failed; please retry"
            ) from exc
        except (ValidationError, AttributeError, TypeError) as exc:
            raise TranscriptionProviderError(
                "Transcription provider returned an empty or invalid result"
            ) from exc
