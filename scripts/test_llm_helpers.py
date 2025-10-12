from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import sqlmodel  # type: ignore  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - optional dependency for smoke test
    import types

    sqlmodel_stub = types.ModuleType("sqlmodel")

    class _Session:  # minimal placeholder to satisfy llm imports
        pass

    sqlmodel_stub.Session = _Session  # type: ignore[attr-defined]
    sys.modules["sqlmodel"] = sqlmodel_stub

from llm import LLMPipeline  # noqa: E402


SAMPLE_JD = """Company: Aurora Cloud Platform
Role: Senior Platform Engineer
Location: Remote - North America

Aurora Cloud helps data teams deliver analytics at scale. We are seeking a Senior Platform Engineer to extend our ingestion
pipelines, improve platform reliability, and partner with product to accelerate feature delivery. The ideal teammate has led
distributed systems projects, collaborated across product and infrastructure teams, and delivered measurable uptime or latency wins.

Must-have skills include Python, Kubernetes, and experience operating observability tooling. Nice-to-haves include experience with
Go, Terraform, and cost optimization in multi-tenant environments. Our mission is to empower analysts with trustworthy, real-time data.
"""

SAMPLE_FACTS: List[Dict[str, Any]] = [
    {
        "id": "fact-platform-1",
        "metadata": {
            "task_name": "Scaled ingestion platform to 5B events/day",
            "project_name": "EventMesh Modernization",
            "skills": ["Python", "Kubernetes", "Kafka"],
            "matched_metrics": ["35% latency reduction", "99.97% uptime"],
            "tense": "past",
        },
    },
    {
        "id": "fact-platform-2",
        "metadata": {
            "task_name": "Rolled out observability standards",
            "project_name": "Telemetry Excellence Program",
            "skills": ["Terraform", "Grafana", "Prometheus"],
            "matched_metrics": ["Unified dashboards adopted by 12 teams"],
            "tense": "past",
        },
    },
]

SAMPLE_STORY = (
    "I thrive in mission-driven platform teams where reliability unlocks customer impact, and I love partnering with product "
    "and analytics peers to translate metrics into better experiences."
)


async def run_smoke_test() -> Tuple[Dict[str, Any], Dict[str, Any], List[str], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    pipeline = LLMPipeline()
    jd_factors, jd_meta = await pipeline.extract_jd_factors(SAMPLE_JD)
    bullets, bullets_meta = await pipeline.generate_bullets(SAMPLE_FACTS, jd_factors)
    cover_payload, cover_meta = await pipeline.generate_cover_letter(SAMPLE_FACTS, jd_factors, SAMPLE_STORY)
    return jd_factors, jd_meta, bullets, bullets_meta, cover_payload, cover_meta


async def main() -> None:
    jd_factors, jd_meta, bullets, bullets_meta, cover_payload, cover_meta = await run_smoke_test()
    summary = {
        "jd_factors": jd_factors,
        "jd_metadata": jd_meta,
        "resume_bullets": bullets,
        "bullets_metadata": bullets_meta,
        "cover_letter": cover_payload,
        "cover_metadata": cover_meta,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
