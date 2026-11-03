"""Settings and storage for managed hosting (Neon / Supabase Postgres, S3-compatible storage)."""

import pytest

from app.core.config import asyncpg_url
from app.services.storage import S3Storage


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (  # Neon's connection string
            "postgresql://u:p@ep-x.eu-central-1.aws.neon.tech/db?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p@ep-x.eu-central-1.aws.neon.tech/db?ssl=require",
        ),
        (  # Supabase session pooler / Heroku-style scheme: TLS turned on for supabase.com
            "postgres://postgres.abc:p@aws-0-ap-south-1.pooler.supabase.com:5432/postgres",
            "postgresql+asyncpg://postgres.abc:p@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?ssl=require",
        ),
        (  # a password with @ and : typed as is …
            "postgresql://postgres.abc:Pa@ss:w0rd#1@aws-0-x.pooler.supabase.com:5432/postgres?sslmode=require",
            "postgresql+asyncpg://postgres.abc:Pa%40ss%3Aw0rd%231@aws-0-x.pooler.supabase.com:5432/postgres?ssl=require",
        ),
        (  # … or already encoded: same result, not encoded twice
            "postgresql://postgres.abc:Pa%40ss%3Aw0rd%231@aws-0-x.pooler.supabase.com:5432/postgres?sslmode=require",
            "postgresql+asyncpg://postgres.abc:Pa%40ss%3Aw0rd%231@aws-0-x.pooler.supabase.com:5432/postgres?ssl=require",
        ),
        (  # already right: unchanged
            "postgresql+asyncpg://eap:eap@127.0.0.1:5432/eap",
            "postgresql+asyncpg://eap:eap@127.0.0.1:5432/eap",
        ),
        ("postgresql://u:p@h/db?sslmode=disable", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_hosted_postgres_urls_become_asyncpg_urls(given: str, expected: str) -> None:
    assert asyncpg_url(given) == expected


def test_settings_convert_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db?sslmode=require")
    assert Settings().database_url == "postgresql+asyncpg://u:p@h:5432/db?ssl=require"


async def test_s3_compatible_storage_uses_endpoint_and_serves_files_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    endpoint = "https://abc.supabase.co/storage/v1/s3"
    storage = S3Storage("uploads", "ap-south-1", endpoint)
    assert storage._s3.meta.endpoint_url == endpoint
    assert storage._s3.meta.config.s3["addressing_style"] == "path"
    assert await storage.url_or_none("org/doc.pdf", "doc.pdf") is None  # API streams it

    aws = S3Storage("uploads", "us-east-1")  # plain AWS keeps presigned download links
    assert (await aws.url_or_none("org/doc.pdf", "doc.pdf") or "").startswith("https://")


def test_special_character_password_reaches_the_driver_intact() -> None:
    from sqlalchemy.engine import make_url

    url = make_url(
        asyncpg_url("postgresql://postgres.abc:Pa@ss:w0rd#1@db.x.supabase.co:5432/postgres")
    )
    assert url.password == "Pa@ss:w0rd#1"
    assert url.host == "db.x.supabase.co" and url.username == "postgres.abc"
    assert url.query == {"ssl": "require"}
