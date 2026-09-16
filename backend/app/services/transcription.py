# Clip orchestration: transcribe in order → restore original timestamps → combine text.
import string
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
        combined_text = ""
        languages = []
        segments = []
        for clip in clips:
            result = await GroqProvider.transcribe(
                Path(folder) / clip.filename, language
            )
            combined_text = _append_without_repeated_words(combined_text, result.text)
            if result.language and result.language not in languages:
                languages.append(result.language)
            for segment in sorted(result.segments, key=lambda item: item.start):
                # Whisper can report an end slightly beyond the clip; bound it to the file.
                end = min(segment.end, clip.duration)
                if segment.start >= end:
                    raise TranscriptionProviderError(
                        "Transcription timestamps are outside the speech clip"
                    )
                absolute_start = clip.start + segment.start
                absolute_end = clip.start + end
                # A hard-split overlap can yield segments wholly covered by the
                # previous clip. Keep only new timeline information.
                if segments and absolute_end <= segments[-1].end:
                    continue
                if segments:
                    absolute_start = max(absolute_start, segments[-1].end)
                    if absolute_start >= absolute_end:
                        continue
                segments.append(
                    TranscriptSegment(
                        start=absolute_start,
                        end=absolute_end,
                        text=segment.text,
                    )
                )

        return TranscriptionResult(
            text=combined_text,
            detected_languages=languages,
            segments=segments,
            processing_time_ms=round((perf_counter() - started) * 1000),
        )

def _append_without_repeated_words(existing: str, incoming: str) -> str:
    """Remove an exact word suffix/prefix repeated by overlapping audio clips."""
    left = existing.split()
    right = incoming.split()
    overlap = 0
    for size in range(min(len(left), len(right), 50), 0, -1):
        if [_comparison_word(word) for word in left[-size:]] == [
            _comparison_word(word) for word in right[:size]
        ]:
            overlap = size
            break
    return " ".join(left + right[overlap:])


def _comparison_word(word: str) -> str:
    return word.casefold().strip(string.punctuation)
