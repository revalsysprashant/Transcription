# Audio inspection: temporary file path → FFprobe JSON → useful audio metadata.
import json
import subprocess
from pathlib import Path

from app.schemas.audio import AudioMetadata


def probe_audio(file_path: str | Path) -> AudioMetadata:
    """Inspect the first audio track without modifying the file.

    Input:
        The path of an existing temporary audio file.
    Processing:
        Run FFprobe, parse its JSON, and check the first audio track's metadata.
    Output:
        An AudioMetadata object with duration, bitrate, sample_rate, channels,
        codec, and format. Bitrate is None when the audio stream omits it.

    Raise ValueError for unreadable audio, missing metadata, or a probe timeout.
    Raise RuntimeError if FFprobe is unavailable. Browser recordings may omit
    duration metadata; measure packet timestamps in that case.

    This is a synchronous helper. An async service should call it through
    run_in_threadpool so waiting for FFprobe does not block other requests.
    """
    # Use separate arguments, not a shell command containing the uploaded filename.
    # a:0 selects the first audio track; video tracks are ignored.
    command = [
        "ffprobe",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=duration,sample_rate,channels,bit_rate,codec_name:format=duration,format_name",
        "-of",
        "json",
        str(Path(file_path).resolve()),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("FFprobe is not installed or is not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Audio inspection timed out") from exc

    if result.returncode != 0:
        raise ValueError("Audio is unreadable or has no audio tracks")

    # Parse FFprobe's JSON. Streams describe audio; format describes its container.
    metadata = json.loads(result.stdout)
    if not isinstance(metadata, dict) or not metadata.get("streams"):
        raise ValueError("Audio has no audio tracks")

    audio = metadata["streams"][0]
    container = metadata.get("format") or {}

    # Prefer audio duration; fall back when only the container reports duration.
    duration = audio.get("duration")
    if duration in (None, "N/A", ""):
        duration = container.get("duration")

    if duration in (None, "N/A", ""):
        duration = measure_packet_duration(file_path)

    # Keep missing bitrate as None, not a made-up zero or whole-container bitrate.
    bitrate = audio.get("bit_rate")
    if bitrate in (None, "N/A", ""):
        bitrate = None

    # Pydantic converts numeric strings and rejects missing/invalid required fields.
    # Returning an object allows the service to use audio_metadata.sample_rate, etc.
    return AudioMetadata(
        duration=duration,
        sample_rate=audio.get("sample_rate"),
        channels=audio.get("channels"),
        bitrate=bitrate,
        codec=audio.get("codec_name"),
        format=container.get("format_name"),
    )


def normalize_audio(input_path: str | Path, output_path: str | Path) -> Path:
    """Convert audio to mono, 16 kHz, signed 16-bit PCM WAV.

    Input: an existing audio file path and a new output path in a temporary folder.
    Processing: FFmpeg decodes the first audio track, mixes to mono, and resamples.
    Output: the path of the normalized WAV; the original file is not modified.

    This does not remove noise, trim silence, or adjust loudness. Run this
    synchronous helper in a worker thread. The caller owns temporary-file cleanup,
    including any partial output when conversion fails.
    """
    source = Path(input_path).resolve()
    destination = Path(output_path).resolve()
    if destination.exists():
        raise ValueError("Choose a new output path; existing files are not overwritten")

    command = [
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",  # Do not wait for keyboard input on the server.
        "-n",  # Never overwrite an existing file.
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(source),  # Input: original audio.
        "-map",
        "0:a:0",  # Select the first audio track.
        "-ac",
        "1",  # One channel: mono.
        "-ar",
        "16000",  # 16,000 samples per second.
        "-c:a",
        "pcm_s16le",  # Signed 16-bit PCM samples.
        "-f",
        "wav",  # Store those samples in a WAV container.
        str(destination),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=60, check=False
        )
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is not installed or is not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Audio normalization timed out") from exc

    if result.returncode != 0:
        raise ValueError("Unable to normalize this audio file")
    return destination


def measure_packet_duration(file_path: str | Path) -> float:
    """Input browser recording → scan audio packet times → duration in seconds.

    MediaRecorder WebM files often omit the container duration. FFprobe can still
    read each packet's timestamp and length without decoding the entire audio.
    """
    command = [
        "ffprobe",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-select_streams",
        "a:0",
        "-show_entries",
        "packet=pts_time,duration_time",
        "-of",
        "csv=p=0",
        str(Path(file_path).resolve()),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=15, check=False
        )
    except FileNotFoundError as exc:
        raise RuntimeError("FFprobe is not installed or is not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Audio inspection timed out") from exc
    if result.returncode:
        raise ValueError("Unable to measure recording duration")
    first = None
    last = 0.0
    for line in result.stdout.splitlines():
        fields = line.split(",")
        if len(fields) < 2 or fields[0] in ("", "N/A"):
            continue
        start = float(fields[0])
        length = 0.0 if fields[1] in ("", "N/A") else float(fields[1])
        first = start if first is None else min(first, start)
        last = max(last, start + length)
    if first is None or last <= first:
        raise ValueError("Recording has no measurable audio duration")
    return last - first
