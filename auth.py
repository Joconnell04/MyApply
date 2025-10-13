from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

import re
from email_validator import EmailNotValidError, validate_email
from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeSerializer
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRateLimiter:
    """Simple in-memory rate limiter for login attempts."""

    def __init__(self, limit: int = 5, window_seconds: int = 600) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._attempts: Dict[str, Deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> None:
        queue = self._attempts[key]
        while queue and now - queue[0] > self.window_seconds:
            queue.popleft()

    def hit(self, key: str) -> None:
        now = time.monotonic()
        queue = self._attempts[key]
        self._prune(key, now)
        if len(queue) >= self.limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
            )
        queue.append(now)

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("Password is required.")
    # Bcrypt has a 72-byte limit, truncate if necessary
    # This is safe because we're still hashing a long enough password
    password_bytes = plain.encode('utf-8')[:72]
    return pwd_context.hash(password_bytes)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        # Bcrypt has a 72-byte limit, truncate to match hash_password
        password_bytes = plain.encode('utf-8')[:72]
        return pwd_context.verify(password_bytes, hashed)
    except ValueError:
        return False


def _normalize_email(email: str) -> str:
    try:
        result = validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return result.normalized


def _serializer(secret_key: str) -> URLSafeSerializer:
    return URLSafeSerializer(secret_key, salt="csrf-token")


def ensure_csrf_token(request: Request, secret_key: str) -> str:
    token = request.session.get("csrf_token")
    if token:
        return token
    raw_token = secrets.token_urlsafe(32)
    signed = _serializer(secret_key).dumps({"nonce": raw_token})
    request.session["csrf_token"] = signed
    return signed


def validate_csrf_token(request: Request, token: Optional[str], secret_key: str) -> None:
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing CSRF token.")
    session_token = request.session.get("csrf_token")
    if not session_token or session_token != token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token.")
    try:
        _serializer(secret_key).loads(token)
    except BadSignature as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF signature.") from exc


def _start_session(request: Request, user_id: int) -> None:
    request.session["uid"] = user_id


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long.",
        )
    if not re.search(r"[A-Za-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must include at least one letter.",
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must include at least one number.",
        )
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must include at least one symbol.",
        )


def register(
    request: Request,
    db: Session,
    *,
    email: str,
    password: str,
    secret_key: str,
) -> User:
    normalized_email = _normalize_email(email)
    _validate_password_strength(password)

    existing = db.exec(select(User).where(User.email == normalized_email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Try signing in or resetting your password.",
        )

    user = User(email=normalized_email, password_hash=hash_password(password))
    try:
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Try signing in or resetting your password.",
        ) from exc
    db.refresh(user)

    _start_session(request, user.id)
    ensure_csrf_token(request, secret_key)
    return user


def login(
    request: Request,
    db: Session,
    *,
    email: str,
    password: str,
    secret_key: str,
    rate_limiter: LoginRateLimiter,
    client_id: str,
) -> User:
    normalized_email = _normalize_email(email)
    rate_key = f"{client_id}:{normalized_email}"
    rate_limiter.hit(rate_key)

    user = db.exec(select(User).where(User.email == normalized_email)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    rate_limiter.reset(rate_key)
    _start_session(request, user.id)
    ensure_csrf_token(request, secret_key)
    return user


def logout(request: Request) -> None:
    request.session.pop("uid", None)


def create_admin_user(
    db: Session,
    *,
    email: str,
    password: str,
    enforce_password_strength: bool = True,
) -> User:
    normalized_email = _normalize_email(email)
    if enforce_password_strength:
        _validate_password_strength(password)
    else:
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long.",
            )
    existing = db.exec(select(User).where(User.email == normalized_email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )
    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        is_admin=True,
    )
    try:
        db.add(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        ) from exc
    db.refresh(user)
    return user
