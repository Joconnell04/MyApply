from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agents import RunConfig, Runner
from pydantic import BaseModel

from services.resume_builder_agents import (
    JobScraperSchema,
    bullet_generator,
    job_scraper,
)


class AgentWorkflowError(RuntimeError):
    """Raised when an AgentKit run fails to produce the expected output."""


@dataclass
class AgentWorkflowRun:
    """Lightweight stand-in for the OpenAI Workflows run payload."""

    id: str
    status: str
    workflow_id: str
    version: str
    output: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "workflow_id": self.workflow_id,
            "version": self.version,
            "output": self.output,
        }


def _ensure_serializable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _ensure_serializable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_ensure_serializable(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()  # type: ignore[attr-defined]
            if isinstance(dumped, dict):
                return _ensure_serializable(dumped)
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(value, "to_dict"):
        try:
            dumped = value.to_dict()  # type: ignore[attr-defined]
            if isinstance(dumped, dict):
                return _ensure_serializable(dumped)
        except Exception:  # pragma: no cover - defensive
            pass
    if hasattr(value, "__dict__") and not isinstance(value, (str, bytes)):
        try:
            return _ensure_serializable({k: getattr(value, k) for k in vars(value)})
        except Exception:  # pragma: no cover - defensive
            pass
    return value


def _clean_bullet_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped[0] in {"-", "•", "*"}:
        stripped = stripped[1:].strip()
    return stripped


def _extract_bullet_list(text: str) -> List[str]:
    bullets: List[str] = []
    for line in text.splitlines():
        cleaned = _clean_bullet_line(line)
        if cleaned:
            bullets.append(cleaned)
    return bullets


def _extract_json_from_markdown(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from markdown code blocks (```json ... ```).
    Handles cases where the LLM wraps JSON in markdown formatting.
    """
    if not isinstance(text, str):
        return None

    # Try to find JSON wrapped in markdown code blocks
    import re

    # Pattern 1: ```json ... ```
    json_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    matches = re.findall(json_block_pattern, text, re.DOTALL)

    for match in matches:
        try:
            parsed = json.loads(match.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # Pattern 2: Direct JSON parsing (no markdown)
    try:
        parsed = json.loads(text.strip())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


def _reconstruct_json_from_lines(lines: List[str]) -> Optional[Dict[str, Any]]:
    """
    Reconstruct JSON from a list of lines that represent a JSON structure.
    This handles cases where the LLM output is split into individual lines.
    """
    if not lines:
        return None

    # Filter out markdown code fence markers
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('```'):
            filtered_lines.append(stripped)

    if not filtered_lines:
        return None

    # Try to join and parse
    json_text = '\n'.join(filtered_lines)
    try:
        parsed = json.loads(json_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try without newlines
    json_text = ''.join(filtered_lines)
    try:
        parsed = json.loads(json_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


def _normalize_bullet_payload(raw: Any) -> Dict[str, Any]:
    if raw is None:
        raise AgentWorkflowError("Bullet generator returned no payload.")

    if isinstance(raw, BaseModel):
        raw = raw.model_dump(mode="json")
    elif hasattr(raw, "to_dict"):
        try:
            raw = raw.to_dict()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            pass
    elif hasattr(raw, "__dict__") and not isinstance(raw, (str, bytes)):
        raw = vars(raw)

    # Handle case where raw is a list
    if isinstance(raw, list):
        if not raw:
            raise AgentWorkflowError("Bullet generator returned empty list.")
        # Try to find the best output in the list
        for item in reversed(raw):  # Start from the end (most recent)
            if isinstance(item, dict) and ("resume_bullet_points" in item or "output_parsed" in item):
                return _normalize_bullet_payload(item)
        # If no good match, use the last item
        return _normalize_bullet_payload(raw[-1])

    if isinstance(raw, dict):
        payload: Dict[str, Any] = dict(raw)
    elif isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = dict(parsed)
        else:
            # If it's plain text, try to extract bullet points from it
            bullets = _extract_bullet_list(raw)
            payload = {
                "resume_bullets_text": raw,
                "resume_bullets": bullets,
                "output_parsed": {
                    "reasoning": "",
                    "plan": [],
                    "resume_bullet_points": bullets,
                }
            }
            return payload
    else:
        payload = {"resume_bullets_text": str(raw)}

    # Extract nested structures
    if payload.get("type") == "text" and isinstance(payload.get("text"), str):
        return _normalize_bullet_payload(payload.get("text"))

    if payload.get("type") == "object" and "value" in payload and isinstance(payload["value"], dict):
        return _normalize_bullet_payload(payload["value"])

    if "output" in payload and isinstance(payload["output"], dict):
        candidate = payload["output"].get("output_parsed") or payload["output"].get("value")
        if candidate:
            return _normalize_bullet_payload(candidate)

    # Handle output_parsed structure
    output_parsed = payload.get("output_parsed")
    if not isinstance(output_parsed, dict):
        # Try to build output_parsed from top-level keys
        resume_points_raw = (
            payload.get("resume_bullet_points") or
            payload.get("bullets") or
            payload.get("resume_bullets") or
            []
        )

        if isinstance(resume_points_raw, list):
            # BACKUP PARSER: Check if this is a list of JSON string lines
            reconstructed = _reconstruct_json_from_lines(resume_points_raw)
            if reconstructed:
                # Successfully reconstructed JSON from lines!
                resume_points = reconstructed.get("resume_bullet_points", [])
                if isinstance(resume_points, list):
                    resume_points = [str(p).strip() for p in resume_points if str(p).strip()]
                else:
                    resume_points = []

                # Update payload with the reconstructed data
                payload["output_parsed"] = {
                    "reasoning": reconstructed.get("reasoning", ""),
                    "plan": reconstructed.get("plan", []) if isinstance(reconstructed.get("plan"), list) else [],
                    "resume_bullet_points": resume_points,
                }
                output_parsed = payload["output_parsed"]
            else:
                # Normal list processing
                resume_points = [str(item).strip() for item in resume_points_raw if str(item).strip()]
                plan = payload.get("plan", [])
                if not isinstance(plan, list):
                    plan = [str(plan)] if plan else []

                output_parsed = {
                    "reasoning": str(payload.get("reasoning", "")),
                    "plan": [str(item) for item in plan if item],
                    "resume_bullet_points": resume_points,
                }
                payload["output_parsed"] = output_parsed
        elif isinstance(resume_points_raw, str):
            resume_points = _extract_bullet_list(resume_points_raw)
            plan = payload.get("plan", [])
            if not isinstance(plan, list):
                plan = [str(plan)] if plan else []

            output_parsed = {
                "reasoning": str(payload.get("reasoning", "")),
                "plan": [str(item) for item in plan if item],
                "resume_bullet_points": resume_points,
            }
            payload["output_parsed"] = output_parsed
        else:
            resume_points = []
            plan = payload.get("plan", [])
            if not isinstance(plan, list):
                plan = [str(plan)] if plan else []

            output_parsed = {
                "reasoning": str(payload.get("reasoning", "")),
                "plan": [str(item) for item in plan if item],
                "resume_bullet_points": resume_points,
            }
            payload["output_parsed"] = output_parsed
    else:
        # Normalize existing output_parsed
        plan = output_parsed.get("plan")
        if isinstance(plan, list):
            output_parsed["plan"] = [str(item) for item in plan if isinstance(item, (str, int, float))]
        elif isinstance(plan, (str, int, float)):
            output_parsed["plan"] = [str(plan)]
        else:
            output_parsed["plan"] = []

        resume_points = output_parsed.get("resume_bullet_points")
        if isinstance(resume_points, list):
            # BACKUP PARSER: Check if this is actually a list of JSON lines
            if resume_points and isinstance(resume_points[0], str) and (
                resume_points[0].strip().startswith('```') or
                resume_points[0].strip().startswith('{') or
                resume_points[0].strip().startswith('"')
            ):
                reconstructed = _reconstruct_json_from_lines(resume_points)
                if reconstructed and "resume_bullet_points" in reconstructed:
                    resume_points = reconstructed["resume_bullet_points"]
                    if isinstance(resume_points, list):
                        normalized_points = [str(item).strip() for item in resume_points if str(item).strip()]
                    else:
                        normalized_points = []
                    # Update with reconstructed data
                    output_parsed["reasoning"] = reconstructed.get("reasoning", output_parsed.get("reasoning", ""))
                    output_parsed["plan"] = reconstructed.get("plan", output_parsed.get("plan", []))
                    output_parsed["resume_bullet_points"] = normalized_points
                else:
                    normalized_points = [str(item).strip() for item in resume_points if str(item).strip()]
                    output_parsed["resume_bullet_points"] = normalized_points
            else:
                normalized_points = [str(item).strip() for item in resume_points if str(item).strip()]
                output_parsed["resume_bullet_points"] = normalized_points
        elif isinstance(resume_points, str):
            normalized_points = _extract_bullet_list(resume_points)
            output_parsed["resume_bullet_points"] = normalized_points
        else:
            output_parsed["resume_bullet_points"] = []

    # Ensure resume_bullets_text is populated
    resume_text = payload.get("resume_bullets_text")
    if not isinstance(resume_text, str) or not resume_text.strip():
        if output_parsed.get("resume_bullet_points"):
            resume_text = "\n".join(f"- {point}" for point in output_parsed["resume_bullet_points"])
            payload["resume_bullets_text"] = resume_text

    # If we have resume_bullets_text but no bullets, extract them
    if not output_parsed.get("resume_bullet_points") and resume_text:
        extracted = _extract_bullet_list(resume_text)
        if extracted:
            output_parsed["resume_bullet_points"] = extracted

    # Ensure top-level resume_bullets key exists
    if "resume_bullets" not in payload or not isinstance(payload["resume_bullets"], list):
        payload["resume_bullets"] = output_parsed.get("resume_bullet_points", [])

    return payload


async def _execute_resume_builder_async(
    job_input: str,
) -> Dict[str, Any]:
    """
    Execute the ResumeBuilder agent graph end-to-end and return a structured
    payload containing the intermediate and final artifacts.
    """
    run_config = RunConfig()

    scraper_result = await Runner.run(
        job_scraper,
        job_input,
        run_config=run_config,
    )
    structured_job_raw = scraper_result.final_output
    if isinstance(structured_job_raw, JobScraperSchema):
        structured_job = structured_job_raw.model_dump(mode="json")
    elif isinstance(structured_job_raw, BaseModel):
        structured_job = structured_job_raw.model_dump(mode="json")
    elif isinstance(structured_job_raw, dict):
        structured_job = structured_job_raw
    else:  # pragma: no cover - defensive
        raise AgentWorkflowError("Job scraper did not return structured data.")

    bullet_input_json = json.dumps(structured_job)
    bullets_result = await Runner.run(
        bullet_generator,
        bullet_input_json,
        run_config=run_config,
    )

    # Extract only the final output, not intermediate execution steps
    bullets_output_raw = _ensure_serializable(bullets_result.final_output)
    bullet_payload = _normalize_bullet_payload(bullets_output_raw)

    resume_bullets = bullet_payload.get("resume_bullets") or []
    if not isinstance(resume_bullets, list):
        resume_bullets = []

    cover_letter = bullet_payload.get("cover_letter")
    if cover_letter is None and isinstance(bullet_payload.get("output_parsed"), dict):
        cover_letter = bullet_payload["output_parsed"].get("cover_letter")

    return {
        "structured_job_data": structured_job,
        "resume_bullets": resume_bullets,
        "resume_bullets_text": bullet_payload.get("resume_bullets_text"),
        "cover_letter": cover_letter,
        "job_scraper_result": _ensure_serializable(structured_job_raw),
        "resume_builder_result": bullet_payload,
    }


def run_resume_builder_workflow(
    workflow_id: str,
    version: str,
    job_input: str,
) -> AgentWorkflowRun:
    """
    Synchronously execute the ResumeBuilder workflow using the AgentKit SDK.

    Args:
        workflow_id: Identifier for the workflow (for compatibility with existing logging).
        version: Version string for the workflow.
        job_input: Either a URL or raw job description text.

    Returns:
        AgentWorkflowRun: Mimics the OpenAI Workflows response structure.
    """

    async def _runner() -> Dict[str, Any]:
        return await _execute_resume_builder_async(job_input)

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            result_payload = asyncio.run(_runner())
        else:  # pragma: no cover - defensive
            if loop.is_running():
                raise AgentWorkflowError(
                    "run_resume_builder_workflow cannot be invoked from an async context."
                )
            result_payload = loop.run_until_complete(_runner())
    except Exception as exc:
        raise AgentWorkflowError(str(exc)) from exc

    run_id = uuid.uuid4().hex
    bullet_payload = result_payload.get("resume_builder_result") or {}
    output_parsed = bullet_payload.get("output_parsed") or {}
    resume_text = result_payload.get("resume_bullets_text") or bullet_payload.get("resume_bullets_text") or ""
    output_payload = {
        "structured_job_data": result_payload.get("structured_job_data"),
        "resume_bullets": result_payload.get("resume_bullets"),
        "resume_bullets_text": resume_text,
        "cover_letter": result_payload.get("cover_letter"),
        "job_scraper_result": result_payload.get("job_scraper_result"),
        "resume_builder_result": bullet_payload,
        "output_text": resume_text,
        "output_parsed": output_parsed,
        "full_result": result_payload,
    }

    return AgentWorkflowRun(
        id=run_id,
        status="completed",
        workflow_id=workflow_id,
        version=version,
        output=output_payload,
    )
