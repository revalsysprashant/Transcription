# Export flow: saved transcript and timestamps → UTF-8 TXT, SRT, or WebVTT text.
from html import escape
from typing import Literal

from app.schemas.transcription import SavedTranscription


def subtitle_timestamp(seconds: float, separator: str) -> str:
    """Convert seconds to hours:minutes:seconds plus three millisecond digits."""
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds_part, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds_part:02}{separator}{milliseconds:03}"


def render_transcript(
    job: SavedTranscription, format: Literal["txt", "srt", "vtt"]
) -> str:
    """Input saved text/segments → format cues on original timeline → downloadable text.

    TXT uses the full transcript. Subtitle formats use each segment's timestamps.
    An empty transcript produces empty TXT/SRT or a WebVTT header with no cues.
    """
    if format == "txt":
        return job.transcript_text or ""
    separator = "," if format == "srt" else "."
    cues = []
    for segment in job.segments or []:
        start = subtitle_timestamp(segment.start, separator)
        end = subtitle_timestamp(segment.end, separator)
        # Do not emit zero-length cues after rounding to subtitle milliseconds.
        if start == end:
            continue
        text = escape(" ".join(segment.text.split()), quote=False)
        cues.append(f"{len(cues) + 1}\n{start} --> {end}\n{text}\n\n")
    return ("WEBVTT\n\n" if format == "vtt" else "") + "".join(cues)
