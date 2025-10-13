from __future__ import annotations

import importlib
import sys
from pathlib import Path
import types
from typing import Any, AsyncIterator, Generic, Optional, TypeVar
from datetime import datetime

from pydantic import BaseModel

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import MetaData
from sqlmodel import SQLModel, create_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_chatkit_stub() -> None:
    """
    Provide a lightweight ChatKit stub so tests can run without the optional dependency.

    The real ChatKit SDK is only required for production deployments. For unit tests we
    emulate the minimal surface that's imported by the FastAPI app and the integration
    layer.
    """
    if "chatkit" in sys.modules:
        return

    TContext = TypeVar("TContext")

    chatkit_pkg = types.ModuleType("chatkit")
    server_mod = types.ModuleType("chatkit.server")
    agents_mod = types.ModuleType("chatkit.agents")
    types_mod = types.ModuleType("chatkit.types")

    class StreamingResult:  # pragma: no cover - stub type
        pass

    class AttachmentStore(Generic[TContext]):  # pragma: no cover - stub base
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class Store(Generic[TContext]):  # pragma: no cover - stub base
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class ChatKitServer(Generic[TContext]):  # pragma: no cover - stub base
        def __init__(self, store: Store[TContext], attachment_store: AttachmentStore[TContext] | None = None) -> None:
            self.store = store
            self.attachment_store = attachment_store

        async def respond(  # noqa: D401
            self,
            thread: "ThreadMetadata",
            input_user_message: "UserMessageItem | None",
            context: Any,
        ) -> AsyncIterator["ThreadStreamEvent"]:
            if False:  # pragma: no cover - generator placeholder
                yield None  # type: ignore[misc]

    server_mod.ChatKitServer = ChatKitServer
    server_mod.Store = Store
    server_mod.AttachmentStore = AttachmentStore
    server_mod.StreamingResult = StreamingResult

    class AgentContext:  # pragma: no cover - stub container
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    async def simple_to_agent_input(items: Any) -> Any:  # pragma: no cover - stub
        return items

    async def stream_agent_response(  # pragma: no cover - stub
        context: AgentContext,
        result_stream: Any,
    ) -> AsyncIterator[Any]:
        if hasattr(result_stream, "__aiter__"):
            async for chunk in result_stream:
                yield chunk
        else:
            for chunk in result_stream or []:
                yield chunk

    agents_mod.AgentContext = AgentContext
    agents_mod.simple_to_agent_input = simple_to_agent_input
    agents_mod.stream_agent_response = stream_agent_response

    class ThreadMetadata(BaseModel):  # pragma: no cover - stub model
        id: str
        title: Optional[str] = None
        status: Optional[str] = None
        metadata: Optional[dict[str, Any]] = None
        created_at: Optional[datetime] = None

    class ThreadItem(BaseModel):  # pragma: no cover - stub model
        id: str
        thread_id: str
        type: str
        created_at: Optional[datetime] = None
        payload: Optional[dict[str, Any]] = None

    class ThreadStreamEvent(BaseModel):  # pragma: no cover - stub model
        type: str = "message"
        data: Optional[dict[str, Any]] = None

    class UserMessageItem(BaseModel):  # pragma: no cover - stub model
        id: str
        thread_id: str
        type: str = "message"
        content: Optional[list[dict[str, Any]]] = None

    class Attachment(BaseModel):  # pragma: no cover - stub model
        id: str
        filename: str
        content_type: Optional[str] = None

    class Page(BaseModel):  # pragma: no cover - stub container
        data: list[Any]
        has_more: bool = False
        after: Optional[str] = None

    types_mod.ThreadMetadata = ThreadMetadata
    types_mod.ThreadItem = ThreadItem
    types_mod.ThreadStreamEvent = ThreadStreamEvent
    types_mod.UserMessageItem = UserMessageItem
    types_mod.Attachment = Attachment
    types_mod.Page = Page

    chatkit_pkg.server = server_mod
    chatkit_pkg.agents = agents_mod
    chatkit_pkg.types = types_mod

    sys.modules["chatkit"] = chatkit_pkg
    sys.modules["chatkit.server"] = server_mod
    sys.modules["chatkit.agents"] = agents_mod
    sys.modules["chatkit.types"] = types_mod


def _import_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "myapply_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SESSION_COOKIE_NAME", "test_session_cookie")
    monkeypatch.setenv("SESSION_SECURE", "auto")
    monkeypatch.setenv("MAPBOX_PUBLIC_TOKEN", "test-public-token")
    monkeypatch.setenv("MAPBOX_SECRET_TOKEN", "")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    # Remove all cached modules completely
    modules_to_clear = [
        "app", "models", "auth", "llm", "validation", "models_llm",
        "applications", "routers", "services",
        "graph", "graph.schema", "graph.loader", "graph.scoring",
        "myapply_tools"
    ]
    for module_name in list(sys.modules.keys()):
        if any(module_name == mod or module_name.startswith(mod + ".") for mod in modules_to_clear):
            sys.modules.pop(module_name, None)

    _install_chatkit_stub()

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
