# Database storage: stage completed jobs and retrieve only records owned by the authenticated user.
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transcription import Transcription, TranscriptionStatus
from app.schemas.audio import ReceivedAudio


class TranscriptionRepository:
    """Read/write transcription records; services own transaction commits."""

    @staticmethod
    async def create_completed(
        db: AsyncSession,
        *,
        job_id: UUID,
        user_id: UUID,
        storage_key: str,
        result: ReceivedAudio,
        size_bytes: int,
        language: str | None,
    ) -> Transcription:
        """Stage a completed transcription using exact byte counts and JSON segments.

        Input: generated IDs, saved file key, and successful processing results.
        Output: flushed ORM record; the service must commit or roll back.
        The existing single language column uses 'mixed' for multilingual results.
        """
        transcript = result.normalized.transcription
        languages = transcript.detected_languages
        detected_language = (
            languages[0] if len(languages) == 1 else ("mixed" if languages else None)
        )
        job = Transcription(
            id=job_id,
            user_id=user_id,
            original_filename=result.filename or "audio",
            original_storage_key=storage_key,
            mime_type=result.content_type or "application/octet-stream",
            file_size_bytes=size_bytes,
            duration_seconds=result.duration,
            status=TranscriptionStatus.COMPLETED,
            requested_language=language,
            detected_language=detected_language,
            transcript_text=transcript.text,
            segments=[segment.model_dump() for segment in transcript.segments],
            processing_time_ms=transcript.processing_time_ms,
            completed_at=datetime.now(UTC),
        )
        db.add(job)
        await db.flush()
        return job

    @staticmethod
    async def get_owned(
        db: AsyncSession, job_id: UUID, user_id: UUID
    ) -> Transcription | None:
        """Return a saved job only when it belongs to user_id; otherwise return None."""
        result = await db.execute(
            select(Transcription).where(
                Transcription.id == job_id, Transcription.user_id == user_id
            )
        )
        return result.scalar_one_or_none()
