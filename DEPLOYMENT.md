# MyApply Deployment Guide

Complete guide for deploying MyApply to Railway and other platforms.

---

## 📋 Table of Contents

- [Quick Start (Local Development)](#quick-start-local-development)
- [AgentKit Workflow Integration](#agentkit-workflow-integration)
- [Railway Deployment](#railway-deployment)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start (Local Development)

### Prerequisites

- Python 3.9+
- OpenAI API key (for AgentKit workflows and LLM features)
- Mapbox tokens (optional, for map features)

### Setup Steps

1. **Clone and setup environment:**

```bash
git clone https://github.com/your-username/MyApply.git
cd MyApply

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

2. **Configure environment variables:**

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```bash
# Required
OPENAI_API_KEY=sk-your-actual-openai-key
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Optional
MAPBOX_PUBLIC_TOKEN=pk.your-token
MAPBOX_ACCESS_TOKEN=pk.your-access-token
```

3. **Start the development server:**

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Visit [http://127.0.0.1:8000](http://127.0.0.1:8000)

4. **Create an admin user (optional):**

```bash
python scripts/create_admin.py admin@example.com "SecurePassword123!"
```

### Run Tests

```bash
# All tests
pytest -v

# Workflow integration tests only
pytest tests/test_workflows.py -v

# With coverage
pytest --cov=. --cov-report=html
```

---

## 🤖 AgentKit Workflow Integration

To wire up AgentKit in any environment:

1. Set `OPENAI_API_KEY` (and optionally `ENV`, `LLM_MODEL`, `COVER_LETTER_MODEL`) in the deployment environment.
2. Update the workflow IDs in [`workflow_constants.py`](workflow_constants.py) so they match the AgentKit workflows you deployed.
3. Confirm the runtime has outbound network access to OpenAI; the backend calls the Workflows API synchronously.
4. Seed or enter MyLife JSON on the Profile page so the resume builder has data to rank.
5. Exercise the endpoints below or the Compose UI to verify end-to-end orchestration.

MyApply orchestrates two AgentKit workflows for automated resume generation:

### Workflows

| Workflow | ID | Version | Purpose |
|----------|----|---------|---------|
| **JD_to_StructuredJD_v0** | `wf_68e80e14fad48190a83d85460325ba7f072fbeb74efb9546` | 4 | Parse & structure job descriptions |
| **Resume_Builder_v1** | `wf_68e969c7da408190b3d046774e86e50700467750faf0f87a` | 4 | Build tailored resumes from structured JD |

### REST API Endpoints

#### 1. Phase 1 — Ingest Job Description URL

**Endpoint:** `POST /api/jd/ingest`

Fetches a job posting URL, runs `JD_to_StructuredJD_v0`, and stores both the structured data and workflow metadata.

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
    "title": "Senior Python Developer",
    "company_name": "...",
    "locations": [
      {"city": "San Francisco", "region": "CA", "country": "USA", "type": "hybrid"}
    ],
    "skills": {"must_have": ["Python", "FastAPI", "PostgreSQL"]}
  }
}
```

#### 2. Phase 2 — Build Tailored Resume

**Endpoint:** `POST /api/resume/build`

Runs `Resume_Builder_v1` using the stored structured JD and persists the generated bullets and packaging.

```bash
curl -X POST http://localhost:8000/api/resume/build \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "user_id": "user-123",
    "application_id": "4b8c57d1-02df-4d6e-9cde-8ab3a845c3dd",
    "target_role": "Backend Engineer"
  }'
```

**Response (truncated):**
```json
{
  "application_id": "4b8c57d1-02df-4d6e-9cde-8ab3a845c3dd",
  "resume_status": "succeeded",
  "resume_output": {
    "output_parsed": {
      "bullets": [
        "Scaled async APIs handling 50M+ daily calls by modernising FastAPI services.",
        "Led cross-functional initiative to harden Python platform security and observability."
      ],
      "package": {"summary": "..."}
    },
    "output_text": "Generated resume bullets..."
  }
}
```

### Architecture

**Backend as Conductor:** Workflows do NOT call each other. The backend:
1. Calls workflows synchronously via `services/openai_workflows.py`
2. Persists job application state in `JobApplication`
3. Stores all workflow metadata in `workflow_run` and artifacts if you extend the schema
4. Passes outputs from one workflow as inputs to another

> **Note:** The backend now uses the official OpenAI Workflows API to run both phases and polls until completion.

---

## ☁️ Railway Deployment

### Prerequisites

- Railway account ([railway.app](https://railway.app))
- GitHub repository with your MyApply code

### Deployment Steps

1. **Create a new Railway project:**
   - Go to [railway.app](https://railway.app/new)
   - Click "Deploy from GitHub repo"
   - Select your MyApply repository
   - Railway will auto-detect Python and FastAPI

2. **Add PostgreSQL database (recommended for production):**
   - In your Railway project, click "+ New"
   - Select "Database" → "PostgreSQL"
   - Railway will create a database and set `DATABASE_URL` automatically

3. **Configure environment variables:**

   Go to your service settings → Variables, and add:

   ```bash
   # Required
   ENV=production
   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
   OPENAI_API_KEY=sk-your-openai-key

   # Session Security
   SESSION_SECURE=true
   SESSION_SAMESITE=lax

   # CORS (add your Railway domain)
   ALLOWED_ORIGINS=https://your-app.railway.app,http://localhost:3000

   # Optional: Mapbox
   MAPBOX_PUBLIC_TOKEN=pk.your-token
   MAPBOX_ACCESS_TOKEN=pk.your-access-token

   # Optional: AgentKit Tools API
   MYAPPLY_API_KEY=your-secure-api-key

   # Optional: LLM Models
   LLM_MODEL=gpt-4o-mini
   COVER_LETTER_MODEL=gpt-4o
   ```

   **Note:** Railway automatically provides `PORT` and `DATABASE_URL` (if using Railway Postgres).

4. **Configure start command:**

   Railway should auto-detect, but you can set manually in Settings → Deploy:

   ```bash
   uvicorn app:app --host 0.0.0.0 --port $PORT
   ```

5. **Deploy:**
   - Railway will automatically deploy on git push
   - Or click "Deploy Now" in the Railway dashboard

6. **Create admin user:**

   Open Railway shell (click on service → Shell):

   ```bash
   python scripts/create_admin.py admin@yourdomain.com "SecurePassword123!"
   ```

### Post-Deployment

1. **Get your Railway URL:**
   - Found in service Settings → Domains
   - Typically: `https://your-app.railway.app`

2. **Update CORS:**
   - Add your Railway domain to `ALLOWED_ORIGINS`
   - Example: `https://your-app.railway.app`

3. **Test the deployment:**
   ```bash
   curl https://your-app.railway.app/
   ```

### Using SQLite on Railway

If you prefer SQLite over Postgres:

1. **Add a volume:**
   - Service settings → Volumes → "+ New Volume"
   - Mount path: `/app/data`

2. **Update DATABASE_URL:**
   ```bash
   DATABASE_URL=sqlite:////app/data/myapply.db
   ```

3. **Note:** SQLite volumes persist across deploys but are not automatically backed up.

---

## 🌍 Environment Variables Reference

### Core Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ | `change-me` | Session encryption key (generate with `secrets.token_hex(32)`) |
| `DATABASE_URL` | ✅ | `sqlite:///./myapply.db` | Database connection string |
| `OPENAI_API_KEY` | ✅ | - | OpenAI API key for AgentKit workflows and LLM features |
| `ENV` | No | `development` | Environment: `development` or `production` |
| `PORT` | No | `8000` | Server port (Railway auto-sets this) |

### Session & Security

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SESSION_COOKIE_NAME` | No | `app_session` | Session cookie name |
| `SESSION_SECURE` | No | `auto` | HTTPS-only cookies (`true`, `false`, or `auto`) |
| `SESSION_SAMESITE` | No | `lax` | SameSite policy (`lax`, `strict`, `none`) |

### LLM Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_MODEL` | No | `gpt-4o-mini` | Default LLM model for compose features |
| `COVER_LETTER_MODEL` | No | - | Specific model for cover letters (uses `LLM_MODEL` if unset) |

### Mapbox (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAPBOX_PUBLIC_TOKEN` | No | - | Public token for Mapbox GL JS (map display) |
| `MAPBOX_ACCESS_TOKEN` | No | - | Access token for Mapbox APIs (isochrones) |

### CORS

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALLOWED_ORIGINS` | No | localhost URLs | Comma-separated list of allowed origins |

### AgentKit Tools (Optional)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MYAPPLY_API_KEY` | No | - | API key for AgentKit tool service authentication |

---

## 💾 Database Setup

### SQLite (Development)

Default configuration uses SQLite:

```bash
DATABASE_URL=sqlite:///./myapply.db
```

Tables are auto-created on startup via SQLModel.

### PostgreSQL (Production - Recommended)

Railway PostgreSQL:

```bash
# Automatically set by Railway
DATABASE_URL=postgresql://user:password@host:port/database
```

External PostgreSQL:

```bash
DATABASE_URL=postgresql://username:password@host:port/dbname
```

### Database Migrations

Currently using SQLModel with auto-creation. For production, consider:

```bash
pip install alembic
alembic init migrations
# Create migration
alembic revision --autogenerate -m "Initial schema"
# Apply migration
alembic upgrade head
```

### Tables Created

- `user` - User accounts
- `workflow_run` - AgentKit workflow execution metadata
- `artifact` - Workflow output artifacts
- `job_applied` - Job application history
- `job_location` - Job location data
- `compose_run` - LLM compose run history
- `user_graph` - User experience graphs
- `nodes` - Graph nodes
- `edges` - Graph edges

---

## 🔧 Troubleshooting

### Common Issues

#### "OPENAI_API_KEY not configured"

**Solution:**
- Verify `.env` file contains `OPENAI_API_KEY=sk-...`
- For Railway: Check Variables in service settings
- Restart the server after adding the key

#### CORS Errors

**Problem:** `Access-Control-Allow-Origin` errors in browser console

**Solution:**
- Add your frontend origin to `ALLOWED_ORIGINS`
- Example: `ALLOWED_ORIGINS=https://myapp.com,http://localhost:3000`
- For Railway: Add your Railway domain to the list

#### Database Connection Errors

**SQLite:**
- Ensure directory exists and is writable
- Check `DATABASE_URL` path is correct

**PostgreSQL:**
- Verify connection string format
- Check Railway database is running
- Ensure database user has permissions

#### Session/Cookie Issues

**Development (HTTP):**
```bash
SESSION_SECURE=false
```

**Production (HTTPS):**
```bash
SESSION_SECURE=true
SESSION_SAMESITE=lax
```

#### Mapbox Maps Not Loading

**Solution:**
- Verify `MAPBOX_PUBLIC_TOKEN` is set
- Check token is valid at mapbox.com
- Ensure token has correct scopes

#### Workflow Execution Fails (502 Error)

**Solution:**
- Check `OPENAI_API_KEY` is valid
- Verify workflow IDs in `routes.py` are correct
- Check OpenAI API rate limits
- Review error details in `/api/runs/{run_id}`

### Railway-Specific Issues

#### Build Fails

**Check:**
- Python version compatibility (3.9+)
- All dependencies in `requirements.txt`
- Railway build logs for errors

#### App Crashes After Deploy

**Check:**
- Environment variables are set
- `PORT` is not hardcoded (use `$PORT`)
- Database connection works
- Railway logs for error messages

#### Database Not Persisting

**SQLite:**
- Add a Railway volume
- Mount to `/app/data`
- Update `DATABASE_URL` to use mounted path

**PostgreSQL:**
- Verify Railway Postgres is linked
- Check `DATABASE_URL` is automatically set

---

## 📊 Performance & Scaling

### Recommendations for Production

1. **Use PostgreSQL** instead of SQLite
2. **Enable connection pooling:**
   ```python
   engine = create_engine(
       DATABASE_URL,
       pool_size=10,
       max_overflow=20
   )
   ```

3. **Add caching** for expensive operations
4. **Use async workflows** for long-running AgentKit calls
5. **Add rate limiting** to API endpoints
6. **Enable monitoring:**
   - Railway provides metrics
   - Add Sentry for error tracking
   - Use Railway logs for debugging

### Horizontal Scaling

Railway supports scaling:
- Go to service → Settings → Scaling
- Increase replicas for high traffic
- Note: SQLite doesn't work with multiple replicas (use Postgres)

---

## 🔐 Security Checklist

Before going to production:

- [ ] Generate strong `SECRET_KEY` (32 bytes hex)
- [ ] Set `SESSION_SECURE=true`
- [ ] Use PostgreSQL with strong password
- [ ] Set restrictive `ALLOWED_ORIGINS`
- [ ] Enable HTTPS (Railway provides this automatically)
- [ ] Don't commit `.env` to git
- [ ] Review and limit API rate limits
- [ ] Set up database backups
- [ ] Monitor for suspicious activity
- [ ] Keep dependencies updated

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Railway Documentation](https://docs.railway.app/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Mapbox Documentation](https://docs.mapbox.com/)

---

## 🆘 Getting Help

- **GitHub Issues:** Report bugs and request features
- **Railway Community:** [discord.gg/railway](https://discord.gg/railway)
- **FastAPI Discord:** [discord.gg/fastapi](https://discord.gg/fastapi)

---

**Happy Deploying! 🚀**
