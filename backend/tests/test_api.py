"""API tests use the real Flask app, SQLite, and PDF pipeline with local providers."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import jwt
import pymupdf
import pytest
from sqlalchemy import text

from api import create_app
from api.auth import AUDIENCE, ISSUER
from api.storage import LocalStorage, user_prefix
from credentialing.llm import LocalProvider
from credentialing.ocr import LocalPdfOcr
from credentialing.retrieval import InMemoryStore

SECRET = "test-secret-test-secret-test-secret-1"


def token(email, secret=SECRET, minutes=5):
    claims = {"sub": email, "aud": AUDIENCE, "iss": ISSUER, "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes)}
    return {"Authorization": f"Bearer {jwt.encode(claims, secret, algorithm='HS256')}"}


@pytest.fixture()
def app(settings, tmp_path):
    configured = replace(
        settings, jwt_secret=SECRET, database_url="sqlite:///:memory:", data_dir=tmp_path,
        storage_backend="local", admin_emails=("admin@example.com",),
    )
    llm = LocalProvider()
    return create_app(
        configured, storage=LocalStorage(tmp_path / "objects"), llm=llm, ocr=LocalPdfOcr(),
        store=InMemoryStore(llm.embed), synchronous=True,
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def upload(client, email, name, data):
    key = f"{user_prefix(email)}abc/{name}"
    response = client.put(f"/api/uploads/local?key={key}", data=data, headers=token(email))
    assert response.status_code == 204
    return key


def make_job(client, form_bytes, cv_bytes, email="a@example.com"):
    body = {"cv_key": upload(client, email, "cv.pdf", cv_bytes), "form_key": upload(client, email, "form.pdf", form_bytes)}
    response = client.post("/api/jobs", json=body, headers=token(email))
    assert response.status_code == 201, response.json
    return response.json["id"]


def test_readme_endpoints_work(client):
    assert client.get("/api/health").json == {"status": "healthy", "service": "backend"}
    assert client.get("/").json["status"] == "running"
    assert client.post("/api/example", json={"a": 1}).json["received"] == {"a": 1}


def test_app_boots_with_only_readme_env_and_protects_routes(settings, tmp_path):
    bare = create_app(replace(settings, jwt_secret=None, database_url="sqlite:///:memory:", data_dir=tmp_path)).test_client()
    assert bare.get("/api/health").status_code == 200
    assert bare.get("/api/jobs").status_code == 503


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer junk"}])
def test_requires_valid_token(client, headers):
    assert client.get("/api/jobs", headers=headers).status_code == 401


def test_rejects_wrong_secret_and_expired(client):
    assert client.get("/api/jobs", headers=token("a@example.com", secret="x" * 40)).status_code == 401
    assert client.get("/api/jobs", headers=token("a@example.com", minutes=-1)).status_code == 401


def test_signup_login_flow(client):
    body = {"email": "New@Example.com", "password": "correct-horse", "name": "N"}
    assert client.post("/api/auth/signup", json=body).status_code == 201
    assert client.post("/api/auth/signup", json=body).status_code == 409
    assert client.post("/api/auth/login", json=body).json["email"] == "new@example.com"
    assert client.post("/api/auth/login", json={**body, "password": "wrongwrong"}).status_code == 401


def test_short_password_rejected(client):
    assert client.post("/api/auth/signup", json={"email": "a@b.co", "password": "short"}).status_code == 400


def test_login_throttled(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "x@y.co", "password": "bad-password"})
    assert client.post("/api/auth/login", json={"email": "x@y.co", "password": "bad-password"}).status_code == 429


def test_cannot_upload_or_reference_other_users_files(client, form_bytes):
    other = f"{user_prefix('victim@example.com')}x/form.pdf"
    assert client.put(f"/api/uploads/local?key={other}", data=b"x", headers=token("a@example.com")).status_code == 403
    assert client.post("/api/jobs", json={"cv_key": other, "form_key": other}, headers=token("a@example.com")).status_code == 403


def test_path_traversal_rejected(client):
    key = f"{user_prefix('a@example.com')}../../../../evil.pdf"
    assert client.put(f"/api/uploads/local?key={key}", data=b"x", headers=token("a@example.com")).status_code == 403


def test_full_lifecycle(client, form_bytes, cv_bytes):
    headers = token("a@example.com")
    job_id = make_job(client, form_bytes, cv_bytes)
    job = client.get(f"/api/jobs/{job_id}", headers=headers).json
    assert job["status"] in ("needs_review", "completed")
    assert len(job["fields"]) == 418
    assert "full_text" not in job["provider"]

    target = next(f for f in job["fields"] if f["field_name"] == "Specialty")
    patched = client.patch(f"/api/jobs/{job_id}/fields", json={"fields": [{"id": target["id"], "value": "Neurology"}]}, headers=headers)
    assert next(f for f in patched.json["fields"] if f["id"] == target["id"])["band"] == "reviewed"

    done = client.post(f"/api/jobs/{job_id}/finalize", headers=headers)
    assert done.status_code == 200 and done.json["status"] == "completed"

    pdf = client.get(f"/api/jobs/{job_id}/pdf?download=1", headers=headers)
    assert pdf.mimetype == "application/pdf" and pdf.headers["Cache-Control"] == "no-store"
    assert "attachment" in pdf.headers["Content-Disposition"]
    doc = pymupdf.open(stream=pdf.data, filetype="pdf")
    assert {w.field_name: w.field_value for p in doc for w in (p.widgets() or [])}["Specialty"] == "Neurology"
    doc.close()

    assert client.get("/api/jobs", headers=headers).json["jobs"][0]["id"] == job_id


def test_other_user_gets_404(client, form_bytes, cv_bytes):
    job_id = make_job(client, form_bytes, cv_bytes)
    intruder = token("b@example.com")
    assert client.get(f"/api/jobs/{job_id}", headers=intruder).status_code == 404
    assert client.get(f"/api/jobs/{job_id}/pdf", headers=intruder).status_code == 404
    assert client.delete(f"/api/jobs/{job_id}", headers=intruder).status_code == 404


def test_admin_requires_role_and_decides(client, form_bytes, cv_bytes):
    job_id = make_job(client, form_bytes, cv_bytes)
    owner = token("a@example.com")
    admin = token("admin@example.com")
    client.post(f"/api/jobs/{job_id}/finalize", headers=owner)
    assert client.get("/api/admin/jobs", headers=owner).status_code == 403
    assert client.get("/api/admin/jobs", headers=admin).json["jobs"][0]["id"] == job_id
    assert client.post(f"/api/admin/jobs/{job_id}/decision", json={"decision": "maybe"}, headers=admin).status_code == 400
    assert client.post(f"/api/admin/jobs/{job_id}/decision", json={"decision": "approved"}, headers=admin).json["review_status"] == "approved"
    assert client.post(f"/api/jobs/{job_id}/finalize", headers=owner).status_code == 409


def test_form_without_widgets_fails_job_cleanly(client, cv_bytes):
    job_id = make_job(client, cv_bytes, cv_bytes)
    job = client.get(f"/api/jobs/{job_id}", headers=token("a@example.com")).json
    assert job["status"] == "failed" and "fillable" in job["error"]


def test_provider_data_encrypted_at_rest(app, client, form_bytes, cv_bytes):
    job_id = make_job(client, form_bytes, cv_bytes)
    services = app.extensions["services"]
    with services.session() as session:
        raw = session.execute(text("select record, fields from jobs where id=:i"), {"i": job_id}).one()
    assert raw[0].startswith("gAAAA") and raw[1].startswith("gAAAA")


def test_correction_feeds_future_mapping(app, client, form_bytes, cv_bytes):
    headers = token("a@example.com")
    first = make_job(client, form_bytes, cv_bytes)
    job = client.get(f"/api/jobs/{first}", headers=headers).json
    target = next(f for f in job["fields"] if f["field_name"] == "Citizenship")
    client.patch(f"/api/jobs/{first}/fields", json={"fields": [{"id": target["id"], "value": "X"}]}, headers=headers)
    client.post(f"/api/jobs/{first}/finalize", headers=headers)
    assert client.delete(f"/api/jobs/{first}", headers=headers).status_code == 204
    assert client.get(f"/api/jobs/{first}", headers=headers).status_code == 404
