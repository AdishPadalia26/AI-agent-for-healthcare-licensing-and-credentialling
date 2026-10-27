#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fill a PDF AcroForm using mapped_fields.json.

Usage:
  python 03_fill_pdf.py --pdf form.pdf --mapped mapped_fields.json --out filled_form.pdf
"""
import json
import argparse
import re
import fitz  # PyMuPDF


TRUE_SET = {"yes", "true", "on", "1", "checked", "x", "y", "t"}

def _widget_type(w):
    """Return canonical widget type string."""
    tstr = getattr(w, "field_type_string", None)
    if isinstance(tstr, str):
        t = tstr.lower()
        if "text" in t: return "text"
        if "check" in t: return "checkbox"
        if "radio" in t: return "radio"
        if "combo" in t: return "combobox"
        if "list" in t: return "listbox"
        if "button" in t: return "button"
        if "sign" in t: return "signature"
        return "unknown"

    # Fallback: map integer type
    ft = getattr(w, "field_type", None)
    mapping = {
        getattr(fitz, "PDF_WIDGET_TYPE_TEXT", -1): "text",
        getattr(fitz, "PDF_WIDGET_TYPE_BUTTON", -1): "button",
        getattr(fitz, "PDF_WIDGET_TYPE_CHECKBOX", -1): "checkbox",
        getattr(fitz, "PDF_WIDGET_TYPE_COMBOBOX", -1): "combobox",
        getattr(fitz, "PDF_WIDGET_TYPE_LISTBOX", -1): "listbox",
        getattr(fitz, "PDF_WIDGET_TYPE_RADIOBUTTON", -1): "radio",
        getattr(fitz, "PDF_WIDGET_TYPE_SIGNATURE", -1): "signature",
    }
    return mapping.get(ft, "unknown")


def _is_truthy(v):
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in TRUE_SET or s == ""  # empty (e.g., any value present) counts as True for radios when no label match


def _coerce_text(v):
    if v is None:
        return None
    s = str(v)
    # Remove control characters that sometimes sneak in from OCR/LLM
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    return s


def _radio_group(doc, field_name):
    """
    Return a list of (page, widget) for all radio buttons in the same field_name group across the document.
    Some PDFs have radio groups spanning multiple pages.
    """
    group = []
    for pno in range(len(doc)):
        page = doc.load_page(pno)
        for w in list(page.widgets() or []):
            if _widget_type(w) == "radio" and w.field_name == field_name:
                group.append((pno, w))
    return group


def _get_button_export_label(w):
    """
    For checkbox/radio, try known attributes for export value/label.
    Different PyMuPDF versions expose different names; be defensive.
    """
    for attr in ("button_label", "export_value", "on_state", "caption"):
        val = getattr(w, attr, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def set_widget_value(doc, w, value):
    """
    Set the widget value based on type.
    """
    wtype = _widget_type(w)

    if value is None or value == "":
        return  # nothing to write

    if wtype == "checkbox":
        # Coerce to boolean and check/uncheck
        w.set_checked(_is_truthy(value))
        w.update()
        return

    if wtype == "radio":
        # Radios are grouped by field_name.
        # If value matches any radio's export label -> check that one.
        # Else if value is truthy -> check the first in the group.
        fname = getattr(w, "field_name", None)
        if not fname:
            return
        group = _radio_group(doc, fname)
        desired = str(value).strip().lower()

        # Try exact label match (case-insensitive, ignoring trivial whitespace)
        matched = False
        for _, rw in group:
            label = _get_button_export_label(rw)
            if label and label.strip().lower() == desired:
                # Turn off all others first
                for _, rw2 in group:
                    rw2.set_checked(False)
                    rw2.update()
                rw.set_checked(True)
                rw.update()
                matched = True
                break

        if not matched and _is_truthy(value) and group:
            # No explicit label match; choose the first
            for _, rw2 in group:
                rw2.set_checked(False)
                rw2.update()
            group[0][1].set_checked(True)
            group[0][1].update()
        return

    if wtype in ("text", "combobox", "listbox"):
        s = _coerce_text(value)
        if s is not None:
            w.field_value = s
            w.update()
        return

    # Buttons/signatures/unknown -> skip
    return


def _closest_mapping_for_widget(w, page_map):
    """
    Choose the best mapped field value for a widget:
     1) exact field_name match (if any)
     2) nearest center distance to bbox
    """
    # 1) field_name match
    for m in page_map:
        if m.get("field_name") and getattr(w, "field_name", None) == m["field_name"]:
            return m

    # 2) spatial fallback (closest center)
    wx = (w.rect.x0 + w.rect.x1) / 2.0
    wy = (w.rect.y0 + w.rect.y1) / 2.0
    best, bd = None, 1e18
    for m in page_map:
        x0, y0, x1, y1 = m["bbox"]
        mx = (x0 + x1) / 2.0
        my = (y0 + y1) / 2.0
        d = (wx - mx) ** 2 + (wy - my) ** 2
        if d < bd:
            bd = d
            best = m
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Input PDF")
    ap.add_argument("--mapped", required=True, help="mapped_fields.json (from step 2)")
    ap.add_argument("--out", required=True, help="filled_form.pdf")
    args = ap.parse_args()

    with open(args.mapped, "r", encoding="utf-8") as f:
        mapped = json.load(f)

    # Index mapped values by page
    by_page = {}
    for m in mapped:
        by_page.setdefault(m["page"], []).append(m)

    doc = fitz.open(args.pdf)

    for pno in range(len(doc)):
        page = doc.load_page(pno)
        widgets = list(page.widgets() or [])
        page_map = by_page.get(pno, [])

        for w in widgets:
            target = _closest_mapping_for_widget(w, page_map) if page_map else None
            if not target:
                continue
            val = target.get("value")
            if val in (None, ""):
                continue
            set_widget_value(doc, w, val)

    # Save with updated appearance streams
    doc.save(args.out, deflate=True)
    doc.close()
    print(f"Saved filled form → {args.out}")


if __name__ == "__main__":
    main()
