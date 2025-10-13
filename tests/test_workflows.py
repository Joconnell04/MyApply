from __future__ import annotations

from types import SimpleNamespace

from sqlmodel import Session
from workflow_constants import (
    WORKFLOW_JD_TO_STRUCT_ID,
    WORKFLOW_JD_TO_STRUCT_VER,
    WORKFLOW_RESUME_BUILDER_ID,
    WORKFLOW_RESUME_BUILDER_VER,
)


def test_two_phase_workflow_success(monkeypatch, test_client):
    client, app_module = test_client
    from applications import JobApplication

    jd_payload = {"title": "Senior AI Engineer", "company": "OpenAI"}
    resume_payload = {"bullets": ["Delivered high-impact AI systems."], "package": {"summary": "Tailored resume"}}

    captured_inputs: list[tuple[str, dict]] = []

    def fake_run_workflow(workflow_id: str, version: str, inputs: dict):
        captured_inputs.append((workflow_id, inputs))
        if workflow_id == WORKFLOW_JD_TO_STRUCT_ID:
            assert version == WORKFLOW_JD_TO_STRUCT_VER
            assert "source_url" in inputs
            return SimpleNamespace(
                id="jd-run-123",
                status="succeeded",
                output={"output_parsed": jd_payload},
            )
        if workflow_id == WORKFLOW_RESUME_BUILDER_ID:
            assert version == WORKFLOW_RESUME_BUILDER_VER
            assert inputs.get("jd_struct_data") == jd_payload
            return SimpleNamespace(
                id="resume-run-456",
                status="succeeded",
                output={
                    "output_parsed": resume_payload,
                    "output_text": "Generated resume bullets",
                },
            )
        raise AssertionError(f"Unexpected workflow {workflow_id}")

    monkeypatch.setattr("services.openai_workflows.run_workflow", fake_run_workflow)
    monkeypatch.setattr("routers.jd_ingest.run_workflow", fake_run_workflow)
    monkeypatch.setattr("routers.resume_build.run_workflow", fake_run_workflow)

    ingest_response = client.post(
        "/api/jd/ingest",
        json={"user_id": "test-user", "source_url": "https://example.com/job"},
    )
    assert ingest_response.status_code == 200
    body = ingest_response.json()
    assert body["jd_status"] == "succeeded"
    assert body["jd_struct_data"] == jd_payload
    application_id = body["application_id"]

    resume_response = client.post(
        "/api/resume/build",
        json={
            "user_id": "test-user",
            "application_id": application_id,
            "target_role": "Staff AI Engineer",
        },
    )
    assert resume_response.status_code == 200
    resume_body = resume_response.json()
    assert resume_body["resume_status"] == "succeeded"
    assert resume_body["resume_output"]["output_parsed"] == resume_payload

    # Two workflow invocations captured
    assert len(captured_inputs) == 2
    assert captured_inputs[0][0] == WORKFLOW_JD_TO_STRUCT_ID
    assert captured_inputs[1][0] == WORKFLOW_RESUME_BUILDER_ID
    assert captured_inputs[1][1]["target_role"] == "Staff AI Engineer"

    with Session(app_module.engine) as session:
        db_app = session.get(JobApplication, application_id)
        assert db_app is not None
        assert db_app.jd_status == "succeeded"
        assert db_app.jd_run_id == "jd-run-123"
        assert db_app.resume_status == "succeeded"
        assert db_app.resume_run_id == "resume-run-456"
        assert db_app.resume_output["output_parsed"] == resume_payload
