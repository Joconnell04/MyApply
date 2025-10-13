from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import HTTPException, status
from openai import OpenAI


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


def run_workflow(workflow_id: str, version: str, inputs: Dict[str, Any]) -> Any:
    """
    Execute an AgentKit workflow and poll until it reaches a terminal state.
    """
    client = get_client()
    try:
        run = client.workflows.runs.create(
            workflow_id=workflow_id,
            version=version,
            inputs=inputs,
        )
    except Exception as exc:  # pragma: no cover - surfaced to FastAPI error handlers
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to start workflow {workflow_id}: {exc}",
        ) from exc

    while run.status in ("queued", "in_progress"):
        time.sleep(0.5)
        run = client.workflows.runs.retrieve(run.id)

    return run

