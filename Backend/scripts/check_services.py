"""Check production keys before deploying: connects to every external service and reports
OK / FAIL per service. Prints no secrets.

    uv run python scripts/check_services.py path/to/prod-values.env

The file uses .env syntax (NAME=value). Needed: DATABASE_URL, REDIS_URL, QDRANT_URL,
QDRANT_API_KEY, MISTRAL_API_KEY, JWT_SECRET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and
optionally S3_ENDPOINT_URL / S3_REGION / S3_BUCKET (derived for Supabase when missing; bucket
defaults to "uploads"). When a name appears twice, the FIRST value is used.
"""

import asyncio
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import asyncpg_url  # noqa: E402


def read_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"([A-Z_][A-Z0-9_]*)=(.*)", line.strip())
        if m and m.group(1) not in values:
            values[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return values


def report(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'OK  ' if ok else 'FAIL'} {name:<9} {detail}")
    return ok


def short(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e)[:150]}"


async def check_postgres(env: dict[str, str]) -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(asyncpg_url(env["DATABASE_URL"]))
    try:
        start = time.perf_counter()
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        took = time.perf_counter() - start
        return report("Postgres", True, f"connected in {took:.1f}s (from this computer)")
    except Exception as e:
        return report("Postgres", False, short(e))
    finally:
        await engine.dispose()


def check_redis(env: dict[str, str]) -> bool:
    import redis

    try:
        r = redis.Redis.from_url(env["REDIS_URL"], socket_timeout=10, socket_connect_timeout=10)
        tls = env["REDIS_URL"].startswith("rediss://")
        return report(
            "Redis", bool(r.ping()), "PING ok" + ("" if tls else " (not encrypted: use rediss://)")
        )
    except Exception as e:
        return report("Redis", False, short(e))


def check_qdrant(env: dict[str, str]) -> bool:
    import httpx

    try:
        r = httpx.get(
            env["QDRANT_URL"].rstrip("/") + "/collections",
            headers={"api-key": env.get("QDRANT_API_KEY", "")},
            timeout=15,
        )
        return report("Qdrant", r.status_code == 200, f"HTTP {r.status_code}")
    except Exception as e:
        return report("Qdrant", False, short(e))


def check_mistral(env: dict[str, str]) -> bool:
    import httpx

    try:
        r = httpx.post(
            "https://api.mistral.ai/v1/embeddings",
            headers={"Authorization": f"Bearer {env['MISTRAL_API_KEY']}"},
            json={"model": "mistral-embed", "input": ["check"]},
            timeout=30,
        )
        busy = " (Mistral busy right now, the key itself is fine)" if r.status_code == 429 else ""
        return report("Mistral", r.status_code in (200, 429), f"HTTP {r.status_code}{busy}")
    except Exception as e:
        return report("Mistral", False, short(e))


def supabase_storage_defaults(env: dict[str, str]) -> tuple[str | None, str | None]:
    """Supabase project ref and region from its pooler DATABASE_URL."""
    authority = env.get("DATABASE_URL", "").split("://", 1)[-1].split("/", 1)[0]
    userinfo, _, host = authority.rpartition("@")
    ref = userinfo.split(":", 1)[0].partition(".")[2]
    region = re.search(r"aws-\d+-([a-z0-9-]+)\.pooler\.supabase\.com", host)
    if not ref or not region:
        return None, None
    return f"https://{ref}.supabase.co/storage/v1/s3", region.group(1)


def check_storage(env: dict[str, str]) -> bool:
    import boto3
    from botocore.config import Config

    endpoint, region = env.get("S3_ENDPOINT_URL"), env.get("S3_REGION")
    if not endpoint or not region:
        derived = supabase_storage_defaults(env)
        endpoint, region = endpoint or derived[0], region or derived[1]
        print(f"     use on Render: S3_ENDPOINT_URL={endpoint}  S3_REGION={region}")
    bucket = env.get("S3_BUCKET", "uploads")
    try:
        s3 = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint,
            aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
            config=Config(s3={"addressing_style": "path"}) if endpoint else None,
        )
        key = "_check_services.txt"
        s3.put_object(Bucket=bucket, Key=key, Body=b"ok")
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        s3.delete_object(Bucket=bucket, Key=key)
        return report("Storage", body == b"ok", f"bucket '{bucket}': write / read / delete ok")
    except Exception as e:
        return report("Storage", False, f"bucket '{bucket}': {short(e)}")


def check_jwt(env: dict[str, str]) -> bool:
    n = len(env.get("JWT_SECRET", ""))
    return report("JWT", n >= 32, f"length {n} (needs 32 or more)")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    env = read_env(sys.argv[1])
    missing = [
        k
        for k in (
            "DATABASE_URL",
            "REDIS_URL",
            "QDRANT_URL",
            "MISTRAL_API_KEY",
            "JWT_SECRET",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        )
        if not env.get(k)
    ]
    if missing:
        sys.exit(f"Missing in {sys.argv[1]}: {', '.join(missing)}")
    results = [
        asyncio.run(check_postgres(env)),
        check_redis(env),
        check_qdrant(env),
        check_mistral(env),
        check_storage(env),
        check_jwt(env),
    ]
    print("\nAll services reachable." if all(results) else "\nFix the FAIL lines before deploying.")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
