from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import EmailStr
from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from graph.schema import EdgeType, NodeType, PrivacyLevel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __table_args__ = (Index("ix_user_email_unique", "email", unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    email: EmailStr = Field(index=True, nullable=False, sa_column_kwargs={"unique": True})
    password_hash: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    is_admin: bool = Field(default=False, nullable=False)
    full_name: Optional[str] = Field(default=None)
    home_lat: Optional[float] = Field(default=None)
    home_lng: Optional[float] = Field(default=None)
    mylife_json: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )


class GraphNode(SQLModel, table=True):
    __tablename__ = "nodes"
    __table_args__ = (
        Index("ix_nodes_node_type", "node_type"),
        Index("ix_nodes_owner_id", "owner_id"),
    )

    id: str = Field(primary_key=True, nullable=False)
    node_type: NodeType = Field(nullable=False)
    version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
    confidence: float = Field(default=0.8, nullable=False)
    privacy: PrivacyLevel = Field(default=PrivacyLevel.INTERNAL, nullable=False)
    owner_id: int = Field(foreign_key="user.id", nullable=False)
    labels: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    provenance: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
    )
    data: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
    )


class GraphEdge(SQLModel, table=True):
    __tablename__ = "edges"
    __table_args__ = (
        Index("ix_edges_edge_type", "edge_type"),
        Index("ix_edges_from_id", "from_id"),
        Index("ix_edges_to_id", "to_id"),
        Index("ix_edges_owner_id", "owner_id"),
    )

    id: str = Field(primary_key=True, nullable=False)
    edge_type: EdgeType = Field(nullable=False)
    version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
    confidence: float = Field(default=0.8, nullable=False)
    privacy: PrivacyLevel = Field(default=PrivacyLevel.INTERNAL, nullable=False)
    owner_id: int = Field(foreign_key="user.id", nullable=False)
    labels: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    provenance: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
    )
    from_id: str = Field(nullable=False, foreign_key="nodes.id")
    to_id: str = Field(nullable=False, foreign_key="nodes.id")
    since: Optional[datetime] = Field(default=None, nullable=True)
    until: Optional[datetime] = Field(default=None, nullable=True)


class UserGraph(SQLModel, table=True):
    user_id: int = Field(primary_key=True, foreign_key="user.id")
    graph: Dict[str, Any] = Field(
        default_factory=lambda: {"nodes": [], "edges": []},
        sa_column=Column(JSON, nullable=False),
    )
    updated_at: datetime = Field(default_factory=utc_now, nullable=False, index=True)


class ComposeRun(SQLModel, table=True):
    __table_args__ = (
        Index("ix_composerun_owner_created", "owner_id", "created_at"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    jd_source_url: Optional[str] = Field(default=None)
    jd_text_excerpt: Optional[str] = Field(default=None)
    jd_factors: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    selected_fact_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    resume_bullets: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    cover_letter: Optional[str] = Field(default=None)
    llm_model: Optional[str] = Field(default=None)
    tokens_used: int = Field(default=0, nullable=False)
    validation_status: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class JobApplied(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    company: str = Field(nullable=False)
    role_title: str = Field(nullable=False)
    source_url: Optional[str] = Field(default=None)
    applied_at: datetime = Field(default_factory=utc_now, nullable=False)
    jd_structured: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False, default=dict))
    resume_bullets: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    cover_letter: Optional[str] = Field(default=None)


class JobLocation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    job_id: str = Field(foreign_key="jobapplied.id", index=True, nullable=False)
    label: Optional[str] = Field(default=None)
    lat: Optional[float] = Field(default=None)
    lng: Optional[float] = Field(default=None)
    raw: Optional[str] = Field(default=None)


class WorkflowRun(SQLModel, table=True):
    """
    Stores metadata for AgentKit workflow runs.

    The backend orchestrator calls workflows synchronously and persists
    the run metadata. Workflows do NOT call each other directly; the
    backend passes outputs as explicit inputs between workflow calls.
    """
    __tablename__ = "workflow_run"
    __table_args__ = (
        Index("ix_workflow_run_user_created", "user_id", "created_at"),
        Index("ix_workflow_run_workflow_id", "workflow_id"),
    )

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    workflow_id: str = Field(nullable=False, index=True)
    version: str = Field(nullable=False)
    status: str = Field(nullable=False)  # "success", "error", "invalid"
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    input_json: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    output_json: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class Artifact(SQLModel, table=True):
    """
    Stores workflow artifacts extracted from WorkflowRun outputs.

    Examples: 'structured_jd', 'resume_bullets', 'warnings'
    """
    __tablename__ = "artifact"
    __table_args__ = (
        Index("ix_artifact_run_id", "run_id"),
        Index("ix_artifact_kind", "kind"),
    )

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    run_id: str = Field(foreign_key="workflow_run.id", nullable=False, index=True)
    kind: str = Field(nullable=False, index=True)  # e.g., "structured_jd", "resume_bullets"
    label: Optional[str] = Field(default=None)
    payload_json: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
