from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import Session, select

from models import APIDebugLog
from services.workflow_output_parser import parse_resume_builder_result


DecodedAgentkitResult = Tuple[
    Optional[str],
    Dict[str, Any],
    Optional[Dict[str, Any]],
    Optional[List[str]],
    Optional[str],
]


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

        parsed_output, structured_job, resume_bullets, cover_letter = parse_resume_builder_result(response_data)
        if not structured_job and not resume_bullets and not cover_letter:
            continue

        run_id: Optional[str] = None
        if isinstance(response_data, dict):
            run_id = response_data.get("id") or response_data.get("run_id")

        if not run_id:
            run_id = parsed_output.get("id") or parsed_output.get("run_id")

        # Tag the decoded payload so downstream consumers know the source.
        parsed_output = dict(parsed_output)
        parsed_output.setdefault("decoder_source", "agentkit_debug_log")
        if (
            "workflow_status" not in parsed_output
            and isinstance(response_data, dict)
        ):
            status_value = response_data.get("status")
            if status_value:
                parsed_output["workflow_status"] = status_value

        return run_id, parsed_output, structured_job, resume_bullets, cover_letter

    return None


__all__ = [
    "decode_latest_agentkit_response",
]
