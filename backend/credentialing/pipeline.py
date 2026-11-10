"""End-to-end orchestration used by the API, CLI wrappers, and evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Settings
from .extract import build_provider_record
from .fields import extract_fields
from .fill import FillReport, fill_pdf
from .llm import LLMProvider
from .mapping import Mapper
from .ocr import DocumentRef, OcrProvider
from .retrieval import RetrievalStore, chunk_lines


class FormError(ValueError):
    """The target PDF cannot be processed."""


@dataclass
class PipelineResult:
    record: dict[str, Any]
    mapped: list[dict[str, Any]]
    filled_pdf: bytes
    report: FillReport
    warnings: list[str]


def filled_values(mapped: list[dict[str, Any]], include_review: bool) -> list[dict[str, Any]]:
    """Fields to write: reviewed always, auto-fill always, unreviewed guesses only on request."""
    allowed = {"auto_fill", "reviewed"} | ({"needs_review"} if include_review else set())
    return [m for m in mapped if m.get("band") in allowed]


def run_pipeline(
    document: DocumentRef,
    form_pdf: bytes,
    ocr: OcrProvider,
    llm: LLMProvider,
    store: RetrievalStore,
    settings: Settings,
    job_id: str | None = None,
    on_stage: Any = None,
) -> PipelineResult:
    def stage(name: str) -> None:
        if on_stage:
            on_stage(name)

    fields = extract_fields(form_pdf)
    if not fields:
        raise FormError("This PDF has no fillable form fields.")

    stage("extracting")
    result = ocr.analyze(document)
    record = build_provider_record(result, llm)

    stage("mapping")
    if job_id:
        store.index_chunks(job_id, chunk_lines(result.lines))
    mapper = Mapper(llm, settings, store)
    mapped = mapper.map(fields, record, job_id)

    stage("filling")
    pdf, report = fill_pdf(form_pdf, filled_values(mapped, include_review=False))
    return PipelineResult(record, mapped, pdf, report, [*record.get("_warnings", []), *mapper.warnings])
