# Clip orchestration: transcribe in order → restore original timestamps → combine text.
from pathlib import Path
from time import perf_counter

from app.providers.groq import GroqProvider, TranscriptionProviderError
from app.schemas.audio import SpeechClip
from app.schemas.transcription import TranscriptionResult, TranscriptSegment


class TranscriptionService:
    """Transcribe temporary speech clips before their directory is deleted."""

    @staticmethod
    async def transcribe_clips(
        folder: str | Path,
        clips: list[SpeechClip],
        language: str | None = None,
    ) -> TranscriptionResult:
        """Return combined text, detected languages, and original-timeline segments.

        Input: an existing clip folder, ordered clip metadata, and optional language.
        Processing: call Groq for each clip and add its original start offset.
        Output: TranscriptionResult; an empty clip list makes no external requests.

        No partial transcript is returned if any clip fails. This step does not
        create database records or preserve files after the upload request ends.
        """
        started = perf_counter()
        texts = []
        languages = []
        segments = []
        for clip in clips:
            result = await GroqProvider.transcribe(
                Path(folder) / clip.filename, language
            )
            texts.append(result.text)
            if result.language and result.language not in languages:
                languages.append(result.language)
            for segment in sorted(result.segments, key=lambda item: item.start):
                # Whisper can report an end slightly beyond the clip; bound it to the file.
                end = min(segment.end, clip.duration)
                if segment.start >= end:
                    raise TranscriptionProviderError(
                        "Transcription timestamps are outside the speech clip"
                    )
                segments.append(
                    TranscriptSegment(
                        start=clip.start + segment.start,
                        end=clip.start + end,
                        text=segment.text,
                    )
                )

        return TranscriptionResult(
            text=" ".join(texts),
            detected_languages=languages,
            segments=segments,
            processing_time_ms=round((perf_counter() - started) * 1000),
        )
