#!/usr/bin/env python
"""
Database initialization script for MyApply.

This script creates all database tables and optionally creates an admin user.
Run this script before starting the application for the first time.

Usage:
    python scripts/init_db.py [--create-admin EMAIL PASSWORD]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, SQLModel, create_engine

from app import get_settings
from auth import create_admin_user
from models import ComposeRun, GraphEdge, GraphNode, User, UserGraph


def init_database(create_admin: bool = False, admin_email: str | None = None, admin_password: str | None = None) -> None:
    """Initialize the database and optionally create an admin user."""
    settings = get_settings()

    print("=" * 60)
    print("MyApply Database Initialization")
    print("=" * 60)
    print(f"\nDatabase URL: {settings.DATABASE_URL}")

    # Create engine
    connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, echo=False)

    # Create all tables
    print("\n📦 Creating database tables...")
    try:
        SQLModel.metadata.create_all(engine)
        print("✓ Tables created successfully:")
        print("  - users")
        print("  - nodes (graph nodes)")
        print("  - edges (graph edges)")
        print("  - usergraph (user graph snapshots)")
        print("  - composerun (generation history)")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        sys.exit(1)

    # Create admin user if requested
    if create_admin:
        if not admin_email or not admin_password:
            print("\n✗ Error: Both email and password required for admin creation")
            sys.exit(1)

        print(f"\n👤 Creating admin user: {admin_email}")
        try:
            with Session(engine) as session:
                user = create_admin_user(session, email=admin_email, password=admin_password)
                print(f"✓ Admin user created: {user.email} (ID: {user.id})")
        except Exception as e:
            print(f"✗ Error creating admin user: {e}")
            sys.exit(1)

    # Summary
    print("\n" + "=" * 60)
    print("✅ Database initialization complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Update your .env file with proper configuration")
    print("  2. Start the application: uvicorn app:app --reload")
    print("  3. Visit http://127.0.0.1:8000 to use MyApply")

    if not create_admin:
        print("\nTip: Create an admin user with:")
        print("  python scripts/create_admin.py <email> <password>")

    print()


def main() -> None:
    """Parse arguments and run initialization."""
    parser = argparse.ArgumentParser(
        description="Initialize MyApply database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create tables only
  python scripts/init_db.py

  # Create tables and admin user
  python scripts/init_db.py --create-admin admin@example.com SecurePass123!
        """
    )

    parser.add_argument(
        "--create-admin",
        nargs=2,
        metavar=("EMAIL", "PASSWORD"),
        help="Create an admin user with the specified email and password"
    )

    args = parser.parse_args()

    if args.create_admin:
        email, password = args.create_admin
        init_database(create_admin=True, admin_email=email, admin_password=password)
    else:
        init_database()


if __name__ == "__main__":
    main()
