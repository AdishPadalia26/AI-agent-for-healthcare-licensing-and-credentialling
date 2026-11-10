"""HTTP API."""
from __future__ import annotations

import collections
import io
import re
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request, send_file
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from credentialing.fields import describe
from credentialing.fill import fill_pdf
from credentialing.pipeline import filled_values

from .auth import admin_required, is_admin, login_required, services
from .models import TERMINAL_STATUSES, Job, User
from .storage import user_prefix

bp = Blueprint("api", __name__)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_INTERNAL_RECORD_KEYS = ("kv_raw", "full_text", "tables")


@bp.get("/")
def home():
    return jsonify({"message": "Welcome to HealthHackathon 2025 API", "status": "running"})


@bp.get("/api/health")
def health_check():
    return jsonify({"status": "healthy", "service": "backend"})


@bp.post("/api/example")
def example_post():
    return jsonify({"message": "Data received", "received": request.get_json(silent=True)})


# --- Accounts -------------------------------------------------------------------------------


@bp.post("/api/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not _EMAIL.fullmatch(email):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400
    with services().session() as session:
        if session.scalars(select(User).where(User.email == email)).first():
            return jsonify(error="An account with this email already exists."), 409
        session.add(User(email=email, name=str(data.get("name", ""))[:200] or None, password_hash=generate_password_hash(password)))
    return jsonify(email=email), 201


@bp.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    throttle = current_app.extensions["login_throttle"]
    if throttle.blocked(email):
        return jsonify(error="Too many attempts. Try again in a few minutes."), 429
    with services().session() as session:
        user = session.scalars(select(User).where(User.email == email)).first()
        valid = bool(user and user.password_hash and check_password_hash(user.password_hash, str(data.get("password", ""))))
        name = user.name if user else None
    if not valid:
        throttle.record_failure(email)
        return jsonify(error="Invalid email or password."), 401
    throttle.clear(email)
    return jsonify(email=email, name=name)


@bp.get("/api/me")
@login_required
def me():
    return jsonify(
        email=g.email,
        is_admin=is_admin(g.email),
        upload_prefix=user_prefix(g.email),
        storage_backend=services().settings.storage_backend,
    )


# --- Local uploads (S3 mode uses the presigned Next.js route instead) ------------------------


@bp.put("/api/uploads/local")
@login_required
def upload_local():
    svc = services()
    if svc.settings.storage_backend != "local":
        return jsonify(error="Local uploads are disabled"), 404
    key = request.args.get("key", "")
    if not key.startswith(user_prefix(g.email)):
        return jsonify(error="Forbidden"), 403
    data = request.get_data(cache=False)
    if len(data) > svc.settings.max_upload_bytes:
        return jsonify(error="File is too large."), 413
    try:
        svc.storage.put(key, data, request.content_type or "application/octet-stream")
    except ValueError:
        return jsonify(error="Forbidden"), 403
    return "", 204


# --- Jobs ------------------------------------------------------------------------------------


def _counts(job: Job) -> dict[str, int]:
    return dict(collections.Counter(item["band"] for item in job.fields or []))


def _summary(job: Job) -> dict[str, Any]:
    counts = _counts(job)
    filled = counts.get("auto_fill", 0) + counts.get("reviewed", 0)
    open_items = counts.get("needs_review", 0)
    return {
        "id": job.id,
        "cv_name": job.cv_name,
        "form_name": job.form_name,
        "status": job.status,
        "review_status": job.review_status,
        "review_note": job.review_note,
        "error": job.error,
        "counts": counts,
        "progress": round(100 * filled / (filled + open_items)) if filled + open_items else 0,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def _detail(job: Job) -> dict[str, Any]:
    record = {k: v for k, v in (job.record or {}).items() if k not in _INTERNAL_RECORD_KEYS}
    return {**_summary(job), "warnings": job.warnings or [], "fields": job.fields or [], "provider": record}


def _owned(session, job_id: str) -> Job | None:
    job = session.get(Job, job_id)
    return job if job and job.user_id == g.user_id else None


@bp.post("/api/jobs")
@login_required
def create_job():
    data = request.get_json(silent=True) or {}
    cv_key, form_key = str(data.get("cv_key", "")), str(data.get("form_key", ""))
    prefix = user_prefix(g.email)
    if not (cv_key.startswith(prefix) and form_key.startswith(prefix)):
        return jsonify(error="Files must belong to the current user."), 403
    if not form_key.lower().endswith(".pdf"):
        return jsonify(error="The form must be a fillable PDF."), 400
    svc = services()
    if not (svc.storage.exists(cv_key) and svc.storage.exists(form_key)):
        return jsonify(error="Uploaded file not found."), 400
    with svc.session() as session:
        job = Job(
            user_id=g.user_id, cv_key=cv_key, form_key=form_key,
            cv_name=str(data.get("cv_name", "CV"))[:300], form_name=str(data.get("form_name", "Form"))[:300],
        )
        session.add(job)
        session.flush()
        job_id = job.id
        svc.audit(session, g.email, "job_created", job_id)
    svc.submit(job_id)
    return jsonify(id=job_id), 201


@bp.get("/api/jobs")
@login_required
def list_jobs():
    with services().session() as session:
        jobs = session.scalars(select(Job).where(Job.user_id == g.user_id).order_by(Job.created_at.desc())).all()
        return jsonify(jobs=[_summary(job) for job in jobs])


@bp.get("/api/jobs/<job_id>")
@login_required
def get_job(job_id: str):
    with services().session() as session:
        job = _owned(session, job_id)
        return jsonify(_detail(job)) if job else (jsonify(error="Not found"), 404)


@bp.patch("/api/jobs/<job_id>/fields")
@login_required
def update_fields(job_id: str):
    edits = {str(e.get("id")): e for e in (request.get_json(silent=True) or {}).get("fields", []) if isinstance(e, dict)}
    svc = services()
    with svc.session() as session:
        job = _owned(session, job_id)
        if not job:
            return jsonify(error="Not found"), 404
        if job.status not in ("needs_review", "completed") or job.review_status == "approved":
            return jsonify(error="This application can no longer be edited."), 409
        updated = []
        for item in job.fields:
            edit = edits.get(item["id"])
            if edit is not None:
                value = edit.get("value")
                value = value.strip() if isinstance(value, str) else value
                item = {**item, "value": value or None, "band": "reviewed" if value else "blank"}
            updated.append(item)
        job.fields = updated
        svc.audit(session, g.email, "fields_reviewed", job_id)
        return jsonify(_detail(job))


@bp.post("/api/jobs/<job_id>/finalize")
@login_required
def finalize(job_id: str):
    svc = services()
    with svc.session() as session:
        job = _owned(session, job_id)
        if not job:
            return jsonify(error="Not found"), 404
        if job.status not in ("needs_review", "completed") or job.review_status == "approved":
            return jsonify(error="This application can no longer be edited."), 409
        pdf, report = fill_pdf(svc.storage.get(job.form_key), filled_values(job.fields, include_review=False))
        svc.storage.put(job.filled_key, pdf)
        for item in job.fields:
            if item["band"] == "reviewed" and item.get("chosen_key") and describe(item):
                svc.store.add_confirmed(describe(item), item["chosen_key"])
        job.status, job.review_status = "completed", "pending"
        svc.audit(session, g.email, "job_finalized", job_id)
        return jsonify({**_detail(job), "written": report.written, "fill_errors": report.errors})


def _send_pdf(job: Job):
    response = send_file(
        io.BytesIO(services().storage.get(job.filled_key)),
        mimetype="application/pdf",
        as_attachment=request.args.get("download") == "1",
        download_name="filled_form.pdf",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/api/jobs/<job_id>/pdf")
@login_required
def job_pdf(job_id: str):
    with services().session() as session:
        job = _owned(session, job_id)
        if not job or not job.filled_key:
            return jsonify(error="Not found"), 404
        services().audit(session, g.email, "pdf_accessed", job_id)
        return _send_pdf(job)


@bp.delete("/api/jobs/<job_id>")
@login_required
def delete_job(job_id: str):
    svc = services()
    with svc.session() as session:
        job = _owned(session, job_id)
        if not job:
            return jsonify(error="Not found"), 404
        if job.status not in TERMINAL_STATUSES:
            return jsonify(error="Wait for processing to finish."), 409
        for key in filter(None, (job.cv_key, job.form_key, job.filled_key)):
            svc.storage.delete(key)
        svc.store.purge_job(job_id)
        session.delete(job)
        svc.audit(session, g.email, "job_deleted", job_id)
    return "", 204


# --- Admin -----------------------------------------------------------------------------------


@bp.get("/api/admin/jobs")
@admin_required
def admin_jobs():
    with services().session() as session:
        jobs = session.scalars(select(Job).where(Job.status == "completed").order_by(Job.updated_at.desc())).all()
        return jsonify(jobs=[{**_summary(j), "applicant": j.user.name or j.user.email, "email": j.user.email} for j in jobs])


@bp.get("/api/admin/jobs/<job_id>/pdf")
@admin_required
def admin_pdf(job_id: str):
    with services().session() as session:
        job = session.get(Job, job_id)
        if not job or not job.filled_key:
            return jsonify(error="Not found"), 404
        services().audit(session, g.email, "pdf_accessed_admin", job_id)
        return _send_pdf(job)


@bp.post("/api/admin/jobs/<job_id>/decision")
@admin_required
def admin_decision(job_id: str):
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    if decision not in ("approved", "rejected"):
        return jsonify(error="Decision must be approved or rejected."), 400
    svc = services()
    with svc.session() as session:
        job = session.get(Job, job_id)
        if not job or job.status != "completed":
            return jsonify(error="Not found"), 404
        job.review_status, job.review_note = decision, str(data.get("note", ""))[:1000] or None
        svc.audit(session, g.email, f"job_{decision}", job_id)
        return jsonify(_summary(job))
