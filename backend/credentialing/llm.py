"""LLM providers. Pipeline code depends only on the LLMProvider interface."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from typing import Any, Protocol

from .config import Settings
from .validators import DOB_RE, EMAIL_RE, NPI_RE, PHONE_RE, SSN_RE

SENSITIVE_KEYS = re.compile(r"(^|\.)(ssn|date_of_birth)$")
EMBEDDING_DIMS = 768

EXTRACT_PROMPT = """You are an expert information extractor for physician CVs.
Read the CV text and return structured data as valid JSON. Use null when the CV does not state
a value. Never guess. Copy identifiers exactly.

Fields: full_name, date_of_birth, place_of_birth, citizenship, gender, race, ethnicity, ssn,
marital_status, npi, ecfmg_certification_number, ecfmg_issue_date,
contact_information {address, phone, email},
address_history [{address, start_date, end_date}],
education [{degree, institution, location, start_date, end_date, graduation_year}],
postgraduate_training [{type, specialty, institution, start_date, end_date}],
licensure [{type, state, license_number, status, issue_date, expiration_date}],
board_certifications [{board, specialty, status, start_date, end_date}],
employment_history [{position, employer, location, start_date, end_date}],
hospital_privileges [{hospital, status, start_date, end_date}],
languages_spoken, clinical_interests, peer_review_notes,
peer_references [{name, position, institution, phone, email}],
professional_liability_insurance {carrier, policy_number, coverage_amount, effective_start_date, effective_end_date},
professional_concerns, has_malpractice_history, has_license_disciplinary_action,
has_criminal_history, has_military_service.

CV TEXT:
"""

MAP_PROMPT = """Match PDF form fields to provider record keys.
Rules:
- For each field choose exactly one key from "candidates", or null if none fits. Never invent keys.
- Use "section", "label", "field_name", and "context" together. Labels can be unreliable.
- Repeated sections map to successive list entries, e.g. education[0] then education[1].
- confidence is 0 to 1. Use below 0.5 if unsure.
Return JSON: {"mappings": [{"id": "<field id>", "chosen_key": "<key or null>", "confidence": 0.0}]}
"""


class LLMError(RuntimeError):
    """The provider failed after retries."""


class LLMProvider(Protocol):
    name: str

    def extract_provider(self, text: str) -> dict[str, Any]: ...

    def map_fields(
        self, fields: list[dict[str, Any]], candidates: dict[str, Any]
    ) -> list[dict[str, Any]]: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def parse_json(text: str) -> Any:
    cleaned = (text or "").strip().replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def redact_candidates(candidates: dict[str, Any]) -> list[dict[str, str]]:
    """Mapping needs the key and a sense of the value, not the identifiers themselves."""
    return [
        {"key": k, "value": "[redacted]" if SENSITIVE_KEYS.search(k) else str(v)[:120]}
        for k, v in candidates.items()
    ]


class GeminiProvider:
    def __init__(self, settings: Settings, client: Any = None, retries: int = 3):
        if client is None:
            if not settings.gemini_api_key:
                raise LLMError("GEMINI_API_KEY is not set")
            from google import genai

            client = genai.Client(api_key=settings.gemini_api_key)
        self._client = client
        self._retries = retries
        self.model = settings.gemini_model
        self.embedding_model = settings.gemini_embedding_model
        self.name = self.model

    def _with_retry(self, call):
        last: Exception | None = None
        for attempt in range(self._retries):
            try:
                return call()
            except Exception as exc:  # provider SDKs raise many transport types
                last = exc
                if attempt < self._retries - 1:
                    time.sleep(2**attempt)
        raise LLMError(f"Gemini request failed: {type(last).__name__}") from last

    def _json(self, prompt: str) -> Any:
        from google.genai import types

        def call():
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0
                ),
            )
            return parse_json(response.text)

        return self._with_retry(call)

    def extract_provider(self, text: str) -> dict[str, Any]:
        data = self._json(EXTRACT_PROMPT + text)
        return data if isinstance(data, dict) else {}

    def map_fields(self, fields, candidates):
        payload = json.dumps({"fields": fields, "candidates": redact_candidates(candidates)})
        data = self._json(MAP_PROMPT + payload)
        return data.get("mappings", []) if isinstance(data, dict) else []

    def embed(self, texts):
        from google.genai import types

        def call():
            response = self._client.models.embed_content(
                model=self.embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMS),
            )
            return [list(e.values) for e in response.embeddings]

        return self._with_retry(call)


class LocalProvider:
    """Offline mode for demos and tests: regex extraction, no generative mapping.

    It reads labelled values from digital text. It is not a substitute for Gemini,
    so unmatched fields are left for review rather than guessed.
    """

    name = "local-heuristic"

    def extract_provider(self, text: str) -> dict[str, Any]:
        def labelled(*labels: str) -> str | None:
            for label in labels:
                match = re.search(rf"{label}\s*[:\-]\s*(.+)", text, re.I)
                if match:
                    return match.group(1).strip()
            return None

        def found(pattern: re.Pattern[str]) -> str | None:
            match = pattern.search(text)
            return (match.group(1) if match.groups() else match.group(0)) if match else None

        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), None)
        return {
            "full_name": labelled("full name", "name") or first_line,
            "date_of_birth": found(DOB_RE),
            "place_of_birth": labelled("place of birth"),
            "citizenship": labelled("citizenship"),
            "gender": labelled("gender", "sex"),
            "ssn": found(SSN_RE),
            "npi": found(NPI_RE),
            "contact_information": {
                "address": labelled("home address", "address"),
                "phone": found(PHONE_RE),
                "email": found(EMAIL_RE),
            },
        }

    def map_fields(self, fields, candidates):
        return []

    def embed(self, texts):
        return [_hash_embedding(text) for text in texts]


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMS
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        index = int(hashlib.sha1(token.encode()).hexdigest(), 16) % EMBEDDING_DIMS
        vector[index] += 1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def build_llm(settings: Settings) -> LLMProvider:
    return LocalProvider() if settings.llm_provider == "local" else GeminiProvider(settings)
