"""Optional utility: extract a provider record from a digital PDF using pdfplumber text.

Usage: python cv_process.py CV.pdf [output.json]
"""
import json
import sys

import pdfplumber

from credentialing.config import get_settings
from credentialing.extract import build_provider_record
from credentialing.llm import build_llm
from credentialing.ocr import OcrResult


def extract_text_from_pdf(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def cv_to_json(pdf_path: str, output_json: str = "cv_output.json") -> dict:
    text = extract_text_from_pdf(pdf_path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    record = build_provider_record(OcrResult(lines=lines), build_llm(get_settings()))
    with open(output_json, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
    print(f"Saved structured JSON to: {output_json}")
    return record


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cv_to_json(sys.argv[1], *sys.argv[2:3])
