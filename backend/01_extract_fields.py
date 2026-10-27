#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract PDF form fields with bounding boxes and nearest labels.

Output schema (fields.json): List[{
  "id": str,
  "page": int,
  "field_name": str | null,
  "field_type": str,            # text | checkbox | radio | combobox | listbox | signature | unknown
  "bbox": [x0, y0, x1, y1],     # PyMuPDF points, origin top-left
  "label": str | null
}]
"""
import json, argparse, uuid
import fitz  # PyMuPDF
from dataclasses import dataclass, asdict

@dataclass
class Field:
    id: str
    page: int
    field_name: str | None
    field_type: str
    bbox: list[float]
    label: str | None

# --- replace your _widget_type() with this ---
def _widget_type(w):
    # Prefer descriptive string when available
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

    # Fallback: map integer field_type via PyMuPDF constants
    import fitz
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


def _words_by_line(page):
    # returns dict[(block,line)] -> list[(x0,y0,x1,y1,word)]
    out = {}
    for x0, y0, x1, y1, w, block, line, _ in page.get_text("words", sort=True):
        out.setdefault((block, line), []).append((x0, y0, x1, y1, w))
    return out

def _line_bbox(words):
    x0 = min(w[0] for w in words); y0 = min(w[1] for w in words)
    x1 = max(w[2] for w in words); y1 = max(w[3] for w in words)
    return (x0, y0, x1, y1)

def _dist_left(field_rect, line_rect):
    # prefer labels to the left with small gap and vertical overlap
    fx0, fy0, fx1, fy1 = field_rect
    lx0, ly0, lx1, ly1 = line_rect
    if lx1 > fx0:  # label’s right edge must be left of field’s left edge
        return None
    # vertical overlap requirement
    v_overlap = max(0, min(fy1, ly1) - max(fy0, ly0))
    if v_overlap <= 0:
        return None
    gap = fx0 - lx1  # positive if line is to the left
    return gap + 0.25 * abs((fy0 + fy1)/2 - (ly0 + ly1)/2)  # small vertical penalty

def _dist_above(field_rect, line_rect):
    # prefer labels just above the field, horizontally overlapping
    fx0, fy0, fx1, fy1 = field_rect
    lx0, ly0, lx1, ly1 = line_rect
    if ly1 > fy0:  # label must be above top of field
        return None
    h_overlap = max(0, min(fx1, lx1) - max(fx0, lx0))
    if h_overlap <= 0:
        return None
    gap = fy0 - ly1
    return gap + 0.25 * abs((fx0 + fx1)/2 - (lx0 + lx1)/2)

def _nearest_label(page, rect, max_dx=180, max_dy=48):
    lines = _words_by_line(page)
    best = (None, 1e9, None)  # (label_text, score, source)
    for (_, _), words in lines.items():
        lb = _line_bbox(words)
        left_score = _dist_left(rect, lb)
        if left_score is not None and left_score <= max_dx:
            text = " ".join(w[4] for w in words)
            if left_score < best[1]:
                best = (text, left_score, "left")
        above_score = _dist_above(rect, lb)
        if above_score is not None and above_score <= max_dy:
            text = " ".join(w[4] for w in words)
            if above_score < best[1]:
                best = (text, above_score, "above")
    return best[0]

def extract_fields(pdf_path: str) -> list[Field]:
    doc = fitz.open(pdf_path)
    fields: list[Field] = []
    for pno in range(len(doc)):
        page = doc.load_page(pno)
        widgets = list(page.widgets() or [])
        for w in widgets:
            r = w.rect
            label = _nearest_label(page, (r.x0, r.y0, r.x1, r.y1))
            fields.append(Field(
                id=str(uuid.uuid4()),
                page=pno,
                field_name=(w.field_name or None),
                field_type=_widget_type(w),
                bbox=[float(r.x0), float(r.y0), float(r.x1), float(r.y1)],
                label=(label.strip() if label else None),
            ))
    doc.close()
    return fields

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, help="Path to the job application PDF")
    ap.add_argument("--out", required=True, help="Output JSON path for fields")
    args = ap.parse_args()

    fields = extract_fields(args.pdf)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump([asdict(x) for x in fields], f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(fields)} fields to {args.out}")

if __name__ == "__main__":
    main()
