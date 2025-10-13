from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from openai import OpenAI
from sqlmodel import Session


def _build_client() -> OpenAI:
    try:
        api_key = os.environ["OPENAI_API_KEY"]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured.",
        ) from exc
    return OpenAI(api_key=api_key)


_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def _serialize_run(run: Any) -> Dict[str, Any]:
    """Convert run object to dictionary for logging."""
    try:
        run_dict = {
            "id": getattr(run, "id", None),
            "status": getattr(run, "status", None),
            "workflow_id": getattr(run, "workflow_id", None),
            "version": getattr(run, "version", None),
        }

        # Safely serialize output
        output = getattr(run, "output", None)
        if output is not None:
            try:
                # Try to convert to dict if it's an object
                if hasattr(output, "__dict__"):
                    run_dict["output"] = output.__dict__
                else:
                    run_dict["output"] = output
            except Exception:  # pylint: disable=broad-except
                run_dict["output"] = str(output)

        # Add any other relevant attributes
        if hasattr(run, "error"):
            run_dict["error"] = getattr(run, "error", None)

        return run_dict
    except Exception:  # pylint: disable=broad-except
        return {"raw": str(run)}


def run_workflow(
    workflow_id: str,
    version: str,
    inputs: Dict[str, Any],
    db_session: Optional[Session] = None,
    application_id: Optional[str] = None,
) -> Any:
    """
    Execute an AgentKit workflow and poll until it reaches a terminal state.

    Args:
        workflow_id: The AgentKit workflow ID
        version: The workflow version
        inputs: Input parameters for the workflow
        db_session: Optional database session for debug logging
        application_id: Optional application ID for linking debug logs
    """
    from debug_logger import log_agentkit_call
    from models import APIDebugLog

    client = get_client()
    start_time = time.time()

    # Log the workflow call
    if db_session:
        try:
            with log_agentkit_call(
                session=db_session,
                workflow_id=workflow_id,
                inputs=inputs,
                application_id=application_id,
            ) as logger:
                try:
                    run = client.workflows.runs.create(
                        workflow_id=workflow_id,
                        version=version,
                        inputs=inputs,
                    )
                except Exception as exc:
                    logger.log_response(
                        error_message=f"Failed to start workflow: {exc}",
                        status_code=502,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Failed to start workflow {workflow_id}: {exc}",
                    ) from exc

                # Poll for completion
                while run.status in ("queued", "in_progress"):
                    time.sleep(0.5)
                    run = client.workflows.runs.retrieve(run.id)

                # Log the final response
                run_dict = _serialize_run(run)
                logger.log_response(
                    response_data=run_dict,
                    status_code=200 if run.status == "completed" else 500,
                )

                return run
        except Exception:  # pylint: disable=broad-except
            # If logging fails, still try to run the workflow
            pass

    # Fallback without logging
    try:
        run = client.workflows.runs.create(
            workflow_id=workflow_id,
            version=version,
            inputs=inputs,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to start workflow {workflow_id}: {exc}",
        ) from exc

    while run.status in ("queued", "in_progress"):
        time.sleep(0.5)
        run = client.workflows.runs.retrieve(run.id)

    return run

