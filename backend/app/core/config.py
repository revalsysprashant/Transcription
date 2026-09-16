# Configuration: load environment variables and .env values into one cached settings object.
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    audio_storage_dir: Path = Path(__file__).resolve().parents[2] / "storage" / "audio"

    # Decimal MB, matching the size shown in the frontend.
    max_audio_size_mb: int = Field(default=25, gt=0)
    max_audio_duration_seconds: int = Field(default=3600, gt=0)

    app_name: str = "Transcription API"
    app_env: str = "development"
    debug: bool = True

    google_client_id: str

    groq_api_key: SecretStr | None = None
    groq_transcription_model: str = "whisper-large-v3-turbo"

    # Keep sentence-sized speech together before sending audio to Whisper.
    vad_min_speech_duration_ms: int = Field(default=250, ge=0)
    vad_min_silence_duration_ms: int = Field(default=700, ge=0)
    vad_speech_pad_ms: int = Field(default=300, ge=0)
    speech_merge_gap_seconds: float = Field(default=1.0, ge=0)
    speech_clip_min_seconds: float = Field(default=3.0, gt=0)
    speech_clip_max_seconds: float = Field(default=30.0, gt=0)
    speech_clip_overlap_seconds: float = Field(default=0.5, ge=0)
    full_audio_fallback_coverage_ratio: float = Field(default=0.6, ge=0, le=1)
    full_audio_fallback_max_mb: float = Field(default=20.0, gt=0)

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached, validated application settings loaded from the environment.

    Settings also reads .env; missing required values raise validation errors.
    """
    return Settings()


settings = get_settings()
