#!/usr/bin/env python3
"""Stage 3: map form fields to provider keys, with normalization and confidence bands."""
import argparse
import collections
import json
from dataclasses import replace
from pathlib import Path

from credentialing.config import get_settings
from credentialing.llm import build_llm
from credentialing.mapping import Mapper
from credentialing.retrieval import build_store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", required=True)
    parser.add_argument("--resume", required=True, help="Provider record from stage 1")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model")
    parser.add_argument("--min-confidence", type=float, help="Values below this become null")
    args = parser.parse_args()

    settings = get_settings()
    settings = replace(
        settings,
        gemini_model=args.model or settings.gemini_model,
        review_threshold=args.min_confidence if args.min_confidence is not None else settings.review_threshold,
    )
    fields = json.loads(Path(args.fields).read_text(encoding="utf-8"))
    record = json.loads(Path(args.resume).read_text(encoding="utf-8"))

    llm = build_llm(settings)
    mapper = Mapper(llm, settings, build_store(settings, llm.embed))
    mapped = mapper.map(fields, record)
    Path(args.out).write_text(json.dumps(mapped, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(mapped)} mapped fields to {args.out}: {dict(collections.Counter(m['band'] for m in mapped))}")
    for warning in mapper.warnings:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()
