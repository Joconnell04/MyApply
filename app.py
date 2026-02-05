from __future__ import annotations

import json
import re
from math import atan2, cos, radians, sin, sqrt
from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union
import os

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.middleware.sessions import SessionMiddleware

from readability import Document

from auth import (
    LoginRateLimiter,
    ensure_csrf_token,
    login as auth_login,
    logout as auth_logout,
    register as auth_register,
    validate_csrf_token,
)
from graph.loader import GraphLoader, parse_graph_payload
from graph.scoring import rank_facts
from llm import LLMPipeline
from models import APIDebugLog, ComposeRun, JobApplied, JobLocation, User
from chatkit_integration.store import SQLChatStore, NoOpAttachmentStore
from chatkit_integration.server import MyChatKitServer
from chatkit.server import StreamingResult
from validation import sanitize_string, validate_json_size, validate_url


class Settings(BaseSettings):
    SECRET_KEY: str = "change-me"
    DATABASE_URL: str = "sqlite:///./myapply.db"
    SESSION_COOKIE_NAME: str = "app_session"
    SESSION_SECURE: Union[bool, Literal["auto"]] = "auto"
    SESSION_SAMESITE: str = "lax"
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    COVER_LETTER_MODEL: Optional[str] = None
    MAPBOX_PUBLIC_TOKEN: Optional[str] = None
    MAPBOX_ACCESS_TOKEN: Optional[str] = None  # Alternate name for secret token
    MAPBOX_SECRET_TOKEN: Optional[str] = None
    ALLOWED_ORIGINS: Optional[str] = None
    PORT: int = 8000
    ENV: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env file

    @model_validator(mode="after")
    def _resolve_session_secure(self):
        if self.SESSION_SECURE == "auto":
            is_sqlite = self.DATABASE_URL.startswith("sqlite")
            object.__setattr__(self, "SESSION_SECURE", not is_sqlite)
        return self

    @property
    def mapbox_secret_token(self) -> Optional[str]:
        """Get Mapbox secret token from either MAPBOX_SECRET_TOKEN or MAPBOX_ACCESS_TOKEN."""
        return self.MAPBOX_SECRET_TOKEN or self.MAPBOX_ACCESS_TOKEN

    @property
    def cors_origins(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list."""
        if self.ALLOWED_ORIGINS:
            return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
        # Default origins for development
        return [
            "http://localhost:8000",
            "http://localhost:8001",
            "http://localhost:3000",
            "http://127.0.0.1:8000",
            "http://127.0.0.1:8001",
            "http://127.0.0.1:3000",
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

if settings.OPENAI_API_KEY:
    os.environ.setdefault("OPENAI_API_KEY", settings.OPENAI_API_KEY)

# Database engine configuration with SSL support for Railway Postgres
def _get_engine_connect_args(db_url: str) -> dict:
    """
    Determine connect_args based on database URL.
    - SQLite: add check_same_thread=False
    - Postgres with proxy.rlwy.net: add sslmode=require
    - Other Postgres: no special connect_args needed
    """
    if db_url.startswith("sqlite"):
        return {"check_same_thread": False}
    elif "proxy.rlwy.net" in db_url:
        return {"sslmode": "require"}
    return {}

connect_args = _get_engine_connect_args(settings.DATABASE_URL)
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

app = FastAPI(title="MyApply")

# CORS middleware for frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    https_only=settings.SESSION_SECURE,
    same_site=settings.SESSION_SAMESITE,
)

# Get base directory for robust path resolution
BASE_DIR = Path(__file__).resolve().parent

# Mount static files with absolute path
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Use absolute path for templates directory for Railway deployment
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
login_rate_limiter = LoginRateLimiter()

pipeline = LLMPipeline(
    api_key=settings.OPENAI_API_KEY,
    model=settings.LLM_MODEL,
    cover_letter_model=settings.COVER_LETTER_MODEL,
)

chatkit_store = SQLChatStore(engine)
chatkit_attachment_store = NoOpAttachmentStore()
chatkit_server = MyChatKitServer(chatkit_store, chatkit_attachment_store)


def _csrf_token(request: Request) -> str:
    return ensure_csrf_token(request, settings.SECRET_KEY)


templates.env.globals["csrf_token"] = _csrf_token
templates.env.globals["mapbox_public_token"] = settings.MAPBOX_PUBLIC_TOKEN


class ProfileUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    mylife_json: Optional[Dict[str, Any]] = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _ensure_mylife_json_is_object(self):
        if self.mylife_json is None:
            return self
        if isinstance(self.mylife_json, dict):
            return self
        if isinstance(self.mylife_json, str):
            try:
                parsed = json.loads(self.mylife_json)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="mylife_json must be valid JSON.",
                ) from exc
            if not isinstance(parsed, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="mylife_json must be a JSON object.",
                )
            object.__setattr__(self, "mylife_json", parsed)
            return self
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mylife_json must be a JSON object.",
        )


class JobAppliedCreatePayload(BaseModel):
    company: str
    role_title: str
    source_url: Optional[str] = None
    jd_structured: Dict[str, Any]
    resume_bullets: List[Any]
    cover_letter: Optional[str] = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _normalize_resume_bullets(self):
        normalized: List[Dict[str, Any]] = []
        for bullet in self.resume_bullets:
            if isinstance(bullet, dict):
                normalized.append(bullet)
            elif isinstance(bullet, str):
                normalized.append({"text": bullet})
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="resume_bullets must be objects or strings.",
                )
        object.__setattr__(self, "resume_bullets", normalized)
        return self


class IsochroneRequestPayload(BaseModel):
    lat: float
    lng: float
    minutes: int
    profile: Literal["driving", "walking", "cycling"]

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_minutes(self):
        if not 1 <= self.minutes <= 180:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="minutes must be between 1 and 180.",
            )
        return self


def _strip_html(content: str) -> str:
    text = re.sub(r"<[^>]+>", " ", content)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _make_excerpt(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


async def _fetch_jd_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        html_content = response.text
    try:
        doc = Document(html_content)
        summary_html = doc.summary() or html_content
    except Exception:  # pylint: disable=broad-except
        summary_html = html_content
    text = _strip_html(summary_html)
    if not text:
        text = _strip_html(html_content)
    return text


def _select_diverse_facts(facts: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[Optional[str], Optional[str]]] = set()
    for fact in facts:
        metadata = fact.get("metadata", {})
        metrics = [m.lower() for m in metadata.get("matched_metrics") or metadata.get("metrics") or []]
        skills = [s.lower() for s in metadata.get("skills") or metadata.get("all_skills") or []]
        combos: Set[Tuple[Optional[str], Optional[str]]]
        if metrics and skills:
            combos = {(metric, skill) for metric in metrics for skill in skills}
        elif metrics:
            combos = {(metric, None) for metric in metrics}
        elif skills:
            combos = {(None, skill) for skill in skills}
        else:
            combos = {(fact.get("id"), None)}

        if seen_pairs.isdisjoint(combos):
            selected.append(fact)
            seen_pairs.update(combos)
        if len(selected) >= limit:
            break
    return selected


def _prepare_fact_response(fact: dict[str, Any]) -> dict[str, Any]:
    metadata = fact.get("metadata", {})
    return {
        "id": fact.get("id"),
        "score": fact.get("score"),
        "task_name": metadata.get("task_name"),
        "project_name": metadata.get("project_name"),
        "skills": metadata.get("skills", []),
        "domains": metadata.get("domains", []),
        "metrics": metadata.get("matched_metrics") or metadata.get("metrics", []),
        "description": metadata.get("task_description", ""),
    }


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in kilometers between two lat/lng coordinates."""
    radius_km = 6371.0088
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def _distance_from_home(
    home_coords: Optional[Tuple[float, float]],
    location: JobLocation,
) -> Optional[dict[str, float]]:
    if not home_coords:
        return None
    if location.lat is None or location.lng is None:
        return None
    km = haversine(home_coords[0], home_coords[1], location.lat, location.lng)
    return {"km": km, "miles": km * 0.621371}


def _serialize_location(
    location: JobLocation,
    home_coords: Optional[Tuple[float, float]],
) -> dict[str, Any]:
    distance = _distance_from_home(home_coords, location)
    payload: dict[str, Any] = {
        "id": location.id,
        "label": location.label,
        "lat": location.lat,
        "lng": location.lng,
        "raw": location.raw,
    }
    if distance:
        payload["distance_km"] = distance["km"]
        payload["distance_miles"] = distance["miles"]
    return payload


def _serialize_job(
    job: JobApplied,
    locations: List[JobLocation],
    *,
    include_details: bool = False,
    home_coords: Optional[Tuple[float, float]] = None,
) -> dict[str, Any]:
    job_payload: dict[str, Any] = {
        "id": job.id,
        "company": job.company,
        "role_title": job.role_title,
        "source_url": job.source_url,
        "applied_at": job.applied_at.isoformat(),
        "locations": [_serialize_location(loc, home_coords) for loc in locations],
        "locations_count": len(locations),
    }
    if include_details:
        job_payload["resume_bullets"] = job.resume_bullets or []
        job_payload["cover_letter"] = job.cover_letter
        job_payload["jd_structured"] = job.jd_structured or {}
    return job_payload


def _serialize_job_run(job_app) -> dict[str, Any]:
    resume_output = job_app.resume_output if isinstance(job_app.resume_output, dict) else {}
    resume_bullets: List[str] = []
    if isinstance(resume_output, dict):
        resume_bullets = (
            resume_output.get("resume_bullets")
            or (resume_output.get("output_parsed") or {}).get("resume_bullet_points")
            or []
        )
        if isinstance(resume_bullets, str):
            resume_bullets = [resume_bullets]
        if isinstance(resume_bullets, str):
            resume_bullets = [resume_bullets]
        if (not resume_bullets) and isinstance(resume_output.get("resume_bullets_text"), str):
            resume_bullets = [
                segment.strip()
                for segment in resume_output["resume_bullets_text"].splitlines()
                if segment.strip()
            ]

    updated_display = job_app.updated_at.strftime("%Y-%m-%d %H:%M") if job_app.updated_at else "—"

    return {
        "id": job_app.id,
        "jd_status": job_app.jd_status,
        "resume_status": job_app.resume_status,
        "source_url": job_app.source_url,
        "linked_job_id": getattr(job_app, "linked_job_id", None),
        "resume_bullets": resume_bullets,
        "resume_output": resume_output,
        "updated_at": job_app.updated_at.isoformat() if job_app.updated_at else None,
        "updated_at_display": updated_display,
    }


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> Optional[User]:
    user_id = request.session.get("uid")
    if not user_id:
        return None
    user = session.get(User, user_id)
    if not user:
        request.session.pop("uid", None)
        return None
    ensure_csrf_token(request, settings.SECRET_KEY)
    return user


def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only.",
        )
    return user


def _ensure_user_profile_columns() -> None:
    with engine.begin() as connection:
        try:
            dialect = connection.dialect.name
        except AttributeError:
            dialect = engine.dialect.name
        column_names: set[str] = set()
        if dialect == "sqlite":
            result = connection.exec_driver_sql('PRAGMA table_info("user");')
            column_names = {row[1] for row in result}
        else:
            result = connection.exec_driver_sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'user' AND table_schema = current_schema();"
            )
            column_names = {row[0] for row in result}

        statements: list[str] = []
        if "full_name" not in column_names:
            if dialect == "sqlite":
                statements.append('ALTER TABLE "user" ADD COLUMN full_name TEXT')
            else:
                statements.append('ALTER TABLE "user" ADD COLUMN full_name TEXT')
        if "home_lat" not in column_names:
            if dialect == "sqlite":
                statements.append('ALTER TABLE "user" ADD COLUMN home_lat REAL')
            else:
                statements.append('ALTER TABLE "user" ADD COLUMN home_lat DOUBLE PRECISION')
        if "home_lng" not in column_names:
            if dialect == "sqlite":
                statements.append('ALTER TABLE "user" ADD COLUMN home_lng REAL')
            else:
                statements.append('ALTER TABLE "user" ADD COLUMN home_lng DOUBLE PRECISION')
        if "mylife_json" not in column_names:
            if dialect == "sqlite":
                statements.append('ALTER TABLE "user" ADD COLUMN mylife_json TEXT DEFAULT \'{}\' NOT NULL')
            else:
                statements.append('ALTER TABLE "user" ADD COLUMN mylife_json JSONB DEFAULT \'{}\'::jsonb NOT NULL')

        for statement in statements:
            try:
                connection.exec_driver_sql(statement)
            except (OperationalError, ProgrammingError):
                # Column may already exist in some environments; ignore failure.
                continue


@app.on_event("startup")
def on_startup() -> None:
    _ensure_user_profile_columns()
    SQLModel.metadata.create_all(engine)


# Include workflow orchestration routes
from routers.jd_ingest import router as jd_router
from routers.resume_build import router as resume_router

app.include_router(jd_router, prefix="/api/jd", tags=["jd"])
app.include_router(resume_router, prefix="/api/resume", tags=["resume"])


@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    result = await chatkit_server.process(await request.body(), {})
    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    return Response(content=result.json, media_type="application/json")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Not found", "detail": str(exc.detail)}
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 404, "message": None, "detail": None},
        status_code=404
    )


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=403,
            content={"ok": False, "error": "Forbidden", "detail": str(exc.detail)}
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 403, "message": None, "detail": str(exc.detail)},
        status_code=403
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Internal server error"}
        )
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "status_code": 500, "message": None, "detail": None},
        status_code=500
    )


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "MyApply"}


@app.get("/health/db")
async def health_check_db(session: Session = Depends(get_session)):
    """Database health check - verifies DB connectivity."""
    try:
        # Execute a simple query to verify database connection
        result = session.exec(select(1)).first()
        if result == 1:
            return {"status": "healthy", "database": "connected"}
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "query_failed"}
        )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "error", "detail": str(exc)}
        )


@app.get("/favicon.ico")
async def favicon():
    """Redirect favicon.ico requests to the SVG favicon."""
    return RedirectResponse(url="/static/favicon.svg", status_code=status.HTTP_301_MOVED_PERMANENTLY)


@app.get("/", response_class=HTMLResponse)
async def root(current_user: Optional[User] = Depends(get_current_user)) -> RedirectResponse:
    if current_user:
        return RedirectResponse(url="/compose", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)


@app.get("/auth/login", response_class=HTMLResponse)
async def show_login(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user:
        return RedirectResponse(url="/compose", status_code=status.HTTP_302_FOUND)
    context = {
        "request": request,
        "error": None,
        "form_email": ""
    }
    return templates.TemplateResponse("auth_login.html", context)


@app.post("/auth/login")
async def perform_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_path: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
):
    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)

    client_id = request.client.host if request.client else "anonymous"
    try:
        user = auth_login(
            request,
            session,
            email=email,
            password=password,
            secret_key=settings.SECRET_KEY,
            rate_limiter=login_rate_limiter,
            client_id=client_id,
        )
    except HTTPException as exc:
        context = {
            "request": request,
            "error": exc.detail,
            "form_email": email
        }
        return templates.TemplateResponse("auth_login.html", context, status_code=exc.status_code)

    next_url = next_path or request.query_params.get("next") or "/compose"
    response = RedirectResponse(url=next_url, status_code=status.HTTP_302_FOUND)
    response.headers["HX-Redirect"] = next_url
    return response


@app.get("/auth/register", response_class=HTMLResponse)
async def show_register(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if current_user:
        return RedirectResponse(url="/compose", status_code=status.HTTP_302_FOUND)
    context = {
        "request": request,
        "error": None,
        "form_email": ""
    }
    return templates.TemplateResponse("auth_register.html", context)


@app.post("/auth/register")
async def perform_register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: str = Form(...),
    session: Session = Depends(get_session),
):
    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)

    if password != password_confirm:
        context = {
            "request": request,
            "error": "Passwords do not match.",
            "form_email": email
        }
        return templates.TemplateResponse("auth_register.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    try:
        user = auth_register(
            request,
            session,
            email=email,
            password=password,
            secret_key=settings.SECRET_KEY,
        )
    except HTTPException as exc:
        context = {
            "request": request,
            "error": exc.detail,
            "form_email": email
        }
        return templates.TemplateResponse("auth_register.html", context, status_code=exc.status_code)

    response = RedirectResponse(url="/compose", status_code=status.HTTP_302_FOUND)
    response.headers["HX-Redirect"] = "/compose"
    return response


def _resolve_current_user(session: Session, user: User) -> User:
    fresh = session.get(User, user.id)
    if not fresh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return fresh


def _home_coords(user: User) -> Optional[Tuple[float, float]]:
    if user.home_lat is None or user.home_lng is None:
        return None
    return (user.home_lat, user.home_lng)


@app.get("/api/profile")
def api_get_profile(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "home_lat": user.home_lat,
        "home_lng": user.home_lng,
        "mylife_json": user.mylife_json or {},
    }


@app.post("/api/profile/update")
def api_update_profile(
    payload: ProfileUpdatePayload,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    updates = payload.model_dump(exclude_unset=True)

    if "full_name" in updates:
        full_name = updates["full_name"]
        user.full_name = sanitize_string(full_name, max_length=200) if full_name else None

    if "home_lat" in updates:
        home_lat = updates["home_lat"]
        if home_lat is not None and not (-90.0 <= home_lat <= 90.0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="home_lat must be between -90 and 90.")
        user.home_lat = home_lat

    if "home_lng" in updates:
        home_lng = updates["home_lng"]
        if home_lng is not None and not (-180.0 <= home_lng <= 180.0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="home_lng must be between -180 and 180.")
        user.home_lng = home_lng

    if "mylife_json" in updates:
        mylife_json = updates["mylife_json"] or {}
        try:
            validate_json_size(json.dumps(mylife_json), max_size_mb=10.0)
        except TypeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mylife_json must be JSON serializable.")
        user.mylife_json = mylife_json

    session.add(user)
    session.commit()
    session.refresh(user)
    return {
        "ok": True,
        "profile": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "home_lat": user.home_lat,
            "home_lng": user.home_lng,
            "mylife_json": user.mylife_json or {},
        },
    }


def _load_locations_for_jobs(session: Session, job_ids: List[str]) -> Dict[str, List[JobLocation]]:
    if not job_ids:
        return {}
    statement = select(JobLocation).where(JobLocation.job_id.in_(job_ids))
    rows = session.exec(statement).all()
    mapping: Dict[str, List[JobLocation]] = {}
    for location in rows:
        mapping.setdefault(location.job_id, []).append(location)
    return mapping


def _serialized_jobs_for_user(
    session: Session,
    user: User,
    *,
    job_id: Optional[str] = None,
    include_details: bool = False,
) -> List[dict[str, Any]]:
    statement = select(JobApplied).where(JobApplied.user_id == user.id)
    if job_id:
        statement = statement.where(JobApplied.id == job_id)
    statement = statement.order_by(JobApplied.applied_at.desc())
    jobs = session.exec(statement).all()
    if job_id and not jobs:
        return []
    job_ids = [job.id for job in jobs]
    location_map = _load_locations_for_jobs(session, job_ids)
    home_coords = _home_coords(user)
    return [
        _serialize_job(
            job,
            location_map.get(job.id, []),
            include_details=include_details,
            home_coords=home_coords,
        )
        for job in jobs
    ]


@app.post("/api/jobs/applied", status_code=status.HTTP_201_CREATED)
def api_create_job_applied(
    payload: JobAppliedCreatePayload,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    jd_structured = payload.jd_structured or {}
    try:
        validate_json_size(json.dumps(jd_structured), max_size_mb=10.0)
    except TypeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="jd_structured must be JSON serializable.")

    company = sanitize_string(payload.company, max_length=200)
    role_title = sanitize_string(payload.role_title, max_length=200)
    source_url = payload.source_url.strip() if payload.source_url else None
    if source_url:
        source_url = validate_url(source_url)

    job = JobApplied(
        user_id=user.id,
        company=company,
        role_title=role_title,
        source_url=source_url,
        jd_structured=jd_structured,
        resume_bullets=payload.resume_bullets or [],
        cover_letter=payload.cover_letter,
    )

    session.add(job)

    locations_payload = []
    for location in jd_structured.get("locations", []) or []:
        if not isinstance(location, dict):
            continue
        lat = location.get("lat")
        lng = location.get("lng")
        try:
            lat = float(lat) if lat is not None else None
        except (TypeError, ValueError):
            lat = None
        try:
            lng = float(lng) if lng is not None else None
        except (TypeError, ValueError):
            lng = None
        label = location.get("label") or location.get("type") or location.get("city")
        raw_value = location.get("raw")
        if raw_value and not isinstance(raw_value, str):
            raw_value = json.dumps(raw_value)
        job_location = JobLocation(
            job_id=job.id,
            label=label,
            lat=lat,
            lng=lng,
            raw=raw_value,
        )
        locations_payload.append(job_location)

    if locations_payload:
        session.add_all(locations_payload)

    session.commit()
    session.refresh(job)

    home_coords = _home_coords(user)
    serialized = _serialize_job(job, locations_payload, include_details=True, home_coords=home_coords)
    return {"ok": True, "job": serialized}


@app.get("/api/jobs/applied")
def api_list_jobs_applied(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    return _serialized_jobs_for_user(session, user)


@app.get("/api/jobs/applied/{job_id}")
def api_get_job_applied(
    job_id: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    jobs = _serialized_jobs_for_user(session, user, job_id=job_id, include_details=True)
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return jobs[0]


@app.post("/api/geo/isochrone")
async def api_geo_isochrone(
    payload: IsochroneRequestPayload,
    current_user: User = Depends(require_user),
):
    _ = current_user  # authenticate only
    if not settings.mapbox_secret_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Isochrone service unavailable. Configure MAPBOX_SECRET_TOKEN or MAPBOX_ACCESS_TOKEN.",
        )

    url = (
        f"https://api.mapbox.com/isochrone/v1/mapbox/{payload.profile}/"
        f"{payload.lng},{payload.lat}"
    )
    params = {
        "contours_minutes": payload.minutes,
        "polygons": "true",
        "access_token": settings.mapbox_secret_token,
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)
    if response.status_code >= 400:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = response.text
        raise HTTPException(
            status_code=response.status_code,
            detail={"message": "Mapbox isochrone request failed.", "response": error_payload},
        )
    return response.json()


@app.get("/api/geo/distance")
def api_geo_distance(
    home_lat: float,
    home_lng: float,
    lat: float,
    lng: float,
    current_user: User = Depends(require_user),
):
    _ = current_user  # ensure authenticated
    km = haversine(home_lat, home_lng, lat, lng)
    return {"km": km, "miles": km * 0.621371}


@app.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    profile_json = json.dumps(user.mylife_json or {}, indent=2)
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "current_user": user,
            "profile": {
                "email": user.email,
                "full_name": user.full_name or "",
                "home_lat": user.home_lat,
                "home_lng": user.home_lng,
                "mylife_json": profile_json,
            },
        },
    )


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    jobs_payload = _serialized_jobs_for_user(session, user)
    from applications import JobApplication

    job_runs_raw = session.exec(
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(JobApplication.updated_at.desc())
    ).all()
    job_runs = [_serialize_job_run(run) for run in job_runs_raw]
    for job in jobs_payload:
        try:
            applied_dt = datetime.fromisoformat(job["applied_at"])
            job["applied_at_display"] = applied_dt.strftime("%b %d, %Y")
        except Exception:  # pylint: disable=broad-except
            job["applied_at_display"] = job["applied_at"]
    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "current_user": user,
            "jobs": jobs_payload,
            "job_runs": job_runs,
        },
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(
    job_id: str,
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    jobs = _serialized_jobs_for_user(session, user, job_id=job_id, include_details=True)
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    job_payload = jobs[0]
    try:
        applied_dt = datetime.fromisoformat(job_payload["applied_at"])
        job_payload["applied_at_display"] = applied_dt.strftime("%B %d, %Y")
    except Exception:  # pylint: disable=broad-except
        job_payload["applied_at_display"] = job_payload["applied_at"]
    return templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "current_user": user,
            "job": job_payload,
        },
    )


@app.get("/map", response_class=HTMLResponse)
def map_page(
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    user = _resolve_current_user(session, current_user)
    jobs_payload = _serialized_jobs_for_user(session, user, include_details=True)
    for job in jobs_payload:
        try:
            applied_dt = datetime.fromisoformat(job["applied_at"])
            job["applied_at_display"] = applied_dt.strftime("%Y-%m-%d")
        except Exception:  # pylint: disable=broad-except
            job["applied_at_display"] = job["applied_at"]
    has_token = bool(settings.MAPBOX_PUBLIC_TOKEN)
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "current_user": user,
            "jobs_json": json.dumps(jobs_payload),
            "profile_json": json.dumps(
                {
                    "home_lat": user.home_lat,
                    "home_lng": user.home_lng,
                    "full_name": user.full_name,
                }
            ),
            "has_mapbox_token": has_token,
        },
    )


@app.post("/auth/logout")
async def perform_logout(
    request: Request,
    csrf_token: str = Form(...),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)
    auth_logout(request)
    ensure_csrf_token(request, settings.SECRET_KEY)
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    response.headers["HX-Redirect"] = "/auth/login"
    return response


@app.get("/about", response_class=HTMLResponse)
async def about(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    context = {
        "request": request,
        "current_user": current_user
    }
    return templates.TemplateResponse("about.html", context)


@app.get("/compose", response_class=HTMLResponse)
async def compose(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

    context = {
        "request": request,
        "current_user": current_user
    }
    # Use the new workflow-integrated compose page
    return templates.TemplateResponse("compose_workflow.html", context)


@app.get("/compose/legacy", response_class=HTMLResponse)
async def compose_legacy(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
):
    """Legacy compose endpoint using LLM pipeline (for backwards compatibility)."""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

    context = {
        "request": request,
        "current_user": current_user
    }
    return templates.TemplateResponse("compose.html", context)


@app.post("/api/compose")
async def api_compose(
    request: Request,
    jd_url: str = Form(""),
    jd_text: str = Form(""),
    user_story: str = Form(""),
    csrf_token: str = Form(...),
    include_resume: Optional[str] = Form(None),
    include_cover_letter: Optional[str] = Form(None),
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)

    # Sanitize and validate inputs
    jd_url = sanitize_string(jd_url.strip(), max_length=2048)
    user_story = sanitize_string(user_story.strip(), max_length=5000)
    jd_text = sanitize_string(jd_text.strip(), max_length=50000)

    jd_parts = [segment for segment in [jd_text] if segment]
    warnings: list[str] = []

    if jd_url:
        try:
            # Validate URL format
            validate_url(jd_url, require_https=False)
            fetched_text = await _fetch_jd_text(jd_url)
            if fetched_text:
                jd_parts.append(sanitize_string(fetched_text, max_length=50000))
        except HTTPException as exc:
            warnings.append(f"Invalid URL: {exc.detail}")
        except Exception as exc:  # pylint: disable=broad-except
            warnings.append(f"Unable to retrieve job description from URL: {exc}")

    jd_content = "\n\n".join(jd_parts).strip()
    if not jd_content:
        return JSONResponse(
            {"ok": False, "errors": ["Provide a job description URL or text."], "warnings": warnings},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    jd_factors, jd_meta = await pipeline.extract_jd_factors(jd_content)

    graph_payload: Any = current_user.mylife_json or {"nodes": [], "edges": []}

    with Session(engine) as validation_session:
        loader = GraphLoader(validation_session, user_id=current_user.id)
        validation_result = loader.validate_and_upsert(graph_payload, commit=False)
    if not validation_result.ok:
        return JSONResponse(
            {
                "ok": False,
                "errors": ["Experience graph validation failed."] + validation_result.errors,
                "warnings": warnings,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        node_payloads, edge_payloads = parse_graph_payload(graph_payload)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "errors": [str(exc)], "warnings": warnings},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ranked_facts = rank_facts(node_payloads, edge_payloads, jd_factors, top_n=25)
    selected_facts = _select_diverse_facts(ranked_facts, limit=5)

    resume_requested = include_resume is not None
    cover_letter_requested = include_cover_letter is not None

    resume_bullets: list[str] = []
    cover_letter_text: Optional[str] = None
    cover_letter_refs: list[str] = []

    resume_meta: dict[str, Any] = {
        "status": "not_requested",
        "source": "skipped",
        "model": None,
        "usage": {"total_tokens": 0},
    }
    cover_letter_meta: dict[str, Any] = {
        "status": "not_requested",
        "source": "skipped",
        "model": None,
        "usage": {"total_tokens": 0},
    }

    if resume_requested:
        resume_bullets, resume_meta = await pipeline.generate_bullets(selected_facts, jd_factors)

    cover_letter_payload: Optional[Dict[str, Any]] = None
    if cover_letter_requested:
        cover_letter_payload, cover_letter_meta = await pipeline.generate_cover_letter(
            selected_facts,
            jd_factors,
            user_story,
        )
        cover_letter_text = cover_letter_payload.get("cover_letter") if cover_letter_payload else None
        cover_letter_refs = cover_letter_payload.get("fact_refs", []) if cover_letter_payload else []

    all_metas = [jd_meta, resume_meta, cover_letter_meta]
    tokens_used = sum(int(meta.get("usage", {}).get("total_tokens", 0) or 0) for meta in all_metas)
    model_candidates = [meta.get("model") for meta in all_metas if meta.get("model")]
    llm_model = model_candidates[0] if model_candidates else (pipeline.model if hasattr(pipeline, "model") else None)
    validation_status = {
        "jd_factors": jd_meta.get("status"),
        "resume_bullets": resume_meta.get("status"),
        "cover_letter": cover_letter_meta.get("status"),
    }

    # Calculate ATS keyword coverage
    ats_keywords = jd_factors.get("ats_keywords", [])
    ats_total = len(ats_keywords)
    ats_covered = 0

    if ats_keywords and (resume_bullets or cover_letter_text):
        # Combine all generated text
        all_generated_text = " ".join(resume_bullets) if resume_bullets else ""
        if cover_letter_text:
            all_generated_text += " " + cover_letter_text
        all_generated_lower = all_generated_text.lower()

        # Count how many ATS keywords are present
        for keyword in ats_keywords:
            if keyword and keyword.lower() in all_generated_lower:
                ats_covered += 1

    ats_coverage = {"total": ats_total, "covered": ats_covered}

    run_inputs = {
        "jd_url": jd_url or None,
        "include_resume": resume_requested,
        "include_cover_letter": cover_letter_requested,
        "user_story": user_story,
    }
    run_outputs = {
        "resume_bullets": resume_bullets,
        "cover_letter": cover_letter_text,
        "cover_letter_fact_refs": cover_letter_refs,
        "warnings": warnings,
        "ats_coverage": ats_coverage,
    }

    run = ComposeRun(
        owner_id=current_user.id,
        jd_source_url=jd_url or None,
        jd_text_excerpt=_make_excerpt(jd_content),
        jd_factors=jd_factors,
        selected_fact_ids=[fact.get("id") for fact in selected_facts if fact.get("id")],
        options={
            "resume": resume_requested,
            "cover_letter": cover_letter_requested,
            "warnings": warnings,
            "cover_letter_fact_refs": cover_letter_refs,
        },
        resume_bullets=resume_bullets,
        cover_letter=cover_letter_text,
        llm_model=llm_model,
        tokens_used=tokens_used,
        validation_status=validation_status,
        inputs=run_inputs,
        outputs=run_outputs,
    )
    session.add(run)
    session.commit()

    response_payload = {
        "ok": True,
        "jd_factors": jd_factors,
        "selected_facts": [_prepare_fact_response(fact) for fact in selected_facts],
        "resume_bullets": resume_bullets,
        "cover_letter": cover_letter_text,
        "cover_letter_fact_refs": cover_letter_refs,
        "ats_coverage": ats_coverage,
        "llm_summary": {
            "model": llm_model,
            "tokens_used": tokens_used,
            "validation_status": validation_status,
        },
        "warnings": warnings,
    }

    return JSONResponse(response_payload)

@app.get("/admin/users")
async def admin_users(
    current_admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> JSONResponse:
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    payload = [
        {
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat(),
        }
        for user in users
    ]
    return JSONResponse({"users": payload})


@app.get("/admin/runs")
async def admin_runs(
    current_admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> JSONResponse:
    runs = session.exec(select(ComposeRun).order_by(ComposeRun.created_at.desc()).limit(100)).all()
    payload = [
        {
            "id": run.id,
            "owner_id": run.owner_id,
            "llm_model": run.llm_model,
            "tokens_used": run.tokens_used,
            "validation_status": run.validation_status,
            "created_at": run.created_at.isoformat(),
        }
        for run in runs
    ]
    return JSONResponse({"runs": payload})


@app.get("/runs", response_class=HTMLResponse)
async def user_runs(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url="/jobs", status_code=status.HTTP_303_SEE_OTHER)


@app.delete("/api/runs/{run_id}")
async def delete_run(
    run_id: int,
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    # Extract CSRF token from JSON body
    body = await request.json()
    csrf_token = body.get("csrf_token")
    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)

    run = session.get(ComposeRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )

    if run.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own runs.",
        )

    session.delete(run)
    session.commit()

    return JSONResponse({"ok": True, "message": "Run deleted successfully."})


@app.get("/api/runs/{run_id}/debug-logs")
async def get_run_debug_logs(
    run_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Get debug logs for a specific compose run."""
    from models import APIDebugLog

    run = session.get(ComposeRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )

    if run.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own run logs.",
        )

    # Get all debug logs for this run
    logs = session.exec(
        select(APIDebugLog)
        .where(APIDebugLog.compose_run_id == run_id)
        .order_by(APIDebugLog.created_at.asc())
    ).all()

    log_entries = [
        {
            "id": log.id,
            "log_type": log.log_type,
            "endpoint": log.endpoint,
            "method": log.method,
            "status_code": log.status_code,
            "request_data": log.request_data,
            "response_data": log.response_data,
            "error_message": log.error_message,
            "duration_ms": log.duration_ms,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]

    return JSONResponse({"ok": True, "logs": log_entries})


@app.get("/api/applications/{application_id}")
async def get_application(
    application_id: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Get application data."""
    from applications import JobApplication

    app_record = session.get(JobApplication, application_id)
    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    # Check if user owns this application
    if str(app_record.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own applications.",
        )

    return JSONResponse({
        "ok": True,
        "application_id": app_record.id,
        "user_id": app_record.user_id,
        "source_url": app_record.source_url,
        "jd_status": app_record.jd_status,
        "jd_struct_data": app_record.jd_struct_data,
        "resume_status": app_record.resume_status,
        "resume_output": app_record.resume_output,
        "created_at": app_record.created_at.isoformat(),
        "updated_at": app_record.updated_at.isoformat(),
    })


@app.get("/applications/{application_id}/details", response_class=HTMLResponse)
async def view_application_details(
    application_id: str,
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
):
    """Render a detail page for a workflow run (JobApplication)."""
    from applications import JobApplication

    app_record = session.get(JobApplication, application_id)
    if not app_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    if str(current_user.id) != app_record.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own runs.")

    resume_output = app_record.resume_output if isinstance(app_record.resume_output, dict) else {}
    resume_bullets = []
    if isinstance(resume_output, dict):
        resume_bullets = (
            resume_output.get("resume_bullets")
            or (resume_output.get("output_parsed") or {}).get("resume_bullet_points")
            or []
        )
    resume_bullets_text = None
    if isinstance(resume_output, dict):
        resume_bullets_text = resume_output.get("resume_bullets_text")
        if not resume_bullets_text and resume_bullets:
            resume_bullets_text = "\n".join(f"- {bullet}" for bullet in resume_bullets)

    structured_job_json = json.dumps(app_record.jd_struct_data or {}, indent=2, default=str)
    resume_output_json = json.dumps(resume_output or {}, indent=2, default=str)

    context = {
        "request": request,
        "current_user": current_user,
        "application": app_record,
        "resume_bullets": resume_bullets,
        "resume_bullets_text": resume_bullets_text,
        "structured_job_json": structured_job_json,
        "resume_output_json": resume_output_json,
    }
    return templates.TemplateResponse("application_detail.html", context)


@app.get("/api/applications/{application_id}/debug-logs")
async def get_application_debug_logs(
    application_id: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Get debug logs for a specific job application (workflow-based)."""
    from applications import JobApplication
    from models import APIDebugLog

    app_record = session.get(JobApplication, application_id)
    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    # Check if user owns this application
    if str(app_record.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own application logs.",
        )

    # Get all debug logs for this application
    logs = session.exec(
        select(APIDebugLog)
        .where(APIDebugLog.application_id == application_id)
        .order_by(APIDebugLog.created_at.asc())
    ).all()

    log_entries = [
        {
            "id": log.id,
            "log_type": log.log_type,
            "endpoint": log.endpoint,
            "method": log.method,
            "status_code": log.status_code,
            "request_data": log.request_data,
            "response_data": log.response_data,
            "error_message": log.error_message,
            "duration_ms": log.duration_ms,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]

    return JSONResponse({"ok": True, "logs": log_entries})


@app.post("/api/applications/{application_id}/abort")
async def abort_application_run(
    application_id: str,
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Abort a running job application."""
    from applications import JobApplication

    # Extract CSRF token from JSON body
    body = await request.json()
    csrf_token = body.get("csrf_token")
    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)

    app_record = session.get(JobApplication, application_id)
    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    # Check if user owns this application
    if str(app_record.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only abort your own application runs.",
        )

    # Only abort if it's actually running
    if app_record.jd_status not in ["running", "pending"] and app_record.resume_status not in ["running", "pending"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application is not in a running state.",
        )

    # Mark as aborted
    app_record.jd_status = "aborted"
    app_record.resume_status = "aborted"
    app_record.resume_output = app_record.resume_output or {}
    if isinstance(app_record.resume_output, dict):
        app_record.resume_output["aborted"] = True
        app_record.resume_output["aborted_by_user"] = True
    app_record.updated_at = datetime.utcnow()

    session.add(app_record)
    session.commit()
    session.refresh(app_record)

    return JSONResponse({"ok": True, "message": "Run aborted successfully.", "application_id": app_record.id})


@app.post("/api/applications/{application_id}/reparse")
async def reparse_application_from_debug_logs(
    application_id: str,
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """
    Reparse an application's output from debug logs.

    This is useful when the initial parsing failed or returned incomplete data.
    The system will search debug logs for the complete workflow output.
    """
    from applications import JobApplication
    from services.debug_log_parser import parse_complete_workflow_from_debug_logs

    # Extract CSRF token from JSON body
    body = await request.json()
    csrf_token = body.get("csrf_token")
    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)

    # Get the application
    app_record = session.get(JobApplication, application_id)
    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    # Check ownership
    if str(app_record.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reparse your own applications.",
        )

    # Parse from debug logs
    debug_result = parse_complete_workflow_from_debug_logs(session, application_id)

    if not debug_result["success"]:
        return JSONResponse({
            "ok": False,
            "message": "No valid data found in debug logs.",
            "parsing_attempted": True
        }, status_code=404)

    # Update the application with the parsed data
    if debug_result["structured_job"]:
        app_record.jd_struct_data = debug_result["structured_job"]
        app_record.jd_status = "succeeded"

    if debug_result["resume_bullets"]:
        app_record.resume_output = app_record.resume_output or {}
        app_record.resume_output["resume_bullets"] = debug_result["resume_bullets"]
        app_record.resume_output["cover_letter"] = debug_result["cover_letter"]
        app_record.resume_output["decoder_source"] = "debug_log_parser_manual"
        app_record.resume_output["parsing_strategy"] = debug_result["parsing_strategy"]
        app_record.resume_status = "succeeded"

    if debug_result["run_id"]:
        app_record.jd_run_id = debug_result["run_id"]
        app_record.resume_run_id = debug_result["run_id"]

    app_record.updated_at = datetime.utcnow()
    session.add(app_record)
    session.commit()
    session.refresh(app_record)

    return JSONResponse({
        "ok": True,
        "message": "Application reparsed successfully from debug logs.",
        "jd_status": app_record.jd_status,
        "resume_status": app_record.resume_status,
        "has_structured_job": bool(app_record.jd_struct_data),
        "has_resume_bullets": bool(app_record.resume_output and app_record.resume_output.get("resume_bullets")),
        "parsing_strategy": debug_result["parsing_strategy"]
    })


@app.post("/api/applications/{application_id}/link-to-job")
async def link_application_to_job(
    application_id: str,
    request: Request,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Link a workflow run (JobApplication) to an applied job (JobApplied)."""
    from applications import JobApplication

    # Extract CSRF token and job_id from JSON body
    body = await request.json()
    csrf_token = body.get("csrf_token")
    job_id = body.get("job_id")

    validate_csrf_token(request, csrf_token, settings.SECRET_KEY)

    if not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id is required.",
        )

    # Get the application run
    app_record = session.get(JobApplication, application_id)
    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application run not found.",
        )

    # Check if user owns this application
    if str(app_record.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only link your own application runs.",
        )

    # Verify the job exists and belongs to the user
    job = session.get(JobApplied, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applied job not found.",
        )

    if str(job.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only link to your own applied jobs.",
        )

    # Link the application to the job
    app_record.linked_job_id = job_id
    app_record.updated_at = datetime.utcnow()

    session.add(app_record)
    session.commit()
    session.refresh(app_record)

    return JSONResponse({
        "ok": True,
        "message": "Run linked to job successfully.",
        "application_id": app_record.id,
        "linked_job_id": job_id
    })
