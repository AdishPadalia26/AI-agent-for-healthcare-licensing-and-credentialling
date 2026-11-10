#!/usr/bin/env python3
"""Stage 1: extract a provider record from a CV in S3 (or a local PDF with --pdf)."""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from credentialing.config import get_settings
from credentialing.extract import build_provider_record
from credentialing.llm import build_llm
from credentialing.ocr import DocumentRef, LocalPdfOcr, TextractOcr


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket")
    parser.add_argument("--key")
    parser.add_argument("--pdf", help="Local digital PDF, read without Textract")
    parser.add_argument("--region")
    parser.add_argument("--profile")
    parser.add_argument("--gemini-model")
    parser.add_argument("--out", help="Write JSON here instead of stdout")
    args = parser.parse_args()
    if not args.pdf and not (args.bucket and args.key):
        parser.error("provide --bucket and --key, or --pdf")

    settings = get_settings()
    settings = replace(
        settings,
        aws_region=args.region or settings.aws_region,
        aws_profile=args.profile or settings.aws_profile,
        gemini_model=args.gemini_model or settings.gemini_model,
    )
    if args.pdf:
        ocr, document = LocalPdfOcr(), DocumentRef(data=Path(args.pdf).read_bytes())
    else:
        ocr, document = TextractOcr(settings), DocumentRef(bucket=args.bucket, key=args.key)

    output = json.dumps(build_provider_record(ocr.analyze(document), build_llm(settings)), indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Wrote provider record to {args.out}", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
