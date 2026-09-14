# Output shapes: FFprobe metadata shared by the helper and upload response.
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.transcription import TranscriptionStatus
from app.schemas.transcription import TranscriptionResult


class AudioMetadata(BaseModel):
    """Audio properties: duration in seconds and bitrate in bits per second."""

    duration: float = Field(gt=0, allow_inf_nan=False)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    # Some audio formats do not report a stream bitrate.
    bitrate: int | None = Field(default=None, gt=0)
    codec: str = Field(min_length=1)
    format: str = Field(min_length=1)


class SpeechRange(BaseModel):
    """A detected speech interval in seconds relative to the original timeline."""

    start: float = Field(ge=0)
    end: float = Field(gt=0)


class SpeechClip(BaseModel):
    """Metadata for one temporary speech WAV; start/end refer to the original audio."""

    filename: str
    start: float
    end: float
    duration: float
    size_mb: float


class NormalizedAudio(AudioMetadata):
    """Converted audio properties plus detected speech; [] means no speech found."""

    speech_ranges: list[SpeechRange]
    speech_clips: list[SpeechClip]
    transcription: TranscriptionResult


class ReceivedAudio(AudioMetadata):
    """Upload response combining file information with inspected audio properties."""

    filename: str | None
    content_type: str | None
    # File size in decimal megabytes, rounded to two decimal places.
    size_mb: float

    # Original properties remain above; compare them with the converted audio here.
    normalized: NormalizedAudio


class SavedAudio(ReceivedAudio):
    """Upload response identifying the permanently stored completed job."""

    id: UUID
    status: TranscriptionStatus
