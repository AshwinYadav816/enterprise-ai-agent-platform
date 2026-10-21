"""File storage behind one interface: local disk (dev) or S3 (prod)."""

import asyncio
import os
import re
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Protocol

from fastapi import Depends

from app.core.config import get_settings

PRESIGNED_URL_SECONDS = 300


class Storage(Protocol):
    async def save(self, key: str, data: bytes) -> None: ...
    async def open(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def url_or_none(self, key: str, download_name: str) -> str | None: ...


_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_filename(name: str, max_length: int = 150) -> str:
    """Basename only, conservative characters, no leading dots, extension kept lowercase."""
    base = PurePosixPath(name.replace("\\", "/")).name
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    stem = _UNSAFE.sub("_", stem).strip(" ._") or "file"
    ext = _UNSAFE.sub("", ext).lower()
    stem = stem[: max_length - len(ext) - 1]
    return f"{stem}.{ext}" if ext else stem


def document_key(org_id: uuid.UUID, document_id: uuid.UUID, filename: str) -> str:
    return f"{org_id}/{document_id}/{safe_filename(filename)}"


def _check_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or "\\" in key or any(p in ("..", "") for p in path.parts):
        raise ValueError(f"Unsafe storage key: {key!r}")
    return path


class LocalStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base = base_dir.resolve()

    def _path(self, key: str) -> Path:
        path = (self.base / _check_key(key)).resolve()
        if not path.is_relative_to(self.base):
            raise ValueError(f"Unsafe storage key: {key!r}")
        return path

    async def save(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self._write, self._path(key), data)

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent)  # write then rename: never a half file
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    async def open(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, missing_ok=True)

    async def url_or_none(self, key: str, download_name: str) -> str | None:
        return None  # served by the API itself


class S3Storage:
    def __init__(self, bucket: str, region: str | None) -> None:
        import boto3  # only needed in S3 mode

        self.bucket = bucket
        self._s3: Any = boto3.client("s3", region_name=region)

    async def save(self, key: str, data: bytes) -> None:
        _check_key(key)
        await asyncio.to_thread(self._s3.put_object, Bucket=self.bucket, Key=key, Body=data)

    async def open(self, key: str) -> bytes:
        _check_key(key)
        obj = await asyncio.to_thread(self._s3.get_object, Bucket=self.bucket, Key=key)
        return await asyncio.to_thread(obj["Body"].read)

    async def delete(self, key: str) -> None:
        _check_key(key)
        await asyncio.to_thread(self._s3.delete_object, Bucket=self.bucket, Key=key)

    async def url_or_none(self, key: str, download_name: str) -> str | None:
        disposition = f'attachment; filename="{safe_filename(download_name)}"'
        return await asyncio.to_thread(
            self._s3.generate_presigned_url,
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=PRESIGNED_URL_SECONDS,
        )


@lru_cache
def get_storage() -> Storage:
    s = get_settings()
    if s.storage_backend == "s3":
        if not s.s3_bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 requires S3_BUCKET")
        return S3Storage(s.s3_bucket, s.s3_region)
    return LocalStorage(s.storage_dir)


StorageDep = Annotated[Storage, Depends(get_storage)]
