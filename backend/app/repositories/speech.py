# Speech detection: normalized WAV → floating-point samples → Silero VAD → ranges in seconds.
import math
import wave
from pathlib import Path
from threading import Lock

import numpy as np
import torch
from silero_vad import get_speech_timestamps

from app.core.config import settings
from app.core.utils.models import load_silero_model
from app.schemas.audio import SpeechClip, SpeechRange

# Silero keeps state between audio windows. Only one request may use it at a time.
_model_lock = Lock()


def detect_speech(file_path: str | Path) -> list[SpeechRange]:
    """Find speech in a normalized file without changing or cutting the audio.

    Input: mono, 16 kHz, 16-bit PCM WAV created by our normalization helper.
    Processing: read PCM samples, scale to floats, and run Silero's speech detector.
    Output: ordered start/end ranges in seconds, or [] when no speech is detected.

    Run in a worker thread. The model is bundled with silero-vad; requests do not
    download weights. Speech detection does not transcribe words or remove noise.
    """
    with wave.open(str(file_path), "rb") as audio:
        if (
            audio.getnchannels() != 1
            or audio.getframerate() != 16000
            or audio.getsampwidth() != 2
        ):
            raise ValueError("VAD requires mono, 16 kHz, 16-bit PCM WAV")
        raw_samples = audio.readframes(audio.getnframes())

    if not raw_samples:
        return []

    # WAV stores signed 16-bit integers. Silero expects values between -1 and 1.
    samples = np.frombuffer(raw_samples, dtype="<i2").astype(np.float32) / 32768.0
    waveform = torch.from_numpy(samples)

    with _model_lock:
        ranges = get_speech_timestamps(
            waveform,
            load_silero_model(),
            sampling_rate=16000,
            return_seconds=False,
            min_speech_duration_ms=settings.vad_min_speech_duration_ms,
            min_silence_duration_ms=settings.vad_min_silence_duration_ms,
            speech_pad_ms=settings.vad_speech_pad_ms,
        )

    # Silero returns sample positions. Divide by samples/second to obtain seconds.
    # Keep this conversion explicit so timestamps never round past the file's end.
    return [
        SpeechRange(start=item["start"] / 16000, end=item["end"] / 16000)
        for item in ranges
    ]


def prepare_speech_ranges(
    speech_ranges: list[SpeechRange],
    audio_duration: float,
    *,
    merge_gap: float | None = None,
    minimum_duration: float | None = None,
    maximum_duration: float | None = None,
    hard_split_overlap: float | None = None,
) -> list[SpeechRange]:
    """Merge nearby VAD hits and turn them into provider-sized source ranges.

    VAD padding is already present in the input ranges. Nearby hits are merged so
    a short pause does not erase sentence context. Isolated short hits are expanded
    using source audio, while long uninterrupted speech is split with a small
    overlap. Returned ranges are ordered, but hard-split ranges may overlap.
    """
    if not math.isfinite(audio_duration) or audio_duration <= 0:
        raise ValueError("Audio duration must be positive and finite")
    gap = settings.speech_merge_gap_seconds if merge_gap is None else merge_gap
    minimum = (
        settings.speech_clip_min_seconds
        if minimum_duration is None
        else minimum_duration
    )
    maximum = (
        settings.speech_clip_max_seconds
        if maximum_duration is None
        else maximum_duration
    )
    overlap = (
        settings.speech_clip_overlap_seconds
        if hard_split_overlap is None
        else hard_split_overlap
    )
    if gap < 0 or minimum <= 0 or maximum <= 0 or overlap < 0:
        raise ValueError("Speech range settings must be non-negative")
    if minimum > maximum or overlap >= maximum:
        raise ValueError("Speech range duration settings are inconsistent")

    grouped: list[SpeechRange] = []
    previous_end = 0.0
    for item in speech_ranges:
        if (
            not math.isfinite(item.start)
            or not math.isfinite(item.end)
            or item.start >= item.end
            or item.end > audio_duration
            or item.start < previous_end
        ):
            raise ValueError("Speech ranges must be ordered and inside the audio")
        previous_end = item.end
        # Keep a silence boundary when adding the next hit would exceed the target.
        if (
            grouped
            and item.start - grouped[-1].end <= gap
            and item.end - grouped[-1].start <= maximum
        ):
            grouped[-1] = SpeechRange(start=grouped[-1].start, end=item.end)
        else:
            grouped.append(item.model_copy())

    prepared: list[SpeechRange] = []
    for item in grouped:
        start, end = item.start, item.end
        missing = max(0.0, minimum - (end - start))
        start = max(0.0, start - missing / 2)
        end = min(audio_duration, end + missing / 2)
        # If one edge hit the recording boundary, grow from the other edge.
        if end - start < minimum:
            if start == 0:
                end = min(audio_duration, minimum)
            elif end == audio_duration:
                start = max(0.0, audio_duration - minimum)

        cursor = start
        while end - cursor > maximum:
            split_end = cursor + maximum
            prepared.append(SpeechRange(start=cursor, end=split_end))
            cursor = split_end - overlap
        prepared.append(SpeechRange(start=cursor, end=end))
    return prepared


def speech_coverage_seconds(speech_ranges: list[SpeechRange]) -> float:
    """Return unique covered timeline seconds, accounting for split overlap."""
    if not speech_ranges:
        return 0.0
    covered = 0.0
    current_start = speech_ranges[0].start
    current_end = speech_ranges[0].end
    for item in speech_ranges[1:]:
        if item.start <= current_end:
            current_end = max(current_end, item.end)
        else:
            covered += current_end - current_start
            current_start, current_end = item.start, item.end
    return covered + current_end - current_start


def should_use_full_audio(
    speech_ranges: list[SpeechRange],
    audio_duration: float,
    normalized_size_bytes: int,
    *,
    minimum_coverage_ratio: float | None = None,
    maximum_size_mb: float | None = None,
) -> bool:
    """Choose full audio when VAD discarded too much and upload size is safe."""
    minimum_coverage = (
        settings.full_audio_fallback_coverage_ratio
        if minimum_coverage_ratio is None
        else minimum_coverage_ratio
    )
    maximum_bytes = int(
        1_000_000
        * (
            settings.full_audio_fallback_max_mb
            if maximum_size_mb is None
            else maximum_size_mb
        )
    )
    if audio_duration <= 0 or normalized_size_bytes < 0:
        raise ValueError("Audio duration and size must be valid")
    coverage = speech_coverage_seconds(speech_ranges) / audio_duration
    return (
        bool(speech_ranges)
        and coverage < minimum_coverage
        and normalized_size_bytes <= maximum_bytes
    )


def extract_speech_clips(
    file_path: str | Path,
    speech_ranges: list[SpeechRange],
    output_folder: str | Path,
) -> list[SpeechClip]:
    """Copy detected speech intervals into individual temporary PCM WAV files.

    Input: normalized WAV, ordered VAD ranges in seconds, and a temporary folder.
    Processing: convert times to sample positions and copy only those samples.
    Output: clip filenames, original start/end times, duration, and size in MB.

    No transcription or re-encoding occurs. Run this helper in a worker thread.
    The caller owns the output folder and deletes it after using the clips.
    Filenames are relative to that folder, not downloadable URLs.
    """
    clips = []
    with wave.open(str(file_path), "rb") as source:
        sample_rate = source.getframerate()
        if (
            source.getnchannels() != 1
            or sample_rate != 16000
            or source.getsampwidth() != 2
        ):
            raise ValueError("Speech extraction requires mono, 16 kHz, 16-bit PCM WAV")

        previous_start = -1
        for index, speech in enumerate(speech_ranges, start=1):
            if not math.isfinite(speech.start) or not math.isfinite(speech.end):
                raise ValueError("Speech times must be finite")
            # At 16 kHz, 1 second corresponds to sample position 16,000.
            start_frame = round(speech.start * sample_rate)
            end_frame = round(speech.end * sample_rate)
            if not (
                previous_start <= start_frame < end_frame <= source.getnframes()
            ):
                raise ValueError(
                    "Speech ranges must be ordered, non-empty, and inside the audio"
                )
            previous_start = start_frame

            filename = f"speech_{index:03d}.wav"
            destination = Path(output_folder) / filename
            source.setpos(start_frame)

            # Exclusive creation protects existing files. The service supplies the folder.
            with (
                destination.open("xb") as clip_file,
                wave.open(clip_file, "wb") as output,
            ):
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(sample_rate)
                remaining = end_frame - start_frame
                while remaining:
                    # Copy at most one second at a time, preserving the PCM bytes.
                    chunk = source.readframes(min(remaining, sample_rate))
                    if not chunk:
                        raise ValueError(
                            "Audio ended before the speech range was copied"
                        )
                    output.writeframesraw(chunk)
                    remaining -= len(chunk) // 2

            clips.append(
                SpeechClip(
                    filename=filename,
                    start=start_frame / sample_rate,
                    end=end_frame / sample_rate,
                    duration=(end_frame - start_frame) / sample_rate,
                    size_mb=round(destination.stat().st_size / 1_000_000, 2),
                )
            )
    return clips
