# Helper tests: inspect a real WAV and verify readable errors for invalid probe results.
import json
import subprocess
import wave
from unittest.mock import patch

import pytest

from app.repositories.audio import probe_audio


def test_probe_real_wav(tmp_path):
    """Read duration, sample rate, and channels from a one-second PCM WAV."""
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)
    assert probe_audio(path).model_dump() == {
        "duration": 1.0,
        "sample_rate": 16000,
        "channels": 1,
        "bitrate": 256000,
        "codec": "pcm_s16le",
        "format": "wav",
    }
    assert path.exists()  # The helper does not delete the caller's temporary file.


def test_probe_invalid_file(tmp_path):
    """Reject text disguised as a WAV file."""
    path = tmp_path / "fake.wav"
    path.write_text("not audio")
    with pytest.raises(ValueError, match="Audio is unreadable"):
        probe_audio(path)


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"streams": []},
        {"streams": [{"sample_rate": "16000", "channels": 1}]},
        {"streams": [{"duration": "nan", "sample_rate": "16000", "channels": 1}]},
        {"streams": [{"duration": "1", "sample_rate": "0", "channels": 1}]},
    ],
)
def test_probe_rejects_incomplete_metadata(metadata):
    """Require an audio stream and usable positive metadata values."""
    with (
        patch(
            "app.repositories.audio.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(metadata)),
        ),
        pytest.raises(ValueError),
    ):
        probe_audio("/tmp/sample.wav")


def test_probe_container_duration_fallback():
    """Use the container duration when the audio stream reports N/A."""
    metadata = {
        "streams": [
            {
                "duration": "N/A",
                "sample_rate": "44100",
                "channels": 2,
                "codec_name": "aac",
            }
        ],
        "format": {"duration": "12.5", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
    }
    with patch(
        "app.repositories.audio.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, json.dumps(metadata)),
    ):
        result = probe_audio("/tmp/sample.m4a")
        assert result.duration == 12.5
        assert result.bitrate is None
        assert result.codec == "aac"
        assert result.channels == 2
        assert result.sample_rate == 44100
        assert result.format == "mov,mp4,m4a,3gp,3g2,mj2"


@pytest.mark.parametrize(
    "failure,expected",
    [
        (FileNotFoundError(), RuntimeError),
        (subprocess.TimeoutExpired("ffprobe", 15), ValueError),
    ],
)
def test_probe_execution_errors(failure, expected):
    """Convert missing FFprobe and timeout failures into clear helper errors."""
    with (
        patch("app.repositories.audio.subprocess.run", side_effect=failure),
        pytest.raises(expected),
    ):
        probe_audio("/tmp/sample.wav")


def test_normalize_stereo_audio(tmp_path):
    """Convert a real stereo 44.1 kHz WAV and preserve its duration and original bytes."""
    from app.repositories.audio import normalize_audio

    source = tmp_path / "stereo.wav"
    output = tmp_path / "normalized.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        audio.writeframes(b"\x00\x00\x00\x00" * 44100)
    original = source.read_bytes()
    assert normalize_audio(source, output) == output
    result = probe_audio(output)
    assert result.sample_rate == 16000
    assert result.channels == 1
    assert result.codec == "pcm_s16le"
    assert result.format == "wav"
    assert result.duration == pytest.approx(1.0)
    assert source.read_bytes() == original
    with pytest.raises(ValueError, match="not overwritten"):
        normalize_audio(source, source)


def test_normalization_rejects_invalid_input(tmp_path):
    """Surface a readable error when FFmpeg cannot decode the input."""
    from app.repositories.audio import normalize_audio

    source = tmp_path / "invalid.audio"
    source.write_text("not audio")
    with pytest.raises(ValueError, match="Unable to normalize"):
        normalize_audio(source, tmp_path / "normalized.wav")


def test_probe_browser_webm_without_duration(tmp_path):
    """A streaming WebM omits duration metadata but still has measurable packets."""
    import subprocess

    path = tmp_path / "browser.webm"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono",
            "-t",
            "2",
            "-c:a",
            "libopus",
            "-live",
            "1",
            str(path),
        ],
        check=True,
        timeout=15,
    )
    metadata = probe_audio(path)
    assert 1.9 < metadata.duration < 2.2
    assert metadata.codec == "opus"
