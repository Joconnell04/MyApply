from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlmodel import Session

from models_llm import BulletsResponse, CoverLetterResponse, JDExtract, Provenance

if TYPE_CHECKING:  # pragma: no cover - imported for type hints only
    from graph.loader import LoaderResult

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - openai not available during offline tests
    OpenAI = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

MYLIFE_SPEC_PATH = Path("MyLifeSchemaInstructions.md")
MAX_JD_CHARS = 20_000
BULLET_WORD_LIMIT = 22
ATS_KEYWORD_LIMIT = 25
MISSION_LIMIT = 5
METRIC_LIMIT = 5

PipelineMetadata = Dict[str, Any]


class LLMCallError(RuntimeError):
    """Raised when an upstream LLM call fails."""


class LLMNotConfiguredError(RuntimeError):
    """Raised when attempting an LLM call without configuration."""


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _truncate_text(text: str, limit: int = MAX_JD_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _limit_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    trimmed = " ".join(words[:limit]).rstrip()
    if not trimmed.endswith("."):
        trimmed += "."
    return trimmed


def _normalize_whitespace(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip()


def _extract_response_text(response: Any) -> str:
    if hasattr(response, "output") and response.output:
        parts: List[str] = []
        for item in response.output:
            content_list = getattr(item, "content", []) or []
            for content_item in content_list:
                text = getattr(content_item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
                elif hasattr(text, "value"):
                    parts.append(getattr(text, "value"))
        if parts:
            return "".join(parts)
    if hasattr(response, "output_text"):
        output_text = getattr(response, "output_text")
        if isinstance(output_text, str):
            return output_text
    if hasattr(response, "choices"):
        choices = getattr(response, "choices") or []
        if choices:
            first = choices[0]
            if hasattr(first, "message"):
                message = getattr(first, "message")
                if isinstance(message, dict):
                    return message.get("content", "") or ""
                if hasattr(message, "content"):
                    content_val = getattr(message, "content")
                    if isinstance(content_val, str):
                        return content_val
            if hasattr(first, "text"):
                text_val = getattr(first, "text")
                if isinstance(text_val, str):
                    return text_val
    return ""


def _usage_to_dict(usage: Any) -> Dict[str, int]:
    if usage is None:
        return {}
    usage_dict: Dict[str, int] = {}
    for key in ("total_tokens", "input_tokens", "output_tokens", "prompt_tokens", "completion_tokens"):
        value = getattr(usage, key, None)
        if value is None and isinstance(usage, dict):
            value = usage.get(key)
        if isinstance(value, (int, float)):
            usage_dict[key] = int(value)
    return usage_dict


def _heuristic_extract_jd_factors(jd_text: str) -> JDExtract:
    text = jd_text.strip()
    normalized = re.sub(r"\s+", " ", text)
    lowered = normalized.lower()

    company = None
    company_match = re.search(r"(?:company|employer)[:\-]\s*([A-Z0-9][^\n,;.]+)", text, re.IGNORECASE)
    if company_match:
        company = company_match.group(1).strip()
    else:
        first_line = text.splitlines()[0] if text.splitlines() else normalized[:80]
        tokens = first_line.strip().split()
        if tokens and tokens[0].istitle():
            company = tokens[0]

    role_title = None
    title_match = re.search(r"(?:role|title|position)[:\-]\s*([^\n,;.]+)", text, re.IGNORECASE)
    if title_match:
        role_title = title_match.group(1).strip()
    else:
        role_title = text.splitlines()[0].strip()[:120] if text.splitlines() else normalized[:120]

    level = None
    for candidate in ["intern", "junior", "associate", "mid", "senior", "lead", "principal", "director"]:
        if candidate in lowered:
            level = candidate.title()
            break

    employment_type = None
    for candidate in ["full-time", "part-time", "contract", "temporary", "internship", "co-op"]:
        if candidate in lowered:
            employment_type = candidate.replace("-", " ").title()
            break
    if not employment_type:
        employment_type = "Full-time"

    location = None
    location_match = re.search(r"location[:\-]\s*([^\n]+)", text, re.IGNORECASE)
    if location_match:
        location = location_match.group(1).strip()

    function = None
    function_map = {
        "Engineering": ["engineer", "developer", "software"],
        "Data": ["data", "analytics", "ml", "ai"],
        "Product": ["product", "pm", "manager"],
        "Design": ["design", "ux", "ui"],
        "Operations": ["operations", "ops", "logistics"],
    }
    for label, keywords in function_map.items():
        if any(keyword in lowered for keyword in keywords):
            function = label
            break

    team = None
    team_match = re.search(r"team[:\-]\s*([^\n]+)", text, re.IGNORECASE)
    if team_match:
        team = team_match.group(1).strip()

    words = re.findall(r"[A-Za-z\+#]{3,}", lowered)
    counts = Counter(words)
    ats_keywords = [word for word, _ in counts.most_common(ATS_KEYWORD_LIMIT)]

    skill_candidates = [word for word, _ in counts.most_common(18)]
    must_have_skills = [word.title() for word in skill_candidates[:8]]
    nice_to_have_skills = [word.title() for word in skill_candidates[8:14]]

    domain_vocab = [
        "fintech",
        "healthcare",
        "ecommerce",
        "cloud",
        "security",
        "analytics",
        "ai",
        "automation",
        "platform",
        "infrastructure",
        "productivity",
    ]
    domain_terms = [term.title() for term in domain_vocab if term in lowered]
    domain = domain_terms[0] if domain_terms else None

    mission_signals: List[str] = []
    metrics_signals: List[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", normalized):
        sentence_clean = sentence.strip()
        sentence_lower = sentence_clean.lower()
        if not sentence_clean:
            continue
        if any(keyword in sentence_lower for keyword in ["mission", "purpose", "vision", "impact"]):
            mission_signals.append(sentence_clean)
        if re.search(r"\d+\s?(?:%|percent|x|k|m)", sentence_lower) or any(
            keyword in sentence_lower for keyword in ["increase", "reduce", "improve", "grow"]
        ):
            metrics_signals.append(sentence_clean)

    return JDExtract(
        company=_normalize_whitespace(company),
        role_title=_normalize_whitespace(role_title),
        function=_normalize_whitespace(function),
        team=_normalize_whitespace(team),
        level=_normalize_whitespace(level),
        location=_normalize_whitespace(location),
        employment_type=_normalize_whitespace(employment_type),
        must_have_skills=must_have_skills,
        nice_to_have_skills=nice_to_have_skills,
        domain=_normalize_whitespace(domain),
        mission_signals=mission_signals[:MISSION_LIMIT],
        metrics_signals=metrics_signals[:METRIC_LIMIT],
        ats_keywords=ats_keywords[:ATS_KEYWORD_LIMIT],
    )


def _heuristic_bullets(
    selected_facts: List[Dict[str, Any]],
    jd_factors: Dict[str, Any],
) -> BulletsResponse:
    role = jd_factors.get("role_title") or "this role"
    company = jd_factors.get("company") or "the organization"
    bullets: List[str] = []
    for fact in selected_facts[:10]:
        fact_id = str(fact.get("id") or "")
        metadata = fact.get("metadata") or {}
        task_name = metadata.get("task_name") or metadata.get("title") or "key initiative"
        project_name = metadata.get("project_name") or metadata.get("organization") or metadata.get("org") or "project"
        skills = metadata.get("skills") or metadata.get("all_skills") or []
        metrics = metadata.get("matched_metrics") or metadata.get("metrics") or []
        skill_phrase = ""
        if skills:
            skill_phrase = f" using {', '.join(skills[:3])}"
        metric_phrase = ""
        if metrics:
            metric_phrase = f" delivering {', '.join(metrics[:2])}"
        core_sentence = f"{task_name} at {project_name}{skill_phrase}{metric_phrase}"
        bullet_text = f"[{fact_id}] {core_sentence.strip()} supports success in {role} at {company}."
        bullet_text = _limit_words(bullet_text, BULLET_WORD_LIMIT)
        if len(bullet_text) > 180:
            bullet_text = bullet_text[:177].rstrip() + "..."
        bullets.append(bullet_text)
    return BulletsResponse(bullets=bullets)


def _heuristic_cover_letter(
    selected_facts: List[Dict[str, Any]],
    jd_factors: Dict[str, Any],
    user_story: str,
) -> CoverLetterResponse:
    role = jd_factors.get("role_title") or "the open role"
    company = jd_factors.get("company") or "your team"
    fact_refs: List[str] = []

    intro = (
        f"Dear Hiring Team,\n"
        f"I am excited to express my interest in the {role} role at {company}. "
        "The scope of the position aligns closely with my experience and motivation."
    )

    highlight_paragraphs: List[str] = []
    for fact in selected_facts[:3]:
        fact_id = str(fact.get("id") or "")
        metadata = fact.get("metadata") or {}
        task_name = metadata.get("task_name") or "a key initiative"
        project_name = metadata.get("project_name") or metadata.get("organization") or "a project"
        skills = metadata.get("skills") or metadata.get("all_skills") or []
        metrics = metadata.get("matched_metrics") or metadata.get("metrics") or []
        tense = metadata.get("tense") or ("present" if metadata.get("is_current") else "past")

        skill_clause = f" leveraging {', '.join(skills[:3])}" if skills else ""
        metric_clause = f", delivering {', '.join(metrics[:2])}" if metrics else ""
        verb = "drive" if tense == "present" else "drove"
        paragraph = (
            f"In ({fact_id}), I {verb} {task_name} for {project_name}{skill_clause}{metric_clause}, "
            f"providing a strong signal for success in the {role} role."
        )
        highlight_paragraphs.append(paragraph)
        if fact_id:
            fact_refs.append(fact_id)

    if not highlight_paragraphs:
        highlight_paragraphs.append(
            "My background includes leading multi-disciplinary teams to translate strategy into measurable outcomes, "
            "experience that maps well to your expectations."
        )

    story_paragraph = (
        user_story.strip()
        if user_story.strip()
        else "I am motivated by missions that marry human impact with well-crafted systems, and I enjoy collaborating across functions."
    )

    closing = (
        "Thank you for considering my application. I'd welcome the opportunity to discuss how these experiences can contribute to your goals."
    )

    paragraphs = [intro] + highlight_paragraphs[:3] + [story_paragraph, closing]
    cover_letter = "\n\n".join(paragraphs[:5])
    return CoverLetterResponse(cover_letter=cover_letter.strip(), fact_refs=fact_refs)


class LLMPipeline:
    """Production-ready pipeline for OpenAI-backed JD and content generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        *,
        cover_letter_model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.cover_letter_model = cover_letter_model or os.getenv("COVER_LETTER_MODEL") or self.model
        self._graph_spec_cache: Optional[str] = None
        self._client = self._init_client()

    def _init_client(self) -> Optional[OpenAI]:
        if OpenAI is None:
            logger.info("OpenAI SDK not installed; LLMPipeline will fall back to heuristics.")
            return None
        if not self.api_key:
            logger.info("OPENAI_API_KEY not provided; LLMPipeline will fall back to heuristics.")
            return None
        try:
            return OpenAI(api_key=self.api_key)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to initialize OpenAI client: %s", exc)
            return None

    async def _call_llm(
        self,
        *,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]],
        model: Optional[str],
        temperature: float,
        max_output_tokens: int,
    ) -> Tuple[str, Dict[str, int], Optional[str]]:
        if self._client is None:
            raise LLMNotConfiguredError("OpenAI client is not configured.")

        model_name = model or self.model

        def _invoke() -> Tuple[str, Dict[str, int], Optional[str]]:
            kwargs: Dict[str, Any] = {
                "model": model_name,
                "input": messages,
                "temperature": temperature,
            }
            if response_format:
                kwargs["response_format"] = response_format
            if max_output_tokens:
                kwargs["max_output_tokens"] = max_output_tokens

            response = self._client.responses.create(**kwargs)
            text = _extract_response_text(response)
            usage = _usage_to_dict(getattr(response, "usage", None))
            actual_model = getattr(response, "model", model_name)
            return text, usage, actual_model

        try:
            return await asyncio.to_thread(_invoke)
        except Exception as exc:
            raise LLMCallError(str(exc)) from exc

    async def extract_job_facts(self, job_description: str) -> Dict[str, Any]:
        """Deprecated placeholder retained for backward compatibility."""
        jd_factors, _ = await self.extract_jd_factors(job_description)
        return jd_factors

    async def rank_experiences(
        self, experience_graph: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Placeholder retained for backward compatibility."""
        return experience_graph.get("experiences", [])

    async def compose_resume_bullets(
        self, ranked_experiences: List[Dict[str, Any]], job_context: Dict[str, Any]
    ) -> List[str]:
        """Placeholder retained for backward compatibility."""
        bullets, _ = await self.generate_bullets(ranked_experiences, job_context)
        return bullets

    async def compose_cover_letter(
        self, experience_graph: Dict[str, Any], job_context: Dict[str, Any]
    ) -> str:
        """Placeholder retained for backward compatibility."""
        cover_letter, _ = await self.generate_cover_letter(experience_graph, job_context, "")
        return cover_letter["cover_letter"]

    async def extract_jd_factors(self, jd_text: str) -> Tuple[Dict[str, Any], PipelineMetadata]:
        truncated_text = _truncate_text(jd_text.strip(), MAX_JD_CHARS)
        heuristic = _heuristic_extract_jd_factors(truncated_text)

        if self._client is None:
            heuristic.provenance = Provenance(source="heuristic", timestamp=_iso_now())
            return heuristic.dict(), {
                "status": "heuristic_only",
                "source": "heuristic",
                "model": None,
                "usage": {"total_tokens": 0},
            }

        schema = {
            "type": "object",
            "properties": {
                "company": {"type": ["string", "null"]},
                "role_title": {"type": ["string", "null"]},
                "function": {"type": ["string", "null"]},
                "team": {"type": ["string", "null"]},
                "level": {"type": ["string", "null"]},
                "location": {"type": ["string", "null"]},
                "employment_type": {"type": ["string", "null"]},
                "must_have_skills": {"type": "array", "items": {"type": "string"}},
                "nice_to_have_skills": {"type": "array", "items": {"type": "string"}},
                "domain": {"type": ["string", "null"]},
                "mission_signals": {"type": "array", "items": {"type": "string"}},
                "metrics_signals": {"type": "array", "items": {"type": "string"}},
                "ats_keywords": {"type": "array", "items": {"type": "string"}, "maxItems": ATS_KEYWORD_LIMIT},
            },
            "required": [
                "company",
                "role_title",
                "must_have_skills",
                "nice_to_have_skills",
                "mission_signals",
                "metrics_signals",
                "ats_keywords",
            ],
            "additionalProperties": False,
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a structured extraction agent. "
                    "Return ONLY valid JSON that matches the provided schema. "
                    "Use null for unknown scalar fields and empty arrays when no values fit."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Job description:\n"
                    f"{truncated_text}\n\n"
                    "Respond with a JSON object that matches the schema exactly."
                ),
            },
        ]

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "jd_extract",
                "schema": schema,
            },
        }

        last_exception: Optional[Exception] = None
        for attempt in range(2):
            try:
                raw_text, usage, model_used = await self._call_llm(
                    messages=messages,
                    response_format=response_format,
                    model=self.model,
                    temperature=0.1,
                    max_output_tokens=900,
                )
                payload = json.loads(raw_text)
                parsed = JDExtract.parse_obj(payload)
                parsed.mission_signals = parsed.mission_signals[:MISSION_LIMIT]
                parsed.metrics_signals = parsed.metrics_signals[:METRIC_LIMIT]
                parsed.ats_keywords = parsed.ats_keywords[:ATS_KEYWORD_LIMIT]
                parsed.provenance = Provenance(source="llm", timestamp=_iso_now())
                jd_dict = parsed.dict()
                jd_dict["provenance"] = parsed.provenance.dict()
                return jd_dict, {
                    "status": "llm_validated",
                    "source": "llm",
                    "model": model_used,
                    "usage": usage or {"total_tokens": 0},
                }
            except json.JSONDecodeError as exc:
                last_exception = exc
                logger.warning("JD extract JSON parsing failed (attempt %s): %s", attempt + 1, exc)
                continue
            except ValidationError as exc:
                last_exception = exc
                logger.warning("JD extract validation failed: %s", exc)
                break
            except (LLMCallError, LLMNotConfiguredError) as exc:
                last_exception = exc
                logger.warning("JD extract LLM call failed: %s", exc)
                break

        logger.info("Falling back to heuristic JD extraction due to error: %s", last_exception)
        heuristic.provenance = Provenance(source="heuristic", timestamp=_iso_now())
        jd_dict = heuristic.dict()
        jd_dict["provenance"] = heuristic.provenance.dict()
        return jd_dict, {
            "status": "heuristic_fallback",
            "source": "heuristic",
            "model": None,
            "usage": {"total_tokens": 0},
        }

    async def generate_bullets(
        self,
        selected_facts: List[Dict[str, Any]],
        jd_factors: Dict[str, Any],
    ) -> Tuple[List[str], PipelineMetadata]:
        if not selected_facts:
            return [], {
                "status": "skipped_no_facts",
                "source": "heuristic",
                "model": None,
                "usage": {"total_tokens": 0},
            }

        heuristic_response = _heuristic_bullets(selected_facts, jd_factors)

        if self._client is None:
            return heuristic_response.bullets, {
                "status": "heuristic_only",
                "source": "heuristic",
                "model": None,
                "usage": {"total_tokens": 0},
            }

        facts_payload = []
        for fact in selected_facts[:10]:
            metadata = fact.get("metadata") or {}
            fact_payload = {
                "fact_id": str(fact.get("id") or ""),
                "task_name": metadata.get("task_name") or metadata.get("title"),
                "project_name": metadata.get("project_name") or metadata.get("organization"),
                "description": metadata.get("task_description") or metadata.get("description"),
                "metrics": metadata.get("matched_metrics") or metadata.get("metrics") or [],
                "skills": metadata.get("skills") or metadata.get("all_skills") or [],
                "tense": metadata.get("tense") or ("present" if metadata.get("is_current") else "past"),
            }
            facts_payload.append(fact_payload)

        jd_summary = {
            "company": jd_factors.get("company"),
            "role_title": jd_factors.get("role_title"),
            "function": jd_factors.get("function"),
            "must_have_skills": jd_factors.get("must_have_skills"),
            "nice_to_have_skills": jd_factors.get("nice_to_have_skills"),
            "ats_keywords": jd_factors.get("ats_keywords"),
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You craft resume bullet points.\n"
                    "- Output JSON only.\n"
                    "- Each bullet must reference exactly one fact_id using the format \"[fact_id] bullet\".\n"
                    "- Max 22 words per bullet; use numerals for numbers.\n"
                    "- Present tense for current initiatives, past tense otherwise.\n"
                    "- No fabrication; stay faithful to provided facts and JD context.\n"
                    "- Naturally weave in ATS keywords when relevant.\n"
                    "- Return at most 10 bullets."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Job factors:\n"
                    f"{json.dumps(jd_summary, ensure_ascii=False, indent=2)}\n\n"
                    "Selected facts:\n"
                    f"{json.dumps(facts_payload, ensure_ascii=False, indent=2)}\n\n"
                    "Respond with JSON like {\"bullets\": [{\"fact_id\": \"...\", \"text\": \"...\"}]}."
                ),
            },
        ]

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "bullets_response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "bullets": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": min(len(facts_payload), 10),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "fact_id": {"type": "string"},
                                    "text": {"type": "string"},
                                },
                                "required": ["fact_id", "text"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["bullets"],
                    "additionalProperties": False,
                },
            },
        }

        try:
            raw_text, usage, model_used = await self._call_llm(
                messages=messages,
                response_format=response_format,
                model=self.model,
                temperature=0.2,
                max_output_tokens=600,
            )
            payload = json.loads(raw_text)
            bullets_raw = payload.get("bullets", [])
            if not isinstance(bullets_raw, list) or not bullets_raw:
                raise ValueError("bullets missing from response")

            formatted: List[str] = []
            fact_ids = [str(fact.get("id") or "") for fact in selected_facts if fact.get("id")]
            for idx, item in enumerate(bullets_raw[:10]):
                fact_id = str(item.get("fact_id") or "")
                if not fact_id and idx < len(fact_ids):
                    fact_id = fact_ids[idx]
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                bullet_text = f"[{fact_id}] {text}".strip()
                bullet_text = _limit_words(bullet_text, BULLET_WORD_LIMIT)
                if len(bullet_text) > 180:
                    bullet_text = bullet_text[:177].rstrip() + "..."
                if fact_id and fact_ids and fact_id not in fact_ids:
                    logger.debug("LLM bullet fact_id %s not in selected facts.", fact_id)
                formatted.append(bullet_text)

            validated = BulletsResponse(bullets=formatted)

            # Enforce 1:1 traceability by ensuring each bullet includes a fact_id marker.
            traceable = []
            remaining_ids = [str(fact.get("id")) for fact in selected_facts if fact.get("id")]
            for idx, bullet in enumerate(validated.bullets):
                if "[" not in bullet or "]" not in bullet:
                    fallback_id = remaining_ids[idx] if idx < len(remaining_ids) else remaining_ids[-1] if remaining_ids else ""
                    prefix = f"[{fallback_id}] " if fallback_id else ""
                    bullet = prefix + bullet
                traceable.append(bullet)

            final_bullets = BulletsResponse(bullets=traceable).bullets
            return final_bullets, {
                "status": "llm_validated",
                "source": "llm",
                "model": model_used,
                "usage": usage or {"total_tokens": 0},
            }
        except (json.JSONDecodeError, ValidationError, LLMCallError, LLMNotConfiguredError, ValueError) as exc:
            logger.warning("Bullet generation failed with LLM; using heuristic fallback: %s", exc)
            return heuristic_response.bullets, {
                "status": "heuristic_fallback",
                "source": "heuristic",
                "model": None,
                "usage": {"total_tokens": 0},
            }

    async def generate_cover_letter(
        self,
        selected_facts: List[Dict[str, Any]],
        jd_factors: Dict[str, Any],
        user_story: str,
    ) -> Tuple[Dict[str, Any], PipelineMetadata]:
        heuristic_response = _heuristic_cover_letter(selected_facts, jd_factors, user_story)

        if self._client is None:
            return heuristic_response.dict(), {
                "status": "heuristic_only",
                "source": "heuristic",
                "model": None,
                "usage": {"total_tokens": 0},
            }

        facts_payload = []
        for fact in selected_facts[:5]:
            metadata = fact.get("metadata") or {}
            facts_payload.append(
                {
                    "fact_id": str(fact.get("id") or ""),
                    "task_name": metadata.get("task_name") or metadata.get("title"),
                    "description": metadata.get("task_description") or metadata.get("description"),
                    "metrics": metadata.get("matched_metrics") or metadata.get("metrics") or [],
                    "skills": metadata.get("skills") or metadata.get("all_skills") or [],
                    "tense": metadata.get("tense") or ("present" if metadata.get("is_current") else "past"),
                }
            )

        jd_summary = {
            "company": jd_factors.get("company"),
            "role_title": jd_factors.get("role_title"),
            "mission_signals": jd_factors.get("mission_signals"),
            "domain": jd_factors.get("domain"),
            "team": jd_factors.get("team"),
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You are writing a concise and tailored cover letter.\n"
                    "- Provide 3 to 5 short paragraphs.\n"
                    "- Each paragraph must anchor to a distinct fact_id drawn from the provided facts.\n"
                    "- Reference the company and role title at least once.\n"
                    "- Avoid generic filler and do not repeat the job description verbatim.\n"
                    "- Use JSON response only."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Job factors:\n"
                    f"{json.dumps(jd_summary, ensure_ascii=False, indent=2)}\n\n"
                    "Selected facts:\n"
                    f"{json.dumps(facts_payload, ensure_ascii=False, indent=2)}\n\n"
                    f"User story:\n{user_story.strip() or 'None provided.'}\n\n"
                    "Respond with JSON like {\"cover_letter\": \"...\", \"fact_refs\": [\"fact_id_1\", ...]}."
                ),
            },
        ]

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "cover_letter_response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "cover_letter": {"type": "string"},
                        "fact_refs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                    },
                    "required": ["cover_letter", "fact_refs"],
                    "additionalProperties": False,
                },
            },
        }

        try:
            raw_text, usage, model_used = await self._call_llm(
                messages=messages,
                response_format=response_format,
                model=self.cover_letter_model,
                temperature=0.35,
                max_output_tokens=1200,
            )
            payload = json.loads(raw_text)
            parsed = CoverLetterResponse.parse_obj(payload)
            parsed.fact_refs = list(dict.fromkeys(parsed.fact_refs))
            valid_fact_ids = {str(fact.get("id") or "") for fact in selected_facts if fact.get("id")}
            if valid_fact_ids:
                filtered_refs = [fact_id for fact_id in parsed.fact_refs if fact_id in valid_fact_ids]
                if filtered_refs:
                    parsed.fact_refs = filtered_refs
                else:
                    parsed.fact_refs = list(valid_fact_ids)[: len(parsed.fact_refs) or 3]

            paragraphs = [paragraph.strip() for paragraph in parsed.cover_letter.split("\n\n") if paragraph.strip()]
            if len(paragraphs) < 3 or len(paragraphs) > 5:
                logger.warning("Cover letter paragraph count out of bounds (%s); keeping content.", len(paragraphs))

            words = parsed.cover_letter.split()
            if len(words) > 1200:
                trimmed = " ".join(words[:1200]).rstrip()
                parsed.cover_letter = trimmed + "..."

            return parsed.dict(), {
                "status": "llm_validated",
                "source": "llm",
                "model": model_used,
                "usage": usage or {"total_tokens": 0},
            }
        except (json.JSONDecodeError, ValidationError, LLMCallError, LLMNotConfiguredError) as exc:
            logger.warning("Cover letter generation failed with LLM; using heuristic fallback: %s", exc)
            return heuristic_response.dict(), {
                "status": "heuristic_fallback",
                "source": "heuristic",
                "model": None,
                "usage": {"total_tokens": 0},
            }

    def get_graph_spec(self) -> str:
        """Return the canonical LLM build spec for the MyLife experience graph."""
        if self._graph_spec_cache is None:
            try:
                self._graph_spec_cache = MYLIFE_SPEC_PATH.read_text(encoding="utf-8")
            except FileNotFoundError:
                self._graph_spec_cache = ""
        return self._graph_spec_cache

    def load_graph_jsonl(
        self,
        jsonl_payload: str,
        session: Session,
        *,
        user_id: Optional[int] = None,
    ) -> "LoaderResult":
        """Validate and load a JSONL payload representing graph updates."""
        from graph.loader import GraphLoader  # local import to avoid heavy dependencies during smoke tests

        loader = GraphLoader(session, user_id=user_id)
        stream = io.StringIO(jsonl_payload)
        return loader.load_stream(stream)
