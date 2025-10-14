from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
import time

from fastapi import HTTPException, status
from sqlmodel import Session

from applications import JobApplication
from routers.utils import SUCCESS_STATUSES, to_dict
from services.agentkit_debug_decoder import decode_latest_agentkit_response
from services.debug_log_parser import parse_complete_workflow_from_debug_logs
from services.openai_workflows import run_workflow
from services.workflow_output_parser import ResumeBuilderParsedOutput, parse_resume_builder_result
from workflow_constants import WORKFLOW_RESUME_BUILDER_V2_ID, WORKFLOW_RESUME_BUILDER_V2_VER

RunMode = Literal["ingest", "resume"]


@dataclass
class ResumeBuilderRunResult:
    run_id: Optional[str]
    workflow_status: Optional[str]
    artifacts: ResumeBuilderParsedOutput
    source: Literal["workflow", "agentkit_debug_log", "debug_log_parser"]
    recovered: bool = False

    @property
    def has_structured_job(self) -> bool:
        return self.artifacts.has_structured_job


_STAGE_MAP = {
    "ingest": {
        "start": "workflow_start",
        "status": "workflow_complete",
        "parse": "parse",
    },
    "resume": {
        "start": "resume_build",
        "status": "resume_build",
        "parse": "parse",
    },
}


def _prepare_for_execution(job_app: JobApplication, mode: RunMode) -> None:
    job_app.jd_status = "running"
    job_app.resume_status = "running"
    job_app.updated_at = datetime.utcnow()


def _apply_failure(job_app: JobApplication, session: Session, *, stage: str, error: str) -> None:
    job_app.jd_status = "failed"
    job_app.resume_status = "failed"
    job_app.resume_output = {
        "error": error,
        "stage": stage,
    }
    job_app.updated_at = datetime.utcnow()
    session.add(job_app)
    session.commit()


def _apply_success(job_app: JobApplication, session: Session, mode: RunMode, result: ResumeBuilderRunResult) -> None:
    job_app.jd_run_id = result.run_id or job_app.jd_run_id
    job_app.jd_struct_data = result.artifacts.structured_job_data
    job_app.jd_status = "succeeded"
    job_app.resume_run_id = result.run_id or job_app.resume_run_id
    job_app.resume_output = dict(result.artifacts.payload)
    if result.artifacts.resume_bullets:
        job_app.resume_output.setdefault("resume_bullets", result.artifacts.resume_bullets)
    if result.artifacts.cover_letter:
        job_app.resume_output.setdefault("cover_letter", result.artifacts.cover_letter)
    if result.workflow_status:
        job_app.resume_output.setdefault("workflow_status", result.workflow_status)
    if result.source in {"agentkit_debug_log", "debug_log_parser"}:
        job_app.resume_output.setdefault("decoder_source", result.source)

    if mode == "ingest":
        job_app.resume_status = "idle"
    else:
        job_app.resume_status = "succeeded"

    job_app.updated_at = datetime.utcnow()
    session.add(job_app)
    session.commit()
    session.refresh(job_app)


def _collect_run_artifacts(
    session: Session,
    application_id: str,
    run: object,
) -> ResumeBuilderRunResult:
    run_dict = to_dict(run) or {}
    run_id = getattr(run, "id", None) or run_dict.get("id")
    status_value = getattr(run, "status", None) or run_dict.get("status")

    # Give debug logging a brief window to flush.
    time.sleep(0.2)

    debug_result = parse_complete_workflow_from_debug_logs(session, application_id)
    artifacts: ResumeBuilderParsedOutput
    source: Literal["workflow", "agentkit_debug_log", "debug_log_parser"]
    recovered = False
    workflow_status = status_value

    if debug_result.get("success"):
        structured_job = debug_result.get("structured_job")
        resume_bullets = debug_result.get("resume_bullets") or []
        cover_letter = debug_result.get("cover_letter")
        payload = {
            "structured_job_data": structured_job,
            "resume_bullets": resume_bullets,
            "cover_letter": cover_letter,
            "decoder_source": "debug_log_parser",
            "parsing_strategy": debug_result.get("parsing_strategy"),
        }
        artifacts = ResumeBuilderParsedOutput(
            payload=payload,
            structured_job_data=structured_job,
            resume_bullets=resume_bullets,
            cover_letter=cover_letter,
        ).ensure_defaults()
        run_id = debug_result.get("run_id") or run_id
        source = "debug_log_parser"
        recovered = True
    else:
        artifacts = parse_resume_builder_result(run)
        source = "workflow"

    if not artifacts.has_structured_job:
        decoded = decode_latest_agentkit_response(session, application_id)
        if decoded:
            run_id = decoded.run_id or run_id
            artifacts = decoded.artifacts
            workflow_status = decoded.workflow_status or status_value
            source = decoded.source
            recovered = True

    # Preserve status information for downstream consumers.
    if workflow_status:
        artifacts.payload.setdefault("workflow_status", workflow_status)

    return ResumeBuilderRunResult(
        run_id=run_id,
        workflow_status=workflow_status,
        artifacts=artifacts.ensure_defaults(),
        source=source,
        recovered=recovered,
    )


def execute_resume_builder_pipeline(
    session: Session,
    job_app: JobApplication,
    *,
    job_input: str,
    mode: RunMode,
) -> ResumeBuilderRunResult:
    if mode not in _STAGE_MAP:
        raise ValueError(f"Unsupported run mode: {mode}")

    _prepare_for_execution(job_app, mode)
    session.add(job_app)
    session.commit()
    session.refresh(job_app)

    stage_map = _STAGE_MAP[mode]

    try:
        run = run_workflow(
            workflow_id=WORKFLOW_RESUME_BUILDER_V2_ID,
            version=WORKFLOW_RESUME_BUILDER_V2_VER,
            inputs={"input_as_text": job_input},
            db_session=session,
            application_id=job_app.id,
        )
    except HTTPException as exc:
        error = str(getattr(exc, "detail", exc))
        _apply_failure(job_app, session, stage=stage_map["start"], error=error)
        raise
    except Exception as exc:  # pragma: no cover - defensive
        _apply_failure(job_app, session, stage=stage_map["start"], error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ResumeBuilderV2 workflow failed: {exc}",
        ) from exc

    result = _collect_run_artifacts(session, job_app.id, run)
    status_value = result.workflow_status
    status_lower = str(status_value).lower() if status_value else None

    if (
        status_lower
        and status_lower not in SUCCESS_STATUSES
        and not result.has_structured_job
    ):
        _apply_failure(
            job_app,
            session,
            stage=stage_map["status"],
            error=f"Workflow status {status_value}",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ResumeBuilderV2 workflow returned status {status_value}",
        )

    if not result.has_structured_job:
        _apply_failure(
            job_app,
            session,
            stage=stage_map["parse"],
            error="Workflow returned no structured job data.",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ResumeBuilderV2 workflow returned no structured job data.",
        )

    # Successful run (even if recovered from AgentKit debug logs).
    _apply_success(job_app, session, mode, result)
    return result


__all__ = [
    "execute_resume_builder_pipeline",
    "ResumeBuilderRunResult",
]
