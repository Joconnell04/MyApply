from __future__ import annotations

from types import SimpleNamespace

from services import resume_builder_service as rbs


def _make_structured_job():
    return {
        "company": {"name": "Example Corp", "industry": "Software", "size": "200"},
        "locations": [{"type": "onsite", "city": "Remote", "country": "USA"}],
        "role": {"title": "Engineer", "level": "Senior", "description": "Build things"},
        "team": {"name": "Platform", "size": 5, "function": "Engineering"},
        "experience": {
            "years_required": 5,
            "minimum_degree": "BS",
            "other_requirements": "Python",
        },
        "skills": {"technical": ["Python"], "soft": ["Collaboration"]},
    }


def _simple_namespace(payload):
    return SimpleNamespace(final_output=payload)


def test_run_resume_builder_handles_structured_dict(monkeypatch):
    structured_job = _make_structured_job()
    bullet_payload = {
        "resume_bullets_text": "- Built APIs\n- Led teams",
        "output_parsed": {
            "reasoning": "Example reasoning",
            "plan": ["APIs", "Leadership"],
            "resume_bullet_points": ["Built APIs", "Led teams"],
        },
    }

    class DummyRunner:
        _responses = [
            _simple_namespace(structured_job),
            _simple_namespace(bullet_payload),
        ]

        @classmethod
        async def run(cls, agent, input, run_config=None, **kwargs):
            return cls._responses.pop(0)

    monkeypatch.setattr(rbs, "Runner", DummyRunner)

    result = rbs.run_resume_builder_workflow("wf_test", "1", "https://example.com/job")
    assert result.output["resume_bullets"] == ["Built APIs", "Led teams"]
    assert result.output["resume_bullets_text"] == "- Built APIs\n- Led teams"
    assert result.output["output_parsed"]["plan"] == ["APIs", "Leadership"]
    assert result.output["structured_job_data"]["company"]["name"] == "Example Corp"


def test_run_resume_builder_handles_text_output(monkeypatch):
    structured_job = _make_structured_job()
    text_output = "- Delivered features\n- Improved uptime"

    class DummyRunner:
        _responses = [
            _simple_namespace(structured_job),
            _simple_namespace(text_output),
        ]

        @classmethod
        async def run(cls, agent, input, run_config=None, **kwargs):
            return cls._responses.pop(0)

    monkeypatch.setattr(rbs, "Runner", DummyRunner)

    result = rbs.run_resume_builder_workflow("wf_test", "1", "https://example.com/job")
    assert result.output["resume_bullets"] == ["Delivered features", "Improved uptime"]
    assert "- Delivered features" in result.output["resume_bullets_text"]
    assert result.output["output_parsed"]["resume_bullet_points"] == [
        "Delivered features",
        "Improved uptime",
    ]


def test_normalize_bullet_payload_handles_text_envelope():
    payload = {
        "type": "text",
        "text": "- Built APIs\n- Improved latency",
    }

    result = rbs._normalize_bullet_payload(payload)  # type: ignore[attr-defined]
    assert result["resume_bullets"] == ["Built APIs", "Improved latency"]
    assert "resume_bullets_text" in result
