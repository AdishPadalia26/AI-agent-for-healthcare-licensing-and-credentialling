"""OCR providers returning lines, key-value pairs, and tables."""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

import pymupdf

from .config import Settings


class OcrError(RuntimeError):
    pass


@dataclass
class OcrResult:
    lines: list[str] = field(default_factory=list)
    kv: dict[str, str] = field(default_factory=dict)
    tables: list[list[list[str]]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class DocumentRef:
    """A document in object storage (for Textract) and/or as bytes (for local OCR)."""

    bucket: str | None = None
    key: str | None = None
    data: bytes | None = None


class OcrProvider(Protocol):
    def analyze(self, document: DocumentRef) -> OcrResult: ...


def _block_text(block: dict[str, Any], blocks: dict[str, dict[str, Any]]) -> str:
    words: list[str] = []
    for relation in block.get("Relationships", []):
        if relation["Type"] != "CHILD":
            continue
        for child_id in relation["Ids"]:
            child = blocks.get(child_id, {})
            if child.get("BlockType") == "WORD":
                words.append(child.get("Text", ""))
            elif child.get("BlockType") == "SELECTION_ELEMENT" and child.get("SelectionStatus") == "SELECTED":
                words.append("☑")
    return " ".join(words).strip()


def parse_textract_pages(pages: list[dict[str, Any]]) -> OcrResult:
    blocks = {b["Id"]: b for page in pages for b in page.get("Blocks", [])}
    ordered = [b for page in pages for b in page.get("Blocks", [])]
    result = OcrResult()
    result.lines = [b["Text"].strip() for b in ordered if b["BlockType"] == "LINE" and b.get("Text", "").strip()]

    for block in ordered:
        if block["BlockType"] == "KEY_VALUE_SET" and "KEY" in block.get("EntityTypes", []):
            key = _block_text(block, blocks)
            value = ""
            for relation in block.get("Relationships", []):
                if relation["Type"] == "VALUE" and relation["Ids"]:
                    target = blocks.get(relation["Ids"][0])
                    value = _block_text(target, blocks) if target else ""
            if key:
                result.kv[key] = value
        elif block["BlockType"] == "TABLE":
            grid: dict[int, dict[int, str]] = defaultdict(dict)
            for relation in block.get("Relationships", []):
                if relation["Type"] != "CHILD":
                    continue
                for child_id in relation["Ids"]:
                    cell = blocks.get(child_id, {})
                    if cell.get("BlockType") == "CELL":
                        grid[cell["RowIndex"]][cell["ColumnIndex"]] = _block_text(cell, blocks)
            if grid:
                columns = max(max(row) for row in grid.values())
                result.tables.append(
                    [[grid[r].get(c, "") for c in range(1, columns + 1)] for r in range(1, max(grid) + 1)]
                )
    return result


class TextractOcr:
    """Asynchronous Textract, the only Textract API that accepts multi-page PDFs."""

    def __init__(self, settings: Settings, client: Any = None, poll_seconds: float = 2.0, timeout_seconds: float = 600.0):
        if client is None:
            import boto3

            session = boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)
            client = session.client("textract")
        self._client = client
        self._poll = poll_seconds
        self._timeout = timeout_seconds

    def _wait(self, job_id: str) -> str:
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            status = self._client.get_document_analysis(JobId=job_id, MaxResults=1)["JobStatus"]
            if status in ("SUCCEEDED", "FAILED", "PARTIAL_SUCCESS"):
                return status
            time.sleep(self._poll)
        raise OcrError(f"Textract job timed out after {self._timeout:.0f}s")

    def analyze(self, document: DocumentRef) -> OcrResult:
        if not document.bucket or not document.key:
            raise OcrError("Textract needs the document in S3. Set STORAGE_BACKEND=s3.")
        job_id = self._client.start_document_analysis(
            DocumentLocation={"S3Object": {"Bucket": document.bucket, "Name": document.key}},
            FeatureTypes=["FORMS", "TABLES"],
        )["JobId"]
        status = self._wait(job_id)
        if status == "FAILED":
            raise OcrError("Textract job failed")

        pages, token = [], None
        while True:
            kwargs: dict[str, Any] = {"JobId": job_id, "MaxResults": 1000}
            if token:
                kwargs["NextToken"] = token
            response = self._client.get_document_analysis(**kwargs)
            pages.append(response)
            token = response.get("NextToken")
            if not token:
                break
        result = parse_textract_pages(pages)
        if status == "PARTIAL_SUCCESS":
            result.warnings.append("Textract returned partial results; some pages may be missing.")
        return result


class LocalPdfOcr:
    """Reads the embedded text layer. Scanned documents need Textract."""

    def analyze(self, document: DocumentRef) -> OcrResult:
        if document.data is None:
            raise OcrError("Local OCR needs document bytes")
        try:
            with pymupdf.open(stream=document.data, filetype="pdf") as pdf:
                text = "\n".join(page.get_text() for page in pdf)
        except Exception as exc:
            raise OcrError("Local OCR only reads PDF files") from exc
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise OcrError("No text layer found. Scanned documents need OCR_PROVIDER=textract.")
        return OcrResult(lines=lines)


def build_ocr(settings: Settings) -> OcrProvider:
    return LocalPdfOcr() if settings.ocr_provider == "local" else TextractOcr(settings)
