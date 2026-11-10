"""Format validators. All accept any input type and return False rather than raise."""
from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)")
NPI_RE = re.compile(r"\bNPI[:\s#]*([0-9]{10})\b", re.I)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
DOB_RE = re.compile(
    r"(?:Date of Birth|DOB)[:\s]*"
    r"([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})",
    re.I,
)
_DOB_VALUE = re.compile(
    r"[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}", re.I
)


def _text(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (str, int)):
        return str(value).strip()
    return None


def digits(value: object) -> str:
    return re.sub(r"\D", "", _text(value) or "")


def is_email(value: object) -> bool:
    text = _text(value)
    return bool(text and EMAIL_RE.fullmatch(text))


def is_phone(value: object) -> bool:
    text = _text(value)
    if not text or not PHONE_RE.fullmatch(text):
        return False
    number = digits(text)
    return len(number) == 10 or (len(number) == 11 and number[0] == "1")


def is_npi(value: object) -> bool:
    """10 digits passing the CMS Luhn check, which prefixes 80840."""
    number = digits(value)
    text = _text(value) or ""
    if len(number) != 10 or number != re.sub(r"\s", "", text):
        return False
    total = 0
    for index, char in enumerate(reversed("80840" + number)):
        value_at = int(char)
        if index % 2 == 1:
            value_at *= 2
            if value_at > 9:
                value_at -= 9
        total += value_at
    return total % 10 == 0


def is_ssn(value: object) -> bool:
    text = _text(value)
    return bool(text and re.fullmatch(r"\d{3}-?\d{2}-?\d{4}", text))


def is_dob(value: object) -> bool:
    text = _text(value)
    return bool(text and _DOB_VALUE.fullmatch(text))
