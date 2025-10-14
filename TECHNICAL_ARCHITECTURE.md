# MyApply Technical Architecture Documentation

**Last Updated:** October 13, 2025
**Version:** 2.0

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Patterns](#architecture-patterns)
3. [AgentKit Workflow System](#agentkit-workflow-system)
4. [ChatKit Integration](#chatkit-integration)
5. [API Architecture](#api-architecture)
6. [Data Flow Diagrams](#data-flow-diagrams)
7. [Database Schema](#database-schema)
8. [Service Layer](#service-layer)
9. [Security Architecture](#security-architecture)
10. [Testing Strategy](#testing-strategy)

---

## System Overview

MyApply is an AI-powered career application platform built on FastAPI that orchestrates OpenAI AgentKit workflows to transform job descriptions into tailored resumes and cover letters.

### Core Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI 0.100+ | High-performance async API |
| **ORM** | SQLModel | Type-safe database operations |
| **Database** | PostgreSQL (psycopg v3) / SQLite | Data persistence |
| **AI Orchestration** | OpenAI AgentKit SDK | Workflow execution |
| **Frontend** | Jinja2 + HTMX + TailwindCSS | Server-rendered reactive UI |
| **LLM Provider** | OpenAI API (GPT-4o-mini) | Language model operations |
| **Maps** | Mapbox GL JS + Isochrone API | Location visualization |
| **Auth** | Passlib[bcrypt] + itsdangerous | Secure authentication |

### System Architecture Principles

1. **Backend Conductor Pattern**: Central orchestrator coordinates workflows
2. **Stateless Workflows**: No inter-workflow communication; backend passes data
3. **Defensive Design**: Comprehensive error handling and validation
4. **Type Safety**: Pydantic models throughout the stack
5. **Progressive Enhancement**: Works without JavaScript, enhanced with HTMX

---

## Architecture Patterns

### 1. Backend Conductor Pattern

The application uses a **conductor pattern** where FastAPI endpoints orchestrate AgentKit workflows:

```
┌─────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│                   (Conductor)                        │
│                                                      │
│  ┌──────────────┐         ┌──────────────┐         │
│  │  JD Ingest   │────────▶│ Resume Build │         │
│  │   Router     │         │    Router    │         │
│  └──────────────┘         └──────────────┘         │
│         │                        │                  │
│         ▼                        ▼                  │
│  ┌──────────────────────────────────────────────┐  │
│  │   services/openai_workflows.py               │  │
│  │   (Workflow Execution Layer)                 │  │
│  └──────────────────────────────────────────────┘  │
│         │                                           │
└─────────┼───────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────┐
│          OpenAI AgentKit Platform                    │
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │    ResumeBuilderV2 Workflow                 │    │
│  │                                              │    │
│  │  ┌──────────────┐    ┌──────────────────┐  │    │
│  │  │ Job Scraper  │───▶│ Bullet Generator │  │    │
│  │  │    Agent     │    │      Agent       │  │    │
│  │  └──────────────┘    └──────────────────┘  │    │
│  └────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Key Characteristics:**
- Workflows are **stateless** and don't call each other
- Backend explicitly passes outputs from one workflow as inputs to the next
- All workflow metadata stored in `workflow_run` table
- Artifacts extracted and stored in `artifact` table
- Debug logs captured in `api_debug_log` table

### 2. Request Flow Architecture

```
User Request
    │
    ▼
┌─────────────────────┐
│   FastAPI Routes    │ ← Auth middleware, CSRF validation
│   (/api/jd/ingest)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Request Validation │ ← Pydantic models
│   (JDIngestRequest) │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Application Model  │ ← Create/update JobApplication
│   (applications.py) │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Workflow Executor  │ ← services/openai_workflows.py
│   run_workflow()    │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  AgentKit Service   │ ← services/resume_builder_service.py
│ _execute_workflow() │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│   Agent Execution   │ ← job_scraper, bullet_generator
│   (AgentKit SDK)    │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Output Parser      │ ← services/workflow_output_parser.py
│  parse_result()     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Database Persist   │ ← Update JobApplication with results
│  (SQLModel/SQLite)  │
└─────────────────────┘
    │
    ▼
Response to User
```

---

## AgentKit Workflow System

### Workflow Architecture

MyApply uses the **OpenAI AgentKit SDK** to execute AI workflows locally. The AgentKit SDK allows agent definitions to live directly in the codebase ([services/resume_builder_agents.py](services/resume_builder_agents.py)) and execute synchronously or asynchronously via the `Runner` API.

### ResumeBuilderV2 Workflow

**Location:** [services/resume_builder_agents.py](services/resume_builder_agents.py)

This module contains the AgentKit agent definitions that orchestrate job description parsing and resume generation. Agents execute locally using the AgentKit SDK, not via external workflow IDs.

#### Agent Graph

```
Input: Job URL or Text
    │
    ▼
┌─────────────────────────────────────────────────┐
│            job_scraper Agent                     │
│  Model: gpt-4o-mini                             │
│  Tools: extract_ats_keywords, web_search        │
│  Output: JobScraperSchema (structured job data) │
└─────────────────────────────────────────────────┘
    │
    │ (structured_job_data JSON)
    ▼
┌─────────────────────────────────────────────────┐
│         bullet_generator Agent                   │
│  Model: gpt-4o-mini                             │
│  Tools: web_search                              │
│  Output: reasoning, plan, resume_bullet_points  │
└─────────────────────────────────────────────────┘
    │
    ▼
Final Output:
{
  "structured_job_data": {...},
  "resume_bullets": [...],
  "cover_letter": "..."
}
```

#### Job Scraper Agent

**Purpose:** Extract structured information from job postings

**Configuration:**
```python
Agent(
    name="Job scraper",
    model="gpt-4o-mini",
    tools=[extract_ats_keywords, web_search_preview],
    output_type=JobScraperSchema,
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
        max_tokens=2048,
        store=True
    )
)
```

**Output Schema:**
```python
class JobScraperSchema(BaseModel):
    company: JobScraperSchemaCompany
    locations: list[JobScraperSchemaLocationsItem]
    role: JobScraperSchemaRole
    team: JobScraperSchemaTeam
    experience: JobScraperSchemaExperience
    skills: JobScraperSchemaSkills
```

**Extraction Categories:**
- `required_skills`: Technical and soft skills explicitly required
- `nice_to_have_skills`: Preferred but not mandatory skills
- `required_experience`: Years of experience and specific backgrounds
- `locations`: Job locations (remote, hybrid, on-site)
- `desired_skills`: Additional beneficial skills
- `other_noteworthy`: Visa requirements, travel expectations, etc.

#### Bullet Generator Agent

**Purpose:** Generate tailored resume bullets based on structured job data

**Configuration:**
```python
Agent(
    name="Bullet Generator",
    model="gpt-4o-mini",
    tools=[web_search_preview],
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
        max_tokens=2048,
        store=True
    )
)
```

**Generation Process:**
1. **Analyze** job JSON for key responsibilities and skills
2. **Research** effective resume bullet examples via web search
3. **Plan** outline for each bullet point (action, skill, impact)
4. **Generate** 3-6 achievement-focused bullets with quantifiable metrics

**Output Structure:**
```json
{
  "reasoning": "Analysis and planning rationale...",
  "plan": [
    "Bullet 1 plan: action + skill + impact",
    "Bullet 2 plan: ..."
  ],
  "resume_bullet_points": [
    "Engineered scalable APIs...",
    "Collaborated with teams..."
  ]
}
```

### Workflow Execution Service

**Location:** `services/resume_builder_service.py`

**Key Class:** `AgentWorkflowRun`
```python
@dataclass
class AgentWorkflowRun:
    id: str                    # Unique run identifier
    status: str                # "completed", "failed", "error"
    workflow_id: str           # Workflow constant ID
    version: str               # Workflow version
    output: Dict[str, Any]     # Parsed workflow results
```

**Execution Flow:**
```python
async def _execute_resume_builder_async(job_input: str) -> Dict[str, Any]:
    # Step 1: Run job scraper agent
    scraper_result = await Runner.run(job_scraper, job_input)
    structured_job = scraper_result.final_output

    # Step 2: Pass structured job to bullet generator
    bullet_input = json.dumps(structured_job)
    bullets_result = await Runner.run(bullet_generator, bullet_input)

    # Step 3: Combine outputs
    return {
        "structured_job_data": structured_job,
        "resume_bullets": bullets_result.final_output.get("resume_bullet_points"),
        "cover_letter": bullets_result.final_output.get("cover_letter")
    }
```

**Synchronous Wrapper:**
The service provides `run_resume_builder_workflow()` which wraps the async execution for use in synchronous FastAPI endpoints.

### Workflow Integration Layer

**Location:** [services/openai_workflows.py](services/openai_workflows.py)

**Purpose:** Compatibility wrapper that provides a familiar API surface for calling AgentKit workflows

**Key Function:**
```python
def run_workflow(
    workflow_id: str,
    version: str,
    inputs: Dict[str, Any],
    db_session: Optional[Session] = None,
    application_id: Optional[str] = None,
) -> AgentWorkflowRun:
    """
    Execute workflow with logging and error handling.
    Mimics the OpenAI Workflows API contract.
    """
```

**Features:**
- Debug logging via `log_agentkit_call()` context manager
- Error handling with HTTPException mapping
- Input normalization (extracts job text from various input formats)
- Output standardization to match legacy Workflows API format

### Output Parsing System

**Location:** `services/workflow_output_parser.py`

**Purpose:** Robust extraction of structured data from workflow outputs

**Key Functions:**

1. **`flatten_workflow_output(run)`**
   - Normalizes workflow output structure
   - Handles dict, string (JSON), and Pydantic model outputs

2. **`extract_structured_job(payload)`**
   - Recursively searches for structured job data
   - Validates presence of key fields: `required_skills`, `locations`, etc.

3. **`extract_resume_bullets(payload)`**
   - Normalizes bullet formats (array, string, nested objects)
   - Cleans markdown-style prefixes (-, •, *)

4. **`extract_cover_letter(payload)`**
   - Searches for cover letter text in multiple possible keys
   - Returns cleaned string output

5. **`parse_resume_builder_result(run)`**
   - Master function that extracts all artifacts
   - Returns: `(parsed_output, structured_job, resume_bullets, cover_letter)`

### Workflow Constants

**Location:** [workflow_constants.py](workflow_constants.py)

```python
WORKFLOW_RESUME_BUILDER_V2_ID = "wf_68ec6800d1948190a0629c0eaf07f8e303633b84fcb85ab9"
WORKFLOW_RESUME_BUILDER_V2_VER = "1"
```

These IDs are used for logging and tracing purposes only. The workflow executes locally via the AgentKit SDK, not through an external OpenAI platform deployment.

---

## ChatKit Integration (Not Currently Implemented)

### Overview

The codebase includes preliminary infrastructure for OpenAI ChatKit integration in the `chatkit_integration/` directory. However, **ChatKit is not currently active or functional** in the application.

### Implementation Status

The `chatkit_integration/` directory contains preliminary code for a conversational AI interface, but it is **not currently integrated** into the main FastAPI application. The `/chatkit` endpoint is not registered, and the ChatKit server is not initialized.

**Existing Files:**
- `chatkit_integration/server.py` - Server scaffolding
- `chatkit_integration/store.py` - SQLModel-based storage layer
- `chatkit_integration/models.py` - Data models for threads and messages

**Tables Defined (but not actively used):**
- `chatkit_thread` - Conversation thread metadata
- `chatkit_thread_item` - Individual messages in threads

If you plan to activate ChatKit, you would need to:
1. Register the `/chatkit` endpoint in `app.py`
2. Initialize `MyChatKitServer` with the database engine
3. Wire up authentication and authorization for chat access

---

## API Architecture

### Route Organization

```
app.py                          # Main FastAPI app + core routes
├── routers/
│   ├── jd_ingest.py           # Job description ingestion
│   └── resume_build.py         # Resume generation
├── services/
│   ├── openai_workflows.py     # Workflow execution
│   ├── resume_builder_agents.py # Agent definitions
│   ├── resume_builder_service.py # Workflow orchestration
│   └── workflow_output_parser.py # Output extraction
└── chatkit_integration/
    ├── server.py               # ChatKit server
    ├── store.py                # Persistence layer
    └── models.py               # Data models
```

### API Endpoints

#### Workflow Orchestration

**1. Job Description Ingestion**
```http
POST /api/jd/ingest
Content-Type: application/json

{
  "user_id": "string",
  "source_url": "https://...",  # Optional
  "jd_text": "Job description", # Optional
  "application_id": "uuid"      # Optional
}
```

**Response:**
```json
{
  "application_id": "uuid",
  "jd_status": "succeeded",
  "jd_struct_data": {
    "required_skills": ["Python", "FastAPI"],
    "locations": ["Remote"],
    "required_experience": ["5+ years"]
  }
}
```

**Flow:**
1. Validate input (URL or text required)
2. Create or update `JobApplication` record
3. Execute `ResumeBuilderV2` workflow
4. Parse structured job data from output
5. Update application with results
6. Return structured job data (bullets/cover letter cached internally)

**2. Resume Building**
```http
POST /api/resume/build
Content-Type: application/json

{
  "user_id": "string",
  "job_url": "https://...",
  "application_id": "uuid"  # Optional
}
```

**Response:**
```json
{
  "application_id": "uuid",
  "source_url": "https://...",
  "resume_run_id": "workflow-run-id",
  "resume_status": "succeeded",
  "structured_job_data": {...},
  "resume_bullets": [
    "Engineered scalable APIs...",
    "Collaborated with teams..."
  ],
  "cover_letter": "I am excited to apply...",
  "resume_output": {
    "resume_bullets": [...],
    "cover_letter": "...",
    "structured_job_data": {...}
  }
}
```

**Flow:**
1. Validate user and job URL
2. Check for cached output in `resume_output` field
3. If cached, return immediately
4. Otherwise, execute `ResumeBuilderV2` workflow
5. Parse all outputs (job data, bullets, cover letter)
6. Persist to database
7. Return complete results

#### Authentication

**Login**
```http
GET  /auth/login          # Show login form
POST /auth/login          # Perform login
```

**Register**
```http
GET  /auth/register       # Show registration form
POST /auth/register       # Create account
```

**Logout**
```http
POST /auth/logout         # End session
```

#### Profile Management

**Get Profile**
```http
GET /api/profile
```

**Update Profile**
```http
POST /api/profile/update
Content-Type: application/json

{
  "full_name": "string",
  "home_lat": 37.7749,
  "home_lng": -122.4194,
  "mylife_json": {
    "nodes": [...],
    "edges": [...]
  }
}
```

#### Job Applications

**List Applications**
```http
GET /api/jobs/applied
```

**Get Application Detail**
```http
GET /api/jobs/applied/{job_id}
```

**Create Application**
```http
POST /api/jobs/applied
Content-Type: application/json

{
  "company": "string",
  "role_title": "string",
  "source_url": "https://...",
  "jd_structured": {...},
  "resume_bullets": [...]
}
```

#### Geographic APIs

**Isochrone**
```http
POST /api/geo/isochrone
Content-Type: application/json

{
  "lat": 37.7749,
  "lng": -122.4194,
  "minutes": 30,
  "profile": "driving"  # or "walking", "cycling"
}
```

**Distance Calculation**
```http
GET /api/geo/distance?home_lat=...&home_lng=...&lat=...&lng=...
```

#### Health Checks

```http
GET /health        # Basic health check
GET /health/db     # Database connectivity check
```

#### Admin APIs

```http
GET /admin/users   # List all users (admin only)
GET /admin/runs    # List workflow runs (admin only)
```

### Request/Response Models

All API endpoints use **Pydantic models** for validation:

**JD Ingest:**
```python
class JDIngestRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    source_url: Optional[str] = Field(None, min_length=5, max_length=2048)
    jd_text: Optional[str] = Field(None, max_length=100000)
    application_id: Optional[str] = Field(default=None)
```

**Resume Build:**
```python
class ResumeBuilderV2Request(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=255)
    job_url: str = Field(..., min_length=5, max_length=2048)
    application_id: Optional[str] = Field(default=None)
```

**Profile Update:**
```python
class ProfileUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    home_lat: Optional[float] = None
    home_lng: Optional[float] = None
    mylife_json: Optional[Dict[str, Any]] = None
```

### Middleware Stack

```python
# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # From ALLOWED_ORIGINS env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    https_only=settings.SESSION_SECURE,      # Auto: True for prod, False for local
    same_site=settings.SESSION_SAMESITE,      # "lax"
)
```

### Error Handling

**Global Exception Handlers:**
```python
@app.exception_handler(404)
async def not_found_handler(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "Not found"})
    return templates.TemplateResponse("error.html", {...}, status_code=404)

@app.exception_handler(403)
async def forbidden_handler(request, exc): ...

@app.exception_handler(500)
async def internal_error_handler(request, exc): ...
```

---

## Data Flow Diagrams

### Complete Request Flow: JD Ingestion to Resume Generation

```
┌────────────┐
│   Client   │
│  (Browser) │
└─────┬──────┘
      │
      │ 1. POST /api/jd/ingest
      │    { source_url: "https://job.com" }
      ▼
┌─────────────────────────────────────────────┐
│          FastAPI Middleware                  │
│  • CORS validation                           │
│  • Session authentication                    │
│  • CSRF token validation                     │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│      routers/jd_ingest.py                    │
│  • Validate JDIngestRequest                  │
│  • Ensure user exists                        │
│  • Validate URL format                       │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│      applications.py (Model)                 │
│  • Create JobApplication record              │
│  • Set jd_status = "running"                 │
│  • Persist to database                       │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│   services/openai_workflows.py               │
│  • Extract job text from inputs              │
│  • Initialize debug logger                   │
│  • Call run_resume_builder_workflow()        │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│   services/resume_builder_service.py         │
│  • run_resume_builder_workflow()             │
│  • Wrap async execution in sync context      │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  _execute_resume_builder_async()             │
│                                              │
│  Step 1: Job Scraper Agent                  │
│  ┌────────────────────────────────────────┐ │
│  │ Runner.run(job_scraper, job_url)       │ │
│  │ • Fetch job posting content            │ │
│  │ • Extract structured data via LLM      │ │
│  │ • Tools: extract_ats_keywords, search  │ │
│  │ • Output: JobScraperSchema             │ │
│  └────────────────────────────────────────┘ │
│         │                                    │
│         │ structured_job_data                │
│         ▼                                    │
│  Step 2: Bullet Generator Agent             │
│  ┌────────────────────────────────────────┐ │
│  │ Runner.run(bullet_generator, job_json) │ │
│  │ • Analyze structured job requirements  │ │
│  │ • Research resume examples via search  │ │
│  │ • Plan bullet point strategy           │ │
│  │ • Generate 3-6 tailored bullets        │ │
│  │ • Output: reasoning, plan, bullets     │ │
│  └────────────────────────────────────────┘ │
│         │                                    │
│         ▼                                    │
│  Return combined output:                    │
│  {                                           │
│    "structured_job_data": {...},            │
│    "resume_bullets": [...],                 │
│    "cover_letter": "..."                    │
│  }                                           │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  services/workflow_output_parser.py          │
│  • parse_resume_builder_result()             │
│  • Extract structured_job_data               │
│  • Extract resume_bullets                    │
│  • Extract cover_letter                      │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  routers/jd_ingest.py (continued)            │
│  • Update JobApplication:                    │
│    - jd_status = "succeeded"                 │
│    - jd_struct_data = structured_job         │
│    - resume_output = { bullets, letter }     │
│  • Commit to database                        │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Response to Client                          │
│  {                                           │
│    "application_id": "uuid",                 │
│    "jd_status": "succeeded",                 │
│    "jd_struct_data": {...}                   │
│  }                                           │
└─────────────────────────────────────────────┘
      │
      │ 2. Client calls POST /api/resume/build
      │    { application_id: "uuid", job_url: "..." }
      ▼
┌─────────────────────────────────────────────┐
│  routers/resume_build.py                     │
│  • Load JobApplication by ID                 │
│  • Check resume_output cache                 │
│  • If cached: extract and return             │
│  • If not cached: run workflow (same steps)  │
│  • Update resume_status = "succeeded"        │
│  • Return full output:                       │
│    - structured_job_data                     │
│    - resume_bullets                          │
│    - cover_letter                            │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Client Receives Complete Application       │
│  • Structured job requirements               │
│  • Tailored resume bullets                   │
│  • Personalized cover letter                 │
└─────────────────────────────────────────────┘
```

### Note on ChatKit

ChatKit integration is not currently active in the application. See the [ChatKit Integration](#chatkit-integration-not-currently-implemented) section above for details.

---

## Database Schema

### Core Tables

#### User Management

**`user` table:**
```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    full_name VARCHAR,
    home_lat FLOAT,
    home_lng FLOAT,
    mylife_json JSON NOT NULL DEFAULT '{}'
);

CREATE INDEX ix_user_email_unique ON user(email);
```

**Fields:**
- `mylife_json`: Experience graph (nodes and edges representing career history)
- `home_lat/lng`: User's home location for distance calculations

#### Application Tracking

**`jobapplication` table:**
```sql
CREATE TABLE jobapplication (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES user(id),
    source_url VARCHAR NOT NULL,
    jd_run_id VARCHAR,
    jd_status VARCHAR DEFAULT 'pending',  -- pending|running|succeeded|failed
    jd_struct_data JSON,
    resume_run_id VARCHAR,
    resume_status VARCHAR DEFAULT 'idle',  -- idle|running|succeeded|failed
    resume_output JSON,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_jobapplication_user_id ON jobapplication(user_id);
```

**Status Flow:**
```
JD Status:    pending → running → succeeded/failed
Resume Status: idle → running → succeeded/failed
```

#### Workflow Metadata

**`workflow_run` table:**
```sql
CREATE TABLE workflow_run (
    id VARCHAR PRIMARY KEY,
    workflow_id VARCHAR NOT NULL,
    version VARCHAR NOT NULL,
    status VARCHAR NOT NULL,  -- success|error|invalid
    user_id INTEGER NOT NULL REFERENCES user(id),
    input_json JSON NOT NULL,
    output_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_workflow_run_user_created ON workflow_run(user_id, created_at);
CREATE INDEX ix_workflow_run_workflow_id_custom ON workflow_run(workflow_id);
```

**`artifact` table:**
```sql
CREATE TABLE artifact (
    id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL REFERENCES workflow_run(id),
    kind VARCHAR NOT NULL,  -- 'structured_jd', 'resume_bullets', 'warnings'
    label VARCHAR,
    payload_json JSON NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_artifact_run_id ON artifact(run_id);
CREATE INDEX ix_artifact_kind ON artifact(kind);
```

#### Debug Logging

**`api_debug_log` table:**
```sql
CREATE TABLE api_debug_log (
    id VARCHAR PRIMARY KEY,
    compose_run_id INTEGER REFERENCES composerun(id),
    application_id VARCHAR REFERENCES jobapplication(id),
    log_type VARCHAR NOT NULL,  -- 'agentkit_call', 'agentkit_response'
    endpoint VARCHAR,
    method VARCHAR,
    status_code INTEGER,
    request_data JSON,
    response_data JSON,
    error_message VARCHAR,
    duration_ms FLOAT,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_api_debug_log_compose_run_id ON api_debug_log(compose_run_id);
CREATE INDEX ix_api_debug_log_application_id ON api_debug_log(application_id);
CREATE INDEX ix_api_debug_log_created_at ON api_debug_log(created_at);
```

#### ChatKit Tables

**`chatkit_thread` and `chatkit_thread_item` tables:**

These tables are defined in the codebase but **not currently used** as ChatKit is not integrated. See [ChatKit Integration](#chatkit-integration-not-currently-implemented) section for details.

#### Legacy Composer (LLM Pipeline)

**`composerun` table:**
```sql
CREATE TABLE composerun (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES user(id),
    jd_source_url VARCHAR,
    jd_text_excerpt VARCHAR,
    jd_factors JSON NOT NULL,
    selected_fact_ids JSON NOT NULL,
    options JSON NOT NULL,
    resume_bullets JSON NOT NULL,
    cover_letter VARCHAR,
    llm_model VARCHAR,
    tokens_used INTEGER DEFAULT 0,
    validation_status JSON NOT NULL,
    inputs JSON NOT NULL,
    outputs JSON NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_composerun_owner_created ON composerun(owner_id, created_at);
```

**Note:** This table is used by the legacy `/compose` endpoint (LLM pipeline) and is separate from the AgentKit workflow system.

#### Experience Graph

**`nodes` table:**
```sql
CREATE TABLE nodes (
    id VARCHAR PRIMARY KEY,
    node_type VARCHAR NOT NULL,  -- task|project|skill|domain
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    confidence FLOAT DEFAULT 0.8,
    privacy VARCHAR DEFAULT 'internal',  -- public|internal|private
    owner_id INTEGER NOT NULL REFERENCES user(id),
    labels JSON NOT NULL DEFAULT '[]',
    provenance JSON NOT NULL,
    data JSON NOT NULL
);

CREATE INDEX ix_nodes_node_type ON nodes(node_type);
CREATE INDEX ix_nodes_owner_id ON nodes(owner_id);
```

**`edges` table:**
```sql
CREATE TABLE edges (
    id VARCHAR PRIMARY KEY,
    edge_type VARCHAR NOT NULL,  -- task_of|uses_skill|in_domain
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    confidence FLOAT DEFAULT 0.8,
    privacy VARCHAR DEFAULT 'internal',
    owner_id INTEGER NOT NULL REFERENCES user(id),
    labels JSON NOT NULL DEFAULT '[]',
    provenance JSON NOT NULL,
    from_id VARCHAR NOT NULL REFERENCES nodes(id),
    to_id VARCHAR NOT NULL REFERENCES nodes(id),
    since TIMESTAMP,
    until TIMESTAMP
);

CREATE INDEX ix_edges_edge_type ON edges(edge_type);
CREATE INDEX ix_edges_from_id ON edges(from_id);
CREATE INDEX ix_edges_to_id ON edges(to_id);
CREATE INDEX ix_edges_owner_id ON edges(owner_id);
```

#### Job Tracking

**`job_applied` table:**
```sql
CREATE TABLE jobapplied (
    id VARCHAR PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    company VARCHAR NOT NULL,
    role_title VARCHAR NOT NULL,
    source_url VARCHAR,
    applied_at TIMESTAMP NOT NULL,
    jd_structured JSON NOT NULL DEFAULT '{}',
    resume_bullets JSON NOT NULL DEFAULT '[]',
    cover_letter VARCHAR
);

CREATE INDEX ix_jobapplied_user_id ON jobapplied(user_id);
```

**`job_location` table:**
```sql
CREATE TABLE joblocation (
    id VARCHAR PRIMARY KEY,
    job_id VARCHAR NOT NULL REFERENCES jobapplied(id),
    label VARCHAR,  -- "Remote", "San Francisco, CA"
    lat FLOAT,
    lng FLOAT,
    raw VARCHAR  -- Original location string or JSON
);

CREATE INDEX ix_joblocation_job_id ON joblocation(job_id);
```

### Database Configuration

**SQLite (Development):**
```python
DATABASE_URL = "sqlite:///./myapply.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
```

**PostgreSQL (Production):**
```python
DATABASE_URL = "postgresql+psycopg://user:pass@host:port/db"
engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"}  # Auto-added for Railway proxy
)
```

**Driver:** `psycopg[binary]` (v3) - **NOT** `psycopg2-binary`

### Migrations

**Automatic Table Creation:**
```python
@app.on_event("startup")
def on_startup():
    _ensure_user_profile_columns()  # Add missing columns to user table
    SQLModel.metadata.create_all(engine)
```

**Alembic (Production):**
```bash
alembic upgrade head
```

---

## Service Layer

### LLM Pipeline (Legacy Composer)

**Location:** `llm.py`

**Class:** `LLMPipeline`

**Purpose:** Direct OpenAI API calls for the `/compose` endpoint (not AgentKit workflows)

**Key Methods:**

1. **`extract_jd_factors(jd_content)`**
   - Extracts structured requirements from job description
   - Returns: `(jd_factors_dict, metadata)`

2. **`generate_bullets(selected_facts, jd_factors)`**
   - Generates resume bullets based on experience facts and job requirements
   - Returns: `(bullets_list, metadata)`

3. **`generate_cover_letter(selected_facts, jd_factors, user_story)`**
   - Writes personalized cover letter
   - Returns: `(cover_letter_dict, metadata)`

**Note:** This is separate from AgentKit workflows and powers the legacy `/compose` UI.

### Graph Validation

**Location:** `graph/loader.py`

**Class:** `GraphLoader`

**Purpose:** Validate and persist experience graphs

**Key Methods:**

1. **`validate_and_upsert(graph_payload, commit=True)`**
   - Validates nodes and edges against schema
   - Upserts to database if valid
   - Returns: `ValidationResult(ok, errors, warnings)`

2. **`_validate_node(node_payload)`**
   - Ensures required fields present
   - Validates node_type enum
   - Checks data schema compliance

3. **`_validate_edge(edge_payload)`**
   - Ensures from_id and to_id exist
   - Validates edge_type enum
   - Checks temporal bounds (since/until)

### Graph Scoring

**Location:** `graph/scoring.py`

**Purpose:** Rank experience facts against job requirements

**Key Function:**
```python
def rank_facts(
    nodes: List[Dict],
    edges: List[Dict],
    jd_factors: Dict[str, Any],
    top_n: int = 25
) -> List[Dict[str, Any]]:
    """
    Score each fact based on:
    - Skill overlap with job requirements
    - Domain relevance
    - Metric/achievement presence
    - Recency
    """
```

**Scoring Factors:**
- **Skill Match**: Overlap between fact skills and required skills
- **Domain Match**: Relevant industries/fields
- **Metrics**: Presence of quantifiable achievements
- **Confidence**: Fact confidence score
- **Recency**: More recent facts weighted higher

### Input Validation

**Location:** `validation.py`

**Key Functions:**

1. **`sanitize_string(text, max_length)`**
   - Strips whitespace
   - Enforces length limits
   - Removes control characters

2. **`validate_url(url, require_https=True)`**
   - Validates URL format
   - Optionally enforces HTTPS
   - Returns cleaned URL or raises HTTPException

3. **`validate_json_size(json_str, max_size_mb)`**
   - Ensures JSON payloads don't exceed size limits
   - Raises HTTPException if too large

### Utility Functions

**Location:** `routers/utils.py`

1. **`to_dict(payload)`**
   - Converts Pydantic models, dataclasses, and objects to dicts
   - Handles `.model_dump()` and `.to_dict()` methods

2. **`try_parse_json_text(text)`**
   - Attempts to parse JSON from string
   - Handles JSON embedded in text (finds `{...}`)
   - Returns dict or None

3. **`ensure_user_id(value)`**
   - Validates and sanitizes user_id parameter
   - Raises HTTPException if invalid

---

## Security Architecture

### Authentication System

**Location:** `auth.py`

**Key Components:**

1. **Password Hashing**
   - Algorithm: **bcrypt** via Passlib
   - Work factor: Automatically calibrated by Passlib

2. **Session Management**
   - Backend: `itsdangerous` signed cookies
   - Cookie name: `SESSION_COOKIE_NAME` (default: `app_session`)
   - Secure flag: Auto-enabled for HTTPS environments
   - SameSite: `lax` (CSRF protection)

3. **CSRF Protection**
   - Tokens generated with `secrets.token_hex(32)`
   - Stored in session
   - Validated on state-changing requests

**Functions:**

```python
def register(request, session, email, password, secret_key) -> User:
    """Create new user with hashed password."""

def login(request, session, email, password, secret_key, rate_limiter, client_id) -> User:
    """Authenticate user and create session."""

def logout(request):
    """Clear session data."""

def ensure_csrf_token(request, secret_key) -> str:
    """Generate or retrieve CSRF token from session."""

def validate_csrf_token(request, token, secret_key):
    """Verify CSRF token matches session."""
```

### Rate Limiting

**Class:** `LoginRateLimiter`

**Configuration:**
- Max attempts: 5 per client
- Window: 15 minutes
- Tracks by client IP

**Implementation:**
```python
class LoginRateLimiter:
    def __init__(self, max_attempts=5, window_seconds=900):
        self.attempts = {}  # {client_id: [(timestamp, ...), ...]}

    def check_rate_limit(self, client_id):
        """Raises HTTPException if rate limit exceeded."""
```

### Authorization Middleware

**Dependency Injection:**

```python
def get_current_user(request: Request, session: Session) -> Optional[User]:
    """Extract user from session, return None if not authenticated."""

def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    """Require authentication, raise 401 if not logged in."""

def require_admin(user: User = Depends(require_user)) -> User:
    """Require admin privileges, raise 403 if not admin."""
```

**Usage:**
```python
@app.get("/profile")
def profile_page(current_user: User = Depends(require_user)):
    # Route accessible only to authenticated users
```

### CORS Configuration

**Default Origins:**
```python
[
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:3000",
]
```

**Production Override:**
```bash
ALLOWED_ORIGINS=https://myapply-production.up.railway.app
```

### Input Sanitization

All user inputs pass through validation:

1. **String Sanitization**: `sanitize_string()`
2. **URL Validation**: `validate_url()`
3. **JSON Size Limits**: `validate_json_size()`
4. **Pydantic Validation**: All request payloads

### SQL Injection Prevention

- **SQLModel ORM**: All queries use parameterized statements
- **No raw SQL**: Direct queries avoided
- **Type safety**: SQLModel enforces types

### Secrets Management

**Environment Variables:**
```bash
SECRET_KEY=<generated-with-secrets-module>
OPENAI_API_KEY=sk-...
MAPBOX_ACCESS_TOKEN=pk...
```

**Generation:**
```python
import secrets
print(secrets.token_hex(32))
```

### Database Security

**PostgreSQL SSL:**
```python
if "proxy.rlwy.net" in DATABASE_URL:
    connect_args = {"sslmode": "require"}
```

**Connection Pooling:**
- Managed by SQLAlchemy
- Automatic connection recycling
- No plaintext password storage

---

## Testing Strategy

### Test Structure

```
tests/
├── conftest.py              # Fixtures and test configuration
├── test_workflows.py        # Workflow orchestration tests
└── test_openai_workflows.py # Workflow execution tests
```

### Test Database

**Fixture:**
```python
@pytest.fixture
def test_engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
```

### Test Coverage

**Workflow Orchestration:**
- ✅ JD ingestion with valid URL
- ✅ JD ingestion with direct text
- ✅ Resume building with cached output
- ✅ Resume building with fresh workflow execution
- ✅ Error handling (invalid inputs, workflow failures)
- ✅ Application status tracking (pending → running → succeeded/failed)

**AgentKit Integration:**
- ✅ Workflow execution with mock AgentKit responses
- ✅ Output parsing (structured job, bullets, cover letter)
- ✅ Error handling (workflow failures, parse errors)

**Authentication:**
- ✅ Registration flow
- ✅ Login with valid credentials
- ✅ Login with invalid credentials
- ✅ Rate limiting enforcement
- ✅ CSRF token validation
- ✅ Session persistence

**Profile Management:**
- ✅ Profile retrieval
- ✅ Profile updates (name, location, graph)
- ✅ Graph validation
- ✅ JSON size limits

**Job Tracking:**
- ✅ Create job application
- ✅ List user's applications
- ✅ Retrieve application details
- ✅ Location serialization with distance calculation

### Running Tests

```bash
# All tests
pytest -v

# Specific test file
pytest tests/test_workflows.py -v

# With coverage
pytest --cov=. --cov-report=html

# Specific test
pytest tests/test_workflows.py::test_jd_ingestion -v
```

### Mocking AgentKit

**Example:**
```python
@pytest.fixture
def mock_agentkit_run():
    with patch("services.resume_builder_service.Runner.run") as mock:
        mock.return_value = MagicMock(
            final_output={
                "structured_job_data": {...},
                "resume_bullets": [...],
                "cover_letter": "..."
            }
        )
        yield mock
```

---

## Performance Considerations

### Caching Strategy

**Resume Output Caching:**
- First call to `/api/jd/ingest` caches bullets and cover letter
- Subsequent call to `/api/resume/build` returns cached output
- Invalidation: Manual (update application record)

**Database Indexes:**
- User email (unique index)
- JobApplication user_id
- WorkflowRun (user_id, created_at)
- APIDebugLog (application_id, created_at)
- ChatKit thread items (thread_id, created_at)

### Connection Pooling

SQLAlchemy manages connection pool:
- Default pool size: 5
- Max overflow: 10
- Pool recycle: 3600 seconds

### Async Operations

**FastAPI Async Endpoints:**
- `async def` for I/O-bound operations
- Database queries run in thread pool
- AgentKit workflows run in event loop

**Gunicorn Workers:**
```bash
gunicorn app:app \
    --workers 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8000}
```

---

## Deployment Architecture

### Railway Configuration

**Services:**
1. **MyApply Web Service**
   - Auto-detected from Dockerfile
   - PORT set automatically
   - Scales horizontally

2. **PostgreSQL Database**
   - Managed by Railway
   - Automatic backups
   - Internal networking

**Environment Variables:**
```bash
ENV=production
SECRET_KEY=<generated>
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+psycopg://...
SESSION_SECURE=true
ALLOWED_ORIGINS=https://myapply-production.up.railway.app
```

### Static Assets

**Mounting:**
```python
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
```

**Contents:**
- `style.css` - TailwindCSS
- `script.js` - HTMX and custom JS
- `favicon.svg` - App icon

### Templates

**Jinja2 Configuration:**
```python
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
```

**Template Globals:**
```python
templates.env.globals["csrf_token"] = _csrf_token
templates.env.globals["mapbox_public_token"] = settings.MAPBOX_PUBLIC_TOKEN
```

---

## Future Enhancements

### Planned Features

1. **Real-time Collaboration**
   - Multi-user graph editing
   - Operational transforms (CRDT)

2. **Enhanced ChatKit Integration**
   - File attachment support
   - Agent context from user profile
   - Workflow triggering from chat

3. **Resume Templates**
   - Visual resume editor
   - PDF generation
   - Multiple format exports

4. **Analytics Dashboard**
   - Application success rates
   - Keyword optimization suggestions
   - Interview tracking

5. **Chrome Extension**
   - One-click job capture
   - Auto-fill from profile

### Technical Debt

- [ ] Migrate legacy `/compose` to AgentKit workflows
- [ ] Consolidate `JobApplied` and `JobApplication` models
- [ ] Add Redis for distributed caching
- [ ] Implement WebSocket for real-time updates
- [ ] Add comprehensive API documentation (OpenAPI/Swagger)

---

## Appendix

### Key Files Reference

| File | Purpose |
|------|---------|
| `app.py` | Main FastAPI application |
| `routers/jd_ingest.py` | Job description ingestion endpoint |
| `routers/resume_build.py` | Resume generation endpoint |
| `services/openai_workflows.py` | Workflow execution wrapper |
| `services/resume_builder_agents.py` | AgentKit agent definitions |
| `services/resume_builder_service.py` | Workflow orchestration |
| `services/workflow_output_parser.py` | Output extraction |
| `chatkit_integration/server.py` | ChatKit server implementation |
| `chatkit_integration/store.py` | ChatKit persistence layer |
| `models.py` | Database models (SQLModel) |
| `applications.py` | JobApplication model |
| `auth.py` | Authentication system |
| `validation.py` | Input sanitization |
| `debug_logger.py` | API call logging |

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ | - | Session encryption key |
| `OPENAI_API_KEY` | ✅ | - | OpenAI API access |
| `DATABASE_URL` | ❌ | `sqlite:///./myapply.db` | Database connection |
| `LLM_MODEL` | ❌ | `gpt-4o-mini` | Default LLM model |
| `COVER_LETTER_MODEL` | ❌ | - | Cover letter LLM (falls back to LLM_MODEL) |
| `SESSION_SECURE` | ❌ | `auto` | HTTPS-only cookies |
| `SESSION_COOKIE_NAME` | ❌ | `app_session` | Session cookie name |
| `ALLOWED_ORIGINS` | ❌ | localhost | CORS origins (comma-separated) |
| `MAPBOX_PUBLIC_TOKEN` | ❌ | - | Mapbox maps |
| `MAPBOX_ACCESS_TOKEN` | ❌ | - | Mapbox isochrone API |
| `PORT` | ❌ | `8000` | Server port (Railway sets automatically) |
| `ENV` | ❌ | `development` | Environment (`development`/`production`) |

---

**Document Version:** 2.0
**Last Updated:** October 13, 2025
**Maintainer:** MyApply Development Team
