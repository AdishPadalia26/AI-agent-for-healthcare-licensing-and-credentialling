"""Shared services and the background job runner."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from credentialing.config import Settings
from credentialing.llm import LLMError, LLMProvider, build_llm
from credentialing.ocr import OcrError, OcrProvider, build_ocr
from credentialing.pipeline import FormError, run_pipeline
from credentialing.retrieval import RetrievalStore, build_store

from .models import TERMINAL_STATUSES, AuditEvent, Job
from .storage import Storage

log = logging.getLogger(__name__)


class Services:
    def __init__(
        self,
        settings: Settings,
        sessions: sessionmaker[Session],
        storage: Storage,
        llm: LLMProvider | None = None,
        ocr: OcrProvider | None = None,
        store: RetrievalStore | None = None,
        synchronous: bool = False,
    ):
        self.settings = settings
        self.sessions = sessions
        self.storage = storage
        self._llm, self._ocr, self._store = llm, ocr, store
        self._synchronous = synchronous
        self._pool = None if synchronous else ThreadPoolExecutor(max_workers=settings.job_workers)

    # Providers are built on first use so the API boots without AWS or Gemini configured.
    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = build_llm(self.settings)
        return self._llm

    @property
    def ocr(self) -> OcrProvider:
        if self._ocr is None:
            self._ocr = build_ocr(self.settings)
        return self._ocr

    @property
    def store(self) -> RetrievalStore:
        if self._store is None:
            self._store = build_store(self.settings, self.llm.embed)
        return self._store

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.sessions()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def audit(self, session: Session, actor: str, action: str, job_id: str | None = None) -> None:
        session.add(AuditEvent(actor=actor, action=action, job_id=job_id))

    def fail_interrupted_jobs(self) -> None:
        with self.session() as session:
            for job in session.scalars(select(Job).where(Job.status.not_in(TERMINAL_STATUSES))):
                job.status, job.error = "failed", "Interrupted by a server restart. Please start again."

    def submit(self, job_id: str) -> None:
        if self._synchronous:
            self.process(job_id)
        else:
            self._pool.submit(self.process, job_id)

    def _set_status(self, job_id: str, status: str) -> None:
        with self.session() as session:
            session.get(Job, job_id).status = status

    def process(self, job_id: str) -> None:
        try:
            with self.session() as session:
                job = session.get(Job, job_id)
                cv_key, form_key, user_id = job.cv_key, job.form_key, job.user_id
            result = run_pipeline(
                self.storage.document_ref(cv_key),
                self.storage.get(form_key),
                self.ocr,
                self.llm,
                self.store,
                self.settings,
                job_id=job_id,
                on_stage=lambda stage: self._set_status(job_id, stage),
            )
            filled_key = f"{cv_key.rsplit('/', 1)[0]}/filled.pdf"
            self.storage.put(filled_key, result.filled_pdf)
            pending = any(item["band"] == "needs_review" for item in result.mapped)
            with self.session() as session:
                job = session.get(Job, job_id)
                job.record = result.record
                job.fields = result.mapped
                job.filled_key = filled_key
                job.warnings = result.warnings
                job.status = "needs_review" if pending else "completed"
                self.audit(session, user_id, "job_processed", job_id)
        except (FormError, OcrError, LLMError, ValueError) as exc:
            self._fail(job_id, str(exc))
        except Exception as exc:  # message may contain provider data, so only the type is logged
            log.error("job %s failed: %s", job_id, type(exc).__name__)
            self._fail(job_id, "Processing failed unexpectedly.")

    def _fail(self, job_id: str, message: str) -> None:
        with self.session() as session:
            job = session.get(Job, job_id)
            job.status, job.error = "failed", message
