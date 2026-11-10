"""Database models. Provider data is encrypted at the column level."""
from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

TERMINAL_STATUSES = ("needs_review", "completed", "failed")
_fernet: Fernet | None = None


def configure_encryption(secret: str) -> None:
    global _fernet
    _fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


class EncryptedJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        if _fernet is None:
            raise RuntimeError("Encryption key is not configured")
        return _fernet.encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value: str | None, dialect: Any) -> Any:
        if value is None:
            return None
        if _fernet is None:
            raise RuntimeError("Encryption key is not configured")
        return json.loads(_fernet.decrypt(value.encode()))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    review_note: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    cv_key: Mapped[str] = mapped_column(String(400))
    form_key: Mapped[str] = mapped_column(String(400))
    filled_key: Mapped[str | None] = mapped_column(String(400))
    cv_name: Mapped[str] = mapped_column(String(300))
    form_name: Mapped[str] = mapped_column(String(300))
    warnings: Mapped[Any] = mapped_column(JSON, default=list)
    record: Mapped[Any] = mapped_column(EncryptedJSON, nullable=True)
    fields: Mapped[Any] = mapped_column(EncryptedJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    user: Mapped[User] = relationship()


class AuditEvent(Base):
    """Who did what to which job. Never holds provider values."""

    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    actor: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(60))
    job_id: Mapped[str | None] = mapped_column(String(32), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
