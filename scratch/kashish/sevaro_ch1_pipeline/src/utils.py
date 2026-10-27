
import re, json
from datetime import datetime
from typing import Dict, Optional

def find_first(pattern: str, text: str, flags=re.IGNORECASE|re.MULTILINE) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None

def find_all(pattern: str, text: str, flags=re.IGNORECASE|re.MULTILINE):
    return re.findall(pattern, text, flags)

def normalize_date_iso(s: str):
    if not s: return None
    s = s.strip()
    fmts = ["%m/%d/%Y","%m-%d-%Y","%Y-%m-%d","%B %d, %Y","%b %d, %Y","%m/%d/%y","%Y/%m/%d"]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except Exception:
            pass
    return s

def only_digits(s: str) -> str:
    return re.sub(r"\D","", s or "")

def to_mmddyyyy(iso_or_raw: str) -> str:
    if not iso_or_raw: return ""
    try:
        d = datetime.fromisoformat(iso_or_raw)
        return d.strftime("%m/%d/%Y")
    except Exception:
        return iso_or_raw
