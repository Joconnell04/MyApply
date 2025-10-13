from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def _json_column() -> Column:
    try:
        from app import settings  # type: ignore
        is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    except Exception:
        is_sqlite = True

    if is_sqlite:
        return Column(SQLiteJSON, nullable=False, default=dict)
    return Column(JSONB, nullable=False, default=dict)


class ChatThread(SQLModel, table=True):
    __tablename__ = "chatkit_thread"

    id: str = Field(primary_key=True)
    title: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    meta: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class ChatThreadItem(SQLModel, table=True):
    __tablename__ = "chatkit_thread_item"

    id: str = Field(primary_key=True)
    thread_id: str = Field(foreign_key="chatkit_thread.id", index=True, nullable=False)
    type: str = Field(nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True, nullable=False)
    payload: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False, default=dict))
