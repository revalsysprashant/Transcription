# Transcription table: track job status, audio storage location, and eventual transcript results.
import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# possible states of transcribed file
class TranscriptionStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Transcription(Base):
    __tablename__ = "transcriptions"

    # id of the transcription
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # id of the user who uploaded the file
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # original filename of the uploaded file
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # where the file is stored in the storage
    original_storage_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

   # tells us what kind of file it is .
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # size of the file in bytes
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    # duration of the audio file in seconds
    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # status of the transcription
    status: Mapped[TranscriptionStatus] = mapped_column(
        Enum(
            TranscriptionStatus,
            name="transcription_status",
        ),
        default=TranscriptionStatus.UPLOADED,
        nullable=False,
        index=True,
    )

    # the language that user chose
    requested_language: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    # the language that model detected
    detected_language: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    # combined transcription text
    transcript_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
      # transcription segments in json format
    segments: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    # processing time in milliseconds
    processing_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # error message if transcription failed
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # 1 to N relationship with User . 1 transcription belongs to 1 user
    user: Mapped["User"] = relationship(
        back_populates="transcriptions",
    )
