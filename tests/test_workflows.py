from __future__ import annotations
import json
from types import SimpleNamespace

from sqlmodel import Session, select
from models import APIDebugLog
from workflow_constants import (
    WORKFLOW_RESUME_BUILDER_V2_ID,
    WORKFLOW_RESUME_BUILDER_V2_VER,
)


def test_resume_builder_v2_ingest_and_resume(monkeypatch, test_client):
    client, app_module = test_client
    from applications import JobApplication
    structured_payload = {
        "required_skills": ["Python", "FastAPI"],
        "nice_to_have_skills": ["SQLModel"],
        "required_experience": ["5+ years building APIs"],
        "locations": ["Remote"],
        "desired_skills": ["Async programming"],
        "other_noteworthy": ["Experience with workflows"],
    }
    resume_bullets = [
        "Engineered scalable APIs in Python, delivering features for [user base size] clients.",
        "Mentored cross-functional teams while implementing async FastAPI services.",
    ]
    cover_letter = "I am excited to apply my FastAPI expertise to this role."

    run_calls: list[tuple[str, dict]] = []

    def fake_run_workflow(workflow_id: str, version: str, inputs: dict, **kwargs):
        run_calls.append((workflow_id, inputs))
        assert workflow_id == WORKFLOW_RESUME_BUILDER_V2_ID
        assert version == WORKFLOW_RESUME_BUILDER_V2_VER
        assert inputs.get("input_as_text") == "https://example.com/job"
        return SimpleNamespace(
            id="resume-v2-run-789",
            status="completed",
            output={
                "job_scraper_result": {"output_parsed": structured_payload},
                "output_text": json.dumps(
                    {
                        "reasoning": "Planned bullets around API delivery and mentorship.",
                        "plan": ["API impact", "Team leadership"],
                        "resume_bullet_points": resume_bullets,
                        "cover_letter": cover_letter,
                    }
                ),
            },
        )

    monkeypatch.setattr("services.openai_workflows.run_workflow", fake_run_workflow)

    ingest_response = client.post(
        "/api/jd/ingest",
        json={"user_id": "test-user", "source_url": "https://example.com/job"},
    )
    assert ingest_response.status_code == 200
    ingest_body = ingest_response.json()
    assert ingest_body["jd_status"] == "succeeded"
    assert ingest_body["jd_struct_data"] == structured_payload
    application_id = ingest_body["application_id"]

    assert len(run_calls) == 1
    assert run_calls[0][0] == WORKFLOW_RESUME_BUILDER_V2_ID

    with Session(app_module.engine) as session:
        db_app = session.get(JobApplication, application_id)
        assert db_app is not None
        assert db_app.jd_status == "succeeded"
        assert db_app.resume_status == "idle"
        assert db_app.jd_struct_data == structured_payload
        assert db_app.resume_output["resume_bullets"] == resume_bullets
        assert db_app.resume_output["cover_letter"] == cover_letter

    resume_response = client.post(
        "/api/resume/build",
        json={
            "user_id": "test-user",
            "application_id": application_id,
            "job_url": "https://example.com/job",
        },
    )
    assert resume_response.status_code == 200
    resume_body = resume_response.json()
    assert resume_body["resume_status"] == "succeeded"
    assert resume_body["structured_job_data"] == structured_payload
    assert resume_body["resume_bullets"] == resume_bullets
    assert resume_body["cover_letter"] == cover_letter
    assert resume_body["resume_output"]["resume_bullets"] == resume_bullets
    assert resume_body["resume_output"]["cover_letter"] == cover_letter
    assert resume_body["resume_run_id"] == "resume-v2-run-789"

    # Resume build reused cached output (no additional run)
    assert len(run_calls) == 1

    with Session(app_module.engine) as session:
        db_app = session.exec(select(JobApplication)).one()
        assert db_app.jd_status == "succeeded"
        assert db_app.resume_status == "succeeded"
        assert db_app.jd_run_id == "resume-v2-run-789"
        assert db_app.resume_run_id == "resume-v2-run-789"
        assert db_app.jd_struct_data == structured_payload
        assert db_app.resume_output["resume_bullets"] == resume_bullets
        assert db_app.resume_output["cover_letter"] == cover_letter


def test_jd_ingest_uses_debug_decoder_when_workflow_reports_failure(monkeypatch, test_client):
    client, app_module = test_client
    from applications import JobApplication

    structured_payload = {
        "company": {"name": "Example Corp"},
        "locations": [
            {"type": "Remote", "city": "", "country": "United States"},
        ],
        "role": {
            "title": "Senior Engineer",
            "level": "Staff",
            "description": "Lead high-impact projects.",
        },
        "required_skills": ["Python", "Architecture"],
        "nice_to_have_skills": ["Leadership"],
        "other_noteworthy": ["Distributed systems experience"],
    }
    resume_bullets = [
        "Led design and delivery of distributed platforms serving [user count] users.",
        "Partnered with cross-functional teams to modernize architecture and reduce latency by [metric]%.",
    ]

    debug_response = {
        "id": "debug-run-123",
        "status": "failed",
        "workflow_id": WORKFLOW_RESUME_BUILDER_V2_ID,
        "version": WORKFLOW_RESUME_BUILDER_V2_VER,
        "output": {
            "structured_job_data": structured_payload,
            "resume_bullets": resume_bullets,
            "resume_bullets_text": "\n".join(f"- {bullet}" for bullet in resume_bullets),
        },
    }

    def fake_run_workflow(workflow_id: str, version: str, inputs: dict, **kwargs):
        db_session: Session = kwargs.get("db_session")
        application_id = kwargs.get("application_id")
        if db_session and application_id:
            log_entry = APIDebugLog(
                application_id=application_id,
                log_type="agentkit_call",
                endpoint=f"workflow:{workflow_id}",
                method="POST",
                status_code=200,
                request_data={"inputs": inputs},
                response_data=debug_response,
            )
            db_session.add(log_entry)
            db_session.commit()
        return SimpleNamespace(
            id="upstream-run-456",
            status="failed",
            output={},
        )

    monkeypatch.setattr("services.openai_workflows.run_workflow", fake_run_workflow)

    ingest_response = client.post(
        "/api/jd/ingest",
        json={"user_id": "debug-user", "source_url": "https://example.com/job"},
    )
    assert ingest_response.status_code == 200
    ingest_body = ingest_response.json()
    assert ingest_body["jd_status"] == "succeeded"
    assert ingest_body["jd_struct_data"] == structured_payload
    application_id = ingest_body["application_id"]

    with Session(app_module.engine) as session:
        db_app = session.get(JobApplication, application_id)
        assert db_app is not None
        assert db_app.jd_status == "succeeded"
        assert db_app.resume_status == "idle"
        assert db_app.jd_run_id == "debug-run-123"
        assert db_app.resume_run_id == "debug-run-123"
        assert db_app.jd_struct_data == structured_payload
        assert db_app.resume_output["resume_bullets"] == resume_bullets
        # New debug log parser is used as primary strategy
        assert db_app.resume_output["decoder_source"] == "debug_log_parser"
        assert db_app.resume_output.get("parsing_strategy") == "debug_log_deep_search"
