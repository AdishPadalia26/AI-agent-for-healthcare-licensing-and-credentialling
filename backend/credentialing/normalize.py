"""Deterministic value formatting. Never invents information absent from the source."""
from __future__ import annotations

import re
from datetime import datetime

from dateutil import parser as dateparse

from .validators import digits

_CREDENTIALS = {
    "md", "do", "phd", "mbbs", "mbchb", "dnp", "np", "pa", "pa-c", "rn", "dds", "dmd", "facp",
    "faan", "facs", "facc", "faap", "mph", "ms", "mba", "jr", "sr", "ii", "iii", "iv",
}
_PREFIXES = {"dr", "mr", "mrs", "ms", "mx", "prof", "doctor"}
_MONTH_YEAR = re.compile(r"^(\d{1,2})[/-](\d{4})$")
_YEAR = re.compile(r"^(19|20)\d{2}$")

_LEAF_KINDS = (
    (re.compile(r"(^|_)ssn$"), "ssn"),
    (re.compile(r"(phone|fax|mobile|cell)$"), "phone"),
    (re.compile(r"(date|date_of_birth|dob)$"), "date"),
)
_TEXT_KINDS = (
    (re.compile(r"\b(ssn|social\s*security)\b"), "ssn"),
    (re.compile(r"\b(first\s*name|given\s*name)\b"), "first_name"),
    (re.compile(r"\b(last\s*name|surname|family\s*name)\b"), "last_name"),
    (re.compile(r"\bmiddle\s*(name|initial)\b"), "middle_name"),
    (re.compile(r"\bplace\s*of\s*birth\b"), "plain"),
    (re.compile(r"\b(phone|telephone|tel|mobile|cell|fax|beeper)\b"), "phone"),
    (re.compile(r"\b(date|dob|birth\s*date|expires?|expiration|issued)\b"), "date"),
)


def value_kind(descriptor: str | None, key: str | None = None) -> str:
    """Decide the format from what the form asks, then from the provider key."""
    text = (descriptor or "").lower()
    for pattern, kind in _TEXT_KINDS:
        if pattern.search(text):
            return kind
    leaf = re.sub(r"\[\d+\]", "", (key or "").rsplit(".", 1)[-1]).lower()
    for pattern, kind in _LEAF_KINDS:
        if pattern.search(leaf):
            return kind
    return "plain"


def normalize_date(text: str) -> str:
    """Format as MM/DD/YYYY, keeping the source's precision.

    `2019` stays `2019` and `06/2008` stays `06/2008`: padding a missing month or
    day would put a date on a credentialing form that the provider never gave.
    """
    value = text.strip()
    if _YEAR.match(value):
        return value
    match = _MONTH_YEAR.match(value)
    if match:
        return f"{int(match.group(1)):02d}/{match.group(2)}"
    try:
        first = dateparse.parse(value, default=datetime(2001, 1, 1))
        second = dateparse.parse(value, default=datetime(2002, 2, 2))
    except (ValueError, OverflowError, TypeError):
        return value
    if first.year != second.year:
        return value
    if first.month != second.month:
        return f"{first.year}"
    if first.day != second.day:
        return f"{first.month:02d}/{first.year}"
    return first.strftime("%m/%d/%Y")


def split_name(full_name: str) -> dict[str, str]:
    """Split a person name, handling `Last, First`, titles, and credentials."""
    pieces = [p.strip() for p in full_name.split(",") if p.strip()]
    while len(pieces) > 1 and all(t.strip(".").lower() in _CREDENTIALS for t in pieces[-1].split()):
        pieces.pop()
    last_first = len(pieces) == 2
    source = f"{pieces[1]} {pieces[0]}" if last_first else " ".join(pieces)
    tokens = source.split()
    while tokens and tokens[0].strip(".").lower() in _PREFIXES:
        tokens.pop(0)
    while len(tokens) > 1 and tokens[-1].strip(".").lower() in _CREDENTIALS:
        tokens.pop()
    if not tokens:
        return {"first": "", "middle": "", "last": ""}
    if len(tokens) == 1:
        return {"first": tokens[0], "middle": "", "last": ""}
    return {"first": tokens[0], "middle": " ".join(tokens[1:-1]), "last": tokens[-1]}


def normalize_value(descriptor: str | None, value: object, key: str | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value).strip()
    kind = value_kind(descriptor, key)
    if kind == "ssn":
        number = digits(text)
        return f"{number[:3]}-{number[3:5]}-{number[5:]}" if len(number) == 9 else text
    if kind == "phone":
        number = digits(text)
        if len(number) == 11 and number[0] == "1":
            number = number[1:]
        return f"({number[:3]}) {number[3:6]}-{number[6:]}" if len(number) == 10 else text
    if kind == "date":
        return normalize_date(text)
    if kind == "first_name":
        return split_name(text)["first"]
    if kind == "last_name":
        return split_name(text)["last"]
    if kind == "middle_name":
        return split_name(text)["middle"]
    return text
