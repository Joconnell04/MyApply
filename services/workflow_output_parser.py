from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from routers.utils import to_dict, try_parse_json_text


_STRUCTURED_JOB_KEYS = {
    "required_skills",
    "nice_to_have_skills",
    "required_experience",
    "locations",
    "desired_skills",
    "other_noteworthy",
}

_RESUME_BULLET_KEYS = [
    "resume_bullets",
    "resume_bullet_points",
    "bullet_points",
    "bullets",
    "draft_bullets",
    "resume_bullets_text",
]

_COVER_LETTER_KEYS = [
    "cover_letter",
    "cover_letter_paragraph",
    "coverLetter",
    "cover_letter_text",
    "cover_letter_summary",
]


def flatten_workflow_output(run: Any) -> Dict[str, Any]:
    run_dict = to_dict(run) or {}
    output_payload = to_dict(getattr(run, "output", None)) or run_dict.get("output")
    flattened: Dict[str, Any] = {}

    if isinstance(output_payload, dict):
        flattened.update(output_payload)
    elif isinstance(output_payload, str):
        parsed = try_parse_json_text(output_payload)
        if parsed:
            flattened["output_parsed"] = parsed
        else:
            flattened["output_text"] = output_payload
    elif output_payload is not None:
        flattened["output"] = output_payload

    parsed_direct = run_dict.get("output_parsed")
    if isinstance(parsed_direct, dict):
        flattened.setdefault("output_parsed", parsed_direct)

    output_text = run_dict.get("output_text") or getattr(run, "output_text", None)
    if isinstance(output_text, str):
        flattened.setdefault("output_text", output_text)

    if not flattened and run_dict:
        flattened = run_dict

    return flattened


def _looks_like_structured_job(payload: Dict[str, Any]) -> bool:
    return len(_STRUCTURED_JOB_KEYS.intersection(payload.keys())) >= 2


def _normalize_bullet_list(value: Any) -> List[str]:
    bullets: List[str] = []

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                text_item = item.strip()
                if text_item:
                    bullets.append(text_item)
            elif isinstance(item, dict):
                text_item = item.get("text") or item.get("content") or item.get("value")
                if isinstance(text_item, str):
                    text_item = text_item.strip()
                    if text_item:
                        bullets.append(text_item)
            elif item is not None:
                text_item = str(item).strip()
                if text_item:
                    bullets.append(text_item)
    elif isinstance(value, str):
        parsed = try_parse_json_text(value)
        if parsed is not None:
            return _normalize_bullet_list(parsed)
        segments = [segment.strip() for segment in value.splitlines() if segment.strip()]
        if len(segments) > 1:
            bullets.extend(segments)
    elif isinstance(value, dict):
        nested = extract_resume_bullets(value)
        if nested:
            bullets.extend(nested)

    return bullets


def extract_structured_job(payload: Any) -> Optional[Dict[str, Any]]:
    if isinstance(payload, dict):
        if _looks_like_structured_job(payload):
            return payload

        # Check specific known keys first
        for key in ["structured_job_data", "job_scraper_result"]:
            if key in payload:
                value = payload[key]
                if isinstance(value, dict) and _looks_like_structured_job(value):
                    return value
                nested = extract_structured_job(value)
                if nested:
                    return nested

        for key, value in payload.items():
            if key in _STRUCTURED_JOB_KEYS or key in {"output_parsed"}:
                if isinstance(value, dict):
                    if _looks_like_structured_job(value):
                        return value
                    nested = extract_structured_job(value)
                    if nested:
                        return nested
                elif isinstance(value, str):
                    parsed = try_parse_json_text(value)
                    if parsed and isinstance(parsed, dict):
                        if _looks_like_structured_job(parsed):
                            return parsed
                        nested = extract_structured_job(parsed)
                        if nested:
                            return nested

        # Recursively search all values as last resort
        for value in payload.values():
            if isinstance(value, (dict, list, str)):
                nested = extract_structured_job(value)
                if nested:
                    return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = extract_structured_job(item)
            if nested:
                return nested
    elif isinstance(payload, str):
        parsed = try_parse_json_text(payload)
        if parsed and isinstance(parsed, dict):
            if _looks_like_structured_job(parsed):
                return parsed
            return extract_structured_job(parsed)
    return None


def extract_resume_bullets(payload: Any) -> Optional[List[str]]:
    if isinstance(payload, dict):
        for key in _RESUME_BULLET_KEYS:
            if key in payload:
                bullets = _normalize_bullet_list(payload[key])
                if bullets:
                    return bullets
        for value in payload.values():
            bullets = extract_resume_bullets(value)
            if bullets:
                return bullets
    elif isinstance(payload, list):
        for item in payload:
            bullets = extract_resume_bullets(item)
            if bullets:
                return bullets
    elif isinstance(payload, str):
        parsed = try_parse_json_text(payload)
        if parsed:
            return extract_resume_bullets(parsed)
    return None


def extract_cover_letter(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        for key in _COVER_LETTER_KEYS:
            if key in payload:
                value = payload[key]
                if isinstance(value, str):
                    cover = value.strip()
                    if cover:
                        return cover
                elif value is not None:
                    nested = extract_cover_letter(value)
                    if nested:
                        return nested
        for value in payload.values():
            nested = extract_cover_letter(value)
            if nested:
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = extract_cover_letter(item)
            if nested:
                return nested
    elif isinstance(payload, str):
        parsed = try_parse_json_text(payload)
        if parsed:
            return extract_cover_letter(parsed)
    return None


def parse_resume_builder_result(run: Any) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Optional[List[str]], Optional[str]]:
    flattened = flatten_workflow_output(run)
    parsed_output = dict(flattened)

    output_text = parsed_output.get("output_text")
    parsed_from_text: Optional[Dict[str, Any]] = None

    if isinstance(output_text, str):
        parsed_candidate = try_parse_json_text(output_text)
        if parsed_candidate and isinstance(parsed_candidate, dict):
            parsed_from_text = parsed_candidate
            parsed_output.setdefault("output_text_parsed", parsed_from_text)
    elif isinstance(output_text, dict):
        parsed_from_text = output_text
        parsed_output.setdefault("output_text_parsed", parsed_from_text)

    structured_job = extract_structured_job(parsed_output)
    if structured_job is None and parsed_from_text:
        structured_job = extract_structured_job(parsed_from_text)

    resume_bullets = extract_resume_bullets(parsed_output)
    if (not resume_bullets) and parsed_from_text:
        resume_bullets = extract_resume_bullets(parsed_from_text)

    resume_text = parsed_output.get("resume_bullets_text")
    if not resume_text and parsed_output.get("resume_builder_result"):
        maybe = parsed_output["resume_builder_result"]
        if isinstance(maybe, dict):
            resume_text = maybe.get("resume_bullets_text")
    if not resume_text and isinstance(parsed_output.get("output_text"), str):
        resume_text = parsed_output.get("output_text")
    if resume_text:
        parsed_output.setdefault("resume_bullets_text", resume_text)
        if (not resume_bullets) and isinstance(resume_text, str):
            alt_bullets = _normalize_bullet_list(resume_text)
            if alt_bullets:
                resume_bullets = alt_bullets

    cover_letter = extract_cover_letter(parsed_output)
    if (not cover_letter) and parsed_from_text:
        cover_letter = extract_cover_letter(parsed_from_text)

    if structured_job:
        parsed_output.setdefault("structured_job_data", structured_job)
    if resume_bullets:
        parsed_output.setdefault("resume_bullets", resume_bullets)
    if cover_letter:
        parsed_output.setdefault("cover_letter", cover_letter)

    return parsed_output, structured_job, resume_bullets, cover_letter


__all__ = [
    "flatten_workflow_output",
    "extract_structured_job",
    "extract_resume_bullets",
    "extract_cover_letter",
    "parse_resume_builder_result",
]
