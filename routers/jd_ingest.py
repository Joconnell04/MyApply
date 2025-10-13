from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import get_session
from applications import JobApplication
from services.openai_workflows import run_workflow
from services.workflow_output_parser import parse_resume_builder_result
from validation import validate_url
from workflow_constants import (
    WORKFLOW_RESUME_BUILDER_V2_ID,
    WORKFLOW_RESUME_BUILDER_V2_VER,
)
from .utils import SUCCESS_STATUSES, ensure_user_id, to_dict

router = APIRouter()


class JDIngestRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    source_url: str = Field(..., min_length=5, max_length=2048)
    application_id: Optional[str] = Field(default=None, min_length=1)

    model_config = {"extra": "forbid"}


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
    job_url = validate_url(payload.source_url)

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
        job_app.source_url = job_url
    else:
        job_app = JobApplication(
            user_id=user_id,
            source_url=job_url,
        )

    job_app.jd_status = "running"
    job_app.resume_status = job_app.resume_status or "idle"
    job_app.updated_at = datetime.utcnow()
    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    try:
        run = run_workflow(
            workflow_id=WORKFLOW_RESUME_BUILDER_V2_ID,
            version=WORKFLOW_RESUME_BUILDER_V2_VER,
            inputs={"input_as_text": job_url},
            db_session=session,
            application_id=job_app.id,
        )
    except HTTPException:
        job_app.jd_status = "failed"
        job_app.resume_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        job_app.jd_status = "failed"
        job_app.resume_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ResumeBuilderV2 workflow failed: {exc}",
        ) from exc

    run_dict = to_dict(run) or {}
    status_value = getattr(run, "status", None) or run_dict.get("status")
    if status_value and str(status_value).lower() not in SUCCESS_STATUSES:
        job_app.jd_status = "failed"
        job_app.resume_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ResumeBuilderV2 workflow returned status {status_value}",
        )

    run_id = getattr(run, "id", None) or run_dict.get("id")
    parsed_output, structured_job, resume_bullets, cover_letter = parse_resume_builder_result(run)
    if structured_job is None:
        job_app.jd_status = "failed"
        job_app.resume_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ResumeBuilderV2 workflow returned no structured job data.",
        )

    job_app.jd_run_id = run_id or job_app.jd_run_id
    job_app.jd_struct_data = structured_job
    job_app.jd_status = "succeeded"
    job_app.resume_run_id = run_id or job_app.resume_run_id
    job_app.resume_output = parsed_output
    job_app.resume_status = "idle"
    job_app.updated_at = datetime.utcnow()

    # Preserve generated bullets & cover letter for later use without exposing them in this response
    if resume_bullets:
        job_app.resume_output.setdefault("resume_bullets", resume_bullets)
    if cover_letter:
        job_app.resume_output.setdefault("cover_letter", cover_letter)

    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    return JDIngestResponse(
        application_id=job_app.id,
        jd_status=job_app.jd_status,
        jd_struct_data=job_app.jd_struct_data,
    )
