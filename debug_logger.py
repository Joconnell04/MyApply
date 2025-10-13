"""
Debug logging utility for capturing API calls and responses.

Logs are stored in the database for user-accessible debugging.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional
from contextlib import contextmanager

from sqlmodel import Session

from models import APIDebugLog


class DebugLogger:
    """Context manager for logging API calls."""

    def __init__(
        self,
        session: Session,
        log_type: str,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        compose_run_id: Optional[int] = None,
        application_id: Optional[str] = None,
    ):
        self.session = session
        self.log_type = log_type
        self.endpoint = endpoint
        self.method = method
        self.compose_run_id = compose_run_id
        self.application_id = application_id
        self.start_time: Optional[float] = None
        self.log_entry: Optional[APIDebugLog] = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.log_entry:
            duration_ms = (time.time() - self.start_time) * 1000 if self.start_time else None
            self.log_entry.duration_ms = duration_ms
            if exc_type:
                self.log_entry.error_message = str(exc_val)
            self.session.add(self.log_entry)
            try:
                self.session.commit()
            except Exception:  # pylint: disable=broad-except
                # Don't let logging errors break the main flow
                self.session.rollback()

    def log_request(self, request_data: Optional[Dict[str, Any]] = None):
        """Log request data."""
        self.log_entry = APIDebugLog(
            compose_run_id=self.compose_run_id,
            application_id=self.application_id,
            log_type=self.log_type,
            endpoint=self.endpoint,
            method=self.method,
            request_data=request_data or {},
        )

    def log_response(
        self,
        response_data: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Log response data."""
        if self.log_entry:
            self.log_entry.response_data = response_data or {}
            self.log_entry.status_code = status_code
            if error_message:
                self.log_entry.error_message = error_message


@contextmanager
def log_agentkit_call(
    session: Session,
    workflow_id: str,
    inputs: Dict[str, Any],
    application_id: Optional[str] = None,
    compose_run_id: Optional[int] = None,
):
    """Context manager for logging AgentKit workflow calls."""
    logger = DebugLogger(
        session=session,
        log_type="agentkit_call",
        endpoint=f"workflow:{workflow_id}",
        method="POST",
        compose_run_id=compose_run_id,
        application_id=application_id,
    )
    with logger:
        logger.log_request({"workflow_id": workflow_id, "inputs": inputs})
        yield logger
