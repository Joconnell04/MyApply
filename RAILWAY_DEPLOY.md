# Railway Production Deployment Guide

Complete guide to deploying MyApply to Railway with PostgreSQL.

## Prerequisites

- Railway account (sign up at [railway.app](https://railway.app))
- GitHub repository with MyApply code
- Railway CLI (optional): `npm install -g @railway/cli`

---

## Step 1: Create Railway Project

1. Go to [railway.app/new](https://railway.app/new)
2. Click **"Deploy from GitHub repo"**
3. Select your MyApply repository
4. Railway will auto-detect the Dockerfile

---

## Step 2: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database" → "PostgreSQL"**
3. Railway automatically creates and links the database
4. The `DATABASE_URL` environment variable is set automatically

**✅ Your Postgres credentials are already configured:**
- Internal URL: `postgresql://postgres:cFrOJOrnwXQfQKVUAnkNwPYPronyPyMq@postgres.railway.internal:5432/railway`
- This URL is automatically available as `DATABASE_URL` in your service

---

## Step 3: Configure Environment Variables

In your **MyApply service** settings, add these environment variables:

### Required Variables

```bash
# Environment
ENV=production
PORT=8000

# Database (should be auto-set by Railway)
DATABASE_URL=<>

# Security
SECRET_KEY=<>
SESSION_COOKIE_NAME=app_session
SESSION_SECURE=true
SESSION_SAMESITE=lax

# OpenAI
COVER_LETTER_MODEL=gpt-4o

# ChatKit
CHATKIT_DOMAIN=production.up.railway.app
CHATKIT_DOMAIN_PUBLIC_KEY=domain_pk_68ebf83e58ec8190a2bc239b475fd88e0fe2738197866eed

# MyApply API Key
MYAPPLY_API_KEY=dev_key

# Admin User (for initial setup)
ADMIN_EMAIL=Jt272004@gmail.com
ADMIN_PASSWORD=09272004
```

### Optional Variables

```bash
# Mapbox (if using map features)
MAPBOX_PUBLIC_TOKEN=pk.eyJ1Ijoib2NvMjciLCJhIjoiY21nbnpzbjd6MDhrYjJqcTQ3bHUwM3hjdCJ9.bCAYMbuiT4aC26mffnKa4w
MAPBOX_ACCESS_TOKEN=<>

# CORS (add your Railway domain)
ALLOWED_ORIGINS=https://myapply-production.up.railway.app,http://localhost:8000
```

---

## Step 4: Run Post-Deploy Setup

After the first deployment, run these commands **once** to set up the database:

### Option A: Using Railway Dashboard

1. Go to your service → **"Settings" → "Deploy"**
2. Click **"Run Command"**
3. Run: `bash scripts/railway_deploy.sh`

### Option B: Using Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link to project
railway login
railway link

# Run migrations
railway run alembic upgrade head

# Create admin user
railway run python scripts/init_admin.py "Jt272004@gmail.com" "09272004"
```

### Option C: Manual Commands

```bash
# Run migrations
railway run alembic upgrade head

# Create admin user
railway run python scripts/init_admin.py "Jt272004@gmail.com" "09272004"
```

---

## Step 5: Verify Deployment

### Check Service Health

```bash
# Replace with your Railway domain
curl https://myapply-production.up.railway.app/health
# Expected: {"status":"healthy","service":"MyApply"}

# Check database connection
curl https://myapply-production.up.railway.app/health/db
# Expected: {"status":"healthy","database":"connected"}
```

### Verify Database Tables

1. Go to Railway → **Postgres service → "Data" tab**
2. You should see tables: `user`, `jobapplication`, `composerun`, `api_debug_log`, etc.

Or use psql:

```bash
# Using Railway CLI
railway connect postgres

# Or using psql directly
psql "postgresql://postgres:cFrOJOrnwXQfQKVUAnkNwPYPronyPyMq@ballast.proxy.rlwy.net:33607/railway?sslmode=require"

# List tables
\dt

# Check admin user
SELECT id, email, is_admin FROM "user";

# Exit
\q
```

### Test Login

1. Visit your Railway app URL (e.g., `https://myapply-production.up.railway.app`)
2. You should be redirected to `/auth/login`
3. Log in with: `Jt272004@gmail.com` / `09272004`

---

## Troubleshooting

### Database Connection Errors

If you see database connection errors:

1. **Check DATABASE_URL**: Ensure it's set correctly in Railway
   - Should be: `postgresql://postgres:cFrOJOrnwXQfQKVUAnkNwPYPronyPyMq@postgres.railway.internal:5432/railway`
   - **Use internal host** (`postgres.railway.internal`), not the proxy
   - No SSL required for internal connections

2. **Verify Postgres is running**: Check the Postgres service in Railway dashboard

3. **Check logs**: Railway → Your service → "Logs" tab

### Migration Errors

If migrations fail:

```bash
# Check current migration state
railway run alembic current

# If needed, reset to base
railway run alembic stamp 0001_create_base

# Run migrations again
railway run alembic upgrade head
```

### Admin User Issues

If admin login fails:

```bash
# Recreate admin user (script is idempotent)
railway run python scripts/init_admin.py "Jt272004@gmail.com" "09272004"
```

### View Application Logs

```bash
# Using Railway CLI
railway logs

# Or in Railway Dashboard
# Your service → "Logs" tab
```

---

## Update Deployment

To deploy new code:

```bash
# Commit and push to GitHub
git add .
git commit -m "Update: description"
git push origin main

# Railway auto-deploys on push
```

Or manually trigger:
- Railway Dashboard → Your service → **"Deploy"**

---

## Database Backups

Railway provides automatic backups for Postgres:

1. Go to Postgres service → **"Settings" → "Backups"**
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

## Security Checklist

- ✅ `SESSION_SECURE=true` (enforces HTTPS cookies)
- ✅ `ENV=production`
- ✅ Strong `SECRET_KEY` (don't use dev key in prod)
- ✅ Database uses internal Railway networking (no public access)
- ✅ Admin password is strong and secure
- ✅ API keys are properly secured in Railway environment variables
- ⚠️ **Never commit `.env` or secrets to git**

---

## Production Monitoring

### Health Checks

Railway automatically monitors `/health` endpoint.

View status:
- Railway Dashboard → Your service → **"Metrics"**

### Custom Alerts

Set up alerts in Railway:
1. Service → **"Settings" → "Alerts"**
2. Configure CPU, memory, or crash alerts

---

## Scaling

To scale your application:

1. Railway Dashboard → Your service → **"Settings" → "Deploy"**
2. Increase **"Replicas"** or **"Resources"**

**Note**: For database-heavy operations, consider:
- Connection pooling
- Read replicas (Railway Pro)
- Caching layer (Redis)

---

## Support

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Railway Discord**: [discord.gg/railway](https://discord.gg/railway)
- **MyApply Issues**: [github.com/yourrepo/issues](https://github.com/yourrepo/issues)

---

## Quick Reference Commands

```bash
# View logs
railway logs

# Run migrations
railway run alembic upgrade head

# Create admin
railway run python scripts/init_admin.py "email" "password"

# Connect to database
railway connect postgres

# Run any command
railway run <command>

# Deploy manually
railway up
```

---

**🎉 Deployment Complete!**

Your MyApply application is now running on Railway with PostgreSQL!

Visit your app at: `https://your-service-name.up.railway.app`
