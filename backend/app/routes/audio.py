# HTTP flow: authenticated multipart request → AudioService → JSON file information.
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.providers.groq import TranscriptionProviderError, TranscriptionUnavailableError
from app.schemas.audio import SavedAudio
from app.schemas.transcription import SavedTranscription
from app.services.audio import AudioLimitError, AudioService
from app.services.exports import render_transcript
from app.services.storage import AudioStorageError, AudioStorageService

router = APIRouter(prefix="/audio", tags=["Audio"])


@router.get("/limits")
async def get_audio_limits() -> dict[str, int]:
    """Return configured upload limits so the browser can show the same rules."""
    return {
        "max_size_bytes": settings.max_audio_size_mb * 1_000_000,
        "max_duration_seconds": settings.max_audio_duration_seconds,
    }


@router.post("/upload", response_model=SavedAudio)
async def receive_audio(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    language: Annotated[str | None, Form(pattern=r"^[a-z]{2}$")] = None,
) -> SavedAudio:
    """Receive the multipart field named file and return its metadata with HTTP 200.

    Input: a multipart file, authentication cookie, and optional language code.
    Processing: authenticate, normalize, detect speech, and transcribe extracted clips.
    Output: saved job ID/status plus audio metadata, transcript text, and timestamps.

    FastAPI may temporarily spool the upload to disk while parsing the request.
    Closing UploadFile releases that temporary resource. The service separately
    preserves the original file and successful transcription in permanent storage.
    """
    try:
        return await AudioService.receive_upload(
            file, language, db=db, user_id=current_user.id
        )
    except AudioLimitError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except AudioStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except TranscriptionUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TranscriptionProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Unable to inspect or normalize this audio"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503, detail="Audio processing tools are unavailable"
        ) from exc
    finally:
        await file.close()


@router.get("/{job_id}", response_model=SavedTranscription)
async def get_saved_audio(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SavedTranscription:
    """Retrieve a completed job by ID, restricted to the authenticated owner."""
    job = await AudioStorageService.get_saved(db, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return job


@router.get("/{job_id}/download", response_class=FileResponse)
async def download_audio(
    job_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """Download an owned original recording as an attachment.

    Input: saved job ID and authentication cookie.
    Output: original audio bytes with the original filename, or HTTP 404.
    FileResponse streams the file and supports byte-range requests.
    """
    download = await AudioStorageService.get_download(db, job_id, current_user.id)
    if download is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    path, filename = download
    return FileResponse(
        path,
        filename=filename,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{job_id}/export/{format}")
async def export_transcript(
    job_id: UUID,
    format: Literal["txt", "srt", "vtt"],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Input owned job ID and format → format saved text → download UTF-8 text."""
    job = await AudioStorageService.get_saved(db, job_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return Response(
        content=render_transcript(job, format),
        media_type="text/vtt" if format == "vtt" else "text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="transcript-{job_id}.{format}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
