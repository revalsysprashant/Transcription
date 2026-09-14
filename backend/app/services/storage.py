# Persistence workflow: save original → stage completed job → commit; remove original on DB failure.
import logging
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models.transcription import TranscriptionStatus
from app.repositories.storage import StorageRepository
from app.repositories.transcription import TranscriptionRepository
from app.schemas.audio import ReceivedAudio, SavedAudio
from app.schemas.transcription import SavedTranscription

logger = logging.getLogger(__name__)


class AudioStorageError(Exception):
    """Audio or transcription persistence failed; details stay in server logs."""


class AudioStorageService:
    """Coordinate permanent files and database records after processing succeeds."""

    @staticmethod
    async def save(
        db: AsyncSession,
        *,
        source: str | Path,
        user_id: UUID,
        result: ReceivedAudio,
        size_bytes: int,
        language: str | None,
    ) -> SavedAudio:
        """Return the job ID after original audio and transcript are both saved.

        Input: successful processing results and a temporary original that still exists.
        Processing: copy the file, stage the database row, then commit once.
        Output: the existing upload response plus id and COMPLETED status.

        Roll back and remove the copied file on failure. Filesystem and database
        commits are not atomic across a process crash; this handles normal errors.
        """
        storage_key = None
        try:
            job_id = uuid4()
            response = SavedAudio(
                **result.model_dump(), id=job_id, status=TranscriptionStatus.COMPLETED
            )
            storage_key = await run_in_threadpool(
                StorageRepository.save_original, source, user_id, job_id
            )
            await TranscriptionRepository.create_completed(
                db,
                job_id=job_id,
                user_id=user_id,
                storage_key=storage_key,
                result=result,
                size_bytes=size_bytes,
                language=language,
            )
            await db.commit()
            return response
        except BaseException as exc:
            try:
                await db.rollback()
            finally:
                if storage_key is not None:
                    await run_in_threadpool(
                        StorageRepository.remove_original, storage_key
                    )
            if not isinstance(exc, Exception):
                raise
            logger.exception("Unable to save completed transcription")
            raise AudioStorageError("Unable to save audio and transcription") from exc

    @staticmethod
    async def get_saved(
        db: AsyncSession, job_id: UUID, user_id: UUID
    ) -> SavedTranscription | None:
        """Read one owner's persisted job and return its public representation."""
        job = await TranscriptionRepository.get_owned(db, job_id, user_id)
        return SavedTranscription.model_validate(job) if job is not None else None

    @staticmethod
    async def get_download(
        db: AsyncSession, job_id: UUID, user_id: UUID
    ) -> tuple[Path, str] | None:
        """Return an owned original's disk path and safe download filename.

        Input: job ID and authenticated user ID.
        Processing: check ownership first, then locate the original in storage.
        Output: (path, filename), or None for an inaccessible job or missing file.
        The HTTP route streams the file; this method does not load audio into RAM.
        """
        job = await TranscriptionRepository.get_owned(db, job_id, user_id)
        if job is None:
            return None
        path = await run_in_threadpool(
            StorageRepository.get_original_path, job.original_storage_key
        )
        if path is None:
            return None
        # Keep the original name, but remove client directory components/control characters.
        filename = job.original_filename.replace("\\", "/").rsplit("/", 1)[-1]
        filename = "".join(
            character
            for character in filename
            if ord(character) >= 32 and ord(character) != 127
        )
        if filename in ("", ".", ".."):
            filename = "audio"
        return path, filename
