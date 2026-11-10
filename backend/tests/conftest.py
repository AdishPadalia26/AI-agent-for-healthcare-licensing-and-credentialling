from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("BACKEND_JWT_SECRET", "test-secret-test-secret-test-secret-1")

from credentialing.config import get_settings  # noqa: E402


@pytest.fixture(scope="session")
def form_bytes() -> bytes:
    return (REPO / "samples" / "forms" / "weehope_tx_application.pdf").read_bytes()


@pytest.fixture(scope="session")
def cv_bytes() -> bytes:
    return (REPO / "samples" / "cvs" / "generated_cv_1.pdf").read_bytes()


@pytest.fixture()
def record() -> dict:
    return json.loads((REPO / "samples" / "provider_records" / "synthetic_cv_3.json").read_text(encoding="utf-8"))


@pytest.fixture()
def settings():
    return replace(get_settings(), llm_provider="local", ocr_provider="local", elasticsearch_url=None)
