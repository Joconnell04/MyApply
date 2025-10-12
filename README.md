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
| **Database** | SQLite / PostgreSQL | Data persistence |
| **Frontend** | Jinja2, HTMX, TailwindCSS | Server-rendered UI |
| **AI/ML** | OpenAI API, AgentKit | LLM, workflow orchestration |
| **Maps** | Mapbox GL JS, Isochrone API | Visualization, travel time |
| **Auth** | Passlib[bcrypt], itsdangerous | Security, sessions |
| **Testing** | Pytest, httpx | Unit & integration tests |
| **Deployment** | Railway, Uvicorn | Cloud hosting, ASGI server |

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
- For PostgreSQL use `postgresql+psycopg://username:password@localhost:5432/myapply` (requires `psycopg[binary]`).
- Alembic reads the same `DATABASE_URL`, so export it or run commands with `.env` loaded before invoking `alembic upgrade head`.

### Create Admin User

```bash
python scripts/create_admin.py admin@example.com "SecurePassword123!"
```

### Run Tests

```bash
pytest -v                              # All tests
pytest tests/test_agentkit_routes.py  # AgentKit tests only
pytest --cov=. --cov-report=html      # With coverage
```

---

## 🤝 AgentKit Setup

1. **Configure credentials**
   - Set `OPENAI_API_KEY` in your `.env` file (copy `.env.example` as a starter).
   - Optionally override `LLM_MODEL` and `COVER_LETTER_MODEL` if you prefer different OpenAI models.
2. **Map workflow IDs**
   - The backend orchestrator calls three AgentKit workflows. Update the IDs in [`routes.py`](routes.py) under `WORKFLOW_INTENT_ROUTER`, `WORKFLOW_JD_TO_STRUCTURED`, and `WORKFLOW_RESUME_BUILDER` to match your AgentKit deployments.
3. **Start the app and sign in**
   - Run `uvicorn app:app --reload`, register or log in, and populate your Profile → MyLife JSON so the composer has data to work with.
4. **Trigger the workflows**
   - Use the Compose UI or call the REST endpoints (`/api/intent/route`, `/api/jd/structure`, `/api/resume/build`) with an authenticated session. Example `curl` commands are provided below.
   - Run `pytest tests/test_agentkit_routes.py` for a quick smoke test.
5. **Troubleshoot connectivity**
   - Ensure outbound network access to OpenAI from your environment.
   - Check server logs for `Workflow execution failed` messages; the error payload will tell you whether the AgentKit call or JSON parsing failed.

> ℹ️ The interim `agentkit.py` wrapper currently uses `chat.completions` with `response_format="json_object"` to simulate AgentKit Workflow Runs until the official SDK is public.

---

## 🤖 AgentKit API Endpoints

### Structure Job Description

Parse raw JD into structured format with locations, skills, and requirements.

```bash
POST /api/jd/structure
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/jd/structure \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "user_id": "user-123",
    "jd_text": "Senior Python Developer\n\nRequirements:\n- 5+ years Python\n- FastAPI\n\nLocation: San Francisco, CA"
  }'
```

**Response:**
```json
{
  "ok": true,
  "run_id": "abc123",
  "structured_jd": {
    "title": "Senior Python Developer",
    "seniority": "senior",
    "locations": [{"city": "San Francisco", "region": "CA", "type": "hybrid"}],
    "skills": {"must_have": ["Python", "FastAPI"]}
  }
}
```

### Build Resume

Generate tailored resume with auto-orchestration (structures JD if needed).

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
    "jd_text": "Backend Engineer role...",
    "target_role": "Backend Engineer"
  }'
```

### Get Workflow Run

Retrieve stored run metadata and artifacts.

```bash
GET /api/runs/{run_id}
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
```

Railway auto-detects FastAPI and sets `PORT` and `DATABASE_URL`.

**Full deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📁 Project Structure

```
MyApply/
├── app.py                      # FastAPI application & main routes
├── auth.py                     # Authentication & session management
├── models.py                   # SQLModel database tables
├── agentkit.py                 # AgentKit workflow runner
├── routes.py                   # AgentKit REST endpoints
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

**Full reference:** [DEPLOYMENT.md#environment-variables](DEPLOYMENT.md#environment-variables)

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
pytest tests/test_agentkit_routes.py -v

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
mypy app.py models.py routes.py
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

1. Add workflow config in `routes.py`:
   ```python
   WORKFLOW_NEW = {
       "id": "wf_...",
       "version": "1",
   }
   ```

2. Create endpoint function:
   ```python
   @router.post("/api/new/endpoint")
   def api_new_endpoint(...):
       result = run_workflow(
           workflow_id=WORKFLOW_NEW["id"],
           version=WORKFLOW_NEW["version"],
           input_vars={...}
       )
       ...
   ```

3. Add tests in `tests/test_agentkit_routes.py`

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

**Full troubleshooting guide:** [DEPLOYMENT.md#troubleshooting](DEPLOYMENT.md#troubleshooting)

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

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide (Railway, local, environment vars)
- **[MyLifeSchemaInstructions.md](MyLifeSchemaInstructions.md)** - Experience graph schema reference

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

- 🌐 [Live Demo](https://myapply.railway.app) *(replace with your URL)*
- 📖 [Full Documentation](DEPLOYMENT.md)
- 🐛 [Report Bug](https://github.com/your-username/MyApply/issues)
- 💡 [Request Feature](https://github.com/your-username/MyApply/issues)
- 💬 [Discussions](https://github.com/your-username/MyApply/discussions)
