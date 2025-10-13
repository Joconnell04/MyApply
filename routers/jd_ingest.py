from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session

from app import get_session
from applications import JobApplication
from services.agentkit_debug_decoder import decode_latest_agentkit_response
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

    job_app.jd_status = "running"
    job_app.resume_status = "running"
    job_app.updated_at = datetime.utcnow()
    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    try:
        run = run_workflow(
            workflow_id=WORKFLOW_RESUME_BUILDER_V2_ID,
            version=WORKFLOW_RESUME_BUILDER_V2_VER,
            inputs={"input_as_text": input_text},
            db_session=session,
            application_id=job_app.id,
        )
    except HTTPException as exc:
        job_app.jd_status = "failed"
        job_app.resume_status = "failed"
        job_app.resume_output = {
            "error": str(getattr(exc, "detail", exc)),
            "stage": "workflow_start",
        }
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        job_app.jd_status = "failed"
        job_app.resume_status = "failed"
        job_app.resume_output = {
            "error": str(exc),
            "stage": "workflow_start",
        }
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ResumeBuilderV2 workflow failed: {exc}",
        ) from exc

    run_dict = to_dict(run) or {}
    run_id = getattr(run, "id", None) or run_dict.get("id")

    # PRIMARY STRATEGY: Always parse from debug logs first
    # Assumption: API responses are unreliable, debug logs are the source of truth
    from services.debug_log_parser import parse_complete_workflow_from_debug_logs
    import time

    # Give the debug log a moment to be written (it's written during workflow execution)
    time.sleep(0.5)

    debug_result = parse_complete_workflow_from_debug_logs(session, job_app.id)

    if debug_result["success"]:
        # Use debug log data as primary source
        structured_job = debug_result["structured_job"]
        resume_bullets = debug_result["resume_bullets"] or []
        cover_letter = debug_result["cover_letter"] or ""
        run_id = debug_result["run_id"] or run_id
        parsed_output = {
            "structured_job_data": structured_job,
            "resume_bullets": resume_bullets,
            "cover_letter": cover_letter,
            "decoder_source": "debug_log_parser",
            "parsing_strategy": debug_result["parsing_strategy"]
        }
    else:
        # FALLBACK STRATEGY: Try parsing API response (unlikely to work)
        parsed_output, structured_job_fallback, resume_bullets_fallback, cover_letter_fallback = parse_resume_builder_result(run)

        if structured_job_fallback:
            structured_job = structured_job_fallback
            resume_bullets = resume_bullets_fallback or []
            cover_letter = cover_letter_fallback or ""
        else:
            # LAST RESORT: Try old decoder
            decoded = decode_latest_agentkit_response(session, job_app.id)
            if decoded:
                decoded_run_id, decoded_output, decoded_structured_job, decoded_bullets, decoded_cover = decoded
                run_id = decoded_run_id or run_id
                parsed_output = decoded_output
                structured_job = decoded_structured_job
                resume_bullets = decoded_bullets or []
                cover_letter = decoded_cover or ""

    status_value = getattr(run, "status", None) or run_dict.get("status")
    status_lower = str(status_value).lower() if status_value else None
    if status_lower and status_lower not in SUCCESS_STATUSES:
        if structured_job:
            parsed_output = dict(parsed_output)
            if status_value:
                parsed_output.setdefault("workflow_status", status_value)
        else:
            job_app.jd_status = "failed"
            job_app.resume_status = "failed"
            job_app.resume_output = {
                "error": f"Workflow status {status_value}",
                "stage": "workflow_complete",
            }
            job_app.updated_at = datetime.utcnow()
            session.add(job_app)
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"ResumeBuilderV2 workflow returned status {status_value}",
            )

    if structured_job is None:
        job_app.jd_status = "failed"
        job_app.resume_status = "failed"
        job_app.resume_output = {
            "error": "Workflow returned no structured job data.",
            "stage": "parse",
        }
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
    job_app.resume_status = "succeeded"
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
