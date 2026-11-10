"""Write mapped values into AcroForm widgets."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pymupdf

from .fields import widget_type

_AFFIRMATIVE = {"yes", "true", "on", "1", "checked", "x", "y", "t"}
_NEGATIVE = {"no", "false", "off", "0", "unchecked", "n", "f"}
_BBOX_TOLERANCE = 2.0


@dataclass
class FillReport:
    written: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _clean_text(value: Any) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value))


def _set_button(widget: Any, value: Any) -> bool:
    desired = str(value).strip().lower()
    state = widget.on_state()
    if widget_type(widget) == "radio":
        if state and str(state).strip().lower() == desired:
            widget.field_value = state
            widget.update()
            return True
        return False
    if desired in _AFFIRMATIVE or (state and desired == str(state).strip().lower()):
        widget.field_value = state
    elif desired in _NEGATIVE:
        widget.field_value = "Off"
    else:
        return False  # An unrecognised value must not silently toggle a legal attestation.
    widget.update()
    return True


def set_widget_value(widget: Any, value: Any) -> bool:
    if value is None or value == "":
        return False
    kind = widget_type(widget)
    if kind in ("checkbox", "radio"):
        return _set_button(widget, value)
    if kind in ("text", "combobox", "listbox"):
        widget.field_value = _clean_text(value)
        widget.update()
        return True
    return False


def _find_target(widget: Any, by_name: dict[str, list[dict]], page_items: list[dict]) -> dict | None:
    """Exact name first, then the same rectangle. Never the merely nearest field."""
    named = by_name.get(widget.field_name or "")
    candidates = named if named else page_items
    rect = widget.rect
    for item in candidates:
        x0, y0, x1, y1 = item["bbox"]
        if (
            abs(rect.x0 - x0) <= _BBOX_TOLERANCE
            and abs(rect.y0 - y0) <= _BBOX_TOLERANCE
            and abs(rect.x1 - x1) <= _BBOX_TOLERANCE
            and abs(rect.y1 - y1) <= _BBOX_TOLERANCE
        ):
            return item
    return named[0] if named and len(named) == 1 else None


def fill_pdf(pdf: str | bytes, mapped: list[dict[str, Any]]) -> tuple[bytes, FillReport]:
    doc = pymupdf.open(stream=pdf, filetype="pdf") if isinstance(pdf, bytes) else pymupdf.open(pdf)
    report = FillReport()
    by_name: dict[str, list[dict]] = {}
    by_page: dict[int, list[dict]] = {}
    for item in mapped:
        if item.get("field_name"):
            by_name.setdefault(item["field_name"], []).append(item)
        by_page.setdefault(item["page"], []).append(item)
    try:
        for page_number in range(len(doc)):
            page = doc.load_page(page_number)
            for widget in page.widgets() or []:
                target = _find_target(widget, by_name, by_page.get(page_number, []))
                if not target or target.get("value") in (None, ""):
                    report.skipped += 1
                    continue
                try:
                    if set_widget_value(widget, target["value"]):
                        report.written += 1
                    else:
                        report.skipped += 1
                except Exception as exc:  # one bad widget must not lose the whole form
                    report.errors.append(f"{widget.field_name}: {type(exc).__name__}")
        return doc.tobytes(garbage=3, deflate=True), report
    finally:
        doc.close()
