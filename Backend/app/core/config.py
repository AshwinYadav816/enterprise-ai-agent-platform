"""Backend settings from environment / .env. All URLs, limits and secrets live here."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, quote, unquote, urlencode

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # The same .env also carries the AI module's variables (MISTRAL_API_KEY, QDRANT_URL, ...);
    # extra="ignore" lets both settings classes read one file.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    # Datastores. Hosted Postgres URLs (postgres://…?sslmode=require) are converted for asyncpg.
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
    s3_endpoint_url: str | None = None  # S3-compatible service (Supabase Storage, R2, B2…)
    max_upload_mb: int = 25
    max_json_body_kb: int = 1024  # all non-upload request bodies
    allowed_extensions: list[str] = ["pdf", "docx", "pptx", "xlsx"]

    # AI module: "fake" needs no Mistral key (local UI work, tests); "real" calls eap_ai
    ai_mode: Literal["fake", "real"] = "fake"
    fake_ai_delay_ms: int = 0  # fake mode only: ms between events, so the UI visibly streams

    # Rate limits (requests per minute)
    login_per_min: int = 5  # per IP + email
    ai_per_min: int = 30  # per user
    ai_org_per_min: int = 60  # per organization (Mistral limits are account-wide)

    # Chat streaming
    sse_heartbeat_seconds: float = 15  # ": ping" comment while waiting, keeps proxies from closing

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _asyncpg_url(cls, url: str) -> str:
        return asyncpg_url(url)


def asyncpg_url(url: str) -> str:
    """Accept the URL a hosted Postgres shows (Neon, Supabase, Render, Railway):
    - postgres(ql)://… → postgresql+asyncpg://…
    - a password with special characters (Supabase often has @ : / #) is percent-encoded, so the
      URL is read correctly whether or not the user encoded it
    - libpq-only query options → asyncpg's: sslmode=require/verify-* becomes ssl=require,
      channel_binding etc. are dropped; Supabase / Neon hosts get ssl=require by default."""
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    authority, slash, path = rest.partition("/")
    userinfo, at, hostport = authority.rpartition("@")  # the LAST @ ends the password
    if at:
        user, colon, password = userinfo.partition(":")
        userinfo = f"{user}{colon}{quote(unquote(password), safe='')}" if colon else user
        authority = f"{userinfo}@{hostport}"
    path, qmark, raw_query = path.partition("?")

    query = []
    for key, value in parse_qsl(raw_query, keep_blank_values=True):
        if key == "sslmode":
            if value not in ("disable", "allow"):
                query.append(("ssl", "require"))
        elif key not in _LIBPQ_ONLY:
            query.append((key, value))
    host = hostport.rsplit(":", 1)[0].lower()
    if host.endswith(_ALWAYS_TLS_HOSTS) and not any(k == "ssl" for k, _ in query):
        if "sslmode=disable" not in raw_query:
            query.append(("ssl", "require"))
    encoded = urlencode(query)
    return f"{scheme}://{authority}{slash}{path}" + (f"?{encoded}" if encoded else "")


# Managed Postgres that always offers TLS: encrypt even if the URL didn't ask for it.
_ALWAYS_TLS_HOSTS = (".supabase.com", ".supabase.co", ".neon.tech")

# libpq connection options asyncpg rejects as unknown keyword arguments
_LIBPQ_ONLY = {
    "channel_binding",
    "sslrootcert",
    "sslcert",
    "sslkey",
    "gssencmode",
    "target_session_attrs",
}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # jwt_secret comes from the environment
