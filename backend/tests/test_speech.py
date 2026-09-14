# VAD checks: real silence detection, sample-to-second conversion, and input requirements.
import wave
from unittest.mock import patch

import pytest

from app.repositories.speech import detect_speech


def write_wav(path, channels=1, sample_rate=16000):
    """Create one second of silent PCM audio for a deterministic test input."""
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * sample_rate * channels)


def test_silence_has_no_speech(tmp_path):
    """Run the real packaged model; silence must produce no speech intervals."""
    path = tmp_path / "silence.wav"
    write_wav(path)
    assert detect_speech(path) == []
    assert path.exists()


def test_vad_sample_positions_become_seconds(tmp_path):
    """Verify model input scaling and preserve ordered sample boundaries as seconds."""
    path = tmp_path / "audio.wav"
    write_wav(path)
    with patch(
        "app.repositories.speech.get_speech_timestamps",
        return_value=[{"start": 1600, "end": 8000}, {"start": 9600, "end": 16000}],
    ) as detector:
        result = detect_speech(path)
    assert [item.model_dump() for item in result] == [
        {"start": 0.1, "end": 0.5},
        {"start": 0.6, "end": 1.0},
    ]
    samples = detector.call_args.args[0]
    assert tuple(samples.shape) == (16000,)
    assert samples.abs().max().item() == 0
    assert detector.call_args.kwargs["sampling_rate"] == 16000


@pytest.mark.parametrize("channels,sample_rate", [(2, 16000), (1, 44100)])
def test_vad_requires_normalized_audio(tmp_path, channels, sample_rate):
    """Reject input that bypassed the mono 16 kHz normalization step."""
    path = tmp_path / "unnormalized.wav"
    write_wav(path, channels, sample_rate)
    with pytest.raises(ValueError, match="VAD requires"):
        detect_speech(path)


def test_extract_clips_preserves_samples_and_offsets(tmp_path):
    """Copy exact selected samples into ordered WAVs without changing the source."""
    import numpy as np

    from app.repositories.speech import extract_speech_clips
    from app.schemas.audio import SpeechRange

    source = tmp_path / "source.wav"
    samples = np.arange(16000, dtype="<i2").tobytes()
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(samples)
    original = source.read_bytes()
    clips = extract_speech_clips(
        source,
        [SpeechRange(start=0.1, end=0.5), SpeechRange(start=0.6, end=1.0)],
        tmp_path,
    )
    assert [clip.filename for clip in clips] == ["speech_001.wav", "speech_002.wav"]
    for clip, start, end in zip(clips, [1600, 9600], [8000, 16000], strict=True):
        with wave.open(str(tmp_path / clip.filename), "rb") as audio:
            assert audio.getframerate() == 16000
            assert audio.getnchannels() == 1
            assert audio.getsampwidth() == 2
            assert audio.readframes(audio.getnframes()) == samples[start * 2 : end * 2]
        assert clip.duration == 0.4
        assert clip.start == start / 16000
        assert clip.end == end / 16000
    assert source.read_bytes() == original


def test_extract_no_speech_creates_no_clips(tmp_path):
    """An empty VAD result creates no output files."""
    from app.repositories.speech import extract_speech_clips

    source = tmp_path / "source.wav"
    write_wav(source)
    assert extract_speech_clips(source, [], tmp_path) == []
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("start,end", [(0.5, 0.2), (0, 2), (0.1, 0.1)])
def test_extract_rejects_invalid_range(tmp_path, start, end):
    """Reject empty, reversed, or out-of-bounds ranges before writing a clip."""
    from app.repositories.speech import extract_speech_clips
    from app.schemas.audio import SpeechRange

    source = tmp_path / "source.wav"
    write_wav(source)
    with pytest.raises(ValueError, match="Speech ranges"):
        extract_speech_clips(source, [SpeechRange(start=start, end=end)], tmp_path)
    assert not list(tmp_path.glob("speech_*.wav"))


@pytest.mark.asyncio
async def test_service_extracts_then_cleans_clips(tmp_path, monkeypatch):
    """Return clip metadata while removing temporary normalized audio and clips."""
    from pathlib import Path

    from app.repositories.speech import extract_speech_clips
    from app.schemas.audio import SpeechRange
    from app.services.audio import AudioService

    source = tmp_path / "source.wav"
    write_wav(source)
    created_paths = []

    def inspect_extraction(file_path, ranges, folder):
        """Record the actual generated clips while the temporary folder exists."""
        result = extract_speech_clips(file_path, ranges, folder)
        for item in result:
            path = Path(folder) / item.filename
            assert path.exists()
            created_paths.append(path)
        return result

    monkeypatch.setattr(
        "app.services.audio.detect_speech",
        lambda path: [SpeechRange(start=0.1, end=0.5)],
    )
    monkeypatch.setattr("app.services.audio.extract_speech_clips", inspect_extraction)
    from unittest.mock import AsyncMock

    from app.schemas.transcription import TranscriptionResult

    monkeypatch.setattr(
        "app.services.audio.TranscriptionService.transcribe_clips",
        AsyncMock(
            return_value=TranscriptionResult(
                text="", detected_languages=[], segments=[], processing_time_ms=0
            )
        ),
    )
    result = await AudioService.get_normalized_metadata(source)
    assert result.speech_clips[0].duration == 0.4
    assert all(not path.exists() for path in created_paths)
