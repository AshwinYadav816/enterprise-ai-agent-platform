"""Backend settings from environment / .env. All URLs, limits and secrets live here."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The same .env also carries the AI module's variables (MISTRAL_API_KEY, QDRANT_URL, ...);
    # extra="ignore" lets both settings classes read one file.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    # Datastores
    database_url: str = "postgresql+asyncpg://eap:eap@127.0.0.1:5432/eap"
    test_database_url: str = "postgresql+asyncpg://eap:eap@127.0.0.1:5432/eap_test"
    redis_url: str = "redis://127.0.0.1:6379/0"

    # Auth
    jwt_secret: SecretStr = Field(min_length=32)  # signs every token: use a long random value
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # HTTP
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # File storage
    storage_backend: Literal["local", "s3"] = "local"
    storage_dir: Path = Path("data/uploads")
    s3_bucket: str | None = None
    s3_region: str | None = None
    max_upload_mb: int = 25
    max_json_body_kb: int = 1024  # all non-upload request bodies
    allowed_extensions: list[str] = ["pdf", "docx", "pptx", "xlsx"]

    # AI module: "fake" needs no Mistral key (local UI work, tests); "real" calls eap_ai
    ai_mode: Literal["fake", "real"] = "fake"

    # Rate limits (requests per minute)
    login_per_min: int = 5  # per IP + email
    ai_per_min: int = 30  # per user
    ai_org_per_min: int = 60  # per organization (Mistral limits are account-wide)

    # Chat streaming
    sse_heartbeat_seconds: float = 15  # ": ping" comment while waiting, keeps proxies from closing


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # jwt_secret comes from the environment
