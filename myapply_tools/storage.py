"""Persistence helpers for the MyApply AgentKit tool service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlmodel import Session, select

from .models import Bundle, BundleKind, Experience


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _normalize_timestamp(value: datetime) -> datetime:
    """Ensure a timestamp is timezone-aware in UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_expired(bundle: Bundle, now: datetime) -> bool:
    """Determine whether a bundle record has expired."""

    elapsed = (now - _normalize_timestamp(bundle.updated_at)).total_seconds()
    return elapsed > float(bundle.ttl_seconds)


def upsert_bundle(
    session: Session,
    *,
    kind: BundleKind,
    user_id: str,
    hash_value: str,
    payload: Dict[str, Any],
    ttl_seconds: int,
) -> Bundle:
    """Insert or update a bundle record."""

    statement = select(Bundle).where(
        Bundle.kind == kind,
        Bundle.user_id == user_id,
        Bundle.hash == hash_value,
    )
    record = session.exec(statement).first()
    now = utc_now()
    if record:
        record.payload = payload
        record.ttl_seconds = ttl_seconds
        record.updated_at = now
    else:
        record = Bundle(
            kind=kind,
            user_id=user_id,
            hash=hash_value,
            payload=payload,
            ttl_seconds=ttl_seconds,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_bundle(
    session: Session,
    *,
    kind: BundleKind,
    user_id: str,
    hash_value: str,
) -> Optional[Bundle]:
    """Retrieve a bundle, deleting it if expired."""

    statement = select(Bundle).where(
        Bundle.kind == kind,
        Bundle.user_id == user_id,
        Bundle.hash == hash_value,
    )
    record = session.exec(statement).first()
    if record is None:
        return None
    now = utc_now()
    if _is_expired(record, now):
        session.delete(record)
        session.commit()
        return None
    return record


def prune_expired_bundles(session: Session) -> int:
    """Remove bundles whose TTL has elapsed."""

    statement = select(Bundle)
    expired: List[Bundle] = []
    now = utc_now()
    for bundle in session.exec(statement):
        if _is_expired(bundle, now):
            expired.append(bundle)
    for bundle in expired:
        session.delete(bundle)
    if expired:
        session.commit()
    return len(expired)


def list_experiences(session: Session, *, user_id: str) -> List[Experience]:
    """Return all experiences for a user."""

    statement = select(Experience).where(Experience.user_id == user_id)
    return list(session.exec(statement))


def get_experience(session: Session, *, user_id: str, experience_id: str) -> Optional[Experience]:
    """Retrieve a single experience for the specified user."""

    statement = select(Experience).where(
        Experience.user_id == user_id,
        Experience.id == experience_id,
    )
    return session.exec(statement).first()


def get_experiences_batch(session: Session, *, user_id: str, experience_ids: Iterable[str]) -> List[Experience]:
    """Return multiple experiences for a user."""

    identifiers = list(experience_ids)
    if not identifiers:
        return []
    statement = select(Experience).where(
        Experience.user_id == user_id,
        Experience.id.in_(identifiers),
    )
    return list(session.exec(statement))


def seed_demo_data(session: Session) -> None:
    """Populate demo experiences if none exist."""

    if session.exec(select(Experience).limit(1)).first():
        return

    now = utc_now()
    demo_records = [
        Experience(
            id="exp-001",
            user_id="demo-user",
            title="Operations Analyst Intern",
            summary="Automated reporting workflows and delivered data dashboards.",
            text="Automated reporting workflows for operations leadership, reducing manual effort.",
            tags=["operations", "automation", "analytics"],
            skills=["Python", "SQL", "Automation"],
            domains=["Aviation", "Analytics"],
            tools=["Python", "Tableau"],
            degrees=["BS Industrial Engineering"],
            bullets=[
                "Built an automated ingestion pipeline for weekly pilot operations metrics.",
                "Partnered with analytics team to surface insights in Tableau dashboards.",
            ],
            metrics=["-40% cycle time", "+3% on-time performance"],
            artifacts=["tableau-dashboard-link"],
            start_date="2024-01-01",
            end_date="2024-06-30",
            created_at=now,
            updated_at=now,
        ),
        Experience(
            id="exp-002",
            user_id="demo-user",
            title="Data Visualization Specialist",
            summary="Designed executive-ready dashboards highlighting SLA adherence.",
            text="Designed dashboards showcasing SLA adherence with drilldowns for leadership.",
            tags=["visualization", "dashboards"],
            skills=["Data Visualization", "Communication"],
            domains=["Analytics"],
            tools=["Power BI", "Python"],
            degrees=["BS Industrial Engineering"],
            bullets=[
                "Developed executive dashboards tracking SLA adherence across 5 regions.",
                "Standardized visualization templates adopted by 6 partner teams.",
            ],
            metrics=["+15% stakeholder satisfaction"],
            artifacts=["powerbi-report"],
            start_date="2023-03-01",
            end_date="2023-12-15",
            created_at=now,
            updated_at=now,
        ),
        Experience(
            id="exp-003",
            user_id="demo-user",
            title="Process Improvement Lead",
            summary="Led cross-functional Kaizen reducing turnaround time.",
            text="Led cross-functional Kaizen initiative reducing turnaround time across maintenance hubs.",
            tags=["process", "lean", "kaizen"],
            skills=["Process Improvement", "Leadership"],
            domains=["Operations"],
            tools=["Miro", "Excel"],
            degrees=["BS Industrial Engineering"],
            bullets=[
                "Facilitated Kaizen focused on maintenance throughput with 12 stakeholders.",
                "Implemented visual management board improving communication cadence.",
            ],
            metrics=["-25% turnaround time"],
            artifacts=["miro-board"],
            start_date="2022-06-01",
            end_date="2022-11-30",
            created_at=now,
            updated_at=now,
        ),
    ]
    for experience in demo_records:
        session.add(experience)
    session.commit()
