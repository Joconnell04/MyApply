# Alembic Database Migrations Setup

This guide explains how to use Alembic for database migrations in the MyApply project.

## What is Alembic?

Alembic is a database migration tool for SQLAlchemy (which SQLModel is built on). It allows you to:

- Track database schema changes over time
- Apply and rollback migrations
- Maintain database version control
- Deploy schema changes safely to production

## Installation

Alembic and python-dotenv have been added to [requirements.txt](requirements.txt):

```bash
pip install -r requirements.txt
```

## Configuration Files

### 1. [alembic.ini](alembic.ini)

The main configuration file. Key settings:

```ini
# Database URL (overridden by DATABASE_URL in .env)
sqlalchemy.url = sqlite:///./myapply.db

# Migration scripts location
script_location = alembic
```

### 2. [alembic/env.py](alembic/env.py)

The environment configuration that:
- Imports your SQLModel models
- Loads DATABASE_URL from `.env`
- Sets up the target metadata for autogenerate

## Usage

### Check Current Migration Status

```bash
# Show current database revision
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

### Creating Migrations

#### Auto-generate from Model Changes

```bash
# Generate migration by comparing models to database
alembic revision --autogenerate -m "Description of changes"
```

This will:
1. Compare your SQLModel models with the current database schema
2. Generate a migration file in `alembic/versions/`
3. Include upgrade() and downgrade() functions

#### Manual Migration

```bash
# Create empty migration template
alembic revision -m "Description"
```

Then edit the generated file in `alembic/versions/` to add your migration logic.

### Applying Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply to a specific revision
alembic upgrade <revision_id>

# Apply one migration forward
alembic upgrade +1
```

### Rolling Back Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

## Current Setup Status

✅ Alembic is initialized and configured
✅ Environment configured to load models from SQLModel
✅ DATABASE_URL loaded from `.env`
✅ Initial migration created: `114dacbd1620_initial_migration.py`

### Initial Migration Details

The auto-generated migration detected type changes in the `user` table:
- `full_name`: TEXT → AutoString
- `home_lat`: REAL → Float
- `home_lng`: REAL → Float
- `mylife_json`: TEXT → JSON

**Note**: These changes were detected because the database already exists. For a fresh database, you would create tables from scratch.

## Workflow for New Features

### 1. Modify Your Models

Edit [models.py](models.py) to add/modify tables:

```python
# Example: Add a new field to User model
class User(SQLModel, table=True):
    # ... existing fields ...
    phone_number: Optional[str] = Field(default=None)  # New field
```

### 2. Generate Migration

```bash
alembic revision --autogenerate -m "Add phone_number to user"
```

### 3. Review Migration

Check the generated file in `alembic/versions/`:

```python
def upgrade() -> None:
    op.add_column('user', sa.Column('phone_number', sa.String(), nullable=True))

def downgrade() -> None:
    op.drop_column('user', 'phone_number')
```

### 4. Apply Migration

```bash
# Development
alembic upgrade head

# Production
alembic upgrade head  # After testing!
```

## Starting Fresh

If you want to start with a clean slate:

### Option 1: Reset Database (Development Only)

```bash
# Backup your data first!
rm myapply.db

# Create fresh database with current models
python -c "from app import engine; from sqlmodel import SQLModel; SQLModel.metadata.create_all(engine)"

# Mark as up-to-date with migrations
alembic stamp head
```

### Option 2: Create Initial Migration for Fresh Database

```bash
# Delete existing database
rm myapply.db

# Remove all migration files
rm alembic/versions/*.py

# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration to create tables
alembic upgrade head
```

## Best Practices

### 1. Always Review Auto-Generated Migrations

Alembic's autogenerate is smart but not perfect. Always review and test migrations before applying.

### 2. Test Migrations Both Ways

```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Test upgrade again
alembic upgrade head
```

### 3. Use Descriptive Messages

```bash
# Good
alembic revision --autogenerate -m "Add email verification fields to user table"

# Bad
alembic revision --autogenerate -m "Update"
```

### 4. One Logical Change Per Migration

Keep migrations focused on a single feature or change.

### 5. Never Modify Applied Migrations

Once a migration is applied (especially in production), never modify it. Create a new migration instead.

### 6. Backup Before Major Changes

```bash
# SQLite backup
cp myapply.db myapply.db.backup

# PostgreSQL backup
pg_dump myapply > backup.sql
```

## Common Operations

### Add a New Table

1. Add model to [models.py](models.py)
2. Run `alembic revision --autogenerate -m "Add new_table"`
3. Review the generated migration
4. Run `alembic upgrade head`

### Add a Column

1. Add field to existing model in [models.py](models.py)
2. Run `alembic revision --autogenerate -m "Add column_name to table_name"`
3. Review the generated migration
4. Run `alembic upgrade head`

### Rename a Column

Alembic can't auto-detect renames. Create a manual migration:

```bash
alembic revision -m "Rename old_name to new_name in table_name"
```

Edit the migration file:

```python
def upgrade() -> None:
    op.alter_column('table_name', 'old_name', new_column_name='new_name')

def downgrade() -> None:
    op.alter_column('table_name', 'new_name', new_column_name='old_name')
```

### Add an Index

```python
def upgrade() -> None:
    op.create_index('ix_user_email', 'user', ['email'])

def downgrade() -> None:
    op.drop_index('ix_user_email', 'user')
```

### Add a Foreign Key

```python
def upgrade() -> None:
    op.create_foreign_key(
        'fk_post_user_id',
        'post', 'user',
        ['user_id'], ['id']
    )

def downgrade() -> None:
    op.drop_constraint('fk_post_user_id', 'post')
```

## Troubleshooting

### "Can't locate revision identified by 'xyz'"

The database thinks it's at a revision that doesn't exist. Fix:

```bash
# Check current revision
alembic current

# Force set to a known good revision
alembic stamp <revision_id>

# Or start fresh
alembic stamp head
```

### "Target database is not up to date"

Apply pending migrations:

```bash
alembic upgrade head
```

### Migration Conflicts

If multiple developers create migrations:

```bash
# Merge migrations
alembic merge heads -m "Merge migrations"

# Or rebase your migration
alembic downgrade <base_revision>
# Delete your migration file
# Recreate with latest head as base
alembic revision --autogenerate -m "Your changes"
```

### SQLite Limitations

SQLite doesn't support many ALTER TABLE operations. Alembic handles this with batch operations, but some changes require table recreation.

## Deployment

### Production Deployment Steps

1. **Backup database**
   ```bash
   # Create backup
   pg_dump myapply_prod > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Test migrations locally**
   ```bash
   # Use production database copy
   alembic upgrade head
   ```

3. **Deploy code**
   ```bash
   git pull
   pip install -r requirements.txt
   ```

4. **Apply migrations**
   ```bash
   alembic upgrade head
   ```

5. **Restart application**
   ```bash
   systemctl restart myapply
   # or
   supervisorctl restart myapply
   ```

### Rollback Plan

Always have a rollback plan:

```bash
# Rollback migration
alembic downgrade -1

# Rollback code
git checkout <previous_commit>

# Restart application
systemctl restart myapply
```

## Integration with Application

### Startup Check (Optional)

You can add a startup check in [app.py](app.py) to ensure migrations are up-to-date:

```python
from alembic import command
from alembic.config import Config

@app.on_event("startup")
def check_migrations():
    alembic_cfg = Config("alembic.ini")
    command.check(alembic_cfg)  # Raises error if not up-to-date
```

### Auto-Migrate on Startup (Development Only)

```python
@app.on_event("startup")
def auto_migrate():
    if settings.ENV == "development":
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
```

⚠️ **Warning**: Never auto-migrate in production!

## Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Auto-generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [SQLModel with Alembic](https://sqlmodel.tiangolo.com/tutorial/create-db-and-table/)

## Next Steps

1. Review the generated initial migration
2. Apply migrations: `alembic upgrade head`
3. Check database state: `alembic current`
4. Make model changes and generate new migrations
5. Test the full migration workflow

The Alembic setup is now complete and ready for use!
