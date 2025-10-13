from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import get_session
from applications import JobApplication
from services.openai_workflows import run_workflow
from services.workflow_output_parser import (
    extract_cover_letter,
    extract_resume_bullets,
    extract_structured_job,
    parse_resume_builder_result,
)
from validation import validate_url
from workflow_constants import (
    WORKFLOW_RESUME_BUILDER_V2_ID,
    WORKFLOW_RESUME_BUILDER_V2_VER,
)
from .utils import SUCCESS_STATUSES, ensure_user_id, to_dict

router = APIRouter()


class ResumeBuilderV2Request(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    job_url: str = Field(..., min_length=5, max_length=2048)
    application_id: Optional[str] = Field(default=None, min_length=1)

    model_config = {"extra": "forbid"}


class ResumeBuilderV2Response(BaseModel):
    application_id: str
    source_url: str
    resume_run_id: Optional[str]
    resume_status: str
    structured_job_data: Optional[Dict[str, Any]] = None
    resume_bullets: Optional[List[str]] = None
    cover_letter: Optional[str] = None
    resume_output: Optional[Dict[str, Any]] = None


@router.post("/build", response_model=ResumeBuilderV2Response)
def run_resume_builder_v2(
    payload: ResumeBuilderV2Request,
    session: Session = Depends(get_session),
) -> ResumeBuilderV2Response:
    user_id = ensure_user_id(payload.user_id)
    job_url = validate_url(payload.job_url)

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
    job_app.resume_status = "running"
    job_app.updated_at = datetime.utcnow()
    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    inputs = {"input_as_text": job_url}

    if job_app.resume_output:
        stored_output = job_app.resume_output
        structured_job = job_app.jd_struct_data or extract_structured_job(stored_output)
        resume_bullets = extract_resume_bullets(stored_output)
        cover_letter = extract_cover_letter(stored_output)

        if resume_bullets or cover_letter:
            job_app.jd_struct_data = structured_job
            job_app.resume_status = "succeeded"
            job_app.updated_at = datetime.utcnow()
            session.add(job_app)
            session.commit()
            session.refresh(job_app)

            return ResumeBuilderV2Response(
                application_id=job_app.id,
                source_url=job_app.source_url,
                resume_run_id=job_app.resume_run_id,
                resume_status=job_app.resume_status,
                structured_job_data=job_app.jd_struct_data,
                resume_bullets=resume_bullets,
                cover_letter=cover_letter,
                resume_output=job_app.resume_output,
            )

    try:
        run = run_workflow(
            workflow_id=WORKFLOW_RESUME_BUILDER_V2_ID,
            version=WORKFLOW_RESUME_BUILDER_V2_VER,
            inputs=inputs,
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

    job_app.jd_run_id = run_id or job_app.jd_run_id
    job_app.resume_run_id = run_id or job_app.resume_run_id
    job_app.jd_struct_data = structured_job
    job_app.resume_output = parsed_output
    job_app.jd_status = "succeeded"
    job_app.resume_status = "succeeded"
    job_app.updated_at = datetime.utcnow()

    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    return ResumeBuilderV2Response(
        application_id=job_app.id,
        source_url=job_app.source_url,
        resume_run_id=job_app.resume_run_id,
        resume_status=job_app.resume_status,
        structured_job_data=job_app.jd_struct_data,
        resume_bullets=resume_bullets,
        cover_letter=cover_letter,
        resume_output=job_app.resume_output,
    )
