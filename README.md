# 🎯 MyApply

**AI-powered career tooling that transforms your experience into tailored resumes and cover letters.**

MyApply is a FastAPI-powered platform that combines structured experience graphs with AgentKit workflows to generate personalized application materials. Built for speed, deployed to Railway in minutes.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

### 🤖 AgentKit Workflow Integration
- **Intent Routing** - Smart workflow selection based on user needs
- **JD Structuring** - Parse job descriptions into structured data
- **Resume Building** - Generate tailored resumes with AI
- **Backend Orchestration** - Workflows communicate via backend conductor pattern
- **Persistent Metadata** - All runs and artifacts stored in database

### 👤 User Management
- **Secure Authentication** - CSRF-protected sessions with bcrypt hashing
- **Rate Limiting** - Login attempt throttling
- **Profile Management** - Store location, skills, and experience
- **Admin Panel** - User and run management

### 📝 Experience Graph
- **Profile-based JSON editor** - Manage the MyLife graph directly from the Profile page with inline formatting helpers
- **Append helper** - Merge new JSON snippets safely with automatic pretty-printing
- **Graph Validation** - Schema enforcement for nodes and edges
- **Fact Ranking** - Score experiences against job requirements
- **Evidence Retrieval** - Query system for experience matching

### 🗺️ Job Tracking
- **Application Dashboard** - Track all job applications
- **Interactive Maps** - Mapbox GL JS with job location clustering
- **Distance Calculations** - Haversine distance from home
- **Isochrone Visualization** - Travel time polygons for commute planning
- **Location Intelligence** - Multi-location support with confidence scores

### 🎨 AI Composer
- **JD Factor Extraction** - Identify key requirements from postings
- **Resume Bullet Generation** - AI-powered achievement bullets
- **Cover Letter Writing** - Personalized cover letters with fact references
- **ATS Optimization** - Keyword coverage tracking
- **Token Usage Tracking** - Monitor LLM costs

### 🔧 Developer Tools
- **AgentKit Tool API** - JSON endpoints for multi-agent integration
- **Tool Specification** - OpenAPI-style tool definitions
- **Bundle Storage** - Stateful generation bundles with TTL
- **Batch Operations** - Evidence batch retrieval
- **Rate Limiting** - Token bucket per user

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI, SQLModel, Pydantic | API, ORM, validation |
| **Database** | PostgreSQL (psycopg v3) / SQLite | Data persistence with modern driver |
| **Frontend** | Jinja2, HTMX, TailwindCSS | Server-rendered UI |
| **AI/ML** | OpenAI API, AgentKit | LLM, workflow orchestration |
| **Maps** | Mapbox GL JS, Isochrone API | Visualization, travel time |
| **Auth** | Passlib[bcrypt], itsdangerous | Security, sessions |
| **Testing** | Pytest, httpx | Unit & integration tests |
| **Deployment** | Railway, Gunicorn, Uvicorn | Cloud hosting, ASGI server |

---

## 🚀 Quick Start

### Local Development

```bash
# Clone and setup
git clone https://github.com/your-username/MyApply.git
cd MyApply
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and set at least OPENAI_API_KEY and DATABASE_URL

# Run
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Visit http://127.0.0.1:8000
```

### Database Configuration

- Set `DATABASE_URL` in `.env`; the default `sqlite:///./myapply.db` stores a SQLite file in the project root.
- **For PostgreSQL** use `postgresql+psycopg://username:password@localhost:5432/myapply`
  - **Requires**: `psycopg[binary]` (v3) driver - NOT `psycopg2-binary`
  - The app automatically adds SSL support for Railway proxy connections
- Alembic reads the same `DATABASE_URL`, so export it or run commands with `.env` loaded before invoking `alembic upgrade head`.

**Note:** We use the modern `psycopg` (v3) driver. See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for details.

### Create Admin User

```bash
python scripts/create_admin.py admin@example.com "SecurePassword123!"
```

### Run Tests

```bash
pytest -v                              # All tests
pytest tests/test_workflows.py  # Workflow orchestration test
pytest --cov=. --cov-report=html      # With coverage
```

---

## 🤝 AgentKit Setup

1. **Configure credentials**
   - Set `OPENAI_API_KEY` in your `.env` file (copy `.env.example` as a starter).
   - Optionally override `LLM_MODEL` and `COVER_LETTER_MODEL` if you prefer different OpenAI models.
2. **Map workflow IDs**
   - The backend orchestrator calls the all-in-one `ResumeBuilderV2` AgentKit workflow. Update the ID in [`workflow_constants.py`](workflow_constants.py) to match your AgentKit deployment.
3. **Start the app and sign in**
   - Run `uvicorn app:app --reload`, register or log in, and populate your Profile → MyLife JSON so the composer has data to work with.
4. **Trigger the workflows**
   - Use the Compose UI or call the REST endpoints (`/api/jd/ingest`, `/api/resume/build`) with an authenticated session. Example `curl` commands are provided below.
   - Run `pytest tests/test_workflows.py` for a quick smoke test.
5. **Troubleshoot connectivity**
   - Ensure outbound network access to OpenAI from your environment.
   - Check server logs for `Workflow execution failed` messages; the error payload will tell you whether the AgentKit call or JSON parsing failed.

> ℹ️ The backend uses the OpenAI Workflows API via `services/openai_workflows.py` with synchronous polling for the ResumeBuilderV2 flow.

---

## 🤖 Workflow API Endpoints

Both endpoints call the single ResumeBuilderV2 workflow. `/api/jd/ingest` caches the structured job data (and downstream artifacts) while `/api/resume/build` surfaces the resume bullets and cover letter, reusing cached output when available.

### JD Ingest — Structured Job Data

```bash
POST /api/jd/ingest
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/jd/ingest \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "user_id": "user-123",
    "source_url": "https://example.com/jobs/senior-python"
  }'
```

**Response:**
```json
{
  "application_id": "4b8c57d1-02df-4d6e-9cde-8ab3a845c3dd",
  "jd_status": "succeeded",
  "jd_struct_data": {
    "required_skills": ["Python", "FastAPI"],
    "locations": ["Remote"],
    "required_experience": ["5+ years building APIs"]
  }
}
```

### ResumeBuilderV2 — Resume + Cover Letter

```bash
POST /api/resume/build
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/resume/build \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "user_id": "user-123",
    "application_id": "4b8c57d1-02df-4d6e-9cde-8ab3a845c3dd",
    "job_url": "https://example.com/jobs/senior-python"
  }'
```

**Response:**
```json
{
  "application_id": "4b8c57d1-02df-4d6e-9cde-8ab3a845c3dd",
  "resume_status": "succeeded",
  "structured_job_data": {
    "required_skills": ["Python", "FastAPI"],
    "locations": ["Remote"],
    "required_experience": ["5+ years building APIs"]
  },
  "resume_bullets": [
    "Engineered scalable APIs in Python, delivering features for [user base size] clients.",
    "Mentored cross-functional teams while implementing async FastAPI services."
  ],
  "cover_letter": "I am excited to apply my FastAPI expertise to this role.",
  "resume_output": {
    "resume_bullets": [
      "Engineered scalable APIs in Python, delivering features for [user base size] clients.",
      "Mentored cross-functional teams while implementing async FastAPI services."
    ],
    "cover_letter": "I am excited to apply my FastAPI expertise to this role.",
    "structured_job_data": {
      "required_skills": ["Python", "FastAPI"],
      "locations": ["Remote"],
      "required_experience": ["5+ years building APIs"]
    }
  }
}
```

---

## ☁️ Railway Deployment

Deploy to Railway in 3 steps:

1. **Create project:** Link your GitHub repo at [railway.app/new](https://railway.app/new)

2. **Add PostgreSQL:** Click "+ New" → Database → PostgreSQL

3. **Set environment variables:**

```bash
ENV=production
SECRET_KEY=<generate-with-python-secrets>
OPENAI_API_KEY=sk-your-key
SESSION_SECURE=true
ALLOWED_ORIGINS=https://your-app.railway.app
# Verify DATABASE_URL uses psycopg driver:
DATABASE_URL=postgresql+psycopg://user:pass@host:port/db
```

Railway auto-detects FastAPI and sets `PORT` and `DATABASE_URL`.

**📚 Complete deployment guide:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - includes:
- Database configuration (psycopg driver setup)
- SSL configuration for Railway
- Template path fixes
- PORT binding verification
- Troubleshooting guide

---

## 📁 Project Structure

```
MyApply/
├── app.py                      # FastAPI application & main routes
├── auth.py                     # Authentication & session management
├── models.py                   # SQLModel database tables
├── applications.py             # Job application persistence models
├── routers/                    # FastAPI routers for workflow orchestration
│   ├── __init__.py
│   ├── jd_ingest.py
│   └── resume_build.py
├── services/
│   ├── __init__.py
│   └── openai_workflows.py     # OpenAI Workflows client helper
├── llm.py                      # LLM pipeline for compose features
├── validation.py               # Input sanitization
├── graph/                      # Experience graph system
│   ├── schema.py              # Node/edge types & validation
│   ├── loader.py              # Graph validation & management helpers
│   └── scoring.py             # Fact ranking algorithms
├── myapply_tools/             # AgentKit tool service
│   ├── app.py                 # Tool API FastAPI app
│   ├── routers/               # Tool endpoints
│   └── schemas.py             # Tool request/response models
├── templates/                  # Jinja2 HTML templates
├── static/                     # CSS, JS, images
├── tests/                      # Pytest test suite
├── scripts/                    # Admin & utility scripts
├── DEPLOYMENT.md              # Deployment guide
└── requirements.txt           # Python dependencies
```

---

## 🔒 Environment Variables

### Required

```bash
SECRET_KEY=<generate-with-python-secrets>    # Session encryption
OPENAI_API_KEY=sk-your-key                   # OpenAI API access
DATABASE_URL=sqlite:///./myapply.db          # Database connection
```

### Optional

```bash
# LLM Configuration
LLM_MODEL=gpt-4o-mini                        # Default model
COVER_LETTER_MODEL=gpt-4o                    # Cover letter model

# Mapbox (for map features)
MAPBOX_PUBLIC_TOKEN=pk.your-token
MAPBOX_ACCESS_TOKEN=pk.your-access-token

# CORS
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000

# Environment
ENV=development                               # or production
PORT=8000                                     # Server port
```

**Full reference:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

## 📊 Database Schema

### Core Tables

- **`user`** - User accounts, profile details, and `mylife_json` experience graph
- **`workflow_run`** - AgentKit workflow execution metadata
- **`artifact`** - Workflow output artifacts (structured JDs, resume sections)
- **`job_applied`** - Job application history
- **`job_location`** - Multi-location support with geocoding
- **`compose_run`** - LLM compose run history & token usage
- **`user_graph`** - Legacy snapshot table (unused by UI; retained for backfills)
- **`nodes`** - Graph nodes (tasks, projects, skills, etc.)
- **`edges`** - Graph relationships with temporal bounds

### Migrations

Tables auto-created via SQLModel on startup. For production, use Alembic:

```bash
pip install alembic
alembic init migrations
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

---

## 🧪 Testing

### Test Coverage

- ✅ Authentication flows (CSRF, rate limiting, sessions)
- ✅ Profile & job application APIs
- ✅ AgentKit workflow orchestration
- ✅ Locations array serialization
- ✅ Graph validation pipeline powering fact ranking
- ✅ Bundle storage with TTL expiry
- ✅ Evidence retrieval & pagination

### Run Tests

```bash
# All tests with verbose output
pytest -v

# Specific test file
pytest tests/test_workflows.py -v

# With coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Fast (skip slow tests)
pytest -m "not slow"
```

---

## 🔧 Development

### Code Quality

```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy app.py models.py routers/jd_ingest.py routers/resume_build.py
```

### Database Management

```bash
# SQLite console
sqlite3 myapply.db

# PostgreSQL console (Railway)
railway run psql $DATABASE_URL

# Reset database (⚠️ destroys data)
rm myapply.db
uvicorn app:app --reload  # Recreates tables
```

### Adding a Workflow

1. Add workflow identifiers in `workflow_constants.py`:
   ```python
   WORKFLOW_NEW = {
       "id": "wf_...",
       "version": "1",
   }
   ```

2. Create or extend a router in `routers/`:
   ```python
   @router.post("/api/new/endpoint")
   def api_new_endpoint(...):
       run = run_workflow(
           workflow_id=WORKFLOW_NEW_ID,
           version=WORKFLOW_NEW_VER,
           inputs={...},
       )
       ...
   ```

3. Add tests in `tests/test_workflows.py`

---

## 🗺️ Map Features

### Setup Mapbox

1. Get tokens at [mapbox.com/account/access-tokens](https://account.mapbox.com/access-tokens)

2. Add to `.env`:
   ```bash
   MAPBOX_PUBLIC_TOKEN=pk.your-public-token
   MAPBOX_ACCESS_TOKEN=pk.your-access-token
   ```

3. Restart server

### Features

- **Job Clustering** - Groups nearby jobs on map
- **Isochrones** - Travel time polygons (drive/walk/bike)
- **Distance Calculation** - Haversine distance from home
- **Multi-Location Jobs** - Support for remote/hybrid/onsite mix
- **Location Confidence** - AI-extracted location confidence scores

---

## 🔍 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| `OPENAI_API_KEY not configured` | Add to `.env` and restart server |
| CORS errors in browser | Add your origin to `ALLOWED_ORIGINS` |
| Session/cookie issues | Set `SESSION_SECURE=false` for local HTTP |
| Database errors | Check `DATABASE_URL` and ensure directory exists |
| Mapbox maps not loading | Verify `MAPBOX_PUBLIC_TOKEN` is set |
| Workflow 502 errors | Check OpenAI API key & rate limits |

**Full troubleshooting guide:** [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Guidelines

- Write tests for new features
- Follow existing code style (use `ruff`)
- Update documentation
- Add type hints where possible

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [OpenAI](https://openai.com/) - LLM & AgentKit platform
- [Mapbox](https://mapbox.com/) - Mapping & geocoding
- [Railway](https://railway.app/) - Deployment platform
- [HTMX](https://htmx.org/) - Progressive enhancement

---

## 📚 Documentation

- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide (Railway, PostgreSQL, psycopg setup, troubleshooting)
- **[MyLifeSchemaInstructions.md](MyLifeSchemaInstructions.md)** - Experience graph schema reference
- **[myapply_tools/README_TOOLS.md](myapply_tools/README_TOOLS.md)** - AgentKit tools service API reference

---

## 🚀 What's Next?

- [ ] Real-time collaboration on experience graphs
- [ ] Multi-language support
- [ ] Resume templates & visual editor
- [ ] Chrome extension for quick JD capture
- [ ] Mobile app (React Native)
- [ ] Analytics dashboard for application tracking
- [ ] ATS parsing & compatibility scoring
- [ ] Interview prep integration

---

**Built with ❤️ for job seekers everywhere.**

**Questions?** Open an issue or start a discussion!

---

### Quick Links

- 🌐 [Live Demo](https://myapply-production.up.railway.app)
- 📖 [Deployment Guide](DEPLOYMENT_GUIDE.md)
- 🐛 [Report Bug](https://github.com/your-username/MyApply/issues)
- 💡 [Request Feature](https://github.com/your-username/MyApply/issues)
- 💬 [Discussions](https://github.com/your-username/MyApply/discussions)
