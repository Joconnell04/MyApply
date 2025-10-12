"""Database models for the MyApply AgentKit tool service."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Index, JSON
from sqlmodel import Field, SQLModel


class BundleKind(str, Enum):
    """Enumeration of supported bundle record kinds."""

    RESUME = "resume"
    COVER_LETTER = "cover_letter"


class Bundle(SQLModel, table=True):
    """Persisted resume and cover-letter bundles keyed by user and hash."""

    __tablename__ = "bundles"
    __table_args__ = (
        Index("ix_bundles_user_hash_kind", "user_id", "hash", "kind", unique=True),
        Index("ix_bundles_user_kind", "user_id", "kind"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True, nullable=False)
    hash: str = Field(index=True, nullable=False)
    kind: BundleKind = Field(nullable=False)
    payload: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    ttl_seconds: int = Field(nullable=False, default=604800)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)


class Experience(SQLModel, table=True):
    """Simplified experience rows backing search and evidence APIs."""

    __tablename__ = "experiences"
    __table_args__ = (Index("ix_experiences_user", "user_id"),)

    id: str = Field(primary_key=True, nullable=False)
    user_id: str = Field(index=True, nullable=False)
    title: str = Field(nullable=False)
    summary: str = Field(nullable=False)
    text: str = Field(nullable=False)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    skills: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    domains: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    tools: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    degrees: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    bullets: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    metrics: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    artifacts: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    start_date: Optional[str] = Field(default=None)
    end_date: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
