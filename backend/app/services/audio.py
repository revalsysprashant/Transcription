# Upload flow: process temporary audio → save original and transcript → return job ID.
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.repositories.audio import normalize_audio, probe_audio
from app.repositories.speech import (
    detect_speech,
    extract_speech_clips,
    prepare_speech_ranges,
    should_use_full_audio,
)
from app.schemas.audio import NormalizedAudio, ReceivedAudio, SavedAudio, SpeechRange
from app.services.storage import AudioStorageService
from app.services.transcription import TranscriptionService


class AudioLimitError(ValueError):
    """An upload exceeds the configured byte or duration limit."""


class AudioService:
    """Process uploads in temporary storage, then persist successful results."""

    @staticmethod
    # file from the client side.
    async def receive_upload(
        file: UploadFile,
        language: str | None = None,
        *,
        db: AsyncSession,
        user_id: UUID,
    ) -> SavedAudio:
        """Copy an upload into a temporary file with a usable filesystem path.

        Input: uploaded bytes, authenticated user ID, database session, and language.
        Processing: copy and count bytes, inspect the original, then normalize to
        mono 16 kHz PCM WAV, detect speech, extract clips, and transcribe them.
        Output: file information plus duration, bitrate, sample rate, channels,
        codec, container format, speech ranges, and transcription on the original timeline.

        The temporary copy exists only inside the with block. It is automatically
        closed and deleted afterward, including when an exception occurs.
        The original and normalized metadata are returned for comparison.
        After processing succeeds, the original is copied to permanent storage
        and the completed transcription is committed. Temporary copies are deleted.
        """
        await file.seek(0)
        size = 0

        # save into a temporary file
        with tempfile.NamedTemporaryFile(mode="w+b", suffix=".audio") as temp_file:
            while True:
                chunk = await file.read(64 * 1024)
                if not chunk:
                    break

                # Write the original bytes to the temporary file on disk.
                size += len(chunk)
                if size > settings.max_audio_size_mb * 1_000_000:
                    raise AudioLimitError(
                        f"Audio must be at most {settings.max_audio_size_mb} MB"
                    )
                temp_file.write(chunk)

            # Flush buffered writes so other programs can read the complete file.
            temp_file.flush()

            # Input: the path of the temporary file, while it still exists.
            # Run FFprobe in a worker thread so other requests can keep running.
            # Output: a metadata object whose attributes populate the API response.
            audio_metadata = await run_in_threadpool(probe_audio, temp_file.name)

            AudioService.validate_duration(audio_metadata.duration)

            # Normalize and inspect a temporary copy in a separate method.
            normalized_metadata = await AudioService.get_normalized_metadata(
                temp_file.name, language
            )

            result = ReceivedAudio(
                filename=file.filename,
                content_type=file.content_type,
                # Decimal megabytes: 1 MB = 1,000,000 bytes.
                size_mb=round(size / 1_000_000, 2),
                duration=audio_metadata.duration,
                bitrate=audio_metadata.bitrate,
                sample_rate=audio_metadata.sample_rate,
                channels=audio_metadata.channels,
                codec=audio_metadata.codec,
                format=audio_metadata.format,
                normalized=normalized_metadata,
            )

            # Save the original before its temporary file is closed and deleted.
            return await AudioStorageService.save(
                db,
                source=temp_file.name,
                user_id=user_id,
                result=result,
                size_bytes=size,
                language=language,
            )

    @staticmethod
    def validate_duration(duration: float) -> None:
        """Input seconds → compare with the limit → reject audio that is too long."""
        if duration > settings.max_audio_duration_seconds:
            raise AudioLimitError(
                f"Audio must be at most {settings.max_audio_duration_seconds} seconds"
            )

    @staticmethod
    async def get_normalized_metadata(
        input_path: str | Path, language: str | None = None
    ) -> NormalizedAudio:
        """Normalize a temporary copy and return its inspected audio properties.

        Input: the path of the original audio file, which must still exist.
        Processing: normalize, inspect, run VAD, extract clips, and call Groq.
        Output: normalized metadata, clip metadata, combined text, and timestamps.

        The temporary folder and WAV are deleted when this method exits,
        including on failure. The original file is not modified.
        """
        # create a temporary folder for the normalized WAV and its metadata
        with tempfile.TemporaryDirectory(prefix="normalized-audio-") as folder:
            normalized_path = Path(folder) / "normalized.wav"
            await run_in_threadpool(normalize_audio, input_path, normalized_path)
            metadata = await run_in_threadpool(probe_audio, normalized_path)
            # Recheck decoded duration before loading samples into the speech model.
            AudioService.validate_duration(metadata.duration)
            # Detect speech before the temporary WAV is deleted by the with block.
            detected_ranges = await run_in_threadpool(detect_speech, normalized_path)
            speech_ranges = await run_in_threadpool(
                prepare_speech_ranges, detected_ranges, metadata.duration
            )
            if should_use_full_audio(
                speech_ranges, metadata.duration, normalized_path.stat().st_size
            ):
                speech_ranges = [SpeechRange(start=0, end=metadata.duration)]
            # Clips must be used here, before this temporary folder is deleted.
            speech_clips = await run_in_threadpool(
                extract_speech_clips, normalized_path, speech_ranges, folder
            )
            # Send the extracted files while they still exist in this folder.
            transcription = await TranscriptionService.transcribe_clips(
                folder, speech_clips, language
            )
            return NormalizedAudio(
                **metadata.model_dump(),
                speech_ranges=speech_ranges,
                speech_clips=speech_clips,
                transcription=transcription,
            )
