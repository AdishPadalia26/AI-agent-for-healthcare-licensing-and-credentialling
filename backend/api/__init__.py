"""Flask application factory."""
from __future__ import annotations

import secrets
from typing import Any

from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from credentialing.config import Settings, get_settings

from .auth import LoginThrottle
from .models import Base, configure_encryption
from .routes import bp
from .services import Services
from .storage import build_storage


def create_app(settings: Settings | None = None, **service_overrides: Any) -> Flask:
    settings = settings or get_settings()
    if settings.database_url.startswith("sqlite:///") and settings.database_url != "sqlite:///:memory:":
        settings.data_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes + 1024
    CORS(app, origins=list(settings.cors_origins))

    # Without a key, nothing protected is reachable, so a per-process key is enough.
    configure_encryption(settings.data_encryption_key or settings.jwt_secret or secrets.token_hex(32))

    engine_args: dict[str, Any] = {}
    if settings.database_url.startswith("sqlite"):
        engine_args["connect_args"] = {"check_same_thread": False}
        if settings.database_url == "sqlite:///:memory:":
            engine_args["poolclass"] = StaticPool
    engine = create_engine(settings.database_url, **engine_args)
    Base.metadata.create_all(engine)

    services = Services(
        settings,
        sessionmaker(engine, expire_on_commit=False),
        service_overrides.pop("storage", None) or build_storage(settings),
        **service_overrides,
    )
    services.fail_interrupted_jobs()
    app.extensions["services"] = services
    app.extensions["login_throttle"] = LoginThrottle()
    app.register_blueprint(bp)

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="File is too large."), 413

    return app
