# Speech detection: normalized WAV → floating-point samples → Silero VAD → ranges in seconds.
import math
import wave
from pathlib import Path
from threading import Lock

import numpy as np
import torch
from silero_vad import get_speech_timestamps

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
        )

    # Silero returns sample positions. Divide by samples/second to obtain seconds.
    # Keep this conversion explicit so timestamps never round past the file's end.
    return [
        SpeechRange(start=item["start"] / 16000, end=item["end"] / 16000)
        for item in ranges
    ]


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

        previous_end = 0
        for index, speech in enumerate(speech_ranges, start=1):
            if not math.isfinite(speech.start) or not math.isfinite(speech.end):
                raise ValueError("Speech times must be finite")
            # At 16 kHz, 1 second corresponds to sample position 16,000.
            start_frame = round(speech.start * sample_rate)
            end_frame = round(speech.end * sample_rate)
            if not (previous_end <= start_frame < end_frame <= source.getnframes()):
                raise ValueError(
                    "Speech ranges must be ordered, non-overlapping, and inside the audio"
                )
            previous_end = end_frame

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
