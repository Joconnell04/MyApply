from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from sqlmodel import Column, Field, JSON, SQLModel


class JobApplication(SQLModel, table=True):
    """
    Persisted record for a user's application workflow state.

    Tracks both workflow runs (job description structuring and resume build)
    alongside the structured job data and generated resume output.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: str = Field(index=True)
    source_url: str
    linked_job_id: Optional[str] = Field(default=None, index=True)  # Link to JobApplied
    jd_run_id: Optional[str] = Field(default=None, index=True)
    jd_status: str = Field(default="pending")  # pending|running|succeeded|failed|aborted
    jd_struct_data: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON)
    )
    resume_run_id: Optional[str] = Field(default=None, index=True)
    resume_status: str = Field(default="idle")  # idle|running|succeeded|failed|aborted
    resume_output: Optional[Dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

