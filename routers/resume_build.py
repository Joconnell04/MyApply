from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import get_session
from applications import JobApplication
from services.openai_workflows import run_workflow
from workflow_constants import WORKFLOW_RESUME_BUILDER_ID, WORKFLOW_RESUME_BUILDER_VER
from .utils import SUCCESS_STATUSES, ensure_user_id, to_dict, try_parse_json_text

router = APIRouter()


class ResumeBuildRequest(BaseModel):
    application_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1, max_length=255)
    target_role: Optional[str] = Field(default=None, max_length=255)

    model_config = {"extra": "forbid"}


class ResumeBuildResponse(BaseModel):
    application_id: str
    resume_status: str
    resume_output: Optional[Dict[str, Any]] = None


def _prepare_inputs(job_app: JobApplication, payload: ResumeBuildRequest) -> Dict[str, Any]:
    if not job_app.jd_struct_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Structured JD data is missing. Re-run JD ingestion first.",
        )

    target_role = (payload.target_role or "").strip()
    if not target_role:
        target_role = ""
        jd_data = job_app.jd_struct_data or {}
        if isinstance(jd_data, dict):
            title = jd_data.get("title")
            if isinstance(title, str):
                target_role = title

    inputs: Dict[str, Any] = {
        "jd_struct_data": job_app.jd_struct_data,
        "user_id": payload.user_id,
    }
    if target_role:
        inputs["target_role"] = target_role
    return inputs


def _coerce_resume_output(run: Any) -> Dict[str, Any]:
    run_dict = to_dict(run) or {}
    output_payload = to_dict(getattr(run, "output", None)) or run_dict.get("output")
    resume_output: Dict[str, Any] = {}

    if isinstance(output_payload, dict):
        resume_output.update(output_payload)
    elif isinstance(output_payload, str):
        parsed = try_parse_json_text(output_payload)
        if parsed:
            resume_output["output_parsed"] = parsed
        else:
            resume_output["output_text"] = output_payload
    elif output_payload is not None:
        resume_output["output"] = output_payload

    parsed_direct = run_dict.get("output_parsed")
    if isinstance(parsed_direct, dict):
        resume_output.setdefault("output_parsed", parsed_direct)

    output_text = run_dict.get("output_text") or getattr(run, "output_text", None)
    if isinstance(output_text, str):
        resume_output.setdefault("output_text", output_text)

    if not resume_output and run_dict:
        resume_output = run_dict

    return resume_output


@router.post("/build", response_model=ResumeBuildResponse)
def build_resume(
    payload: ResumeBuildRequest,
    session: Session = Depends(get_session),
) -> ResumeBuildResponse:
    user_id = ensure_user_id(payload.user_id)

    job_app = session.get(JobApplication, payload.application_id)
    if not job_app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if job_app.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Application does not belong to user",
        )

    if job_app.jd_status != "succeeded" or not job_app.jd_struct_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job description not ready. Complete JD ingestion first.",
        )

    job_app.resume_status = "running"
    job_app.updated_at = datetime.utcnow()
    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    inputs = _prepare_inputs(job_app, payload)

    try:
        run = run_workflow(
            workflow_id=WORKFLOW_RESUME_BUILDER_ID,
            version=WORKFLOW_RESUME_BUILDER_VER,
            inputs=inputs,
        )
    except HTTPException:
        job_app.resume_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        job_app.resume_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Resume workflow failed: {exc}",
        ) from exc

    run_dict = to_dict(run) or {}
    status_value = getattr(run, "status", None) or run_dict.get("status")
    if status_value and str(status_value).lower() not in SUCCESS_STATUSES:
        job_app.resume_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Resume workflow returned status {status_value}",
        )

    job_app.resume_run_id = getattr(run, "id", None) or run_dict.get("id") or job_app.resume_run_id
    job_app.resume_output = _coerce_resume_output(run)
    job_app.resume_status = "succeeded"
    job_app.updated_at = datetime.utcnow()

    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    return ResumeBuildResponse(
        application_id=job_app.id,
        resume_status=job_app.resume_status,
        resume_output=job_app.resume_output,
    )
