"""Object storage: S3 in deployment, a local directory otherwise."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

from credentialing.config import Settings
from credentialing.ocr import DocumentRef


def user_prefix(email: str) -> str:
    """Per-user key prefix. The Next.js upload route computes the same value."""
    return f"users/{hashlib.sha256(email.lower().encode()).hexdigest()[:16]}/"


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str = "application/pdf") -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def document_ref(self, key: str) -> DocumentRef: ...


class LocalStorage:
    def __init__(self, root: Path):
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("Invalid storage key")
        return path

    def put(self, key, data, content_type="application/pdf"):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key):
        return self._path(key).read_bytes()

    def exists(self, key):
        return self._path(key).is_file()

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)

    def document_ref(self, key):
        return DocumentRef(data=self.get(key))


class S3Storage:
    def __init__(self, settings: Settings, client=None):
        if not settings.s3_bucket:
            raise ValueError("AWS_S3_BUCKET_NAME is required when STORAGE_BACKEND=s3")
        if client is None:
            import boto3

            client = boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region).client("s3")
        self._client = client
        self._bucket = settings.s3_bucket

    def put(self, key, data, content_type="application/pdf"):
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type, ServerSideEncryption="AES256"
        )

    def get(self, key):
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def exists(self, key):
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key):
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def document_ref(self, key):
        return DocumentRef(bucket=self._bucket, key=key, data=self.get(key))


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(settings.data_dir / "objects")
