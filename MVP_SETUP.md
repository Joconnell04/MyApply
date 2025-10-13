# MyApply MVP Setup Guide

Quick start guide for getting the MyApply MVP running with AgentKit workflows and basic authentication.

---

## 🚀 Quick Start (5 minutes)

### 1. Prerequisites

```bash
# Required
- Python 3.9+
- OpenAI API key (for workflows)

# Optional
- Mapbox tokens (for map features)
```

### 2. Install Dependencies

```bash
# Clone repository
cd MyApply

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env and set required values
```

**Required environment variables:**

```bash
# Security (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-secret-key-here

# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key-here

# Database (default SQLite is fine for MVP)
DATABASE_URL=sqlite:///./myapply.db

# Environment
ENV=development
```

### 4. Start the Server

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Visit: **http://127.0.0.1:8000**

---

## 🔐 Authentication Setup (MVP)

The auth system is **production-ready** but simplified for MVP use:

### Features Included

✅ **Bcrypt password hashing** - Secure password storage
✅ **CSRF protection** - Prevents cross-site attacks
✅ **Rate limiting** - 5 failed login attempts per 10 minutes
✅ **Email validation** - Proper email format checking
✅ **Session management** - Secure cookie-based sessions

### Creating Your First User

**Option 1: Via Web Interface**

1. Visit http://127.0.0.1:8000
2. Click "Register"
3. Enter email and password
4. Click "Create Account"

**Option 2: Via Script**

```bash
python scripts/create_admin.py your-email@example.com "YourPassword123"
```

This creates an admin user who can access `/admin/users` and `/admin/runs`.

### Security Notes for MVP

- ✅ **Passwords are hashed** with bcrypt (not stored in plaintext)
- ✅ **Sessions are encrypted** with your SECRET_KEY
- ✅ **CSRF tokens** protect against cross-site attacks
- ⚠️ **For production:** Set `SESSION_SECURE=true` to require HTTPS
- ⚠️ **For production:** Use PostgreSQL instead of SQLite
- ⚠️ **For production:** Set strong SECRET_KEY and rotate regularly

---

## 🤖 AgentKit Workflow Integration

### How It Works

MyApply now uses a **single all-in-one workflow** with two API entry points:

```
┌───────────────────────────┐
│   ResumeBuilderV2         │
│   • POST /api/jd/ingest   │  Cache structured job data
│   • POST /api/resume/build│  Return resume bullets + cover letter
│   • Scrape, plan, persist │
└───────────────────────────┘
```

### Workflow Configuration

The workflow IDs are defined in [`workflow_constants.py`](workflow_constants.py):

```python
# ResumeBuilderV2 (all-in-one)
WORKFLOW_RESUME_BUILDER_V2_ID = "wf_68ec6800d1948190a0629c0eaf07f8e303633b84fcb85ab9"
WORKFLOW_RESUME_BUILDER_V2_VER = "1"
```

**To use your own workflow:** Update these values to match your AgentKit deployment.

### Testing Workflows

```bash
# Run integration tests
pytest tests/test_workflows.py -v

# Run full test suite
pytest -v
```

---

## 📱 Using the Application

### Web Interface

1. **Login**
   - Visit http://127.0.0.1:8000
   - Enter credentials
   - You'll be redirected to `/compose`

2. **Compose Page (Workflow UI)**
   - Enter a job posting URL and click "Run ResumeBuilderV2"
   - The UI calls `/api/jd/ingest` to parse the job, then `/api/resume/build` to surface the cached resume artifacts
   - Review the structured job insights, resume bullets, and optional cover letter
   - Copy or save the generated content to your application

3. **Profile Management**
   - Visit `/profile`
   - Set your home location (for map features)
   - Edit MyLife JSON (experience graph data)

4. **View Jobs**
   - `/jobs` - List of applications
   - `/map` - Geographic view (requires Mapbox tokens)
   - `/runs` - View workflow run history

### Legacy Compose (LLM Pipeline)

The original compose endpoint is still available at `/compose/legacy` for backwards compatibility. It uses the LLM pipeline instead of workflows.

---

## 🔧 API Endpoints

### `/api/jd/ingest`

```bash
POST /api/jd/ingest
Content-Type: application/json

{
  "user_id": "user-123",
  "source_url": "https://example.com/jobs/senior-python"
}

# Response
{
  "application_id": "uuid-here",
  "jd_status": "succeeded",
  "jd_struct_data": {
    "title": "Senior Engineer",
    "locations": ["Remote"],
    "required_skills": ["Python", "FastAPI"]
  }
}
```

### `/api/resume/build`

```bash
POST /api/resume/build
Content-Type: application/json

{
  "user_id": "user-123",
  "application_id": "uuid-here",
  "job_url": "https://example.com/jobs/senior-python"
}

# Response
{
  "application_id": "uuid-here",
  "resume_status": "succeeded",
  "structured_job_data": {
    "title": "Senior Engineer",
    "locations": ["Remote"],
    "required_skills": ["Python", "FastAPI"]
  },
  "resume_bullets": [
    "Scaled APIs handling 50M+ requests...",
    "Led cross-functional team..."
  ],
  "cover_letter": "I am excited to apply my FastAPI expertise to this role.",
  "resume_output": {
    "structured_job_data": {
      "title": "Senior Engineer",
      "locations": ["Remote"],
      "required_skills": ["Python", "FastAPI"]
    },
    "resume_bullets": [
      "Scaled APIs handling 50M+ requests...",
      "Led cross-functional team..."
    ],
    "cover_letter": "I am excited to apply my FastAPI expertise to this role."
  }
}
```

---

## 🗂️ Database Schema

MyApply uses SQLite by default (PostgreSQL for production).

### Key Tables

- **`user`** - User accounts and profiles
- **`jobapplication`** - Job application workflow state
  - Tracks both JD and resume workflow runs
  - Stores structured JD data
  - Stores resume output
- **`workflow_run`** - AgentKit workflow execution metadata
- **`job_applied`** - Saved job applications
- **`compose_run`** - Legacy LLM compose runs

### Viewing Data

```bash
# SQLite console
sqlite3 myapply.db

# List tables
.tables

# View applications
SELECT id, user_id, jd_status, resume_status, created_at FROM jobapplication;

# Exit
.quit
```

---

## 🐛 Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| "OPENAI_API_KEY not configured" | Add to `.env` and restart server |
| "favicon.ico not found" | Fixed! Now redirects to `/static/favicon.svg` |
| Login page not loading | Check templates exist in `templates/` directory |
| CSRF errors | Clear browser cookies and try again |
| Workflow 502 errors | Check OpenAI API key validity and rate limits |
| Database locked | Close other connections to SQLite file |

### Error Logs

```bash
# View server logs
uvicorn app:app --reload --log-level debug

# Check specific errors
# Server logs appear in terminal
```

### Reset Database

```bash
# ⚠️ WARNING: This deletes all data
rm myapply.db

# Restart server to recreate tables
uvicorn app:app --reload
```

---

## ☁️ Deployment

### Railway (Recommended for MVP)

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "MVP ready"
   git push origin main
   ```

2. **Create Railway Project**
   - Visit [railway.app/new](https://railway.app/new)
   - Select your GitHub repo
   - Railway auto-detects FastAPI

3. **Add PostgreSQL Database**
   - Click "+ New"
   - Select "Database" → "PostgreSQL"
   - Railway auto-sets `DATABASE_URL`

4. **Set Environment Variables**
   ```bash
   SECRET_KEY=<generate-new-key>
   OPENAI_API_KEY=sk-your-key
   ENV=production
   SESSION_SECURE=true
   ALLOWED_ORIGINS=https://your-app.up.railway.app
   ```

5. **Deploy**
   - Railway deploys automatically on push
   - Visit your app URL

**Full deployment guide:** [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 📚 Additional Resources

### Documentation

- **[README.md](README.md)** - Full feature documentation
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Complete deployment guide
- **[workflow_constants.py](workflow_constants.py)** - Workflow IDs

### Code Structure

```
MyApply/
├── app.py                          # Main FastAPI app
├── auth.py                         # Authentication logic
├── models.py                       # Database models
├── applications.py                 # JobApplication model
├── workflow_constants.py           # Workflow IDs
├── routers/
│   ├── jd_ingest.py               # JD ingest endpoint (ResumeBuilderV2 cache)
│   └── resume_build.py            # ResumeBuilderV2 resume endpoint
├── services/
│   ├── openai_workflows.py        # OpenAI client
│   └── workflow_output_parser.py  # Shared output helpers
├── templates/
│   ├── compose_workflow.html      # New workflow UI
│   ├── compose.html               # Legacy LLM UI
│   ├── auth_login.html
│   └── auth_register.html
└── tests/
    └── test_workflows.py          # Integration tests
```

### Getting Help

- **Issues:** File bugs or feature requests on GitHub
- **Questions:** Check [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section

---

## ✅ Verification Checklist

Before deploying, verify:

- [ ] Environment variables set in `.env`
- [ ] OPENAI_API_KEY is valid
- [ ] Can register a new user
- [ ] Can login successfully
- [ ] Can access `/compose` page
- [ ] Workflow IDs match your AgentKit deployments
- [ ] Tests pass: `pytest tests/test_workflows.py -v`
- [ ] Database creates successfully
- [ ] Favicon loads without 404

Run verification script:

```bash
bash scripts/verify_agentkit_integration.sh
```

Expected output: `✅ All checks passed! (24/24)`

---

## 🎯 What's Included in MVP

### ✅ Authentication
- User registration
- Login/logout
- Password hashing (bcrypt)
- CSRF protection
- Rate limiting
- Session management

### ✅ Workflow Integration
- Two-phase workflow orchestration
- Job description parsing
- Resume generation
- Persistent state tracking
- Error handling

### ✅ Frontend
- Modern UI with TailwindCSS
- HTMX for dynamic updates
- Real-time feedback
- Copy-to-clipboard utilities
- Responsive design

### ✅ Database
- SQLite (dev) / PostgreSQL (prod)
- Automatic table creation
- Migration support
- User profiles
- Workflow run history

---

## 🚦 Next Steps

1. **Add Experience Data**
   - Visit `/profile`
   - Edit MyLife JSON to add your experience
   - This data is used by Resume Builder

2. **Test Workflows**
   - Go to `/compose`
   - Enter a job posting URL
   - Generate resume bullets

3. **Deploy to Production**
   - Follow [DEPLOYMENT.md](DEPLOYMENT.md)
   - Set up PostgreSQL
   - Configure environment variables
   - Enable HTTPS

4. **Customize Workflows**
   - Update workflow IDs in `workflow_constants.py`
   - Test with your own AgentKit workflows
   - Adjust input/output parsing as needed

---

**Questions?** Check [DEPLOYMENT.md](DEPLOYMENT.md) or open an issue!

**Built with FastAPI, OpenAI AgentKit, and TailwindCSS** 🚀
