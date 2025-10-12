"""FastAPI application entrypoint for the MyApply AgentKit tool service."""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable, Dict

from fastapi import FastAPI, Request, Response
from sqlmodel import SQLModel, Session

from .deps import engine
from .routers import bundles, cover_letter, graph
from .schemas import AGENTKIT_TOOL_SPEC
from .storage import seed_demo_data

app = FastAPI(
    title="MyApply AgentKit Tools",
    version="0.1.0",
    openapi_tags=[
        {"name": "Bundles", "description": "Resume and cover-letter bundle management."},
        {"name": "Graph", "description": "Experience graph search and retrieval tools."},
        {"name": "Cover Letter", "description": "Cover-letter helper utilities."},
    ],
)


@app.on_event("startup")
def startup() -> None:
    """Initialize database tables and seed demo content."""

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo_data(session)


@app.middleware("http")
async def add_request_id(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Ensure every response contains an X-Request-Id header."""

    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/tools/toolspec")
def get_toolspec() -> Dict[str, Any]:
    """Return JSON schema definitions for all AgentKit tools."""

    return AGENTKIT_TOOL_SPEC


app.include_router(bundles.router)
app.include_router(graph.router)
app.include_router(cover_letter.router)
