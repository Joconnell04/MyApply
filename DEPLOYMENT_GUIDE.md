# 🚀 MyApply Deployment Guide

Complete guide for deploying MyApply to Railway with PostgreSQL and psycopg driver.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Database Configuration](#database-configuration)
- [Railway Deployment](#railway-deployment)
- [Environment Variables](#environment-variables)
- [Post-Deployment Setup](#post-deployment-setup)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Security Checklist](#security-checklist)

---

## Prerequisites

- **Railway Account**: Sign up at [railway.app](https://railway.app)
- **GitHub Repository**: MyApply code pushed to GitHub
- **OpenAI API Key**: Required for LLM features and AgentKit workflows
- **Railway CLI** (optional): `npm install -g @railway/cli`

---

## Database Configuration

MyApply uses **PostgreSQL with the psycopg driver** (v3, not psycopg2).

### Database URL Format

```bash
# Correct format with psycopg driver
DATABASE_URL=postgresql+psycopg://user:password@host:port/database

# For Railway internal networking
DATABASE_URL=postgresql+psycopg://postgres:password@postgres.railway.internal:5432/railway

# For Railway proxy (with SSL)
DATABASE_URL=postgresql+psycopg://postgres:password@ballast.proxy.rlwy.net:33607/railway
```

### Driver Requirements

The app uses:
- **Driver**: `psycopg[binary]` (version 3)
- **NOT**: `psycopg2-binary` (version 2)
- **SSL Mode**: Automatically adds `sslmode=require` for Railway proxy connections

---

## Railway Deployment

### Step 1: Create Railway Project

1. Go to [railway.app/new](https://railway.app/new)
2. Click **"Deploy from GitHub repo"**
3. Select your MyApply repository
4. Railway will auto-detect the Dockerfile

### Step 2: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database" → "PostgreSQL"**
3. Railway automatically creates and links the database
4. The `DATABASE_URL` environment variable is set automatically

**Note:** Use the internal Railway URL format when possible:
```bash
postgresql+psycopg://postgres:password@postgres.railway.internal:5432/railway
```

### Step 3: Configure Environment Variables

In your **MyApply service** settings → Variables, add these:

#### Required Variables

```bash
# Environment
ENV=production

# Database (auto-set by Railway, verify it uses psycopg driver)
DATABASE_URL=postgresql+psycopg://postgres:password@postgres.railway.internal:5432/railway

# Security - Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-generated-secret-key-here

# Session Configuration
SESSION_COOKIE_NAME=app_session
SESSION_SECURE=true
SESSION_SAMESITE=lax

# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key

# LLM Models
LLM_MODEL=gpt-4o-mini
COVER_LETTER_MODEL=gpt-4o
```

#### Optional Variables

```bash
# CORS Origins (add your Railway domain with https://)
ALLOWED_ORIGINS=https://myapply-production.up.railway.app,http://localhost:8000

# Mapbox (for map features)
MAPBOX_PUBLIC_TOKEN=pk.your-public-token
MAPBOX_ACCESS_TOKEN=pk.your-access-token

# AgentKit Tools API
MYAPPLY_API_KEY=your-api-key

# ChatKit (if using)
CHATKIT_DOMAIN=production.up.railway.app
CHATKIT_DOMAIN_PUBLIC_KEY=your-chatkit-public-key
```

**Important:** Railway automatically sets `PORT` - do not override it.

### Step 4: Verify Start Command

Railway should auto-detect from `Procfile`, but verify in Settings → Deploy:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Or use the Dockerfile CMD (recommended):
```bash
gunicorn app:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000}
```

---

## Post-Deployment Setup

### Run Database Migrations

After first deployment, run migrations:

#### Option A: Railway Dashboard

1. Go to your service → **"Settings" → "Deploy"**
2. Click **"Run Command"**
3. Run: `alembic upgrade head`

#### Option B: Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link to project
railway login
railway link

# Run migrations
railway run alembic upgrade head
```

### Create Admin User

```bash
# Using Railway CLI
railway run python scripts/create_admin.py admin@example.com "SecurePassword123!"

# Or via Railway Dashboard shell
python scripts/create_admin.py admin@example.com "SecurePassword123!"
```

---

## Verification

### 1. Check Service Health

```bash
# Replace with your Railway domain
curl https://myapply-production.up.railway.app/health
# Expected: {"status":"healthy","service":"MyApply"}

# Check database connection
curl https://myapply-production.up.railway.app/health/db
# Expected: {"status":"healthy","database":"connected"}
```

### 2. Verify Database Tables

Using Railway CLI:

```bash
# Connect to database
railway connect postgres

# List tables
\dt

# Check user table
SELECT id, email, is_admin FROM "user";

# Exit
\q
```

### 3. Test Authentication

1. Visit your Railway app URL: `https://your-app.up.railway.app`
2. You should be redirected to `/auth/login`
3. Log in with your admin credentials
4. Verify redirect to `/compose`

### 4. Test Database Connection

Check the application logs for any database connection errors:

```bash
# Using Railway CLI
railway logs

# Or check in Railway Dashboard → Logs tab
```

---

## Troubleshooting

### Database Connection Errors

**Symptom:** `connection refused` or `SSL required`

**Solutions:**

1. **Verify DATABASE_URL format:**
   ```bash
   # Should be:
   postgresql+psycopg://user:password@host:port/db

   # NOT:
   postgresql://user:password@host:port/db  # Missing +psycopg
   postgresql+psycopg2://...                 # Wrong driver
   ```

2. **For Railway proxy connections**, SSL is auto-configured:
   - URL contains `proxy.rlwy.net` → app adds `sslmode=require`
   - Internal URLs (`postgres.railway.internal`) don't need SSL

3. **Check logs** for connection errors:
   ```bash
   railway logs | grep -i database
   ```

### Driver/Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'psycopg2'`

**Solution:**
- Ensure `requirements.txt` contains `psycopg[binary]`, NOT `psycopg2-binary`
- Redeploy after updating requirements

### Template Not Found Errors

**Symptom:** `TemplateNotFound: auth_login.html`

**Solution:**
- Templates are now loaded with absolute paths
- Verify `templates/` directory exists in deployment
- Check Railway build logs for file copy issues

### CORS Errors

**Symptom:** `Access-Control-Allow-Origin` errors in browser

**Solution:**
1. Add Railway domain to `ALLOWED_ORIGINS` with `https://`:
   ```bash
   ALLOWED_ORIGINS=https://myapply-production.up.railway.app
   ```
2. Restart the service

### Session/Cookie Issues

**Symptom:** Can't stay logged in, constant redirects

**Solution:**
- For production (HTTPS): `SESSION_SECURE=true`
- For local dev (HTTP): `SESSION_SECURE=false` or `SESSION_SECURE=auto`
- Verify `ALLOWED_ORIGINS` matches your domain exactly

### Port Binding Issues

**Symptom:** App starts but Railway shows unhealthy

**Solution:**
- Verify app binds to `0.0.0.0:$PORT`, not `localhost:8000`
- Check Dockerfile/Procfile uses `$PORT` variable
- Railway provides `PORT` env var automatically

---

## Security Checklist

Before going to production:

- ✅ Generate strong `SECRET_KEY` (32+ bytes, use `secrets.token_hex(32)`)
- ✅ Set `SESSION_SECURE=true` for HTTPS
- ✅ Use `ALLOWED_ORIGINS` with explicit HTTPS Railway domain
- ✅ Database URL uses `psycopg` driver with SSL for proxy connections
- ✅ Strong admin password (not dev password)
- ✅ API keys stored in Railway environment variables (not in code)
- ✅ Never commit `.env` or secrets to git
- ✅ Enable Railway database backups
- ✅ Monitor Railway logs for suspicious activity

---

## Performance & Scaling

### Recommended Settings

1. **Use Gunicorn with multiple workers** (already configured in Dockerfile):
   ```bash
   gunicorn app:app --workers 2 --worker-class uvicorn.workers.UvicornWorker
   ```

2. **Connection pooling** is handled by SQLAlchemy

3. **Railway scaling:**
   - Go to service → Settings → Resources
   - Increase memory/CPU as needed
   - Add replicas for horizontal scaling (requires PostgreSQL, not SQLite)

---

## Database Backups

Railway provides automatic backups:

1. Go to Postgres service → **"Backups"**
2. Configure backup schedule
3. Download backups as needed

Manual backup:

```bash
# Backup to file
railway run pg_dump $DATABASE_URL > backup.sql

# Restore from file
railway run psql $DATABASE_URL < backup.sql
```

---

## Quick Reference Commands

```bash
# View logs
railway logs

# Run migrations
railway run alembic upgrade head

# Check current migration
railway run alembic current

# Create admin user
railway run python scripts/create_admin.py "email" "password"

# Connect to database
railway connect postgres

# Run any command
railway run <command>

# Deploy manually
railway up
```

---

## Additional Resources

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **FastAPI Docs**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **SQLAlchemy Docs**: [docs.sqlalchemy.org](https://docs.sqlalchemy.org)
- **Psycopg3 Docs**: [www.psycopg.org/psycopg3](https://www.psycopg.org/psycopg3/)
- **Railway Discord**: [discord.gg/railway](https://discord.gg/railway)

---

## Support

Need help?
- 🐛 **Report bugs**: GitHub Issues
- 💬 **Ask questions**: GitHub Discussions
- 📚 **Read docs**: [README.md](README.md)
- 🚂 **Railway support**: Railway Discord

---

**🎉 Deployment Complete!**

Your MyApply application is now running on Railway with PostgreSQL and psycopg driver!

Visit your app at: `https://your-service-name.up.railway.app`
