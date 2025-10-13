"""
Debug Log Parser Service

This service assumes that workflow outputs are ALWAYS malformed and unreliable.
It extracts data exclusively from debug logs with multiple fallback strategies.
"""
from typing import Any, Dict, List, Optional, Tuple
import json
import re
from sqlmodel import Session, select
from models import APIDebugLog


def _extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from various text formats including markdown code blocks."""
    if not isinstance(text, str):
        return None

    # Strategy 1: Find JSON in markdown code blocks
    patterns = [
        r'```(?:json)?\s*\n?(.*?)\n?```',  # ```json ... ``` or ``` ... ```
        r'```(.*?)```',  # Any code block
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    # Strategy 2: Direct JSON parsing
    try:
        parsed = json.loads(text.strip())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


def _reconstruct_json_from_list(items: List[Any]) -> Optional[Dict[str, Any]]:
    """Reconstruct JSON from a list of string lines."""
    if not isinstance(items, list) or not items:
        return None

    # Filter out code fence markers
    lines = []
    for item in items:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped and not stripped.startswith('```'):
                lines.append(stripped)

    if not lines:
        return None

    # Try to join and parse
    for separator in ['\n', '']:
        json_text = separator.join(lines)
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    return None


def _extract_from_nested_structure(data: Any, target_keys: List[str]) -> Optional[Dict[str, Any]]:
    """Recursively search for data in nested structures."""
    if isinstance(data, dict):
        # Check if this dict has the target keys
        if any(key in data for key in target_keys):
            return data

        # Recursively search values
        for value in data.values():
            result = _extract_from_nested_structure(value, target_keys)
            if result:
                return result

    elif isinstance(data, list):
        # Try to reconstruct from list
        reconstructed = _reconstruct_json_from_list(data)
        if reconstructed and any(key in reconstructed for key in target_keys):
            return reconstructed

        # Search each item
        for item in data:
            result = _extract_from_nested_structure(item, target_keys)
            if result:
                return result

    elif isinstance(data, str):
        # Try to parse as JSON
        extracted = _extract_json_from_text(data)
        if extracted and any(key in extracted for key in target_keys):
            return extracted

    return None


def parse_structured_job_from_debug_logs(
    session: Session,
    application_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Extract structured job data from debug logs.

    Returns:
        (structured_job_data, run_id) or (None, None)
    """
    # Get all debug logs for this application, ordered by creation time
    logs = session.exec(
        select(APIDebugLog)
        .where(APIDebugLog.application_id == application_id)
        .order_by(APIDebugLog.created_at.desc())
    ).all()

    if not logs:
        return None, None

    # Target keys we're looking for
    job_keys = ["company", "role", "locations", "required_skills", "experience"]

    for log in logs:
        if not log.response_data:
            continue

        # Strategy 1: Check response_data directly
        result = _extract_from_nested_structure(log.response_data, job_keys)
        if result:
            # Verify it looks like a job structure
            if any(key in result for key in job_keys):
                run_id = log.response_data.get("id") if isinstance(log.response_data, dict) else None
                return result, run_id

    return None, None


def parse_resume_bullets_from_debug_logs(
    session: Session,
    application_id: str
) -> Tuple[Optional[List[str]], Optional[str], Optional[str]]:
    """
    Extract resume bullets from debug logs.

    Returns:
        (resume_bullets, cover_letter, run_id) or (None, None, None)
    """
    # Get all debug logs for this application, ordered by creation time
    logs = session.exec(
        select(APIDebugLog)
        .where(APIDebugLog.application_id == application_id)
        .order_by(APIDebugLog.created_at.desc())
    ).all()

    if not logs:
        return None, None, None

    # Target keys we're looking for
    bullet_keys = ["resume_bullet_points", "resume_bullets", "bullets"]

    for log in logs:
        if not log.response_data:
            continue

        # Strategy 1: Search for bullet points in nested structure
        result = _extract_from_nested_structure(log.response_data, bullet_keys)

        if result and isinstance(result, dict):
            # Extract bullets
            bullets = (
                result.get("resume_bullet_points") or
                result.get("resume_bullets") or
                result.get("bullets")
            )

            # If bullets is a list, clean it up
            if isinstance(bullets, list):
                # Check if it's a list of JSON string lines (markdown wrapped)
                if bullets and isinstance(bullets[0], str) and (
                    bullets[0].strip().startswith('```') or
                    bullets[0].strip().startswith('{') or
                    bullets[0].strip().startswith('"')
                ):
                    # Try to reconstruct
                    reconstructed = _reconstruct_json_from_list(bullets)
                    if reconstructed:
                        bullets = (
                            reconstructed.get("resume_bullet_points") or
                            reconstructed.get("resume_bullets") or
                            reconstructed.get("bullets")
                        )

            # Normalize to list of strings
            if isinstance(bullets, list):
                cleaned_bullets = [str(b).strip() for b in bullets if str(b).strip()]
                if cleaned_bullets:
                    cover_letter = result.get("cover_letter", "")
                    run_id = log.response_data.get("id") if isinstance(log.response_data, dict) else None
                    return cleaned_bullets, cover_letter, run_id

    return None, None, None


def parse_complete_workflow_from_debug_logs(
    session: Session,
    application_id: str
) -> Dict[str, Any]:
    """
    Extract complete workflow results from debug logs.

    This is the MAIN function to use. It returns everything in one call.

    Returns:
        {
            "structured_job": {...} or None,
            "resume_bullets": [...] or None,
            "cover_letter": str or None,
            "run_id": str or None,
            "parsing_strategy": str,
            "success": bool
        }
    """
    result = {
        "structured_job": None,
        "resume_bullets": None,
        "cover_letter": None,
        "run_id": None,
        "parsing_strategy": "none",
        "success": False
    }

    # Get all debug logs
    logs = session.exec(
        select(APIDebugLog)
        .where(APIDebugLog.application_id == application_id)
        .order_by(APIDebugLog.created_at.desc())
    ).all()

    if not logs:
        return result

    # Try to find the most recent log with complete data
    for log in logs:
        if not log.response_data or not isinstance(log.response_data, dict):
            continue

        response = log.response_data

        # Look for output in various locations
        output_locations = [
            response.get("output"),
            response.get("output_text"),
            response.get("result"),
            response
        ]

        for output in output_locations:
            if not output:
                continue

            # Try to parse if it's a string
            if isinstance(output, str):
                parsed = _extract_json_from_text(output)
                if parsed:
                    output = parsed

            if not isinstance(output, dict):
                continue

            # Extract structured job
            if not result["structured_job"]:
                job_keys = ["company", "role", "locations", "required_skills"]
                job_data = _extract_from_nested_structure(output, job_keys)
                if job_data and any(k in job_data for k in job_keys):
                    result["structured_job"] = job_data
                    result["parsing_strategy"] = "debug_log_deep_search"

            # Extract resume bullets
            if not result["resume_bullets"]:
                bullet_keys = ["resume_bullet_points", "resume_bullets", "bullets"]
                bullet_data = _extract_from_nested_structure(output, bullet_keys)

                if bullet_data and isinstance(bullet_data, dict):
                    bullets = (
                        bullet_data.get("resume_bullet_points") or
                        bullet_data.get("resume_bullets") or
                        bullet_data.get("bullets")
                    )

                    # Handle markdown-wrapped JSON
                    if isinstance(bullets, list) and bullets:
                        if isinstance(bullets[0], str) and (
                            bullets[0].strip().startswith('```') or
                            bullets[0].strip().startswith('{')
                        ):
                            reconstructed = _reconstruct_json_from_list(bullets)
                            if reconstructed:
                                bullets = (
                                    reconstructed.get("resume_bullet_points") or
                                    reconstructed.get("resume_bullets") or
                                    reconstructed.get("bullets")
                                )

                    # Normalize to list
                    if isinstance(bullets, list):
                        result["resume_bullets"] = [str(b).strip() for b in bullets if str(b).strip()]
                        result["cover_letter"] = bullet_data.get("cover_letter")
                        result["parsing_strategy"] = "debug_log_deep_search"

            # If we found everything, we can stop
            if result["structured_job"] and result["resume_bullets"]:
                result["run_id"] = response.get("id")
                result["success"] = True
                return result

    # Determine success based on what we found
    result["success"] = bool(result["structured_job"] or result["resume_bullets"])

    return result
