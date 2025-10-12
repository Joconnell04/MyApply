from __future__ import annotations

import importlib
import sys
from typing import Callable, Dict, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SAWarning

import warnings

warnings.filterwarnings("ignore", category=SAWarning)


def _reload_app(tmp_path, monkeypatch):
    db_path = tmp_path / "tools.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("MYAPPLY_API_KEY", "test-key")
    for key in list(sys.modules):
        if key.startswith("myapply_tools"):
            sys.modules.pop(key)
    from sqlmodel import SQLModel

    SQLModel.metadata.clear()
    return importlib.import_module("myapply_tools.app")


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    app_module = _reload_app(tmp_path, monkeypatch)
    with TestClient(app_module.app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers() -> Callable[[str], Dict[str, str]]:
    def _builder(user_id: str = "demo-user") -> Dict[str, str]:
        return {
            "Authorization": "Bearer test-key",
            "X-MyApply-User": user_id,
        }

    return _builder
