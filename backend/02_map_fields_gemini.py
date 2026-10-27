#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Map PDF fields to resume JSON keys using Gemini and produce mapped_fields.json

Input:
  fields.json from step 1
  output.json (your resume extraction)

Output schema (mapped_fields.json): List[{
  "id": str,
  "page": int,
  "field_name": str | null,
  "field_type": str,
  "bbox": [x0,y0,x1,y1],
  "label": str | null,
  "chosen_key": str | null,
  "raw_value": str | null,
  "value": str | null,          # normalized for common patterns (phone, ssn, dates)
  "confidence": float           # 0..1 from LLM (approx)
}]
"""
import os, json, argparse, re
from datetime import datetime
from rapidfuzz import fuzz, process
from dateutil import parser as dateparse

import google.generativeai as genai

def flatten_dict(d, parent_key=""):
    items = {}
    if isinstance(d, dict):
        for k, v in d.items():
            nk = f"{parent_key}.{k}" if parent_key else k
            items.update(flatten_dict(v, nk))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            nk = f"{parent_key}[{i}]"
            items.update(flatten_dict(v, nk))
    else:
        items[parent_key] = d
    return items

def normalize_value(label, value):
    if value is None:
        return None
    s = str(value).strip()

    # SSN formats
    if re.search(r"\b(ssn|social\s*security)\b", (label or "").lower()):
        digits = re.sub(r"\D", "", s)
        if len(digits) == 9:
            return f"{digits[0:3]}-{digits[3:5]}-{digits[5:9]}"
        return s

    # Phone formats
    if re.search(r"\b(phone|mobile|cell|tel)\b", (label or "").lower()):
        digits = re.sub(r"\D", "", s)
        if len(digits) == 10:
            return f"({digits[0:3]}) {digits[3:6]}-{digits[6:]}"
        return s

    # Date formats -> MM/DD/YYYY if likely a date
    if re.search(r"\b(date|dob|birth)\b", (label or "").lower()):
        try:
            dt = dateparse.parse(s, dayfirst=False, yearfirst=True, fuzzy=True)
            return dt.strftime("%m/%d/%Y")
        except Exception:
            return s

    # Name splits if the form asks for specific part
    if "last name" in (label or "").lower():
        parts = re.split(r",\s*|\s+", s)
        # If "Lastname, First ..." style
        if "," in s:
            return parts[0]
        return parts[-1] if parts else s
    if "first name" in (label or "").lower():
        parts = re.split(r",\s*|\s+", s)
        if "," in s and len(parts) > 1:
            return parts[1]
        return parts[0] if parts else s
    if "middle" in (label or "").lower():
        parts = re.split(r",\s*|\s+", s)
        core = parts[0] if "," in s else s
        mids = core.split()
        if len(mids) > 2:
            return " ".join(mids[1:-1])
        return ""

    return s

def local_fallback(label, candidates):
    # Simple fuzzy fallback if API fails
    name = (label or "").lower()
    if not name:
        return None, None, 0.0
    keys = list(candidates.keys())
    best, score, _ = process.extractOne(
        name,
        keys,
        scorer=fuzz.token_set_ratio
    ) if keys else (None, 0, None)
    if best and score >= 75:
        return best, candidates[best], min(0.75, score / 100.0)
    return None, None, 0.0

def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

PROMPT = """You are matching PDF form field labels to keys from a resume JSON.
Rules:
- For each field, choose EXACTLY ONE key from candidates that best matches the field's meaning, or null if none is appropriate.
- Output ONLY JSON. Do not invent values; use the provided candidate values.
- Prefer contextually correct keys (e.g., "SSN" -> "ssn", "NPI" -> "npi", "DOB" -> "date_of_birth", "Citizenship" -> "citizenship").
- For address-related fields, prefer the most specific candidate (e.g., "contact_information.address" for street address).
- If label requests "First Name"/"Last Name" but only "full_name" exists, still map to "full_name" (we will split later).
Response JSON schema:
{
  "mappings": [
    { "id": "<field.id>", "chosen_key": "<candidate-key-or-null>", "value": "<the candidate value or null>", "confidence": 0.0-1.0 }
  ]
}
"""

def call_gemini(model, fields_batch, candidates):
    # Build compact candidates list to control token size
    # Use only stringified values
    cand_items = [{"key": k, "value": str(v)} for k, v in candidates.items()]

    request = {
        "fields": [{"id": f["id"],
                    "label": f.get("label"),
                    "field_name": f.get("field_name"),
                    "type": f.get("field_type")}
                   for f in fields_batch],
        "candidates": cand_items
    }

    res = model.generate_content(
        contents=[
            {"role": "user", "parts": [{"text": PROMPT}]},
            {"role": "user", "parts": [{"text": json.dumps(request, ensure_ascii=False)}]},
        ],
        generation_config={"response_mime_type": "application/json"},
    )
    text = res.text or "{}"
    try:
        data = json.loads(text)
        return data.get("mappings", [])
    except Exception:
        return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fields", required=True, help="fields.json from step 1")
    ap.add_argument("--resume", required=True, help="output.json (resume data)")
    ap.add_argument("--out", required=True, help="Output mapped_fields.json")
    ap.add_argument("--api-key", default=os.getenv("GOOGLE_API_KEY", "xxxxxx"))
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--min-confidence", type=float, default=0.50,
                    help="Values under this confidence become null")
    args = ap.parse_args()

    with open(args.fields, "r", encoding="utf-8") as f:
        fields = json.load(f)
    with open(args.resume, "r", encoding="utf-8") as f:
        resume = json.load(f)

    candidates = flatten_dict(resume)

    # Configure Gemini
    genai.configure(api_key=args.api_key)
    model = genai.GenerativeModel(args.model)

    mapped = []
    id_to_result = {}

    for batch in chunk(fields, 50):
        mappings = call_gemini(model, batch, candidates)
        # Index by id
        for m in mappings:
            id_to_result[m.get("id")] = {
                "chosen_key": m.get("chosen_key"),
                "raw_value": m.get("value"),
                "confidence": float(m.get("confidence") or 0.0)
            }

    # Fallback + normalization + thresholding
    for f in fields:
        mid = f["id"]
        result = id_to_result.get(mid)
        if not result:
            # Fallback if API missed it
            key, val, conf = local_fallback(f.get("label"), candidates)
            result = {"chosen_key": key, "raw_value": val, "confidence": conf}

        chosen_key = result["chosen_key"]
        raw_value = result["raw_value"]
        conf = float(result["confidence"])

        if not chosen_key or conf < args.min_confidence:
            chosen_key = None
            raw_value = None

        value = normalize_value(f.get("label"), raw_value) if raw_value is not None else None

        mapped.append({
            **f,
            "chosen_key": chosen_key,
            "raw_value": raw_value,
            "value": value,
            "confidence": round(conf, 3)
        })

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(mapped, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(mapped)} mapped fields → {args.out}")

if __name__ == "__main__":
    main()
