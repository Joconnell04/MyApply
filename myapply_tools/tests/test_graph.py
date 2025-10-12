from __future__ import annotations

from fastapi.testclient import TestClient


def test_candidate_facets_aggregation(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/tools/get_candidate_facets",
        json={"user_id": "demo-user", "limit": 2},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["skills"]) <= 2
    assert "Python" in data["skills"]


def test_search_experiences_pagination(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/tools/search_experiences",
        json={"user_id": "demo-user", "query": "dashboards", "page_size": 1},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["next_page_token"] == "2"

    response = client.post(
        "/tools/search_experiences",
        json={"user_id": "demo-user", "query": "dashboards", "page": 2, "page_size": 1},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]


def test_evidence_single_and_batch(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/tools/get_evidence",
        json={"experience_id": "exp-001", "include_artifacts": False},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["evidence"]["experience_id"] == "exp-001"
    assert data["evidence"]["artifacts"] == []

    response = client.post(
        "/tools/get_evidence_batch",
        json={"experience_ids": ["exp-001", "exp-002"]},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    batch = response.json()
    assert len(batch["items"]) == 2
    assert batch["items"][0]["experience_id"] == "exp-001"
    assert batch["items"][0]["artifacts"]
