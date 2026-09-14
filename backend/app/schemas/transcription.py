# Transcription data: provider timestamps are clip-relative; combined timestamps are original-relative.
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.models.transcription import TranscriptionStatus


class TranscriptSegment(BaseModel):
    """One piece of text with start/end times in seconds."""

    model_config = ConfigDict(str_strip_whitespace=True)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_time_order(self):
        """Reject reversed or empty time intervals from the transcription provider."""
        if self.end <= self.start:
            raise ValueError("Segment end must be after its start")
        return self


class ClipTranscription(BaseModel):
    """Validated Groq response for one speech clip."""

    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(min_length=1)
    language: str | None = None
    segments: list[TranscriptSegment] = Field(min_length=1)


class TranscriptionResult(BaseModel):
    """Combined text and segments; empty text/segments mean no speech was detected."""

    text: str
    detected_languages: list[str]
    segments: list[TranscriptSegment]
    processing_time_ms: int


class SavedTranscription(BaseModel):
    """A saved job without its internal storage path or other users' data."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int = Field(exclude=True)
    duration_seconds: float | None
    status: TranscriptionStatus
    requested_language: str | None
    detected_language: str | None
    transcript_text: str | None
    segments: list[TranscriptSegment] | None
    processing_time_ms: int | None
    created_at: datetime
    completed_at: datetime | None

    @computed_field
    @property
    def size_mb(self) -> float:
        """Expose decimal megabytes while the database keeps the exact byte count."""
        return round(self.file_size_bytes / 1_000_000, 2)
