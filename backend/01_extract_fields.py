#!/usr/bin/env python3
"""Stage 2: discover form widgets, stable IDs, labels, and bounding boxes."""
import argparse
import json
from pathlib import Path

from credentialing.fields import extract_fields


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    fields = extract_fields(args.pdf)
    Path(args.out).write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(fields)} fields to {args.out}")


if __name__ == "__main__":
    main()
