# MyApply Setup and Deployment Guide

**Complete guide for local development, testing, and production deployment**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Local Development Setup](#local-development-setup)
3. [Environment Configuration](#environment-configuration)
4. [AgentKit Workflow Setup](#agentkit-workflow-setup)
5. [Database Setup](#database-setup)
7. [Testing](#testing)
8. [Railway Deployment](#railway-deployment)
9. [Production Checklist](#production-checklist)
10. [Troubleshooting](#troubleshooting)
11. [Maintenance](#maintenance)

---

## Quick Start

Get MyApply running in 5 minutes:

```bash
# 1. Clone and install
git clone https://github.com/your-username/MyApply.git
cd MyApply
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and set OPENAI_API_KEY

# 3. Run
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 4. Visit
open http://127.0.0.1:8000
```

**Default credentials for first time:**
Register a new account at `/auth/register`

---

## Local Development Setup

### Prerequisites

- **Python 3.9+** (3.11 recommended)
- **pip** (latest version)
- **Git**
- **OpenAI API Key** (required for AI features)
- **Mapbox Token** (optional, for map features)

### Step-by-Step Setup

#### 1. Clone Repository

```bash
git clone https://github.com/your-username/MyApply.git
cd MyApply
```

#### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# Activate (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.venv\Scripts\activate.bat
```

#### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

**Key Dependencies:**
```
fastapi             # Web framework
uvicorn[standard]   # ASGI server
sqlmodel            # ORM
psycopg[binary]     # PostgreSQL driver (v3)
openai              # OpenAI API client
agents              # AgentKit SDK
passlib[bcrypt]     # Password hashing
python-multipart    # Form parsing
httpx               # Async HTTP client
jinja2              # Templates
alembic             # Database migrations
pytest              # Testing
```

#### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Minimum required configuration:**
```bash
SECRET_KEY=your-secret-key-here  # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
OPENAI_API_KEY=sk-your-openai-api-key
```

#### 5. Initialize Database

```bash
# Database tables are auto-created on startup
# For development, SQLite is used by default (myapply.db in project root)

# Start the application
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The application will automatically:
- Create database tables via SQLModel
- Add missing columns to existing tables
- Initialize the database schema

#### 6. Create Admin User

```bash
# While app is running, open a new terminal
source .venv/bin/activate
python scripts/create_admin.py admin@example.com "SecurePassword123!"
```

#### 7. Verify Installation

Visit http://127.0.0.1:8000 and you should see:
- ✅ Login page loads
- ✅ Can register/login
- ✅ Profile page accessible
- ✅ Compose page loads

**Check health endpoints:**
```bash
curl http://127.0.0.1:8000/health
# Expected: {"status":"healthy","service":"MyApply"}

curl http://127.0.0.1:8000/health/db
# Expected: {"status":"healthy","database":"connected"}
```

---

## Environment Configuration

### Environment Variables Reference

Create a `.env` file in the project root with these variables:

```bash
# ================================================================
# Required Variables
# ================================================================

# Session encryption key (generate with secrets.token_hex(32))
SECRET_KEY=your-generated-secret-key-here

# OpenAI API key for LLM and AgentKit features
OPENAI_API_KEY=sk-your-openai-api-key

# ================================================================
# Database Configuration
# ================================================================

# SQLite (default for local development)
DATABASE_URL=sqlite:///./myapply.db

# PostgreSQL (for production)
# DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/myapply

# Railway PostgreSQL (auto-set by Railway)
# DATABASE_URL=postgresql+psycopg://postgres:password@postgres.railway.internal:5432/railway

# ================================================================
# LLM Configuration
# ================================================================

# Default model for most operations
LLM_MODEL=gpt-4o-mini

# Optional: Separate model for cover letters (defaults to LLM_MODEL)
COVER_LETTER_MODEL=gpt-4o

# ================================================================
# Session Configuration
# ================================================================

# Session cookie name
SESSION_COOKIE_NAME=app_session

# HTTPS-only cookies (auto: enabled for prod, disabled for dev)
SESSION_SECURE=auto

# SameSite cookie attribute (lax recommended)
SESSION_SAMESITE=lax

# ================================================================
# CORS Configuration
# ================================================================

# Comma-separated list of allowed origins
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000

# Production example:
# ALLOWED_ORIGINS=https://myapply-production.up.railway.app

# ================================================================
# Mapbox (Optional - for map features)
# ================================================================

# Public token for Mapbox GL JS
MAPBOX_PUBLIC_TOKEN=pk.your-public-token

# Access token for isochrone API
MAPBOX_ACCESS_TOKEN=pk.your-access-token

# Alternative name for access token
MAPBOX_SECRET_TOKEN=pk.your-secret-token

# ================================================================
# Server Configuration
# ================================================================

# Environment (development or production)
ENV=development

# Server port (Railway sets this automatically)
PORT=8000

# ================================================================
# AgentKit Workflow IDs (Advanced)
# ================================================================

# These are configured in workflow_constants.py
# Only change if you deploy custom workflows to AgentKit

# ================================================================
# ChatKit Configuration (Optional)
# ================================================================

# ChatKit domain (if using custom domain)
# CHATKIT_DOMAIN=myapply.example.com

# ChatKit public key (if required)
# CHATKIT_DOMAIN_PUBLIC_KEY=your-public-key
```

### Environment-Specific Configurations

#### Development (.env.local)
```bash
ENV=development
DATABASE_URL=sqlite:///./myapply.db
SESSION_SECURE=false
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
```

#### Production (.env.production)
```bash
ENV=production
DATABASE_URL=postgresql+psycopg://user:pass@host:port/db
SESSION_SECURE=true
ALLOWED_ORIGINS=https://myapply-production.up.railway.app
```

### Generating Secret Keys

```bash
# Generate SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Generate multiple keys at once
python << EOF
import secrets
print("SECRET_KEY=" + secrets.token_hex(32))
print("API_KEY=" + secrets.token_urlsafe(32))
EOF
```

---

## AgentKit Workflow Setup

### Overview

MyApply uses **OpenAI AgentKit** to orchestrate AI workflows for job description parsing and resume generation.

### Setup Steps

#### 1. Obtain OpenAI API Key

1. Visit [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-`)
4. Add to `.env`: `OPENAI_API_KEY=sk-your-key`

#### 2. Configure Workflow IDs

The workflow IDs are pre-configured in `workflow_constants.py`:

```python
WORKFLOW_RESUME_BUILDER_V2_ID = "wf_68ec6800d1948190a0629c0eaf07f8e303633b84fcb85ab9"
WORKFLOW_RESUME_BUILDER_V2_VER = "1"
```

**If you deployed custom workflows to AgentKit:**

1. Open [agentkit.openai.com](https://agentkit.openai.com)
2. Find your workflow
3. Copy the workflow ID
4. Update `workflow_constants.py` with your ID

#### 3. Understand the Workflow

The **ResumeBuilderV2** workflow consists of two agents:

**Job Scraper Agent:**
- Extracts structured data from job postings
- Tools: `extract_ats_keywords`, `web_search`
- Output: Structured job requirements (skills, experience, locations)

**Bullet Generator Agent:**
- Generates tailored resume bullets
- Tools: `web_search`
- Process: Analyze → Research → Plan → Generate
- Output: 3-6 achievement-focused bullets

### Agent Configuration

The agents are defined in `services/resume_builder_agents.py`:

```python
job_scraper = Agent(
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

bullet_generator = Agent(
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

### Testing Workflows

#### Via API

**1. Ingest Job Description:**
```bash
# Start a session (save cookies)
curl -c cookies.txt -X POST http://localhost:8000/auth/login \
  -F "email=admin@example.com" \
  -F "password=SecurePassword123!" \
  -F "csrf_token=$(curl -s http://localhost:8000/auth/login | grep csrf_token | cut -d'"' -f4)"

# Ingest job description
curl -b cookies.txt -X POST http://localhost:8000/api/jd/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1",
    "source_url": "https://example.com/jobs/senior-python-engineer"
  }'
```

**2. Build Resume:**
```bash
curl -b cookies.txt -X POST http://localhost:8000/api/resume/build \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1",
    "job_url": "https://example.com/jobs/senior-python-engineer",
    "application_id": "uuid-from-previous-response"
  }'
```

#### Via UI

1. Navigate to http://127.0.0.1:8000/compose
2. Enter a job URL or paste job description text
3. Click "Generate" to trigger the workflow
4. View results: structured job data, resume bullets, cover letter

#### Via Tests

```bash
# Run workflow tests
pytest tests/test_workflows.py -v

# Run specific test
pytest tests/test_workflows.py::test_jd_ingestion -v
```

### Monitoring Workflows

**Check Debug Logs:**
```bash
# View logs for an application
curl -b cookies.txt http://localhost:8000/api/applications/{application_id}/debug-logs
```

**Logs include:**
- Request data (workflow inputs)
- Response data (workflow outputs)
- Status codes
- Error messages
- Duration (milliseconds)

**Database Query:**
```sql
-- View recent workflow runs
SELECT * FROM api_debug_log
WHERE log_type = 'agentkit_call'
ORDER BY created_at DESC
LIMIT 10;
```

---

---

## Database Setup

### SQLite (Development)

**Default configuration:**
```bash
DATABASE_URL=sqlite:///./myapply.db
```

**Database file:** `myapply.db` in project root

**Management:**
```bash
# Open SQLite console
sqlite3 myapply.db

# List tables
.tables

# View schema
.schema user

# Query data
SELECT * FROM user;

# Exit
.quit
```

**Reset database:**
```bash
# Stop the application
rm myapply.db
# Restart the application (tables auto-created)
```

### PostgreSQL (Production)

#### Local PostgreSQL Setup

**1. Install PostgreSQL:**
```bash
# macOS (Homebrew)
brew install postgresql@15
brew services start postgresql@15

# Ubuntu
sudo apt update
sudo apt install postgresql postgresql-contrib

# Windows
# Download from: https://www.postgresql.org/download/windows/
```

**2. Create Database:**
```bash
# Connect as postgres user
psql -U postgres

# Create database and user
CREATE DATABASE myapply;
CREATE USER myapply_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE myapply TO myapply_user;
\q
```

**3. Configure Application:**
```bash
# Update .env
DATABASE_URL=postgresql+psycopg://myapply_user:secure_password@localhost:5432/myapply
```

**4. Run Migrations:**
```bash
# Auto-create tables on startup
uvicorn app:app --reload

# Or use Alembic
alembic upgrade head
```

#### Database Migrations with Alembic

**Initialize Alembic (if not already initialized):**
```bash
alembic init migrations
```

**Configure Alembic:**

Edit `alembic.ini`:
```ini
sqlalchemy.url = postgresql+psycopg://user:password@localhost:5432/myapply
```

Or use environment variable:
```bash
export DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/myapply"
alembic upgrade head
```

**Create Migration:**
```bash
# Auto-generate migration from models
alembic revision --autogenerate -m "Add new column"

# Create empty migration
alembic revision -m "Custom migration"
```

**Apply Migrations:**
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# View current version
alembic current

# View history
alembic history
```

### Database Maintenance

#### Backup

**SQLite:**
```bash
# Copy database file
cp myapply.db myapply.db.backup

# Or use SQLite backup command
sqlite3 myapply.db ".backup 'myapply.db.backup'"
```

**PostgreSQL:**
```bash
# Dump database
pg_dump -U myapply_user myapply > backup.sql

# Restore from dump
psql -U myapply_user myapply < backup.sql
```

#### Clean Up Old Data

**Remove old workflow runs:**
```sql
DELETE FROM api_debug_log
WHERE created_at < NOW() - INTERVAL '30 days';

DELETE FROM chatkit_thread_item
WHERE created_at < NOW() - INTERVAL '90 days';
```

**Vacuum (PostgreSQL):**
```sql
VACUUM ANALYZE;
```

---

## Testing

### Test Setup

**Install test dependencies:**
```bash
pip install pytest pytest-cov
```

**Test structure:**
```
tests/
├── conftest.py              # Fixtures
├── test_workflows.py        # Workflow tests
└── test_openai_workflows.py # AgentKit tests
```

### Running Tests

**All tests:**
```bash
pytest -v
```

**Specific test file:**
```bash
pytest tests/test_workflows.py -v
```

**Specific test:**
```bash
pytest tests/test_workflows.py::test_jd_ingestion -v
```

**With coverage:**
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html  # View coverage report
```

**Fast (skip slow tests):**
```bash
pytest -m "not slow"
```

### Test Fixtures

**Test database:**
```python
@pytest.fixture
def test_engine():
    """In-memory SQLite for fast tests."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
```

**Test user:**
```python
@pytest.fixture
def test_user(test_session):
    """Create authenticated test user."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass"),
        is_admin=False
    )
    test_session.add(user)
    test_session.commit()
    return user
```

### Mocking AgentKit

```python
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_workflow_run():
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

### Writing New Tests

**Example workflow test:**
```python
def test_new_workflow_feature(test_client, test_user, mock_workflow_run):
    """Test description."""
    # Arrange
    payload = {"user_id": test_user.id, "job_url": "https://example.com/job"}

    # Act
    response = test_client.post("/api/new-endpoint", json=payload)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "succeeded"
    assert "output" in data
```

---

## Railway Deployment

### Overview

Railway is a modern platform-as-a-service that simplifies deployment with:
- Automatic Dockerfile detection
- Managed PostgreSQL
- Environment variable management
- Automatic SSL certificates
- GitHub integration

### Prerequisites

- Railway account ([railway.app/new](https://railway.app/new))
- GitHub repository with MyApply code
- OpenAI API key

### Step-by-Step Deployment

#### 1. Create Railway Project

1. Go to [railway.app/new](https://railway.app/new)
2. Click **"Deploy from GitHub repo"**
3. Authorize Railway to access your GitHub
4. Select your MyApply repository
5. Railway detects Dockerfile and begins build

#### 2. Add PostgreSQL Database

1. In your Railway project dashboard, click **"+ New"**
2. Select **"Database" → "PostgreSQL"**
3. Railway creates and links the database
4. `DATABASE_URL` is automatically set in your service

**Verify DATABASE_URL format:**
- Should be: `postgresql+psycopg://...`
- NOT: `postgresql://...` (missing +psycopg)

If Railway sets wrong format:
1. Go to PostgreSQL service → Variables
2. Copy the connection string
3. Go to MyApply service → Variables
4. Set `DATABASE_URL=postgresql+psycopg://user:pass@host:port/db`

#### 3. Configure Environment Variables

In your **MyApply service** → Settings → Variables:

**Required Variables:**
```bash
ENV=production
SECRET_KEY=<generate-with-secrets.token_hex(32)>
OPENAI_API_KEY=sk-your-api-key
SESSION_SECURE=true
SESSION_COOKIE_NAME=app_session
SESSION_SAMESITE=lax
```

**Optional Variables:**
```bash
# CORS (add your Railway domain)
ALLOWED_ORIGINS=https://myapply-production.up.railway.app

# LLM Configuration
LLM_MODEL=gpt-4o-mini
COVER_LETTER_MODEL=gpt-4o

# Mapbox (for map features)
MAPBOX_PUBLIC_TOKEN=pk.your-public-token
MAPBOX_ACCESS_TOKEN=pk.your-access-token
```

**Railway auto-sets:**
- `PORT` - Server port (don't override)
- `DATABASE_URL` - PostgreSQL connection string

#### 4. Deploy

Railway automatically deploys when:
- You push to GitHub
- You change environment variables
- You trigger manual deploy

**Monitor deployment:**
1. Go to your service → "Deployments"
2. Click latest deployment
3. View build logs
4. View runtime logs

#### 5. Run Database Migrations

**Option A: Railway Dashboard**
1. Service → Settings → Deploy
2. Click "Run Command"
3. Enter: `alembic upgrade head`
4. Click "Run"

**Option B: Railway CLI**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to project
railway link

# Run migrations
railway run alembic upgrade head
```

#### 6. Create Admin User

```bash
# Using Railway CLI
railway run python scripts/create_admin.py admin@example.com "SecurePassword123!"

# Or via Railway Dashboard shell
# Service → Settings → Deploy → Run Command
python scripts/create_admin.py admin@example.com "SecurePassword123!"
```

#### 7. Verify Deployment

**Get your Railway URL:**
- Service → Settings → Networking → Public Domain
- Example: `myapply-production.up.railway.app`

**Test endpoints:**
```bash
# Health check
curl https://myapply-production.up.railway.app/health

# Database health
curl https://myapply-production.up.railway.app/health/db

# Open in browser
open https://myapply-production.up.railway.app
```

### Railway CLI Commands

```bash
# Install CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# View logs
railway logs

# Run command
railway run <command>

# Connect to database
railway connect postgres

# Deploy
railway up

# View status
railway status
```

### Custom Domains

**Add custom domain:**
1. Service → Settings → Networking
2. Click "Add Custom Domain"
3. Enter your domain: `myapply.example.com`
4. Add CNAME record to your DNS:
   ```
   CNAME myapply -> myapply-production.up.railway.app
   ```
5. Wait for SSL certificate (automatic)

**Update CORS:**
```bash
ALLOWED_ORIGINS=https://myapply.example.com
```

### Scaling

**Vertical Scaling:**
1. Service → Settings → Resources
2. Increase memory/CPU
3. Restart service

**Horizontal Scaling:**
- Railway supports multiple replicas
- Requires PostgreSQL (not SQLite)
- Session state stored in database (compatible)

### Monitoring

**View Logs:**
```bash
# Via CLI
railway logs --tail 100

# Via Dashboard
Service → Logs tab
```

**Metrics:**
- Service → Metrics tab
- CPU usage
- Memory usage
- Network traffic

---

## Production Checklist

Before launching to production, verify:

### Security

- [ ] Generated strong `SECRET_KEY` (32+ bytes)
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- [ ] Set `SESSION_SECURE=true`
- [ ] Configured `ALLOWED_ORIGINS` with HTTPS URLs only
- [ ] Database uses SSL (`postgresql+psycopg://...` with Railway proxy)
- [ ] Admin password is strong and unique
- [ ] API keys not committed to Git
- [ ] `.env` file in `.gitignore`

### Configuration

- [ ] `ENV=production`
- [ ] Database URL uses `psycopg` driver (v3)
- [ ] CORS origins match actual domains
- [ ] Session cookies configured correctly
- [ ] OpenAI API key valid and funded

### Database

- [ ] Migrations applied: `alembic upgrade head`
- [ ] Admin user created
- [ ] Database backups enabled (Railway dashboard)
- [ ] Connection pooling configured (automatic with SQLAlchemy)

### Performance

- [ ] Using Gunicorn with multiple workers (configured in Dockerfile)
- [ ] Static files served efficiently
- [ ] Database indexes present (automatic with SQLModel)
- [ ] Connection pooling enabled (automatic)

### Monitoring

- [ ] Health endpoints responding:
  - `/health`
  - `/health/db`
- [ ] Error tracking configured (logs in Railway)
- [ ] Uptime monitoring setup (optional: UptimeRobot, Pingdom)

### Testing

- [ ] All tests passing: `pytest -v`
- [ ] Workflow integration tested
- [ ] Authentication flows verified
- [ ] CORS headers correct
- [ ] Session persistence working

### Documentation

- [ ] README updated with production URL
- [ ] API documentation accessible
- [ ] Deployment notes recorded
- [ ] Runbook created for common issues

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

**Symptom:**
```
connection refused
could not connect to server
SSL required
```

**Solutions:**

**Check DATABASE_URL format:**
```bash
# Correct for Railway PostgreSQL
postgresql+psycopg://user:pass@host:port/db

# Wrong formats
postgresql://...         # Missing +psycopg
postgresql+psycopg2://   # Wrong driver version
```

**Verify SSL configuration:**
- Railway proxy URLs (`.proxy.rlwy.net`) → SSL auto-added
- Internal URLs (`.railway.internal`) → No SSL needed

**Test connection:**
```bash
# Using Railway CLI
railway connect postgres

# Manual test
psql "postgresql://user:pass@host:port/db?sslmode=require"
```

#### 2. Module Not Found Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'psycopg2'
ModuleNotFoundError: No module named 'agents'
```

**Solutions:**

**Ensure correct driver:**
```bash
# requirements.txt should have:
psycopg[binary]

# NOT:
psycopg2-binary
```

**Reinstall dependencies:**
```bash
pip install --upgrade -r requirements.txt
```

**Clear cache:**
```bash
pip cache purge
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. Template Not Found

**Symptom:**
```
TemplateNotFound: auth_login.html
```

**Solutions:**

**Verify templates directory:**
```bash
ls templates/
# Should show: auth_login.html, base.html, etc.
```

**Check BASE_DIR:**
In `app.py`:
```python
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
```

**Railway deployment:**
- Ensure Dockerfile copies templates
- Check build logs for file copy errors

#### 4. CORS Errors

**Symptom (browser console):**
```
Access to fetch at 'https://api.example.com' from origin 'https://app.example.com'
has been blocked by CORS policy
```

**Solutions:**

**Add origin to ALLOWED_ORIGINS:**
```bash
ALLOWED_ORIGINS=https://app.example.com,https://other-domain.com
```

**Include protocol:**
- ✅ `https://myapply.up.railway.app`
- ❌ `myapply.up.railway.app` (missing https://)

**Restart application** after changing CORS settings.

#### 5. Session/Cookie Issues

**Symptom:**
- Can't stay logged in
- Constant redirects to login
- "Authentication required" errors

**Solutions:**

**Local development (HTTP):**
```bash
SESSION_SECURE=false
# or
SESSION_SECURE=auto  # Auto-detects based on database
```

**Production (HTTPS):**
```bash
SESSION_SECURE=true
```

**Check cookie settings:**
```bash
SESSION_COOKIE_NAME=app_session
SESSION_SAMESITE=lax
```

**Verify ALLOWED_ORIGINS matches exactly:**
```bash
# If accessing via https://myapply.railway.app
ALLOWED_ORIGINS=https://myapply.railway.app

# Not http:// or www. or different subdomain
```

#### 6. OpenAI API Errors

**Symptom:**
```
Failed to start workflow
502 Bad Gateway
Workflow execution failed
```

**Solutions:**

**Verify API key:**
```bash
# Test OpenAI API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Check API quota:**
- Visit [platform.openai.com/usage](https://platform.openai.com/usage)
- Ensure you have available credits

**Network connectivity:**
- Ensure outbound HTTPS allowed (port 443)
- No firewall blocking OpenAI API

**Rate limits:**
- OpenAI has rate limits per model
- Add retry logic or backoff if hitting limits

#### 7. Port Binding Issues

**Symptom (Railway):**
```
Application started but showing unhealthy
Port binding error
```

**Solutions:**

**Verify PORT usage:**
```python
# Correct
uvicorn app:app --host 0.0.0.0 --port $PORT

# Wrong
uvicorn app:app --host localhost --port 8000
```

**Check Dockerfile:**
```dockerfile
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Railway sets PORT automatically - don't override it.**

#### 8. Workflow Timeout

**Symptom:**
```
Workflow timed out
Request timeout
```

**Solutions:**

**Check OpenAI status:**
- [status.openai.com](https://status.openai.com)

**Increase timeout:**
In `services/resume_builder_service.py`:
```python
async with httpx.AsyncClient(timeout=60.0) as client:
    # Increase from default 30s to 60s
```

**Simplify input:**
- Long job descriptions may take longer
- Try with shorter input first

### Debug Logs

**Enable debug logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**View application logs:**
```bash
# Railway
railway logs --tail 100

# Local
# Logs print to terminal where uvicorn is running
```

**View debug logs in database:**
```sql
SELECT * FROM api_debug_log
WHERE log_type = 'agentkit_call'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Maintenance

### Regular Tasks

#### Daily

- [ ] Monitor error logs
- [ ] Check API usage/costs
- [ ] Verify health endpoints

#### Weekly

- [ ] Review debug logs
- [ ] Check database size
- [ ] Update dependencies (if needed)

#### Monthly

- [ ] Database backup
- [ ] Review and rotate API keys (if policy requires)
- [ ] Update dependencies
- [ ] Review Railway usage/costs

### Database Maintenance

**Backup:**
```bash
# Railway
railway run pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Local PostgreSQL
pg_dump -U myapply_user myapply > backup_$(date +%Y%m%d).sql
```

**Restore:**
```bash
# Railway
railway run psql $DATABASE_URL < backup.sql

# Local
psql -U myapply_user myapply < backup.sql
```

**Clean old data:**
```sql
-- Remove logs older than 30 days
DELETE FROM api_debug_log WHERE created_at < NOW() - INTERVAL '30 days';

-- Remove old chat history (optional)
# ChatKit tables exist but are not currently used in the application
```

**Optimize (PostgreSQL):**
```sql
VACUUM ANALYZE;
```

### Dependency Updates

```bash
# Check outdated packages
pip list --outdated

# Update specific package
pip install --upgrade fastapi

# Update all (careful!)
pip install --upgrade -r requirements.txt

# Freeze updated versions
pip freeze > requirements.txt

# Test thoroughly after updates
pytest -v
```

### Monitoring

**Setup uptime monitoring:**
- [UptimeRobot](https://uptimerobot.com) (free)
- [Pingdom](https://pingdom.com)
- Monitor `/health` endpoint every 5 minutes

**Setup error tracking:**
- [Sentry](https://sentry.io)
- [Rollbar](https://rollbar.com)
- Integrate with Python SDK

**Monitor costs:**
- OpenAI API usage: [platform.openai.com/usage](https://platform.openai.com/usage)
- Railway usage: Project → Usage tab
- Set up billing alerts

---

## Additional Resources

### Documentation

- **Technical Architecture**: [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)
- **API Reference**: [README.md](README.md)
- **Experience Graph**: [MyLifeSchemaInstructions.md](MyLifeSchemaInstructions.md)

### External Resources

- **FastAPI**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **SQLModel**: [sqlmodel.tiangolo.com](https://sqlmodel.tiangolo.com)
- **OpenAI AgentKit**: [platform.openai.com/docs/agentkit](https://platform.openai.com/docs/agentkit)
- **Railway**: [docs.railway.app](https://docs.railway.app)
- **Psycopg3**: [www.psycopg.org/psycopg3](https://www.psycopg.org/psycopg3/)

### Support

- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas
- **Railway Discord**: [discord.gg/railway](https://discord.gg/railway)

---

## Quick Reference

### Development Commands

```bash
# Start development server
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest -v

# Run with coverage
pytest --cov=. --cov-report=html

# Create admin user
python scripts/create_admin.py admin@example.com "password"

# Database migrations
alembic upgrade head
alembic current
alembic history

# Database console
sqlite3 myapply.db
psql postgresql://user:pass@host/db
```

### Railway Commands

```bash
# Login and link
railway login
railway link

# View logs
railway logs

# Run command
railway run <command>

# Migrations
railway run alembic upgrade head

# Create admin
railway run python scripts/create_admin.py "email" "pass"

# Connect to database
railway connect postgres

# Deploy
railway up
```

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Database health
curl http://localhost:8000/health/db

# Test workflow
curl -X POST http://localhost:8000/api/jd/ingest \
  -H "Content-Type: application/json" \
  -d '{"user_id": "1", "source_url": "https://example.com/job"}'
```

---

**Setup Complete!** 🎉

Your MyApply instance is ready for development or production.

For questions or issues, consult:
- [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) - Deep technical details
- [README.md](README.md) - Feature overview
- GitHub Issues - Report bugs or request features

**Happy building!**
