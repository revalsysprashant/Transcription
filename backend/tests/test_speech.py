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
    assert detector.call_args.kwargs["min_speech_duration_ms"] == 250
    assert detector.call_args.kwargs["min_silence_duration_ms"] == 700
    assert detector.call_args.kwargs["speech_pad_ms"] == 300


def test_prepare_ranges_merges_sentence_pauses_and_expands_short_audio():
    """Join nearby words and retain surrounding source context for short speech."""
    from app.repositories.speech import prepare_speech_ranges
    from app.schemas.audio import SpeechRange

    result = prepare_speech_ranges(
        [SpeechRange(start=4, end=4.5), SpeechRange(start=5.2, end=6)],
        10,
        merge_gap=1,
        minimum_duration=3,
        maximum_duration=30,
        hard_split_overlap=0.5,
    )
    assert result == [SpeechRange(start=3.5, end=6.5)]


def test_prepare_ranges_prefers_silence_boundary_before_maximum():
    """Do not merge across a real pause when the result would exceed clip size."""
    from app.repositories.speech import prepare_speech_ranges
    from app.schemas.audio import SpeechRange

    result = prepare_speech_ranges(
        [SpeechRange(start=0, end=18), SpeechRange(start=18.5, end=32)],
        40,
        merge_gap=1,
        minimum_duration=3,
        maximum_duration=30,
        hard_split_overlap=0.5,
    )
    assert result == [SpeechRange(start=0, end=18), SpeechRange(start=18.5, end=32)]


def test_prepare_ranges_overlaps_only_hard_splits():
    """Long uninterrupted speech gets bounded chunks with explicit context overlap."""
    from app.repositories.speech import prepare_speech_ranges
    from app.schemas.audio import SpeechRange

    result = prepare_speech_ranges(
        [SpeechRange(start=2, end=67)],
        70,
        merge_gap=1,
        minimum_duration=3,
        maximum_duration=30,
        hard_split_overlap=0.5,
    )
    assert result == [
        SpeechRange(start=2, end=32),
        SpeechRange(start=31.5, end=61.5),
        SpeechRange(start=61, end=67),
    ]


def test_prepare_ranges_clamps_context_to_recording():
    from app.repositories.speech import prepare_speech_ranges
    from app.schemas.audio import SpeechRange

    assert prepare_speech_ranges(
        [SpeechRange(start=0.1, end=0.4)],
        2,
        minimum_duration=3,
        maximum_duration=30,
    ) == [SpeechRange(start=0, end=2)]


def test_low_vad_coverage_uses_full_audio_when_file_is_safe():
    from app.repositories.speech import should_use_full_audio
    from app.schemas.audio import SpeechRange

    assert should_use_full_audio(
        [SpeechRange(start=10, end=40)],
        audio_duration=100,
        normalized_size_bytes=10_000_000,
        minimum_coverage_ratio=0.6,
        maximum_size_mb=20,
    )


def test_low_vad_coverage_keeps_clips_when_full_file_is_too_large():
    from app.repositories.speech import should_use_full_audio
    from app.schemas.audio import SpeechRange

    assert not should_use_full_audio(
        [SpeechRange(start=10, end=40)],
        audio_duration=100,
        normalized_size_bytes=20_000_001,
        minimum_coverage_ratio=0.6,
        maximum_size_mb=20,
    )


def test_silence_does_not_trigger_full_audio_fallback():
    from app.repositories.speech import should_use_full_audio

    assert not should_use_full_audio(
        [],
        audio_duration=100,
        normalized_size_bytes=1_000_000,
        minimum_coverage_ratio=0.6,
        maximum_size_mb=20,
    )


def test_coverage_counts_overlaps_once():
    from app.repositories.speech import speech_coverage_seconds
    from app.schemas.audio import SpeechRange

    assert speech_coverage_seconds(
        [SpeechRange(start=0, end=30), SpeechRange(start=29.5, end=40)]
    ) == 40


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


def test_extract_clips_allows_intentional_hard_split_overlap(tmp_path):
    """Copy overlapping source ranges used to preserve hard-split context."""
    from app.repositories.speech import extract_speech_clips
    from app.schemas.audio import SpeechRange

    source = tmp_path / "source.wav"
    write_wav(source)
    clips = extract_speech_clips(
        source,
        [SpeechRange(start=0, end=0.6), SpeechRange(start=0.5, end=1)],
        tmp_path,
    )
    assert [(clip.start, clip.end) for clip in clips] == [(0, 0.6), (0.5, 1)]


def test_extract_clips_rejects_out_of_order_overlap(tmp_path):
    from app.repositories.speech import extract_speech_clips
    from app.schemas.audio import SpeechRange

    source = tmp_path / "source.wav"
    write_wav(source)
    with pytest.raises(ValueError, match="ordered"):
        extract_speech_clips(
            source,
            [SpeechRange(start=0.5, end=1), SpeechRange(start=0.1, end=0.6)],
            tmp_path,
        )


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
    assert result.speech_clips[0].duration == 1.0
    assert all(not path.exists() for path in created_paths)


@pytest.mark.asyncio
async def test_service_replaces_sparse_vad_ranges_with_full_audio(tmp_path, monkeypatch):
    """Use one complete source range when the low-coverage fallback is selected."""
    from unittest.mock import AsyncMock

    from app.schemas.audio import SpeechRange
    from app.schemas.transcription import TranscriptionResult
    from app.services.audio import AudioService

    source = tmp_path / "source.wav"
    write_wav(source)
    extracted_ranges = []

    def capture_extraction(_path, ranges, _folder):
        extracted_ranges.extend(ranges)
        return []

    monkeypatch.setattr(
        "app.services.audio.detect_speech",
        lambda _path: [SpeechRange(start=0.2, end=0.4)],
    )
    monkeypatch.setattr("app.services.audio.should_use_full_audio", lambda *_args: True)
    monkeypatch.setattr("app.services.audio.extract_speech_clips", capture_extraction)
    monkeypatch.setattr(
        "app.services.audio.TranscriptionService.transcribe_clips",
        AsyncMock(
            return_value=TranscriptionResult(
                text="", detected_languages=[], segments=[], processing_time_ms=0
            )
        ),
    )

    result = await AudioService.get_normalized_metadata(source)

    assert extracted_ranges == [SpeechRange(start=0, end=1)]
    assert result.speech_ranges == [SpeechRange(start=0, end=1)]
