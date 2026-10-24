"""Database-backed browser sessions and request-integrity checks."""

from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import os
import secrets
import time
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from pwdlib import PasswordHash
from sqlalchemy import delete
from sqlalchemy.orm import Session

from database import get_db
from models import AuthSession, User


SESSION_COOKIE = "motanafas_session"
SESSION_SECONDS = 12 * 60 * 60
password_hasher = PasswordHash.recommended()


@dataclass
class AuthContext:
    user: User
    session: AuthSession


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def allowed_origins() -> set[str]:
    configured = os.getenv("MOTANAFAS_ALLOWED_ORIGINS")
    if configured:
        return {origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()}
    return {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    }


async def verify_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").rstrip("/")
    if not origin or origin not in allowed_origins():
        raise HTTPException(status_code=403, detail="الطلب غير مسموح.")


async def optional_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext | None:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return None
    session = db.get(AuthSession, hash_secret(raw_token))
    if session is None:
        return None
    if session.expires_at <= time.time():
        db.delete(session)
        db.commit()
        return None
    user = db.get(User, session.user_id)
    if user is None:
        db.delete(session)
        db.commit()
        return None
    return AuthContext(user=user, session=session)


async def require_auth(context: AuthContext | None = Depends(optional_auth)) -> AuthContext:
    if context is None:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول للوصول إلى يومياتك.")
    return context


async def require_csrf(
    request: Request,
    context: AuthContext = Depends(require_auth),
) -> AuthContext:
    await verify_origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not secrets.compare_digest(supplied, context.session.csrf_token):
        raise HTTPException(status_code=403, detail="تعذر التحقق من الطلب. حدّث الصفحة وحاول مجدداً.")
    return context


def create_session(db: Session, user: User) -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    db.add(AuthSession(
        token_hash=hash_secret(raw_token),
        csrf_token=csrf_token,
        user_id=user.id,
        expires_at=time.time() + SESSION_SECONDS,
    ))
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= time.time()))
    db.commit()
    return raw_token, csrf_token


def set_session_cookie(response, raw_token: str) -> None:
    secure = _cookie_secure()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/api",
    )


def _cookie_secure() -> bool:
    configured = os.getenv("MOTANAFAS_COOKIE_SECURE")
    if configured is not None:
        return configured.lower() in {"1", "true", "yes"}
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    origins = allowed_origins()
    return not origins or any(urlparse(origin).hostname not in local_hosts for origin in origins)


_LOGIN_FAILURES: dict[str, deque[float]] = defaultdict(deque)
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_FAILURE_LIMIT = 5


def _login_key(email: str, client_host: str) -> str:
    return hash_secret(f"{email}\0{client_host}")


def check_login_limit(email: str, client_host: str) -> str:
    key = _login_key(email, client_host)
    now = time.time()
    failures = _LOGIN_FAILURES[key]
    while failures and failures[0] <= now - LOGIN_WINDOW_SECONDS:
        failures.popleft()
    if len(failures) >= LOGIN_FAILURE_LIMIT:
        raise HTTPException(status_code=429, detail="محاولات كثيرة. حاول بعد قليل.")
    return key


def record_login_failure(key: str) -> None:
    now = time.time()
    failures = _LOGIN_FAILURES[key]
    failures.append(now)
    if len(_LOGIN_FAILURES) > 10_000:
        for stale_key in list(_LOGIN_FAILURES)[:2_000]:
            stale = _LOGIN_FAILURES[stale_key]
            while stale and stale[0] <= now - LOGIN_WINDOW_SECONDS:
                stale.popleft()
            if not stale:
                _LOGIN_FAILURES.pop(stale_key, None)


def clear_login_failures(key: str) -> None:
    _LOGIN_FAILURES.pop(key, None)
