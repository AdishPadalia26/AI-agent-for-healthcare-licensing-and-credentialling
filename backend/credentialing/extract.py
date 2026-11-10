"""Hybrid provider extraction: LLM reading plus OCR evidence, reconciled field by field."""
from __future__ import annotations

import re
from typing import Any, Callable

from .llm import LLMError, LLMProvider
from .ocr import OcrResult
from .schema import coerce_record
from .validators import DOB_RE, EMAIL_RE, NPI_RE, PHONE_RE, digits, is_dob, is_email, is_npi, is_phone


def _comparable(value: Any) -> str:
    text = str(value).lower()
    number = digits(text)
    return number if len(number) >= 7 else re.sub(r"[^a-z0-9]", "", text)


def reconcile(
    llm_value: Any, ocr_value: Any, validator: Callable[[Any], bool] | None = None
) -> tuple[Any, dict[str, Any]]:
    """Pick a value and score it from independent evidence, not a fixed constant per source."""

    def usable(value: Any) -> bool:
        if value is None or (isinstance(value, str) and not value.strip()):
            return False
        return validator(value) if validator else True

    llm_ok, ocr_ok = usable(llm_value), usable(ocr_value)
    if llm_ok and ocr_ok:
        if _comparable(llm_value) == _comparable(ocr_value):
            return llm_value, {"source": "llm+ocr", "confidence": 0.98, "status": "agreed"}
        return llm_value, {"source": "llm", "confidence": 0.55, "status": "conflict", "alternative": str(ocr_value)}
    if llm_ok:
        return llm_value, {"source": "llm", "confidence": 0.85 if validator else 0.75, "status": "llm_only"}
    if ocr_ok:
        return ocr_value, {"source": "ocr", "confidence": 0.75, "status": "ocr_only"}
    value = llm_value or ocr_value
    return value, {
        "source": "unknown",
        "confidence": 0.3 if value else 0.0,
        "status": "failed_validation" if value else "missing",
    }


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return (match.group(1) if match.groups() else match.group(0)) if match else None


def build_provider_record(ocr: OcrResult, llm: LLMProvider) -> dict[str, Any]:
    warnings = list(ocr.warnings)
    try:
        raw = llm.extract_provider(ocr.text)
    except LLMError as exc:
        warnings.append(f"LLM extraction failed, using OCR evidence only: {exc}")
        raw = {}
    record = coerce_record(raw)
    contact = record["contact_information"]

    kv = {re.sub(r"[^a-z0-9]+", " ", k.lower()).strip(): v for k, v in ocr.kv.items()}

    def lookup(*aliases: str) -> str | None:
        return next((kv[a] for a in aliases if kv.get(a)), None)

    text = ocr.text
    full_name, p_name = reconcile(record["full_name"], lookup("full name", "name", "provider name", "applicant name"))
    dob, p_dob = reconcile(record["date_of_birth"], lookup("date of birth", "dob") or _first(DOB_RE, text), is_dob)
    npi, p_npi = reconcile(record["npi"], lookup("npi", "npi number") or _first(NPI_RE, text), is_npi)
    email, p_email = reconcile(contact.get("email"), lookup("email", "e mail", "email address") or _first(EMAIL_RE, text), is_email)
    phone, p_phone = reconcile(contact.get("phone"), lookup("phone", "telephone", "mobile") or _first(PHONE_RE, text), is_phone)
    address, p_addr = reconcile(contact.get("address"), lookup("address", "home address", "mailing address"))

    record.update(
        full_name=full_name,
        date_of_birth=dob,
        npi=npi,
        contact_information={**contact, "address": address, "phone": phone, "email": email},
        _provenance={
            "full_name": p_name,
            "date_of_birth": p_dob,
            "npi": p_npi,
            "contact_information.email": p_email,
            "contact_information.phone": p_phone,
            "contact_information.address": p_addr,
            "llm_model": llm.name,
        },
        _warnings=warnings,
        kv_raw=ocr.kv,
        full_text=text,
        tables=ocr.tables,
    )
    return record
