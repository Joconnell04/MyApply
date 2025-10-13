from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from debug_logger import log_agentkit_call
from services.resume_builder_service import (
    AgentWorkflowError,
    AgentWorkflowRun,
    run_resume_builder_workflow,
)


def _extract_job_input(inputs: Dict[str, Any]) -> str:
    """
    Normalize workflow inputs used by the historic Workflows API into the
    single text payload consumed by the AgentKit implementation.
    """
    if not inputs:
        raise ValueError("Workflow inputs are required.")

    for key in ("input_as_text", "job_url", "job_text", "text"):
        value = inputs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise ValueError("Unable to determine job input text from workflow inputs.")


def _run_resume_builder_agentkit(
    workflow_id: str,
    version: str,
    inputs: Dict[str, Any],
) -> AgentWorkflowRun:
    job_input = _extract_job_input(inputs)
    return run_resume_builder_workflow(
        workflow_id=workflow_id,
        version=version,
        job_input=job_input,
    )


def run_workflow(
    workflow_id: str,
    version: str,
    inputs: Dict[str, Any],
    db_session: Optional[Session] = None,
    application_id: Optional[str] = None,
) -> AgentWorkflowRun:
    """
    Execute the ResumeBuilder workflow using the AgentKit SDK.

    This is a drop-in replacement for the former OpenAI Workflows integration.
    It preserves the logging contract and mimics the Workflows run payload.
    """
    def _execute() -> AgentWorkflowRun:
        try:
            return _run_resume_builder_agentkit(
                workflow_id=workflow_id,
                version=version,
                inputs=inputs,
            )
        except (ValueError, AgentWorkflowError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to start workflow {workflow_id}: {exc}",
            ) from exc

    if db_session is not None:
        try:
            with log_agentkit_call(
                session=db_session,
                workflow_id=workflow_id,
                inputs=inputs,
                application_id=application_id,
            ) as logger:
                run = _execute()
                # Log the complete workflow output for debugging
                logger.log_response(
                    response_data=run.to_dict(),
                    status_code=200,
                )
                return run
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to start workflow {workflow_id}: {exc}",
            ) from exc

    return _execute()
