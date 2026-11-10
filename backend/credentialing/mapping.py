"""Map form fields to provider keys through layered, explainable strategies.

Order: regex rules, neighbour anchoring, confirmed past mappings, LLM with retrieved
context, then fuzzy matching. Every result records which layer decided and why.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from rapidfuzz import fuzz

from .config import Settings
from .fields import describe
from .llm import LLMError, LLMProvider
from .normalize import normalize_value, value_kind
from .retrieval import NullStore, RetrievalStore
from .schema import mapping_candidates
from .validators import is_email, is_npi, is_phone, is_ssn

log = logging.getLogger(__name__)
LLM_BATCH = 50
FILLABLE = {"text", "checkbox", "radio", "combobox", "listbox"}
CONFIRMED_MIN_SIMILARITY = 0.8
FUZZY_MIN_SCORE = 85
_ANCHOR_REACH = 4  # Unmapped fields an anchor can span, e.g. address and phone in a block.

_RULE_CONFIDENCE, _ANCHOR_CONFIDENCE, _CONFIRMED_CONFIDENCE = 0.95, 0.85, 0.9
_LLM_CAP, _FUZZY_CAP = 0.9, 0.6


def _license_where(candidates: dict[str, Any], needle: str, leaf: str, attr: str = "state") -> str | None:
    for key, value in candidates.items():
        match = re.fullmatch(rf"licensure\[(\d+)\]\.{attr}", key)
        if match and re.search(needle, str(value), re.I):
            target = f"licensure[{match.group(1)}].{leaf}"
            if target in candidates:
                return target
    return None


def _first_present(candidates: dict[str, Any], *keys: str) -> str | None:
    return next((k for k in keys if k in candidates), None)


# (pattern on the field descriptor, resolver). Resolvers return a candidate key or None.
_RULES: list[tuple[re.Pattern[str], Any]] = [
    (re.compile(r"^(applicant |provider |practitioner )?(full )?name$", re.I), lambda c: _first_present(c, "full_name")),
    (re.compile(r"^(first|last|middle) name$", re.I), lambda c: _first_present(c, "full_name")),
    (re.compile(r"^e-?\s?mail( address)?$", re.I), lambda c: _first_present(c, "contact_information.email")),
    (re.compile(r"social security|^ssn\b", re.I), lambda c: _first_present(c, "ssn")),
    (re.compile(r"\bnpi\b|national provider", re.I), lambda c: _first_present(c, "npi")),
    (re.compile(r"place of birth", re.I), lambda c: _first_present(c, "place_of_birth")),
    (re.compile(r"date of birth|^dob$", re.I), lambda c: _first_present(c, "date_of_birth")),
    (re.compile(r"^gender$|^sex$", re.I), lambda c: _first_present(c, "gender")),
    (re.compile(r"^citizenship$", re.I), lambda c: _first_present(c, "citizenship")),
    (re.compile(r"local residence|home address|residence address", re.I), lambda c: _first_present(c, "contact_information.address")),
    (re.compile(r"(beeper|cell|mobile).*(number)?$", re.I), lambda c: _first_present(c, "contact_information.phone")),
    (re.compile(r"^specialty$", re.I), lambda c: _first_present(c, "board_certifications[0].specialty", "postgraduate_training[0].specialty")),
    (re.compile(r"^languages?", re.I), lambda c: _first_present(c, "languages_spoken")),
    (re.compile(r"texas medical licen[sc]e", re.I), lambda c: _license_where(c, r"^(tx|texas)$", "license_number")),
    (re.compile(r"\bdea\b", re.I), lambda c: _license_where(c, r"\bdea\b", "license_number", "type") or _first_present(c, "dea.number")),
    (re.compile(r"^ecfmg", re.I), lambda c: _first_present(c, "ecfmg_certification_number")),
    (re.compile(r"present carrier|current carrier", re.I), lambda c: _first_present(c, "professional_liability_insurance.carrier")),
]

# Generic labels whose meaning comes from the record entry the previous field used.
_ANCHOR_LEAVES: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (re.compile(r"date ?issued|issue date|date of certification|effective date", re.I), ("issue_date", "effective_start_date", "ecfmg_issue_date")),
    (re.compile(r"date ?expires|expiration date|expiry", re.I), ("expiration_date", "effective_end_date", "end_date")),
    (re.compile(r"^policy", re.I), ("policy_number",)),
]


def _combine_lists(candidates: dict[str, Any]) -> dict[str, Any]:
    """Expose simple string lists as one joined value, e.g. languages_spoken."""
    joined: dict[str, list[str]] = {}
    for key, value in candidates.items():
        match = re.fullmatch(r"([a-z_]+)\[\d+\]", key)
        if match and isinstance(value, str):
            joined.setdefault(match.group(1), []).append(value)
    return {**candidates, **{key: ", ".join(values) for key, values in joined.items()}}


def _humanize(key: str) -> str:
    return re.sub(r"\[\d+\]", " ", key).replace(".", " ").replace("_", " ").strip()


def fuzzy_match(descriptor: str, candidates: dict[str, Any]) -> tuple[str | None, float]:
    text = descriptor.lower().strip()
    if len(text) < 3:
        return None, 0.0
    best, best_score = None, 0.0
    for key in candidates:
        if "[" in key:  # Which list entry a generic label means is not a string-similarity question.
            continue
        leaf = _humanize(key.rsplit(".", 1)[-1])
        depth = key.count(".") + key.count("[")
        score = max(fuzz.ratio(text, leaf), fuzz.token_sort_ratio(text, _humanize(key))) - 2 * depth
        if score > best_score:
            best, best_score = key, score
    return (best, best_score) if best_score >= FUZZY_MIN_SCORE else (None, best_score)


def _value_check(kind: str, value: Any) -> bool | None:
    checks = {"phone": is_phone, "ssn": is_ssn}
    return checks[kind](value) if kind in checks else None


def _grounded(value: Any, full_text: str) -> bool:
    squash = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    needle = squash(value)
    return len(needle) >= 3 and needle in squash(full_text)


def score_field(
    layer_confidence: float, key: str, raw_value: Any, kind: str, record: dict[str, Any]
) -> tuple[float, list[str]]:
    """Combine how sure the mapping is with how much evidence backs the value."""
    score, reasons = layer_confidence, []
    provenance = (record.get("_provenance") or {}).get(key)
    if isinstance(provenance, dict):
        score *= provenance.get("confidence", 1.0)
        reasons.append(f"value evidence: {provenance.get('status')}")
    elif record.get("full_text"):
        if _grounded(raw_value, record["full_text"]):
            reasons.append("value found verbatim in source document")
        else:
            score *= 0.75
            reasons.append("value not found verbatim in source document")
    valid = _value_check(kind, raw_value)
    if valid is False:
        score *= 0.6
        reasons.append(f"value failed {kind} format check")
    if key == "npi" and not is_npi(raw_value):
        reasons.append("NPI failed checksum")
    if key.endswith("email") and not is_email(raw_value):
        score *= 0.6
    return round(score, 3), reasons


def band_for(score: float, has_value: bool, settings: Settings) -> str:
    if not has_value:
        return "blank"
    if score >= settings.auto_fill_threshold:
        return "auto_fill"
    return "needs_review" if score >= settings.review_threshold else "blank"


class Mapper:
    def __init__(self, llm: LLMProvider, settings: Settings, store: RetrievalStore | None = None):
        self._llm = llm
        self._settings = settings
        self._store = store or NullStore()
        self.warnings: list[str] = []

    def _rule(self, descriptor: str, candidates: dict[str, Any]) -> str | None:
        for pattern, resolve in _RULES:
            if pattern.search(descriptor):
                return resolve(candidates)
        return None

    def _anchor(self, descriptor: str, previous_key: str | None, candidates: dict[str, Any]) -> str | None:
        if not previous_key or "." not in previous_key and "[" not in previous_key:
            return None
        parent = previous_key.rsplit(".", 1)[0]
        for pattern, leaves in _ANCHOR_LEAVES:
            if pattern.search(descriptor):
                return next((f"{parent}.{leaf}" for leaf in leaves if f"{parent}.{leaf}" in candidates), None)
        return None

    def _confirmed(self, descriptor: str, candidates: dict[str, Any]) -> str | None:
        for hit in self._store.search_confirmed(descriptor, k=3):
            if hit.score >= CONFIRMED_MIN_SIMILARITY and hit.chosen_key in candidates:
                return hit.chosen_key
        return None

    def _ask_llm(self, pending: list[dict[str, Any]], candidates: dict[str, Any], job_id: str | None) -> dict[str, dict[str, Any]]:
        answers: dict[str, dict[str, Any]] = {}
        for start in range(0, len(pending), LLM_BATCH):
            batch = []
            for field in pending[start : start + LLM_BATCH]:
                descriptor = describe(field)
                query = " ".join(filter(None, [field.get("section"), descriptor, field.get("context")]))
                evidence = self._store.search_chunks(job_id, query, k=2) if job_id and query else []
                similar = self._store.search_confirmed(query, k=2) if query else []
                batch.append(
                    {
                        "id": field["id"],
                        "field_name": field.get("field_name"),
                        "label": field.get("label"),
                        "section": field.get("section"),
                        "context": field.get("context"),
                        "type": field.get("field_type"),
                        "retrieved_document_text": evidence,
                        "similar_confirmed_mappings": [
                            {"field": hit.descriptor, "key": hit.chosen_key} for hit in similar
                        ],
                    }
                )
            try:
                for item in self._llm.map_fields(batch, candidates):
                    if isinstance(item, dict) and item.get("id"):
                        answers[item["id"]] = item
            except LLMError as exc:
                self.warnings.append(f"LLM mapping failed for a batch, using fuzzy fallback: {exc}")
        return answers

    def map(self, fields: list[dict[str, Any]], record: dict[str, Any], job_id: str | None = None) -> list[dict[str, Any]]:
        candidates = _combine_lists(mapping_candidates(record))
        decisions: dict[str, tuple[str | None, float, str]] = {}
        pending: list[dict[str, Any]] = []
        previous_key: str | None = None
        previous_page, misses = None, 0

        for field in fields:
            if field.get("field_type") not in FILLABLE:
                decisions[field["id"]] = (None, 0.0, "unsupported")
                continue
            if field["page"] != previous_page or misses > _ANCHOR_REACH:
                previous_key, misses = None, 0
            previous_page = field["page"]
            descriptor = describe(field)
            key = self._rule(descriptor, candidates) if descriptor else None
            layer, confidence = "rule", _RULE_CONFIDENCE
            if key is None and descriptor:
                key = self._anchor(descriptor, previous_key, candidates)
                layer, confidence = "anchor", _ANCHOR_CONFIDENCE
            if key is None and descriptor:
                key = self._confirmed(descriptor, candidates)
                layer, confidence = "confirmed", _CONFIRMED_CONFIDENCE
            if key is None:
                pending.append(field)
                misses += 1
                continue
            decisions[field["id"]] = (key, confidence, layer)
            previous_key, misses = key, 0

        answers = self._ask_llm(pending, candidates, job_id) if pending else {}
        for field in pending:
            answer = answers.get(field["id"]) or {}
            key = answer.get("chosen_key")
            if key in candidates:
                try:
                    confidence = max(0.0, min(float(answer.get("confidence") or 0.0), 1.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                decisions[field["id"]] = (key, min(confidence, _LLM_CAP), "llm")
                continue
            key, score = fuzzy_match(describe(field), candidates)
            decisions[field["id"]] = (key, min(score / 100.0, _FUZZY_CAP), "fuzzy") if key else (None, 0.0, "none")

        return [self._result(field, decisions[field["id"]], candidates, record) for field in fields]

    def _result(self, field, decision, candidates, record) -> dict[str, Any]:
        key, layer_confidence, layer = decision
        descriptor = describe(field)
        raw = candidates.get(key) if key else None
        kind = value_kind(descriptor, key)
        confidence, reasons = score_field(layer_confidence, key, raw, kind, record) if key else (0.0, [])
        band = band_for(confidence, raw is not None, self._settings)
        keep = band != "blank"
        return {
            **field,
            "chosen_key": key if keep else None,
            "raw_value": raw if keep else None,
            "value": normalize_value(descriptor, raw, key) if keep else None,
            "confidence": confidence,
            "band": band,
            "layer": layer,
            "reasons": reasons,
        }
