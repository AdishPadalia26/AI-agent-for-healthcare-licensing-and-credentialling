"""Discover AcroForm widgets with stable IDs, cleaned names, and nearby label text."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any

import pymupdf

_TYPE_NAMES = {
    pymupdf.PDF_WIDGET_TYPE_TEXT: "text",
    pymupdf.PDF_WIDGET_TYPE_BUTTON: "button",
    pymupdf.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
    pymupdf.PDF_WIDGET_TYPE_COMBOBOX: "combobox",
    pymupdf.PDF_WIDGET_TYPE_LISTBOX: "listbox",
    pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
    pymupdf.PDF_WIDGET_TYPE_SIGNATURE: "signature",
}
_GENERIC_NAME = re.compile(r"^(text|check\s*box|field|undefined|signature|button|untitled)[\s_]*\d*$", re.I)
_MAX_LABEL_GAP = 40.0
_MAX_ABOVE_GAP = 26.0


@dataclass
class Field:
    id: str
    page: int
    field_name: str | None
    field_type: str
    bbox: list[float]
    label: str | None
    section: str | None = None
    context: str | None = None


def widget_type(widget: Any) -> str:
    return _TYPE_NAMES.get(widget.field_type, "unknown")


def clean_field_name(name: str | None) -> str | None:
    """Turn `4 NPI National Provider Identifier` style names into a usable descriptor."""
    if not name:
        return None
    text = re.sub(r"_\d+$", "", name.strip())
    if _GENERIC_NAME.match(text):
        return None
    text = re.sub(r"^\d+[A-Z]?\s+", "", text)
    text = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    return re.sub(r"\s+", " ", text).strip() or None


def describe(field: dict[str, Any]) -> str:
    """Best text for what a field asks. Authored names beat position-derived labels."""
    return clean_field_name(field.get("field_name")) or field.get("label") or ""


def _is_blank_run(word: str) -> bool:
    return not re.sub(r"[_\-=.:´`'~ ]", "", word)


def _left_label(rect: pymupdf.Rect, words: list[tuple]) -> str | None:
    """Words directly left of the field on its line, stopping at the previous blank."""
    same_line = []
    for word in words:
        overlap = min(rect.y1, word[3]) - max(rect.y0, word[1])
        if overlap > 0.4 * (word[3] - word[1]) and word[2] <= rect.x0 + 3:
            same_line.append(word)
    same_line.sort(key=lambda w: -w[2])

    picked: list[str] = []
    edge = rect.x0
    for word in same_line:
        if edge - word[2] > _MAX_LABEL_GAP or len(picked) >= 10:
            break
        text = word[4]
        if _is_blank_run(text):
            if picked:
                break
            edge = word[0]
            continue
        if "_" in text:
            tail = text.rsplit("_", 1)[-1]
            if tail:
                picked.append(tail)
            if picked:
                break
            edge = word[0]
            continue
        picked.append(text)
        edge = word[0]
    return " ".join(reversed(picked)).strip(" :") or None


def _above_label(rect: pymupdf.Rect, lines: list[dict[str, Any]]) -> str | None:
    best, best_gap = None, _MAX_ABOVE_GAP
    for line in lines:
        gap = rect.y0 - line["y1"]
        overlap = min(rect.x1, line["x1"]) - max(rect.x0, line["x0"])
        if 0 <= gap < best_gap and overlap > 0 and "_" not in line["text"]:
            best, best_gap = line["text"], gap
    return best


def _section(rect: pymupdf.Rect, lines: list[dict[str, Any]]) -> str | None:
    best = None
    for line in lines:
        letters = [c for c in line["text"] if c.isalpha()]
        if (
            line["y1"] <= rect.y0 + 2
            and len(letters) >= 5
            and sum(c.isupper() for c in letters) / len(letters) > 0.8
            and "_" not in line["text"]
            and (best is None or line["y1"] > best["y1"])
        ):
            best = line
    return best["text"] if best else None


def _context(rect: pymupdf.Rect, lines: list[dict[str, Any]]) -> str | None:
    nearby = sorted(
        (ln for ln in lines if -4 <= rect.y0 - ln["y0"] <= 45),
        key=lambda ln: abs(rect.y0 - ln["y0"]),
    )[:3]
    text = " | ".join(re.sub(r"_+", " ", ln["text"]).strip() for ln in nearby)
    return text[:240] or None


def _page_lines(words: list[tuple]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], list[tuple]] = {}
    for word in words:
        grouped.setdefault((word[5], word[6]), []).append(word)
    return [
        {
            "text": " ".join(w[4] for w in group),
            "x0": min(w[0] for w in group),
            "y0": min(w[1] for w in group),
            "x1": max(w[2] for w in group),
            "y1": max(w[3] for w in group),
        }
        for group in grouped.values()
    ]


def stable_id(page: int, name: str | None, rect: pymupdf.Rect) -> str:
    raw = f"{page}|{name}|{rect.x0:.1f}|{rect.y0:.1f}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def extract_fields(pdf: str | bytes) -> list[dict[str, Any]]:
    doc = pymupdf.open(stream=pdf, filetype="pdf") if isinstance(pdf, bytes) else pymupdf.open(pdf)
    fields: list[dict[str, Any]] = []
    try:
        for page_number in range(len(doc)):
            page = doc.load_page(page_number)
            words = page.get_text("words", sort=True)
            lines = _page_lines(words)
            for widget in page.widgets() or []:
                rect = widget.rect
                label = _left_label(rect, words) or _above_label(rect, lines)
                fields.append(
                    asdict(
                        Field(
                            id=stable_id(page_number, widget.field_name, rect),
                            page=page_number,
                            field_name=widget.field_name or None,
                            field_type=widget_type(widget),
                            bbox=[float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                            label=label,
                            section=_section(rect, lines),
                            context=_context(rect, lines),
                        )
                    )
                )
    finally:
        doc.close()
    return fields
