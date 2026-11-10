#!/usr/bin/env python3
"""Stage 4: write mapped values into the PDF's form widgets."""
import argparse
import json
from pathlib import Path

from credentialing.fill import fill_pdf
from credentialing.pipeline import filled_values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--mapped", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--auto-only", action="store_true", help="Skip values that need human review")
    args = parser.parse_args()

    mapped = json.loads(Path(args.mapped).read_text(encoding="utf-8"))
    pdf, report = fill_pdf(args.pdf, filled_values(mapped, include_review=not args.auto_only))
    Path(args.out).write_bytes(pdf)
    print(f"Saved {args.out}: {report.written} written, {report.skipped} skipped, {len(report.errors)} errors")
    for error in report.errors:
        print(f"error: {error}")


if __name__ == "__main__":
    main()
