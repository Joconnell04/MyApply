#!/usr/bin/env python
"""
Seed demo data for MyApply.

Creates a sample user with a home location and three job applications with locations.

Usage:
    python scripts/seed_demo_data.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, create_engine, select

from app import get_settings
from auth import hash_password
from models import JobApplied, JobLocation, User

DEMO_EMAIL = "demo@myapply.dev"
DEMO_PASSWORD = "DemoPass123!"
DEMO_FULL_NAME = "Avery Candidate"
DEMO_HOME_LAT = 33.749
DEMO_HOME_LNG = -84.388


def _ensure_user(session: Session) -> User:
    user = session.exec(select(User).where(User.email == DEMO_EMAIL)).first()
    if user:
        user.full_name = user.full_name or DEMO_FULL_NAME
        user.home_lat = user.home_lat if user.home_lat is not None else DEMO_HOME_LAT
        user.home_lng = user.home_lng if user.home_lng is not None else DEMO_HOME_LNG
        user.mylife_json = user.mylife_json or {
            "summary": "Analytics leader focused on aviation, enterprise data, and healthcare IT transformations.",
            "roles": [
                {
                    "title": "Senior Data Analyst",
                    "company": "Delta Air Lines",
                    "start_year": 2020,
                    "highlights": [
                        "Built predictive models that reduced maintenance delays by 18%.",
                        "Partnered with OAP to align analytics roadmaps."
                    ],
                },
                {
                    "title": "Analytics Consultant",
                    "company": "IBM",
                    "start_year": 2017,
                    "end_year": 2020,
                    "highlights": [
                        "Led hybrid analytics engagements across NYC and RTP hub.",
                        "Implemented travel metrics reporting for Fortune 100 client."
                    ],
                },
            ],
            "skills": ["Python", "SQL", "Airflow", "Tableau"],
        }
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    user = User(
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name=DEMO_FULL_NAME,
        home_lat=DEMO_HOME_LAT,
        home_lng=DEMO_HOME_LNG,
        mylife_json={
            "summary": "Analytics leader focused on aviation, enterprise data, and healthcare IT transformations.",
            "roles": [
                {
                    "title": "Senior Data Analyst",
                    "company": "Delta Air Lines",
                    "start_year": 2020,
                    "highlights": [
                        "Built predictive models that reduced maintenance delays by 18%.",
                        "Partnered with OAP to align analytics roadmaps."
                    ],
                },
                {
                    "title": "Analytics Consultant",
                    "company": "IBM",
                    "start_year": 2017,
                    "end_year": 2020,
                    "highlights": [
                        "Led hybrid analytics engagements across NYC and RTP hub.",
                        "Implemented travel metrics reporting for Fortune 100 client."
                    ],
                },
            ],
            "skills": ["Python", "SQL", "Airflow", "Tableau"],
        },
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    print(f"Created demo user: {user.email} (password: {DEMO_PASSWORD})")
    return user


def _create_job_payloads() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "company": "Delta Air Lines",
            "role_title": "OAP Analyst",
            "source_url": "https://delta.com/careers/oap-analyst",
            "applied_at": now - timedelta(days=6),
            "jd_structured": {
                "title": "OAP Analyst",
                "company": "Delta Air Lines",
                "locations": [
                    {
                        "label": "ATL HQ",
                        "city": "Atlanta",
                        "region": "GA",
                        "country": "USA",
                        "lat": 33.6407,
                        "lng": -84.4277,
                        "raw": "Atlanta HQ - 1030 Delta Blvd, Atlanta, GA",
                    }
                ],
                "keywords": ["operations", "analytics", "aviation"],
            },
            "resume_bullets": [
                {"text": "Orchestrated fleet readiness analytics that cut turnaround time by 12% for ATL hub."},
                {"text": "Launched automated KPI dashboards for Operations Analysis & Performance leadership."},
            ],
            "cover_letter": "Dear Delta team,\n\nThrilled to bring aviation analytics experience to Operations Analysis & Performance. I have worked closely with ATL hub leaders to translate operational data into confident decisions.\n\nRegards,\nAvery",
        },
        {
            "company": "IBM",
            "role_title": "Data Analyst",
            "source_url": "https://careers.ibm.com/jobs/12345",
            "applied_at": now - timedelta(days=3),
            "jd_structured": {
                "title": "Data Analyst",
                "company": "IBM Consulting",
                "locations": [
                    {
                        "label": "New York HQ",
                        "city": "New York",
                        "region": "NY",
                        "country": "USA",
                        "lat": 40.758,
                        "lng": -73.9855,
                        "raw": "IBM Consulting, Bryant Park, New York, NY",
                    },
                    {
                        "label": "Remote Hub",
                        "city": "Raleigh",
                        "region": "NC",
                        "country": "USA",
                        "lat": 35.7796,
                        "lng": -78.6382,
                        "raw": "Hybrid travel to RTP innovation hub",
                    },
                ],
                "keywords": ["hybrid", "consulting", "analytics"],
            },
            "resume_bullets": [
                {"text": "Delivered hybrid analytics engagements with 95% client satisfaction across NYC and RTP."},
                {"text": "Built reusable data models that accelerated remote delivery pods by 30%."},
            ],
            "cover_letter": "Hello IBM,\n\nExcited about continuing hybrid analytics engagements with IBM Consulting. My recent projects balanced NYC clients with remote delivery pods out of RTP.\n\nBest,\nAvery",
        },
        {
            "company": "Epic Systems",
            "role_title": "Systems Administrator",
            "source_url": "https://careers.epic.com/position-6789",
            "applied_at": now - timedelta(days=1),
            "jd_structured": {
                "title": "Systems Administrator",
                "company": "Epic Systems",
                "locations": [
                    {
                        "label": "Madison Campus",
                        "city": "Madison",
                        "region": "WI",
                        "country": "USA",
                        "lat": 43.0731,
                        "lng": -89.4012,
                        "raw": "Verona campus outside Madison, WI",
                    }
                ],
                "keywords": ["healthcare", "systems", "infrastructure"],
            },
            "resume_bullets": [
                {"text": "Maintained HIPAA-compliant analytics infrastructure supporting 35 hospital clients."},
                {"text": "Partnered with Epic analysts to translate operational tickets into automated fixes."},
            ],
            "cover_letter": "Epic team,\n\nMy healthcare analytics background pairs well with Epic's systems admin role. I have supported health systems migrating to Epic and managed on-prem analytics platforms for compliance.\n\nThanks,\nAvery",
        },
    ]


def _seed_jobs(session: Session, user: User) -> None:
    jobs = _create_job_payloads()
    created = 0
    for job in jobs:
        existing = session.exec(
            select(JobApplied).where(
                JobApplied.user_id == user.id,
                JobApplied.company == job["company"],
                JobApplied.role_title == job["role_title"],
            )
        ).first()
        if existing:
            continue

        job_model = JobApplied(
            user_id=user.id,
            company=job["company"],
            role_title=job["role_title"],
            source_url=job["source_url"],
            applied_at=job["applied_at"],
            jd_structured=job["jd_structured"],
            resume_bullets=job["resume_bullets"],
            cover_letter=job["cover_letter"],
        )
        session.add(job_model)
        session.flush()

        for location in job["jd_structured"].get("locations", []):
            session.add(
                JobLocation(
                    job_id=job_model.id,
                    label=location.get("label"),
                    lat=location.get("lat"),
                    lng=location.get("lng"),
                    raw=location.get("raw") or location.get("city"),
                )
            )
        created += 1

    session.commit()
    print(f"Seeded {created} job applications for {user.email}.")


def main() -> None:
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, echo=False)

    with Session(engine) as session:
        user = _ensure_user(session)
        _seed_jobs(session, user)

    print("Demo data ready. Log in with:")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
