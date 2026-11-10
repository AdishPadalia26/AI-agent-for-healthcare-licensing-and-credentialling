#!/usr/bin/env python3
"""Measure field mapping and filling against hand-labelled expectations.

Default mode is offline: provider records are the ground truth and no LLM is called, so it
measures rules, anchoring, normalization, gating, and filling only. Use --live to include
Gemini on the unnamed fields, and --cv to also measure OCR and extraction from a real document.

Usage: python -m eval.run_eval [--live] [--cv PATH] [--out eval/results.json]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pymupdf

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
REPO = BACKEND.parent

from credentialing.config import get_settings  # noqa: E402
from credentialing.fields import describe, extract_fields  # noqa: E402
from credentialing.fill import fill_pdf  # noqa: E402
from credentialing.llm import LocalProvider, build_llm  # noqa: E402
from credentialing.mapping import Mapper  # noqa: E402
from credentialing.normalize import normalize_value  # noqa: E402
from credentialing.pipeline import filled_values  # noqa: E402
from credentialing.retrieval import InMemoryStore  # noqa: E402
from credentialing.schema import flatten  # noqa: E402

CAVEATS = [
    "Records are synthetic and the gold labels were written by the author of the mapping rules, so "
    "offline results describe this form and are not an independent accuracy estimate.",
    "Offline mode makes no OCR or Gemini calls. Run with --live and --cv to measure those stages.",
    "This is not a measurement of the speed, review-effort, or error-rate claims in the README, "
    "which need a baseline that is not in this repository.",
]


def resolve(expect: str | None, record: dict[str, Any]) -> tuple[str | None, Any]:
    if expect is None:
        return None, None
    if expect == "@languages":
        languages = record.get("languages_spoken") or []
        return "languages_spoken", ", ".join(languages) if languages else None
    if expect.startswith("@license:"):
        _, needle, leaf = expect.split(":")
        for index, entry in enumerate(record.get("licensure") or []):
            kind = entry.get("type") or ""
            matches = "dea" in kind.lower() if needle == "dea" else (
                "dea" not in kind.lower() and str(entry.get("state", "")).lower() in {"tx", "texas"}
            )
            if matches:
                return f"licensure[{index}].{leaf}", entry.get(leaf)
        return None, None
    return expect, flatten(record).get(expect)


def score_record(mapped: list[dict], gold: list[dict], record: dict) -> dict[str, int | list]:
    by_name = {m["field_name"]: m for m in mapped}
    result: dict[str, Any] = dict(correct=0, wrong=0, missed=0, deferred=0, correct_blank=0, wrong_fill=0, errors=[])
    for item in gold:
        field = by_name[item["field"]]
        key, raw = resolve(item["expect"], record)
        auto = field["band"] == "auto_fill"
        if raw is None:
            if auto:
                result["wrong_fill"] += 1
                result["errors"].append({"field": item["field"], "problem": "auto-filled, expected none"})
            else:
                result["correct_blank"] += 1
            continue
        expected = normalize_value(describe(field), raw, key)
        if auto and field["value"] == expected:
            result["correct"] += 1
        elif auto:
            result["wrong"] += 1
            result["errors"].append({"field": item["field"], "problem": "wrong auto-filled value"})
        elif field["band"] == "needs_review":
            result["deferred"] += 1
        else:
            result["missed"] += 1
            result["errors"].append({"field": item["field"], "problem": "left blank"})
    return result


def verify_written(pdf: bytes, written: list[dict]) -> int:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    values = {w.field_name: w.field_value for page in doc for w in (page.widgets() or [])}
    doc.close()
    return sum(1 for m in written if m["field_type"] == "text" and values.get(m["field_name"]) != m["value"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use the configured Gemini provider")
    parser.add_argument("--cv", help="Also run OCR and extraction on this PDF (needs --live)")
    parser.add_argument("--out", default=str(BACKEND / "eval" / "results.json"))
    args = parser.parse_args()

    settings = replace(get_settings(), elasticsearch_url=None)
    gold = json.loads((BACKEND / "eval" / "gold_weehope.json").read_text(encoding="utf-8"))
    form = (REPO / gold["form"]).read_bytes()
    fields = extract_fields(form)
    llm = build_llm(settings) if args.live else LocalProvider()

    runs, timings = [], []
    for path in sorted((REPO / "samples" / "provider_records").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        started = time.perf_counter()
        mapper = Mapper(llm, settings, InMemoryStore(LocalProvider().embed))
        mapped = mapper.map(fields, record)
        written = filled_values(mapped, include_review=False)
        pdf, report = fill_pdf(form, written)
        timings.append(time.perf_counter() - started)
        scored = score_record(mapped, gold["fields"], record)
        runs.append(
            {
                "record": path.name,
                **scored,
                "written": report.written,
                "fill_errors": report.errors,
                "readback_mismatches": verify_written(pdf, written),
                "bands": {b: sum(m["band"] == b for m in mapped) for b in ("auto_fill", "needs_review", "blank")},
            }
        )

    total = lambda name: sum(run[name] for run in runs)
    auto = total("correct") + total("wrong") + total("wrong_fill")
    answerable = total("correct") + total("wrong") + total("deferred") + total("missed")
    fields_total = len(fields)
    output: dict[str, Any] = {
        "mode": f"live ({llm.name})" if args.live else "offline (no OCR, no LLM)",
        "caveats": CAVEATS,
        "form_fields": fields_total,
        "gold_fields": len(gold["fields"]),
        "records": len(runs),
        "auto_fill_precision": round(total("correct") / auto, 4) if auto else None,
        "answerable_auto_fill_coverage": round(total("correct") / answerable, 4) if answerable else None,
        "deferred_to_review": total("deferred"),
        "mean_seconds_map_and_fill": round(statistics.mean(timings), 3),
        "mean_share_of_form_needing_review": round(
            statistics.mean(r["bands"]["needs_review"] / fields_total for r in runs), 4
        ),
        "runs": runs,
    }

    if args.cv:
        if not args.live:
            parser.error("--cv requires --live")
        from credentialing.extract import build_provider_record
        from credentialing.ocr import DocumentRef, LocalPdfOcr

        record = build_provider_record(LocalPdfOcr().analyze(DocumentRef(data=Path(args.cv).read_bytes())), llm)
        output["cv_extraction"] = {"provenance": record["_provenance"], "warnings": record["_warnings"]}

    Path(args.out).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {k: v for k, v in output.items() if k not in ("runs", "caveats", "cv_extraction")}
    print(json.dumps(summary, indent=2))
    print(re.sub(r"\s+", " ", " ".join(CAVEATS)))


if __name__ == "__main__":
    main()
