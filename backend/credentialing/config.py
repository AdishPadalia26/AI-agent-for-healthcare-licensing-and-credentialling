"""One place for environment configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / "config" / ".env")
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    ocr_provider: str
    gemini_api_key: str | None
    gemini_model: str
    gemini_embedding_model: str
    aws_region: str | None
    aws_profile: str | None
    s3_bucket: str | None
    storage_backend: str
    data_dir: Path
    database_url: str
    data_encryption_key: str | None
    elasticsearch_url: str | None
    elasticsearch_api_key: str | None
    jwt_secret: str | None
    cors_origins: tuple[str, ...]
    admin_emails: tuple[str, ...]
    flask_debug: bool
    auto_fill_threshold: float
    review_threshold: float
    max_upload_bytes: int
    job_workers: int


def get_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", str(BACKEND_DIR / "data")))
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "gemini").lower(),
        ocr_provider=os.getenv("OCR_PROVIDER", "textract").lower(),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        gemini_embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
        aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        aws_profile=os.getenv("AWS_PROFILE"),
        s3_bucket=os.getenv("AWS_S3_BUCKET_NAME"),
        storage_backend=os.getenv("STORAGE_BACKEND", "local").lower(),
        data_dir=data_dir,
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{(data_dir / 'app.db').as_posix()}"),
        data_encryption_key=os.getenv("DATA_ENCRYPTION_KEY"),
        elasticsearch_url=os.getenv("ELASTICSEARCH_URL") or None,
        elasticsearch_api_key=os.getenv("ELASTICSEARCH_API_KEY") or None,
        jwt_secret=os.getenv("BACKEND_JWT_SECRET"),
        cors_origins=_list("CORS_ORIGINS", "http://localhost:3000"),
        admin_emails=tuple(e.lower() for e in _list("ADMIN_EMAILS")),
        flask_debug=_bool("FLASK_DEBUG", True),
        auto_fill_threshold=float(os.getenv("AUTO_FILL_THRESHOLD", "0.80")),
        review_threshold=float(os.getenv("REVIEW_THRESHOLD", "0.50")),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024,
        job_workers=int(os.getenv("JOB_WORKERS", "2")),
    )
