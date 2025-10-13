from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from services import openai_workflows
from services.resume_builder_service import AgentWorkflowRun


def test_extract_job_input_precedence():
    job_input = openai_workflows._extract_job_input(
        {
            "job_text": "ignored",
            "input_as_text": "https://example.com",
            "other": "value",
        }
    )
    assert job_input == "https://example.com"


def test_extract_job_input_raises():
    with pytest.raises(ValueError):
        openai_workflows._extract_job_input({})


def test_run_workflow_invokes_agentkit(monkeypatch: pytest.MonkeyPatch):
    run_id = uuid.uuid4().hex

    def fake_runner(workflow_id: str, version: str, inputs: dict[str, str]):
        assert workflow_id == "wf_test"
        assert version == "1"
        assert inputs["input_as_text"] == "payload"
        return AgentWorkflowRun(
            id=run_id,
            status="completed",
            workflow_id=workflow_id,
            version=version,
            output={"resume_bullets": ["item"]},
        )

    monkeypatch.setattr(openai_workflows, "_run_resume_builder_agentkit", fake_runner)

    result = openai_workflows.run_workflow(
        workflow_id="wf_test",
        version="1",
        inputs={"input_as_text": "payload"},
    )

    assert isinstance(result, AgentWorkflowRun)
    assert result.id == run_id
    assert result.output["resume_bullets"] == ["item"]


def test_run_workflow_raises_http(monkeypatch: pytest.MonkeyPatch):
    def fake_runner(*args, **kwargs):
        raise ValueError("bad input")

    monkeypatch.setattr(openai_workflows, "_run_resume_builder_agentkit", fake_runner)

    with pytest.raises(HTTPException) as exc:
        openai_workflows.run_workflow(
            workflow_id="wf_test",
            version="1",
            inputs={"scene": "fail"},
        )

    assert exc.value.status_code == 502
