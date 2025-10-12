"""Pydantic schemas and tool specifications."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import BundleKind


class BaseSchema(BaseModel):
    """Shared model configuration enforcing immutability and type safety."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class BundleBase(BaseSchema):
    """Common fields for bundle operations."""

    user_id: str = Field(..., min_length=1, max_length=128)
    hash: str = Field(..., min_length=1, max_length=256)


class SetGenerationBundleRequest(BundleBase):
    """Request payload to upsert the resume generation bundle."""

    plan: Dict[str, Any]
    resolved_jd: Dict[str, Any]
    prefs: Dict[str, Any]
    ttl_seconds: int = Field(default=604800, ge=60, le=60 * 60 * 24 * 30)


class SetCoverLetterBundleRequest(BundleBase):
    """Request payload to upsert the cover-letter bundle."""

    jd: Dict[str, Any]
    story_plan: Dict[str, Any]
    prefs: Dict[str, Any]
    ttl_seconds: int = Field(default=604800, ge=60, le=60 * 60 * 24 * 30)


class GetBundleRequest(BundleBase):
    """Request payload to fetch a bundle."""


class BundleAck(BaseSchema):
    """Generic acknowledgement response."""

    ok: bool = True


class BundlePayload(BaseSchema):
    """Represent a bundle payload with metadata."""

    user_id: str
    hash: str
    kind: BundleKind
    payload: Dict[str, Any]
    ttl_seconds: int


class BundleResponse(BaseSchema):
    """Response for bundle retrieval."""

    ok: bool
    bundle: Optional[BundlePayload] = None

    @model_validator(mode="after")
    def validate_bundle_presence(self) -> "BundleResponse":
        """Ensure bundle presence aligns with ok flag."""
        if self.ok and self.bundle is None:
            msg = "Bundle payload required when ok is true."
            raise ValueError(msg)
        return self


class CandidateFacetsResponse(BaseSchema):
    """Aggregated candidate facets."""

    ok: bool = True
    skills: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    degrees: List[str] = Field(default_factory=list)


class CandidateFacetsRequest(BaseSchema):
    """Request payload for candidate facet aggregation."""

    user_id: str = Field(..., min_length=1, max_length=128)
    limit: int = Field(default=100, ge=1, le=500)


class SearchExperiencesRequest(BaseSchema):
    """Request payload for experience search."""

    user_id: str = Field(..., min_length=1, max_length=128)
    query: Optional[str] = Field(default=None, max_length=2000)
    must_terms: List[str] = Field(default_factory=list)
    nice_terms: List[str] = Field(default_factory=list)
    selected_ids: List[str] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchMatch(BaseSchema):
    """Individual search result entry."""

    experience_id: str
    score: float
    matched_terms: List[str] = Field(default_factory=list)


class SearchExperiencesResponse(BaseSchema):
    """Paginated search response."""

    ok: bool = True
    items: List[SearchMatch] = Field(default_factory=list)
    next_page_token: Optional[str] = None


class EvidenceRequest(BaseSchema):
    """Request for a single experience evidence payload."""

    experience_id: str = Field(..., min_length=1, max_length=128)
    include_artifacts: bool = True


class EvidenceBatchRequest(BaseSchema):
    """Request for batched evidence retrieval."""

    experience_ids: List[str] = Field(..., min_length=1)


class ExperienceEvidence(BaseSchema):
    """Evidence representation for an experience."""

    experience_id: str
    title: str
    summary: str
    bullets: List[str]
    metrics: List[str]
    tags: List[str]
    dates: Dict[str, Optional[str]]
    artifacts: List[str]


class EvidenceResponse(BaseSchema):
    """Response wrapper for single evidence endpoint."""

    ok: bool = True
    evidence: ExperienceEvidence


class EvidenceBatchResponse(BaseSchema):
    """Batch evidence response."""

    ok: bool = True
    items: List[ExperienceEvidence] = Field(default_factory=list)


class CompanyInsightsRequest(BaseSchema):
    """Stub request for company insights."""

    company_name: str = Field(..., min_length=1, max_length=256)
    limit: int = Field(default=5, ge=1, le=20)


class CompanyInsightsResponse(BaseSchema):
    """Response for company insights stub."""

    ok: bool = True
    company_name: str
    insights: List[str] = Field(default_factory=list)


AGENTKIT_TOOL_SPEC: Dict[str, Any] = {
    "tools": [
        {
            "name": "get_candidate_facets",
            "description": "Return normalized candidate facets: skills, domains, tools, degrees.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "default": 100},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "search_experiences",
            "description": "Search MyLife experiences relevant to JD. Returns ranked IDs and match info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "query": {"type": "string"},
                    "must_terms": {"type": "array", "items": {"type": "string"}, "default": []},
                    "nice_terms": {"type": "array", "items": {"type": "string"}, "default": []},
                    "selected_ids": {"type": "array", "items": {"type": "string"}, "default": []},
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "get_evidence",
            "description": "Fetch rich evidence for one experience. Include metrics, dates, role, artifacts, tags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "experience_id": {"type": "string"},
                    "include_artifacts": {"type": "boolean", "default": True},
                },
                "required": ["experience_id"],
            },
        },
        {
            "name": "get_evidence_batch",
            "description": "Fetch evidence for multiple experiences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "experience_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["experience_ids"],
            },
        },
        {
            "name": "set_generation_bundle",
            "description": "Upsert the resume-generation bundle for a run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "hash": {"type": "string"},
                    "plan": {"type": "object"},
                    "resolved_jd": {"type": "object"},
                    "prefs": {"type": "object"},
                    "ttl_seconds": {"type": "integer", "default": 604800},
                },
                "required": ["user_id", "hash", "plan", "resolved_jd", "prefs"],
            },
        },
        {
            "name": "get_generation_bundle",
            "description": "Fetch the resume-generation bundle for a run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "hash": {"type": "string"},
                },
                "required": ["user_id", "hash"],
            },
        },
        {
            "name": "set_cl_bundle",
            "description": "Upsert the cover-letter bundle for a run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "hash": {"type": "string"},
                    "jd": {"type": "object"},
                    "story_plan": {"type": "object"},
                    "prefs": {"type": "object"},
                    "ttl_seconds": {"type": "integer", "default": 604800},
                },
                "required": ["user_id", "hash", "jd", "story_plan", "prefs"],
            },
        },
        {
            "name": "get_cl_bundle",
            "description": "Fetch the cover-letter bundle for a run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "hash": {"type": "string"},
                },
                "required": ["user_id", "hash"],
            },
        },
        {
            "name": "get_company_insights",
            "description": "Optional helper for cover letters. Returns brief insights about the company from internal notes or cached sources.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["company_name"],
            },
        },
    ]
}
