"""Canonical provider record. Tolerant of the shapes LLMs actually return."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# Pipeline bookkeeping, excluded from anything that can be mapped into a form.
INTERNAL_KEYS = ("_provenance", "_warnings", "kv_raw", "full_text", "tables", "session_tag")
SCALARS = (
    "full_name", "date_of_birth", "place_of_birth", "citizenship", "gender", "race", "ethnicity",
    "ssn", "marital_status", "npi", "ecfmg_certification_number", "ecfmg_issue_date",
)
LISTS = (
    "address_history", "education", "postgraduate_training", "licensure", "board_certifications",
    "employment_history", "hospital_privileges", "languages_spoken", "clinical_interests",
    "peer_review_notes", "peer_references",
)


def _scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip() or None
    return None


class Contact(BaseModel):
    model_config = ConfigDict(extra="allow")
    address: Any = None
    phone: str | None = None
    email: str | None = None

    @field_validator("phone", "email", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return _scalar(value)


class ProviderRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    full_name: str | None = None
    date_of_birth: str | None = None
    place_of_birth: str | None = None
    citizenship: str | None = None
    gender: str | None = None
    race: str | None = None
    ethnicity: str | None = None
    ssn: str | None = None
    marital_status: str | None = None
    npi: str | None = None
    ecfmg_certification_number: str | None = None
    ecfmg_issue_date: str | None = None
    contact_information: Contact = Contact()
    address_history: list[Any] = []
    education: list[Any] = []
    postgraduate_training: list[Any] = []
    licensure: list[Any] = []
    board_certifications: list[Any] = []
    employment_history: list[Any] = []
    hospital_privileges: list[Any] = []
    languages_spoken: list[Any] = []
    clinical_interests: list[Any] = []
    peer_review_notes: list[Any] = []
    peer_references: list[Any] = []
    professional_liability_insurance: Any = None
    professional_concerns: Any = None

    @field_validator(*SCALARS, mode="before")
    @classmethod
    def _coerce_scalar(cls, value: Any) -> Any:
        return _scalar(value)

    @field_validator("contact_information", mode="before")
    @classmethod
    def _coerce_contact(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"address": value}
        return value if isinstance(value, dict) else {}

    @field_validator(*LISTS, mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        return value if isinstance(value, list) else [value]


def coerce_record(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return a plain dict in canonical shape from arbitrary LLM or JSON input."""
    return ProviderRecord.model_validate(raw if isinstance(raw, dict) else {}).model_dump()


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    items: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            items.update(flatten(child, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.update(flatten(child, f"{prefix}[{index}]"))
    else:
        items[prefix] = value
    return items


def mapping_candidates(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten to fillable keys only: no bookkeeping, no empty values."""
    usable = {k: v for k, v in record.items() if k not in INTERNAL_KEYS}
    return {
        key: value
        for key, value in flatten(usable).items()
        if value is not None and not (isinstance(value, str) and not value.strip())
    }
