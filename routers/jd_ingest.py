from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session

from app import get_session
from applications import JobApplication
from services.resume_builder_pipeline import execute_resume_builder_pipeline
from validation import validate_url
from .utils import ensure_user_id

router = APIRouter()


class JDIngestRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    source_url: Optional[str] = Field(None, min_length=5, max_length=2048)
    jd_text: Optional[str] = Field(None, max_length=100000)
    application_id: Optional[str] = Field(default=None, min_length=1)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_url_or_text(self):
        if not self.source_url and not self.jd_text:
            raise ValueError("Either source_url or jd_text must be provided.")
        return self


class JDIngestResponse(BaseModel):
    application_id: str
    jd_status: str
    jd_struct_data: Optional[Dict[str, Any]] = None


@router.post("/ingest", response_model=JDIngestResponse)
def ingest_job_description(
    payload: JDIngestRequest,
    session: Session = Depends(get_session),
) -> JDIngestResponse:
    user_id = ensure_user_id(payload.user_id)

    # Determine the input text - either URL or raw text
    if payload.source_url:
        job_source = validate_url(payload.source_url)
        input_text = job_source
    else:
        job_source = "text:///direct-input"  # Placeholder for tracking
        input_text = payload.jd_text

    if payload.application_id:
        job_app = session.get(JobApplication, payload.application_id)
        if not job_app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found.",
            )
        if job_app.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Application does not belong to user.",
            )
        job_app.source_url = job_source
    else:
        job_app = JobApplication(
            user_id=user_id,
            source_url=job_source,
        )

    execute_resume_builder_pipeline(
        session=session,
        job_app=job_app,
        job_input=input_text,
        mode="ingest",
    )

    return JDIngestResponse(
        application_id=job_app.id,
        jd_status=job_app.jd_status,
        jd_struct_data=job_app.jd_struct_data,
    )
