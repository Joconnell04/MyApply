# 🚀 Railway Production Deployment Checklist

Use this checklist to ensure a successful deployment to Railway.

---

## ✅ Pre-Deployment Checklist

### Code & Configuration

- [x] `requirements.txt` includes `psycopg2-binary` and `gunicorn`
- [x] `Dockerfile` created and tested
- [x] `.dockerignore` excludes unnecessary files
- [x] `railway.json` configuration file created
- [x] Database engine handles PostgreSQL with SSL
- [x] `/health` and `/health/db` endpoints added
- [x] Alembic migrations are up to date
- [x] `scripts/init_admin.py` created and tested
- [ ] All code committed to GitHub
- [ ] GitHub repository is accessible by Railway

### Environment Variables Prepared

- [x] `DATABASE_URL` (Railway Postgres internal URL)
- [x] `SECRET_KEY` ready
- [x] `OPENAI_API_KEY` ready
- [x] `ADMIN_EMAIL` and `ADMIN_PASSWORD` ready
- [x] `CHATKIT_DOMAIN` and `CHATKIT_DOMAIN_PUBLIC_KEY` ready
- [x] `MAPBOX_PUBLIC_TOKEN` and `MAPBOX_ACCESS_TOKEN` (if using maps)
- [x] `ALLOWED_ORIGINS` includes Railway domain

---

## 🎯 Deployment Steps

### 1. Create Railway Project

- [ ] Sign up/login to [railway.app](https://railway.app)
- [ ] Create new project from GitHub repo
- [ ] Railway detects Dockerfile automatically

### 2. Add PostgreSQL Database

- [ ] Click "+ New" → "Database" → "PostgreSQL"
- [ ] Verify `DATABASE_URL` is auto-set
- [ ] Confirm using internal URL: `postgres.railway.internal`

### 3. Configure Environment Variables

Set these in Railway service → Variables:

**Required:**
- [ ] `ENV=production`
- [ ] `PORT=8000`
- [ ] `DATABASE_URL` (should be auto-set)
- [ ] `SECRET_KEY` (from `.env`)
- [ ] `SESSION_SECURE=true`
- [ ] `SESSION_COOKIE_NAME=app_session`
- [ ] `SESSION_SAMESITE=lax`
- [ ] `OPENAI_API_KEY`
- [ ] `LLM_MODEL=gpt-4o-mini`
- [ ] `COVER_LETTER_MODEL=gpt-4o`
- [ ] `CHATKIT_DOMAIN=production.up.railway.app`
- [ ] `CHATKIT_DOMAIN_PUBLIC_KEY`
- [ ] `MYAPPLY_API_KEY`
- [ ] `ADMIN_EMAIL=Jt272004@gmail.com`
- [ ] `ADMIN_PASSWORD=09272004`

**Optional:**
- [ ] `MAPBOX_PUBLIC_TOKEN`
- [ ] `MAPBOX_ACCESS_TOKEN`
- [ ] `ALLOWED_ORIGINS` (add Railway domain)

### 4. First Deployment

- [ ] Railway auto-builds and deploys
- [ ] Wait for deployment to complete
- [ ] Check deployment logs for errors

### 5. Post-Deploy Setup

Run these commands **once** after first deployment:

```bash
# Option A: All-in-one script
railway run bash scripts/railway_deploy.sh

# Option B: Individual commands
railway run alembic upgrade head
railway run python scripts/init_admin.py "Jt272004@gmail.com" "09272004"
```

- [ ] Migrations completed successfully
- [ ] Admin user created

---

## ✅ Verification Checklist

### Health Checks

```bash
# Replace with your Railway domain
RAILWAY_DOMAIN="myapply-production.up.railway.app"
```

- [ ] Service health: `curl https://${RAILWAY_DOMAIN}/health`
  - Expected: `{"status":"healthy","service":"MyApply"}`

- [ ] Database health: `curl https://${RAILWAY_DOMAIN}/health/db`
  - Expected: `{"status":"healthy","database":"connected"}`

### Database Verification

- [ ] Connect to Postgres: `railway connect postgres`
- [ ] List tables: `\dt` shows all expected tables
- [ ] Check admin user: `SELECT * FROM "user" WHERE is_admin = true;`
- [ ] Check migration: `SELECT * FROM alembic_version;` shows `0001_create_base`

### Application Testing

- [ ] Visit Railway URL in browser
- [ ] Redirected to login page
- [ ] Login with admin credentials works
- [ ] Dashboard loads successfully
- [ ] Can create a test compose run
- [ ] Static files (favicon, CSS) load correctly

### Railway Dashboard Checks

- [ ] Service shows "Active" status
- [ ] No deployment errors in logs
- [ ] Metrics show healthy CPU/memory
- [ ] Health checks passing (green)

---

## 🔒 Security Verification

- [ ] `SESSION_SECURE=true` (HTTPS cookies only)
- [ ] `ENV=production`
- [ ] Admin password is strong and secure
- [ ] No secrets in git repository
- [ ] No secrets visible in logs
- [ ] CORS configured correctly
- [ ] Database uses internal Railway network (not public proxy)

---

## 📝 Post-Deployment Tasks

### Documentation

- [ ] Update Railway domain in documentation
- [ ] Share deployment URL with team
- [ ] Document any custom configuration

### Monitoring Setup

- [ ] Configure Railway alerts (Settings → Alerts)
- [ ] Set up error monitoring (optional: Sentry)
- [ ] Configure uptime monitoring (optional: UptimeRobot)

### Backup Strategy

- [ ] Enable Railway Postgres automatic backups
- [ ] Document backup/restore procedures
- [ ] Test backup restoration process

---

## 🎉 Success Criteria

Your deployment is successful when:

✅ All health checks return 200 OK
✅ Database connection works
✅ Admin login succeeds
✅ Application pages load correctly
✅ No errors in deployment logs
✅ Tables exist in Railway Postgres
✅ Environment variables are set correctly
✅ SSL/HTTPS works properly

---

## 📞 Troubleshooting

If something goes wrong, check:

1. **Deployment Logs**: Railway → Service → Logs tab
2. **Environment Variables**: Railway → Service → Variables tab
3. **Database Status**: Railway → Postgres service → Metrics
4. **Health Endpoints**: Use curl commands from verification checklist

Common issues:

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check logs, verify PORT is set to 8000 |
| Database connection failed | Verify DATABASE_URL uses `postgres.railway.internal` |
| Static files 404 | Ensure `static/` directory is included in Docker image |
| Login fails | Run `railway run python scripts/init_admin.py` again |
| CORS errors | Add Railway domain to ALLOWED_ORIGINS |

---

## 📚 Documentation Links

- **Deployment Guide**: [RAILWAY_DEPLOY.md](./RAILWAY_DEPLOY.md)
- **Verification Commands**: [VERIFICATION.md](./VERIFICATION.md)
- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **MyApply Setup**: [MVP_SETUP.md](./MVP_SETUP.md)

---

## 🔄 Update Deployment

For future updates:

```bash
# 1. Make changes to code
# 2. Commit and push
git add .
git commit -m "Update: description"
git push origin main

# 3. Railway auto-deploys

# 4. If database changes, run migrations
railway run alembic upgrade head
```

---

**Need Help?**
- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Railway Docs: [docs.railway.app](https://docs.railway.app)

---

**Deployment Date**: _____________________
**Railway Project URL**: _____________________
**Production URL**: _____________________
**Database**: Railway PostgreSQL
**Deployed By**: _____________________

✅ **Deployment Complete!**
