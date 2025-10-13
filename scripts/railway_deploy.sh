#!/bin/bash
# Railway deployment post-deploy script
# Run migrations and initialize admin user

set -e  # Exit on error

echo "🚀 Starting Railway post-deploy tasks..."

# Run database migrations
echo "📦 Running database migrations..."
alembic upgrade head

# Initialize admin user (idempotent - safe to run multiple times)
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "👤 Initializing admin user..."
    python scripts/init_admin.py "$ADMIN_EMAIL" "$ADMIN_PASSWORD"
else
    echo "⚠️  Warning: ADMIN_EMAIL and ADMIN_PASSWORD not set, skipping admin creation"
fi

echo "✅ Post-deploy tasks completed successfully!"
