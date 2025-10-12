# SQLModel Setup Guide

This document provides instructions for setting up and working with SQLModel in the MyApply application.

## Overview

MyApply uses **SQLModel** - a modern Python library that combines SQLAlchemy and Pydantic for database operations. SQLModel provides:

- Type hints and validation via Pydantic
- Async support and database migrations
- Simple ORM interface
- FastAPI integration

## Installation

SQLModel is already included in [requirements.txt](requirements.txt):

```bash
pip install -r requirements.txt
```

This installs:
- `sqlmodel` - The main library
- `fastapi` - Web framework
- `sqlalchemy` - Underlying ORM (installed as sqlmodel dependency)

## Database Configuration

### Environment Variables

Configure your database connection in `.env`:

```bash
# SQLite (default for development)
DATABASE_URL=sqlite:///./myapply.db

# PostgreSQL (recommended for production)
DATABASE_URL=postgresql://user:password@localhost:5432/myapply

# PostgreSQL with asyncpg
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/myapply
```

### Database Engine Setup

The database engine is configured in [app.py](app.py:99-100):

```python
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
```

## Database Models

All SQLModel models are defined in [models.py](models.py). Here's the structure:

### Core Models

1. **User** ([models.py:19](models.py#L19)) - User accounts and authentication
2. **GraphNode** ([models.py:36](models.py#L36)) - Knowledge graph nodes
3. **GraphEdge** ([models.py:63](models.py#L63)) - Knowledge graph edges
4. **UserGraph** ([models.py:93](models.py#L93)) - Legacy serialized graph snapshots (UI now writes to `User.mylife_json`)
5. **ComposeRun** ([models.py:102](models.py#L102)) - Resume/cover letter generation runs
6. **JobApplied** ([models.py:142](models.py#L142)) - Job applications
7. **JobLocation** ([models.py:157](models.py#L157)) - Job location data
8. **WorkflowRun** ([models.py:166](models.py#L166)) - AgentKit workflow execution metadata
9. **Artifact** ([models.py:191](models.py#L191)) - Workflow output artifacts

### Model Example

```python
from sqlmodel import Field, SQLModel
from typing import Optional
from datetime import datetime

class User(SQLModel, table=True):
    __table_args__ = (Index("ix_user_email_unique", "email", unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    email: EmailStr = Field(index=True, nullable=False, sa_column_kwargs={"unique": True})
    password_hash: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    is_admin: bool = Field(default=False, nullable=False)
```

## Database Initialization

### Application Startup

Tables are automatically created on application startup via the `on_startup` event ([app.py:471-474](app.py#L471-L474)):

```python
@app.on_event("startup")
def on_startup() -> None:
    _ensure_user_profile_columns()
    SQLModel.metadata.create_all(engine)
```

### Manual Database Setup

To manually initialize the database:

```python
from sqlmodel import SQLModel, create_engine
from models import *  # Import all models

engine = create_engine("sqlite:///./myapply.db")
SQLModel.metadata.create_all(engine)
```

### Database Migrations

✅ **Alembic is configured and ready to use!** See [ALEMBIC_SETUP.md](ALEMBIC_SETUP.md) for detailed instructions.

```bash
# Create a migration (auto-generate from model changes)
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migrations
alembic downgrade -1

# Check current migration status
alembic current
```

**Important**: Always review auto-generated migrations before applying them!

## Database Operations

### Creating a Session

Use the `get_session` dependency ([app.py:334-336](app.py#L334-L336)):

```python
from sqlmodel import Session
from app import engine

def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
```

### CRUD Operations

#### Create

```python
from sqlmodel import Session, select
from models import User

with Session(engine) as session:
    user = User(
        email="user@example.com",
        password_hash="hashed_password",
    )
    session.add(user)
    session.commit()
    session.refresh(user)  # Get the auto-generated ID
```

#### Read

```python
# Get by ID
with Session(engine) as session:
    user = session.get(User, user_id)

# Query with filters
with Session(engine) as session:
    statement = select(User).where(User.email == "user@example.com")
    user = session.exec(statement).first()

# Get all
with Session(engine) as session:
    statement = select(User)
    users = session.exec(statement).all()
```

#### Update

```python
with Session(engine) as session:
    user = session.get(User, user_id)
    user.full_name = "New Name"
    session.add(user)
    session.commit()
```

#### Delete

```python
with Session(engine) as session:
    user = session.get(User, user_id)
    session.delete(user)
    session.commit()
```

### Using in FastAPI Routes

```python
from fastapi import Depends
from sqlmodel import Session

@app.get("/api/users/{user_id}")
def get_user(
    user_id: int,
    session: Session = Depends(get_session)
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

## Testing

### Test Database Setup

Tests use a separate SQLite database created in a temporary directory. The setup is in [tests/conftest.py](tests/conftest.py):

```python
@pytest.fixture
def app_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "myapply_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # Clear metadata to avoid conflicts
    SQLModel.metadata.clear()

    # Import app and create tables
    app_module = importlib.import_module("app")
    SQLModel.metadata.create_all(app_module.engine)

    return app_module
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth_flow.py

# Run with verbose output
pytest -v
```

## Common Patterns

### JSON Fields

Store complex data structures in JSON columns:

```python
from sqlalchemy import Column
from sqlalchemy.types import JSON
from typing import Dict, Any

class ComposeRun(SQLModel, table=True):
    jd_factors: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    options: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
```

### Indexes

Add indexes for frequently queried fields:

```python
from sqlalchemy import Index

class WorkflowRun(SQLModel, table=True):
    __table_args__ = (
        Index("ix_workflow_run_user_created", "user_id", "created_at"),
        Index("ix_workflow_run_workflow_id", "workflow_id"),
    )
```

### Foreign Keys

Define relationships between tables:

```python
class JobApplied(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)

class JobLocation(SQLModel, table=True):
    job_id: str = Field(foreign_key="jobapplied.id", index=True, nullable=False)
```

### Timestamps

Use `default_factory` for automatic timestamps:

```python
from datetime import datetime, timezone

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(SQLModel, table=True):
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
```

## Troubleshooting

### "Table already exists" Error

Clear the metadata before creating tables:

```python
SQLModel.metadata.clear()
SQLModel.metadata.create_all(engine)
```

### "No such table" Error

Ensure tables are created before running queries:

```python
SQLModel.metadata.create_all(engine)
```

### "Index already exists" Error

This happens when metadata isn't properly cleared between test runs. The fix is in [tests/conftest.py](tests/conftest.py:26).

### Database Locked Error (SQLite)

Add `check_same_thread=False` for SQLite:

```python
connect_args = {"check_same_thread": False}
engine = create_engine("sqlite:///./myapply.db", connect_args=connect_args)
```

## Best Practices

1. **Use Sessions properly** - Always use context managers or dependency injection
2. **Commit transactions** - Don't forget to call `session.commit()` after modifications
3. **Refresh after commit** - Call `session.refresh(obj)` to get auto-generated values
4. **Use indexes** - Add indexes on frequently queried columns
5. **Validate input** - Use Pydantic models for request validation
6. **Handle errors** - Catch `SQLAlchemyError` exceptions
7. **Use migrations** - For production, use Alembic for schema changes
8. **Separate test databases** - Never run tests against production databases

## Resources

- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Database Documentation](https://fastapi.tiangolo.com/tutorial/sql-databases/)

## Next Steps

1. Review the models in [models.py](models.py)
2. Check the database operations in [app.py](app.py)
3. Run tests to verify setup: `pytest`
4. Set up database migrations with Alembic (optional, for production)
