# Production Verification Commands

Quick reference for verifying your Railway deployment.

---

## Database Connection Verification

### Using psql (Public Proxy)

```bash
# Connect via public proxy (requires SSL)
psql "postgresql://postgres:cFrOJOrnwXQfQKVUAnkNwPYPronyPyMq@ballast.proxy.rlwy.net:33607/railway?sslmode=require"
```

### Using Railway CLI

```bash
# Connect to Postgres via Railway
railway connect postgres
```

### Verify Tables Exist

```sql
-- List all tables
\dt

-- Check specific tables
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Verify admin user
SELECT id, email, is_admin, created_at FROM "user" WHERE is_admin = true;

-- Check alembic version
SELECT * FROM alembic_version;

-- Exit
\q
```

---

## Health Check Endpoints

### Basic Health Check

```bash
# Replace with your Railway domain
RAILWAY_DOMAIN="myapply-production.up.railway.app"

curl https://${RAILWAY_DOMAIN}/health
# Expected: {"status":"healthy","service":"MyApply"}
```

### Database Health Check

```bash
curl https://${RAILWAY_DOMAIN}/health/db
# Expected: {"status":"healthy","database":"connected"}
```

### With Response Codes

```bash
# Check HTTP status
curl -w "\nHTTP Status: %{http_code}\n" https://${RAILWAY_DOMAIN}/health
curl -w "\nHTTP Status: %{http_code}\n" https://${RAILWAY_DOMAIN}/health/db
```

---

## Application Verification

### Test Login Page

```bash
# Should return HTML with login form
curl https://${RAILWAY_DOMAIN}/auth/login
```

### Test Static Files

```bash
# Should redirect to static favicon
curl -I https://${RAILWAY_DOMAIN}/favicon.ico
```

### Test API Endpoint

```bash
# Should return 401 Unauthorized (auth required)
curl https://${RAILWAY_DOMAIN}/api/profile
```

---

## Railway CLI Commands

### View Logs

```bash
# Real-time logs
railway logs

# Follow logs
railway logs --follow

# Last 100 lines
railway logs --lines 100
```

### Check Service Status

```bash
# Show service info
railway status

# List all services
railway list
```

### Run Commands in Production

```bash
# Check Python version
railway run python --version

# Check installed packages
railway run pip list

# Run health check locally against production DB
railway run python -c "from app import engine; print(engine.url)"

# Test database connection
railway run python -c "from app import engine, Session; from sqlmodel import select; session = Session(engine); print('DB Connected:', session.exec(select(1)).first())"
```

---

## Database Queries

### Check User Count

```bash
railway run python -c "
from app import engine, Session
from models import User
from sqlmodel import select, func

session = Session(engine)
count = session.exec(select(func.count(User.id))).first()
print(f'Total users: {count}')
"
```

### List All Users

```bash
railway run python -c "
from app import engine, Session
from models import User
from sqlmodel import select

session = Session(engine)
users = session.exec(select(User)).all()
for user in users:
    print(f'{user.id}: {user.email} (admin={user.is_admin})')
"
```

### Check ComposeRun Count

```bash
railway run python -c "
from app import engine, Session
from models import ComposeRun
from sqlmodel import select, func

session = Session(engine)
count = session.exec(select(func.count(ComposeRun.id))).first()
print(f'Total compose runs: {count}')
"
```

---

## Environment Variable Verification

### Check Current Variables

```bash
# Using Railway CLI
railway variables

# Check specific variable (sanitized output)
railway run sh -c 'echo "ENV=$ENV"'
railway run sh -c 'echo "PORT=$PORT"'
railway run sh -c 'echo "DATABASE_URL=postgresql://...${DATABASE_URL##*@}"'  # Shows only host
```

### Verify Settings in Code

```bash
railway run python -c "
from app import settings
print(f'ENV: {settings.ENV}')
print(f'PORT: {settings.PORT}')
print(f'DB: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'SQLite'}')
print(f'SESSION_SECURE: {settings.SESSION_SECURE}')
"
```

---

## Migration Verification

### Check Current Migration

```bash
railway run alembic current
# Expected: 0001_create_base (head)
```

### View Migration History

```bash
railway run alembic history
```

### Verify Migration in Database

```bash
railway run python -c "
from app import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT version_num FROM alembic_version')).fetchone()
    print(f'Current migration: {result[0] if result else \"None\"}')
"
```

---

## Performance Checks

### Response Time Test

```bash
# Test health endpoint response time
time curl -s https://${RAILWAY_DOMAIN}/health > /dev/null

# Test with timing details
curl -w "DNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTotal: %{time_total}s\n" \
     -o /dev/null -s https://${RAILWAY_DOMAIN}/health
```

### Load Test (Optional)

```bash
# Simple load test with Apache Bench (if installed)
ab -n 100 -c 10 https://${RAILWAY_DOMAIN}/health

# Or with curl in a loop
for i in {1..10}; do
    curl -s https://${RAILWAY_DOMAIN}/health > /dev/null && echo "Request $i: OK"
done
```

---

## Security Verification

### Check HTTPS Redirect

```bash
# Should redirect to HTTPS (if configured)
curl -I http://${RAILWAY_DOMAIN}/
```

### Check Security Headers

```bash
curl -I https://${RAILWAY_DOMAIN}/ | grep -i "strict-transport\|x-frame\|x-content"
```

### Verify Session Cookie Settings

```bash
# Login and check cookie attributes
curl -c cookies.txt -X POST https://${RAILWAY_DOMAIN}/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "email=test@example.com&password=test"

cat cookies.txt | grep -i "secure\|httponly"
```

---

## Troubleshooting Commands

### Check if Service is Running

```bash
# Should return 200
curl -I https://${RAILWAY_DOMAIN}/health

# Check DNS resolution
nslookup ${RAILWAY_DOMAIN}
```

### Test Database Connection Directly

```bash
# Test from Railway service
railway run python -c "
import sys
from sqlalchemy import create_engine, text
from app import settings

try:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1')).fetchone()
        print('✓ Database connection successful')
        print(f'Result: {result[0]}')
except Exception as e:
    print(f'✗ Database connection failed: {e}')
    sys.exit(1)
"
```

### Check for Errors in Logs

```bash
# Filter for errors
railway logs | grep -i error

# Filter for warnings
railway logs | grep -i warn

# Show only last errors
railway logs --lines 100 | grep -i "error\|exception\|traceback"
```

---

## Quick Success Verification

Run this complete verification script:

```bash
#!/bin/bash
RAILWAY_DOMAIN="myapply-production.up.railway.app"

echo "🔍 Verifying MyApply deployment..."
echo ""

echo "1. Health Check..."
curl -s https://${RAILWAY_DOMAIN}/health | grep -q "healthy" && echo "   ✓ Service is healthy" || echo "   ✗ Health check failed"

echo "2. Database Check..."
curl -s https://${RAILWAY_DOMAIN}/health/db | grep -q "connected" && echo "   ✓ Database is connected" || echo "   ✗ Database connection failed"

echo "3. Login Page..."
curl -s https://${RAILWAY_DOMAIN}/auth/login | grep -q "login" && echo "   ✓ Login page accessible" || echo "   ✗ Login page not found"

echo "4. Railway Service..."
railway status > /dev/null 2>&1 && echo "   ✓ Railway CLI connected" || echo "   ℹ Railway CLI not configured"

echo ""
echo "✅ Verification complete!"
```

---

## Emergency Commands

### Restart Service

```bash
# Using Railway CLI
railway restart

# Or in dashboard: Service → Settings → Restart
```

### Rollback Deployment

```bash
# View deployment history
railway deployments

# Rollback to previous
railway rollback
```

### Reset Database (⚠️ DESTRUCTIVE)

```bash
# Drop all tables and recreate
railway run python -c "
from app import engine
from sqlmodel import SQLModel
SQLModel.metadata.drop_all(engine)
SQLModel.metadata.create_all(engine)
print('Database reset complete')
"

# Then re-run migrations
railway run alembic stamp 0001_create_base
railway run alembic upgrade head
railway run python scripts/init_admin.py "Jt272004@gmail.com" "09272004"
```

---

## Additional Resources

- **Railway Dashboard**: [railway.app/dashboard](https://railway.app/dashboard)
- **Logs**: Service → Logs tab
- **Metrics**: Service → Metrics tab
- **Database Data**: Postgres service → Data tab
- **Environment Variables**: Service → Variables tab

---

**Quick Link**: [Railway Deployment Guide](./RAILWAY_DEPLOY.md)
