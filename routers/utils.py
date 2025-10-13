from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

SUCCESS_STATUSES = {"succeeded", "success", "completed"}


def ensure_user_id(value: str) -> str:
    value = value.strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )
    return value


def to_dict(payload: Any) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        try:
            dumped = payload.model_dump()  # type: ignore[attr-defined]
            if isinstance(dumped, dict):
                return dumped
        except TypeError:
            pass
    if hasattr(payload, "to_dict"):
        try:
            dumped = payload.to_dict()  # type: ignore[attr-defined]
            if isinstance(dumped, dict):
                return dumped
        except TypeError:
            pass
    return None


def try_parse_json_text(text: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None

