"""Graph and experience related endpoints."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable, List, Sequence, Set

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from .. import storage
from ..deps import get_rate_limiter_dependency, get_session
from ..models import Experience
from ..schemas import (
    CandidateFacetsRequest,
    CandidateFacetsResponse,
    EvidenceBatchRequest,
    EvidenceBatchResponse,
    EvidenceRequest,
    EvidenceResponse,
    ExperienceEvidence,
    SearchExperiencesRequest,
    SearchExperiencesResponse,
    SearchMatch,
)
from ..security import AuthContext, require_auth

router = APIRouter(prefix="/tools", tags=["Graph"])

WORD_PATTERN = re.compile(r"[a-zA-Z0-9]+")


def _validate_user(auth: AuthContext, user_id: str) -> None:
    if auth.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User mismatch.")


def _tokenize(text: str) -> Set[str]:
    return {match.group(0).lower() for match in WORD_PATTERN.finditer(text)}


def _experience_text(exp: Experience) -> str:
    parts: List[str] = [
        exp.title,
        exp.summary,
        exp.text,
        " ".join(exp.tags),
        " ".join(exp.skills),
        " ".join(exp.domains),
        " ".join(exp.tools),
        " ".join(exp.bullets),
    ]
    return " ".join(part for part in parts if part)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_terms(values: Iterable[str]) -> Set[str]:
    terms: Set[str] = set()
    for value in values:
        terms.update(_tokenize(value))
    return terms


def _score_experience(
    exp: Experience,
    query_terms: Set[str],
    must_terms: Set[str],
    nice_terms: Set[str],
) -> tuple[float, Set[str]]:
    tokens = _tokenize(_experience_text(exp))
    if must_terms and not must_terms.issubset(tokens):
        return (0.0, set())
    matched: Set[str] = set()
    score = 1.0 if must_terms else 0.0
    for term in query_terms:
        if term in tokens:
            matched.add(term)
            score += 2.0
    for term in nice_terms:
        if term in tokens:
            matched.add(term)
            score += 1.0
    updated_at = exp.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    age_days = (_utc_now() - updated_at).days
    recency_boost = max(0.5, 1.0 - min(age_days, 365) / 365.0 * 0.5)
    return (score * recency_boost, matched)


def _paginate(items: Sequence[SearchMatch], page: int, page_size: int) -> tuple[List[SearchMatch], str | None]:
    start = (page - 1) * page_size
    end = start + page_size
    slice_items = list(items[start:end])
    next_page = None
    if end < len(items):
        next_page = str(page + 1)
    return slice_items, next_page


def _to_evidence(exp: Experience, include_artifacts: bool) -> ExperienceEvidence:
    return ExperienceEvidence(
        experience_id=exp.id,
        title=exp.title,
        summary=exp.summary,
        bullets=list(exp.bullets),
        metrics=list(exp.metrics),
        tags=list(exp.tags),
        dates={"start": exp.start_date, "end": exp.end_date},
        artifacts=list(exp.artifacts) if include_artifacts else [],
    )


@router.post(
    "/get_candidate_facets",
    response_model=CandidateFacetsResponse,
)
def get_candidate_facets(
    payload: CandidateFacetsRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> CandidateFacetsResponse:
    """Aggregate normalized facets for a candidate."""

    _validate_user(auth, payload.user_id)
    get_rate_limiter_dependency(auth.user_id)
    experiences = storage.list_experiences(session, user_id=payload.user_id)
    limit = payload.limit

    def harvest(values: Iterable[str]) -> List[str]:
        counter = Counter(value for value in values if value)
        ordered = [value for value, _ in counter.most_common(limit)]
        return ordered

    skills = harvest(tag for exp in experiences for tag in exp.skills)
    domains = harvest(tag for exp in experiences for tag in exp.domains)
    tools = harvest(tag for exp in experiences for tag in exp.tools)
    degrees = harvest(tag for exp in experiences for tag in exp.degrees)
    return CandidateFacetsResponse(skills=skills, domains=domains, tools=tools, degrees=degrees)


@router.post(
    "/search_experiences",
    response_model=SearchExperiencesResponse,
)
def search_experiences(
    payload: SearchExperiencesRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> SearchExperiencesResponse:
    """Search candidate experiences using a simple keyword scorer."""

    _validate_user(auth, payload.user_id)
    get_rate_limiter_dependency(auth.user_id)
    experiences = storage.list_experiences(session, user_id=payload.user_id)
    if payload.selected_ids:
        selected = set(payload.selected_ids)
        experiences = [exp for exp in experiences if exp.id in selected]

    query_terms = _tokenize(payload.query or "")
    must_terms = _normalize_terms(payload.must_terms)
    nice_terms = _normalize_terms(payload.nice_terms)

    matches: List[SearchMatch] = []
    for exp in experiences:
        score, matched = _score_experience(exp, query_terms, must_terms, nice_terms)
        if score <= 0 and not must_terms:
            continue
        matches.append(SearchMatch(experience_id=exp.id, score=score, matched_terms=sorted(matched)))

    matches.sort(key=lambda match: match.score, reverse=True)
    paginated, next_token = _paginate(matches, payload.page, payload.page_size)
    return SearchExperiencesResponse(items=paginated, next_page_token=next_token)


@router.post(
    "/get_evidence",
    response_model=EvidenceResponse,
)
def get_evidence(
    payload: EvidenceRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> EvidenceResponse:
    """Return the evidence for a specific experience."""

    get_rate_limiter_dependency(auth.user_id)
    exp = storage.get_experience(session, user_id=auth.user_id, experience_id=payload.experience_id)
    if exp is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experience not found.")
    evidence = _to_evidence(exp, payload.include_artifacts)
    return EvidenceResponse(evidence=evidence)


@router.post(
    "/get_evidence_batch",
    response_model=EvidenceBatchResponse,
)
def get_evidence_batch(
    payload: EvidenceBatchRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> EvidenceBatchResponse:
    """Return evidence for multiple experiences."""

    get_rate_limiter_dependency(auth.user_id)
    experiences = storage.get_experiences_batch(
        session,
        user_id=auth.user_id,
        experience_ids=payload.experience_ids,
    )
    evidence_map = {exp.id: _to_evidence(exp, include_artifacts=True) for exp in experiences}
    ordered = [evidence_map[exp_id] for exp_id in payload.experience_ids if exp_id in evidence_map]
    if not ordered:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No experiences found.")
    return EvidenceBatchResponse(items=ordered)
