"""Request authentication. Next.js mints a short-lived token per proxied request."""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable

import jwt
from flask import current_app, g, jsonify, request
from sqlalchemy import select

from .models import User

AUDIENCE = "credentialing-api"
ISSUER = "credentialing-web"
_MAX_FAILURES, _WINDOW_SECONDS = 5, 300


class LoginThrottle:
    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        cutoff = time.monotonic() - _WINDOW_SECONDS
        self._failures[key] = [t for t in self._failures[key] if t > cutoff]
        return self._failures[key]

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key)) >= _MAX_FAILURES

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._recent(key).append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


def services():
    return current_app.extensions["services"]


def is_admin(email: str) -> bool:
    return email.lower() in services().settings.admin_emails


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        secret = services().settings.jwt_secret
        if not secret:
            return jsonify(error="BACKEND_JWT_SECRET is not configured"), 503
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Authentication required"), 401
        try:
            claims = jwt.decode(
                header[7:], secret, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError:
            return jsonify(error="Invalid or expired token"), 401

        email = str(claims["sub"]).lower()
        with services().session() as session:
            user = session.scalars(select(User).where(User.email == email)).first()
            if user is None:
                user = User(email=email, name=claims.get("name"))
                session.add(user)
                session.flush()
            g.user_id, g.email = user.id, user.email
        return view(*args, **kwargs)

    return wrapper


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    @login_required
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not is_admin(g.email):
            return jsonify(error="Admin access required"), 403
        return view(*args, **kwargs)

    return wrapper
