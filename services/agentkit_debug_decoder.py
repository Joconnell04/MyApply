from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from models import APIDebugLog
from services.workflow_output_parser import (
    ResumeBuilderParsedOutput,
    parse_resume_builder_result,
)


@dataclass
class DecodedAgentkitResult:
    run_id: Optional[str]
    artifacts: ResumeBuilderParsedOutput
    workflow_status: Optional[str]
    source: str = "agentkit_debug_log"


def _iter_agentkit_logs(session: Session, application_id: str):
    """
    Yield AgentKit debug log entries for an application, newest first.

    The Router passes in the same session that created the job application,
    so we can reuse it to read the debug log rows without flushing.
    """
    statement = (
        select(APIDebugLog)
        .where(
            APIDebugLog.application_id == application_id,
            APIDebugLog.log_type == "agentkit_call",
        )
        .order_by(APIDebugLog.created_at.desc())
    )
    return session.exec(statement)


def decode_latest_agentkit_response(
    session: Session,
    application_id: str,
) -> Optional[DecodedAgentkitResult]:
    """
    Parse the most recent AgentKit debug log entry and extract the structured
    workflow output.

    Returns:
        Tuple containing (run_id, parsed_output, structured_job, resume_bullets, cover_letter)
        when data could be decoded, otherwise None.
    """
    for log_entry in _iter_agentkit_logs(session, application_id):
        response_data = log_entry.response_data
        if response_data is None:
            continue

        artifacts = parse_resume_builder_result(response_data)
        if (
            not artifacts.has_structured_job
            and not artifacts.resume_bullets
            and not artifacts.cover_letter
        ):
            continue

        run_id: Optional[str] = None
        if isinstance(response_data, dict):
            run_id = response_data.get("id") or response_data.get("run_id")

        if not run_id:
            run_id = artifacts.payload.get("id") or artifacts.payload.get("run_id")

        # Tag the decoded payload so downstream consumers know the source.
        artifacts.payload.setdefault("decoder_source", "agentkit_debug_log")
        workflow_status = artifacts.payload.get("workflow_status")
        if (
            not workflow_status
            and isinstance(response_data, dict)
        ):
            status_value = response_data.get("status")
            if status_value:
                artifacts.payload["workflow_status"] = status_value
                workflow_status = status_value

        return DecodedAgentkitResult(
            run_id=run_id,
            artifacts=artifacts.ensure_defaults(),
            workflow_status=workflow_status,
        )

    return None


__all__ = [
    "decode_latest_agentkit_response",
    "DecodedAgentkitResult",
]
