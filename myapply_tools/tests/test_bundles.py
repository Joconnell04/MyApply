from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session


def test_set_and_get_generation_bundle(client: TestClient, auth_headers) -> None:
    payload = {
        "user_id": "demo-user",
        "hash": "hash-123",
        "plan": {"steps": ["a", "b"]},
        "resolved_jd": {"role": "Analyst"},
        "prefs": {"tone": "confident"},
    }
    response = client.post("/tools/set_generation_bundle", json=payload, headers=auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True

    response = client.post(
        "/tools/get_generation_bundle",
        json={"user_id": "demo-user", "hash": "hash-123"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    bundle = response.json()["bundle"]
    assert bundle["payload"]["plan"]["steps"] == ["a", "b"]


def test_set_and_get_cover_letter_bundle(client: TestClient, auth_headers) -> None:
    payload = {
        "user_id": "demo-user",
        "hash": "cover-xyz",
        "jd": {"title": "Engineer"},
        "story_plan": {"sections": 3},
        "prefs": {"voice": "enthusiastic"},
    }
    response = client.post("/tools/set_cl_bundle", json=payload, headers=auth_headers())
    assert response.status_code == 200

    response = client.post(
        "/tools/get_cl_bundle",
        json={"user_id": "demo-user", "hash": "cover-xyz"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    bundle = response.json()["bundle"]
    assert bundle["payload"]["story_plan"]["sections"] == 3


def test_bundle_ttl_expiry(client: TestClient, auth_headers) -> None:
    payload = {
        "user_id": "demo-user",
        "hash": "ephemeral",
        "plan": {"steps": []},
        "resolved_jd": {"role": "Planner"},
        "prefs": {},
        "ttl_seconds": 60,
    }
    response = client.post("/tools/set_generation_bundle", json=payload, headers=auth_headers())
    assert response.status_code == 200

    from myapply_tools import storage
    from myapply_tools.deps import engine
    from myapply_tools.models import BundleKind

    with Session(engine) as session:
        bundle = storage.get_bundle(session, kind=BundleKind.RESUME, user_id="demo-user", hash_value="ephemeral")
        assert bundle is not None
        bundle.updated_at = storage.utc_now() - timedelta(seconds=120)
        session.add(bundle)
        session.commit()

    response = client.post(
        "/tools/get_generation_bundle",
        json={"user_id": "demo-user", "hash": "ephemeral"},
        headers=auth_headers(),
    )
    assert response.status_code == 404


def test_missing_auth_rejected(client: TestClient) -> None:
    response = client.post(
        "/tools/get_generation_bundle",
        json={"user_id": "demo-user", "hash": "none"},
    )
    assert response.status_code == 401
