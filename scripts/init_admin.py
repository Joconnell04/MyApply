#!/usr/bin/env python
"""
Initialize admin user if it doesn't exist.
Idempotent - safe to run multiple times.

Usage:
    python scripts/init_admin.py <email> <password>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import from the app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, SQLModel, create_engine, select

from app import get_settings
from auth import hash_password
from models import User


def init_admin(email: str, password: str) -> None:
    """Create admin user if it doesn't exist."""
    settings = get_settings()

    # Determine connect_args based on database type
    connect_args = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif "proxy.rlwy.net" in settings.DATABASE_URL:
        connect_args = {"sslmode": "require"}

    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

    # Ensure tables exist
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Check if user already exists
        statement = select(User).where(User.email == email)
        existing_user = session.exec(statement).first()

        if existing_user:
            print(f"✓ Admin user {email} already exists (id={existing_user.id})")
            # Update to ensure they're admin
            if not existing_user.is_admin:
                existing_user.is_admin = True
                session.add(existing_user)
                session.commit()
                print(f"✓ Updated {email} to admin")
            return

        # Create new admin user
        password_hash = hash_password(password)
        admin_user = User(
            email=email,
            password_hash=password_hash,
            is_admin=True,
        )
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)

        print(f"✓ Created admin user: {admin_user.email} (id={admin_user.id})")


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/init_admin.py <email> <password>")
        print("\nExample:")
        print('  python scripts/init_admin.py admin@example.com "MySecurePassword123"')
        sys.exit(1)

    email, password = sys.argv[1], sys.argv[2]

    # Validate inputs
    if not email or "@" not in email:
        print("Error: Invalid email address")
        sys.exit(1)

    if not password or len(password) < 8:
        print("Error: Password must be at least 8 characters")
        sys.exit(1)

    try:
        init_admin(email, password)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
