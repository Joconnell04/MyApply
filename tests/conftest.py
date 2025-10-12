from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData
from sqlmodel import SQLModel, create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "myapply_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "test_session_cookie")
    monkeypatch.setenv("SESSION_SECURE", "auto")
    monkeypatch.setenv("MAPBOX_PUBLIC_TOKEN", "test-public-token")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "")

    # Remove all cached modules completely
    modules_to_clear = [
        "app", "models", "auth", "routes", "llm", "validation", "models_llm",
        "graph", "graph.schema", "graph.loader", "graph.scoring",
        "myapply_tools", "agentkit"
    ]
    for module_name in list(sys.modules.keys()):
        if any(module_name == mod or module_name.startswith(mod + ".") for mod in modules_to_clear):
            sys.modules.pop(module_name, None)

    # Replace SQLModel metadata with a fresh instance
    SQLModel.metadata = MetaData()

    # Import app module - this will create a fresh engine
    app_module = importlib.import_module("app")

    # Create all tables in the test database (checkfirst prevents errors if tables exist)
    SQLModel.metadata.create_all(app_module.engine, checkfirst=True)

    return app_module


@pytest.fixture
def app_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    return _import_app(tmp_path, monkeypatch)


@pytest.fixture
def test_client(app_module):
    with TestClient(app_module.app) as client:
        yield client, app_module
