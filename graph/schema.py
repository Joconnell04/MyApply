from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, Literal, Optional, Tuple, Type, Union, cast
from uuid import uuid4

from pydantic import BaseModel, Field, PositiveInt, UUID4, conint, confloat, root_validator, validator


class PrivacyLevel(str, Enum):
    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC = "public"


class IngestionSource(str, Enum):
    LLM = "LLM"
    MANUAL = "manual"
    IMPORT = "import"
    CATALOG = "catalog"


class NodeType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    ROLE = "Role"
    PROJECT = "Project"
    TASK = "Task"
    SKILL = "Skill"
    TOOL = "Tool"
    DATASET = "Dataset"
    OUTCOME = "Outcome"
    METRIC = "Metric"
    EVIDENCE = "Evidence"
    CREDENTIAL = "Credential"
    PUBLICATION = "Publication"
    EVENT = "Event"
    DECISION = "Decision"
    ISSUE = "Issue"
    SOURCETEXT = "SourceText"


class EdgeType(str, Enum):
    HAS_MEMBER = "HAS_MEMBER"
    HELD_ROLE_AT = "HELD_ROLE_AT"
    ROLE_AT_ORG = "ROLE_AT_ORG"
    WORKED_ON = "WORKED_ON"
    CONTAINS_TASK = "CONTAINS_TASK"
    USED_TOOL = "USED_TOOL"
    USED_DATASET = "USED_DATASET"
    APPLIED_SKILL = "APPLIED_SKILL"
    PRODUCED_OUTCOME = "PRODUCED_OUTCOME"
    MEASURED_BY = "MEASURED_BY"
    SUPPORTED_BY = "SUPPORTED_BY"
    EARNED = "EARNED"
    PUBLISHED = "PUBLISHED"
    ATTENDED = "ATTENDED"
    MADE_DECISION = "MADE_DECISION"
    RAISED_ISSUE = "RAISED_ISSUE"
    RESOLVED_BY = "RESOLVED_BY"
    TRACE_TO_TEXT = "TRACE_TO_TEXT"


class RoleEmploymentType(str, Enum):
    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    INTERN = "Intern"
    CO_OP = "Co-op"
    CONTRACT = "Contract"
    VOLUNTEER = "Volunteer"


class RoleLocationMode(str, Enum):
    ONSITE = "Onsite"
    HYBRID = "Hybrid"
    REMOTE = "Remote"


class JobFunction(str, Enum):
    ANALYTICS = "Analytics"
    AUTOMATION = "Automation"
    SOFTWARE = "Software"
    PM = "PM"
    OPS = "Ops"


class ProjectStatus(str, Enum):
    PLANNED = "Planned"
    IN_PROGRESS = "In-Progress"
    COMPLETED = "Completed"
    ON_HOLD = "On-Hold"


class ProjectDomain(str, Enum):
    FLIGHT_OPS = "Flight Ops"
    AIRLINE_ANALYTICS = "Airline Analytics"
    FINTECH = "Fintech"
    DATA_PLATFORM = "Data Platform"
    RESEARCH = "Research"
    ETL = "ETL"
    AUTOMATION = "Automation"
    WEB = "Web"
    UI_UX = "UI/UX"
    GOVERNANCE = "Governance"


class SkillCategory(str, Enum):
    PROGRAMMING = "Programming"
    DATA = "Data"
    ML = "ML"
    CLOUD = "Cloud"
    PM = "PM"
    DESIGN = "Design"
    DOMAIN = "Domain"
    HARDWARE = "Hardware"


class SkillLevel(str, Enum):
    NOVICE = "Novice"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"
    EXPERT = "Expert"


class ToolCategory(str, Enum):
    BI = "BI"
    ETL = "ETL"
    DB = "DB"
    IDE = "IDE"
    AUTOMATION = "Automation"
    CLOUD = "Cloud"
    VERSION_CONTROL = "VersionControl"
    OTHER = "Other"


class DatasetSensitivity(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"


class OutcomeCategory(str, Enum):
    COST = "Cost"
    SPEED = "Speed"
    QUALITY = "Quality"
    RELIABILITY = "Reliability"
    REVENUE = "Revenue"
    ADOPTION = "Adoption"


class MetricUnit(str, Enum):
    HOURS = "hours"
    DOLLARS = "$"
    PERCENT = "%"
    COUNT = "count"


class MetricDirection(str, Enum):
    HIGHER_IS_BETTER = "HigherIsBetter"
    LOWER_IS_BETTER = "LowerIsBetter"
    TARGET = "Target"


class EvidenceKind(str, Enum):
    DOC = "Doc"
    PR = "PR"
    SCREENSHOT = "Screenshot"
    EMAIL = "Email"
    TICKET = "Ticket"
    PRESENTATION = "Presentation"
    DATASET = "Dataset"
    PAPER = "Paper"


class EvidenceAccess(str, Enum):
    PUBLIC = "public"
    RESTRICTED = "restricted"
    PRIVATE = "private"


class PublicationVenue(str, Enum):
    BLOG = "Blog"
    JOURNAL = "Journal"
    CONFERENCE = "Conference"
    INTERNAL = "Internal"


class EventKind(str, Enum):
    INTERVIEW = "Interview"
    RELEASE = "Release"
    DEMO = "Demo"
    TALK = "Talk"
    MEETING = "Meeting"


class IssueSeverity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class Provenance(BaseModel):
    ingested_from: IngestionSource = Field(default=IngestionSource.MANUAL)
    source_doc_id: Optional[str] = None
    source_span: str = Field(default="N/A")
    curator: str = Field(default="system")


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class BaseGraphObject(BaseModel):
    id: UUID4 = Field(default_factory=uuid4)
    type: Literal["node", "edge"]
    version: PositiveInt = Field(default=1)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    confidence: confloat(ge=0.0, le=1.0) = Field(default=0.8)
    privacy: PrivacyLevel = Field(default=PrivacyLevel.INTERNAL)
    labels: list[str] = Field(default_factory=list)
    provenance: Provenance

    @validator("labels", pre=True, always=True)
    def _default_labels(cls, value: Optional[Iterable[str]]) -> list[str]:
        if not value:
            return []
        # preserve order while removing duplicates
        seen = set()
        ordered = []
        for label in value:
            if label not in seen:
                seen.add(label)
                ordered.append(label)
        return ordered


class PersonData(BaseModel):
    full_name: str
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    links: list[str] = Field(default_factory=list)
    profiles: Dict[str, str] = Field(default_factory=dict)


class OrganizationSize(str, Enum):
    SIZE_1_10 = "1-10"
    SIZE_11_50 = "11-50"
    SIZE_51_200 = "51-200"
    SIZE_201_1000 = "201-1000"
    SIZE_1001_5000 = "1001-5000"
    SIZE_5001_PLUS = "5001+"


class OrganizationData(BaseModel):
    name: str
    sector: str
    size: OrganizationSize
    locations: list[str] = Field(default_factory=list)


class RoleData(BaseModel):
    title: str
    employment_type: RoleEmploymentType
    start_date: date
    end_date: Optional[date] = None
    location_mode: RoleLocationMode
    job_functions: list[JobFunction] = Field(default_factory=list)


class ProjectData(BaseModel):
    name: str
    summary: str
    start_date: date
    end_date: Optional[date] = None
    status: ProjectStatus
    domain: list[ProjectDomain]


class TaskData(BaseModel):
    name: str
    description: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    effort_hours: float = Field(default=0.0, ge=0.0)
    outcome: Optional[str] = None


class SkillData(BaseModel):
    name: str
    category: SkillCategory
    level: SkillLevel
    evidence_metric_ids: list[UUID4] = Field(default_factory=list)


class ToolData(BaseModel):
    name: str
    vendor: Optional[str] = None
    category: ToolCategory


class TimeRange(BaseModel):
    start: date
    end: Optional[date] = None

    @root_validator(skip_on_failure=True)
    def _validate_range(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        start = values.get("start")
        end = values.get("end")
        if start and end and end < start:
            raise ValueError("time_range.end cannot be before start")
        return values


class DatasetData(BaseModel):
    name: str
    schema_desc: str
    record_count: conint(ge=0) = 0  # type: ignore[assignment]
    sensitivity: DatasetSensitivity
    retention_policy: Optional[str] = None
    time_range: TimeRange


class OutcomeData(BaseModel):
    title: str
    description: str
    category: OutcomeCategory
    metric_impacts: list[UUID4] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)


class MetricData(BaseModel):
    name: str
    unit: MetricUnit
    baseline_value: float = 0.0
    baseline_date: Optional[date] = None
    final_value: float = 0.0
    final_date: Optional[date] = None
    direction: MetricDirection
    calculation_notes: Optional[str] = None

    @validator("final_value")
    def _check_final_value(cls, value: float) -> float:
        return float(value)

    @validator("baseline_value")
    def _check_baseline_value(cls, value: float) -> float:
        return float(value)


class EvidenceData(BaseModel):
    kind: EvidenceKind
    title: str
    uri: str
    access: EvidenceAccess


class CredentialData(BaseModel):
    name: str
    issuer: str
    issue_date: date
    expire_date: Optional[date] = None
    credential_id: Optional[str] = None
    link: Optional[str] = None


class PublicationData(BaseModel):
    title: str
    venue: PublicationVenue
    date: date
    url: Optional[str] = None


class EventData(BaseModel):
    name: str
    date: date
    kind: EventKind
    notes: Optional[str] = None


class DecisionData(BaseModel):
    statement: str
    date: date
    options_considered: list[str] = Field(default_factory=list)
    rationale: str


class IssueData(BaseModel):
    title: str
    severity: IssueSeverity
    opened: date
    closed: Optional[date] = None
    summary: str


class SourceTextData(BaseModel):
    text: str
    lang: str = "en"
    source_ref: Optional[str] = None


NodeDataModel = Union[
    PersonData,
    OrganizationData,
    RoleData,
    ProjectData,
    TaskData,
    SkillData,
    ToolData,
    DatasetData,
    OutcomeData,
    MetricData,
    EvidenceData,
    CredentialData,
    PublicationData,
    EventData,
    DecisionData,
    IssueData,
    SourceTextData,
]


NODE_DATA_MODEL_MAP: Dict[NodeType, Type[BaseModel]] = {
    NodeType.PERSON: PersonData,
    NodeType.ORGANIZATION: OrganizationData,
    NodeType.ROLE: RoleData,
    NodeType.PROJECT: ProjectData,
    NodeType.TASK: TaskData,
    NodeType.SKILL: SkillData,
    NodeType.TOOL: ToolData,
    NodeType.DATASET: DatasetData,
    NodeType.OUTCOME: OutcomeData,
    NodeType.METRIC: MetricData,
    NodeType.EVIDENCE: EvidenceData,
    NodeType.CREDENTIAL: CredentialData,
    NodeType.PUBLICATION: PublicationData,
    NodeType.EVENT: EventData,
    NodeType.DECISION: DecisionData,
    NodeType.ISSUE: IssueData,
    NodeType.SOURCETEXT: SourceTextData,
}


class GraphNodePayload(BaseGraphObject):
    type: Literal["node"] = "node"
    node_type: NodeType
    data: NodeDataModel  # type: ignore[assignment]

    @root_validator(pre=True)
    def _ensure_data_model(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        raw_data = values.get("data", {})
        node_type = values.get("node_type")
        if isinstance(raw_data, BaseModel):
            return values
        if not node_type:
            raise ValueError("node_type is required for GraphNodePayload")
        node_type_enum = NodeType(node_type)
        data_model = NODE_DATA_MODEL_MAP[node_type_enum]
        values["data"] = data_model(**raw_data)
        return values

    @validator("privacy", pre=True, always=True)
    def _default_privacy(cls, value: Optional[PrivacyLevel], values: Dict[str, Any]) -> PrivacyLevel:
        if value is not None:
            return PrivacyLevel(value)
        node_type = values.get("node_type")
        if node_type:
            node_type_enum = node_type if isinstance(node_type, NodeType) else NodeType(node_type)
            return get_default_privacy(node_type_enum)
        return PrivacyLevel.INTERNAL

    def dict(self, **kwargs: Any) -> Dict[str, Any]:
        base = super().dict(**kwargs)
        data_model = cast(BaseModel, self.data)
        base["data"] = data_model.dict()
        return base


class GraphEdgePayload(BaseGraphObject):
    type: Literal["edge"] = "edge"
    edge_type: EdgeType
    from_id: UUID4
    to_id: UUID4
    since: Optional[date] = None
    until: Optional[date] = None

    @validator("until")
    def _validate_dates(cls, until: Optional[date], values: Dict[str, Any]) -> Optional[date]:
        since = values.get("since")
        if since and until and until < since:
            raise ValueError("until cannot be before since")
        return until


GraphObjectPayload = Union[GraphNodePayload, GraphEdgePayload]


def serialize_graph_object(obj: GraphObjectPayload) -> Dict[str, Any]:
    """Serialize a graph payload to a JSON-safe dictionary."""
    payload = obj.dict()
    payload["id"] = str(obj.id)
    if isinstance(obj, GraphEdgePayload):
        payload["from_id"] = str(obj.from_id)
        payload["to_id"] = str(obj.to_id)
        if obj.since:
            payload["since"] = obj.since.isoformat()
        if obj.until:
            payload["until"] = obj.until.isoformat()
    else:
        payload.pop("from_id", None)
        payload.pop("to_id", None)
        payload.pop("since", None)
        payload.pop("until", None)
    payload["provenance"] = obj.provenance.dict()
    # Ensure datetime serialization
    payload["created_at"] = obj.created_at.isoformat()
    payload["updated_at"] = obj.updated_at.isoformat()
    return payload


def get_default_privacy(node_type: NodeType) -> PrivacyLevel:
    if node_type in {NodeType.DATASET, NodeType.EVIDENCE}:
        return PrivacyLevel.PRIVATE
    return PrivacyLevel.INTERNAL


def normalize_labels(labels: Iterable[str]) -> Tuple[str, ...]:
    seen = set()
    normalized = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            normalized.append(label)
    return tuple(normalized)
