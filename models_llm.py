from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, constr


class Provenance(BaseModel):
    source: Literal["llm", "heuristic"]
    timestamp: constr(strip_whitespace=True)


class JDExtract(BaseModel):
    company: Optional[str] = None
    role_title: Optional[str] = None
    function: Optional[str] = None
    team: Optional[str] = None
    level: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = None
    must_have_skills: List[constr(strip_whitespace=True)] = Field(default_factory=list)
    nice_to_have_skills: List[constr(strip_whitespace=True)] = Field(default_factory=list)
    domain: Optional[str] = None
    mission_signals: List[constr(strip_whitespace=True)] = Field(default_factory=list)
    metrics_signals: List[constr(strip_whitespace=True)] = Field(default_factory=list)
    ats_keywords: List[constr(strip_whitespace=True)] = Field(default_factory=list)
    provenance: Optional[Provenance] = None


class BulletsResponse(BaseModel):
    bullets: List[constr(strip_whitespace=True, max_length=180)] = Field(default_factory=list, max_items=10)


class CoverLetterResponse(BaseModel):
    cover_letter: constr(strip_whitespace=True, max_length=6000)
    fact_refs: List[constr(strip_whitespace=True)] = Field(default_factory=list)
