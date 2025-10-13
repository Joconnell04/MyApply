from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from app import get_session
from applications import JobApplication
from services.openai_workflows import run_workflow
from validation import validate_url
from workflow_constants import WORKFLOW_JD_TO_STRUCT_ID, WORKFLOW_JD_TO_STRUCT_VER
from .utils import SUCCESS_STATUSES, ensure_user_id, to_dict, try_parse_json_text

router = APIRouter()


class JDIngestRequest(BaseModel):
    source_url: str = Field(..., min_length=5, max_length=2048)
    user_id: str = Field(..., min_length=1, max_length=255)

    model_config = {"extra": "forbid"}


class JDIngestResponse(BaseModel):
    application_id: str
    jd_status: str
    jd_struct_data: Optional[Dict[str, Any]] = None


def _extract_structured_jd(run: Any) -> Dict[str, Any]:
    run_output = getattr(run, "output", None)
    output_dict = to_dict(run_output) or to_dict(run)

    structured = None
    if output_dict:
        structured = output_dict.get("output_parsed") or output_dict.get("jd_struct_data")
        if structured is None:
            output_text = output_dict.get("output_text")
            if isinstance(output_text, str):
                structured = try_parse_json_text(output_text)
    if structured is None:
        output_text = getattr(run, "output_text", None)
        if isinstance(output_text, str):
            structured = try_parse_json_text(output_text)

    if structured is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="JD workflow returned no structured data.",
        )
    if not isinstance(structured, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="JD workflow returned invalid structured data.",
        )
    return structured


@router.post("/ingest", response_model=JDIngestResponse)
def ingest_job_description(
    payload: JDIngestRequest,
    session: Session = Depends(get_session),
) -> JDIngestResponse:
    source_url = validate_url(payload.source_url)
    user_id = ensure_user_id(payload.user_id)

    job_app = JobApplication(
        user_id=user_id,
        source_url=source_url,
        jd_status="running",
    )
    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    try:
        run = run_workflow(
            workflow_id=WORKFLOW_JD_TO_STRUCT_ID,
            version=WORKFLOW_JD_TO_STRUCT_VER,
            inputs={"source_url": source_url},
        )
    except HTTPException:
        job_app.jd_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise
    except Exception as exc:  # pragma: no cover - defensive
        job_app.jd_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JD workflow failed: {exc}",
        ) from exc

    run_dict = to_dict(run) or {}
    status_value = getattr(run, "status", None) or run_dict.get("status")
    if status_value and str(status_value).lower() not in SUCCESS_STATUSES:
        job_app.jd_status = "failed"
        job_app.updated_at = datetime.utcnow()
        session.add(job_app)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JD workflow returned status {status_value}",
        )

    job_app.jd_run_id = getattr(run, "id", None) or run_dict.get("id") or job_app.jd_run_id
    job_app.jd_struct_data = _extract_structured_jd(run)
    job_app.jd_status = "succeeded"
    job_app.updated_at = datetime.utcnow()

    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    return JDIngestResponse(
        application_id=job_app.id,
        jd_status=job_app.jd_status,
        jd_struct_data=job_app.jd_struct_data,
    )
