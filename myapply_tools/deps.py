"""Shared dependencies and configuration for the MyApply AgentKit tool service."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Iterator

from fastapi import HTTPException, status
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlmodel import Session, create_engine


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="", case_sensitive=False)

    database_url: str = "sqlite:///./myapply_tools.db"
    myapply_api_key: str = "dev_key"
    rate_limit_capacity: int = 60
    rate_limit_refill_seconds: float = 60.0


settings = Settings()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {})


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""

    with Session(engine) as session:
        yield session


@dataclass
class TokenBucket:
    """Simple token bucket implementation for rate limiting."""

    capacity: int
    refill_seconds: float
    lock: Lock
    available: float
    last_checked: float

    def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume tokens, returning True if permitted."""

        with self.lock:
            now = monotonic()
            elapsed = now - self.last_checked
            if elapsed > 0:
                refill = (elapsed / self.refill_seconds) * self.capacity
                self.available = min(self.capacity, self.available + refill)
                self.last_checked = now
            if self.available >= tokens:
                self.available -= tokens
                return True
            return False


class RateLimiter:
    """In-memory per-user rate limiter using token buckets."""

    def __init__(self, capacity: int, refill_seconds: float) -> None:
        self.capacity = capacity
        self.refill_seconds = refill_seconds
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = Lock()

    def check(self, user_id: str) -> bool:
        """Return True if the user is allowed to proceed."""

        with self._lock:
            bucket = self._buckets.get(user_id)
            if bucket is None:
                bucket = TokenBucket(
                    capacity=self.capacity,
                    refill_seconds=self.refill_seconds,
                    lock=Lock(),
                    available=float(self.capacity),
                    last_checked=monotonic(),
                )
                self._buckets[user_id] = bucket
        return bucket.consume()


rate_limiter = RateLimiter(settings.rate_limit_capacity, settings.rate_limit_refill_seconds)


def get_rate_limiter_dependency(user_id: str) -> None:
    """Helper to invoke the rate limiter for a given user."""

    if not rate_limiter.check(user_id):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")
