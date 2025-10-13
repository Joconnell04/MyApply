from __future__ import annotations

import sys

from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app import get_settings
from auth import create_admin_user


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_admin.py <email> <password>")
        sys.exit(1)

    email, password = sys.argv[1], sys.argv[2]
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        try:
            user = create_admin_user(
                session,
                email=email,
                password=password,
                enforce_password_strength=False,
            )
        except HTTPException as exc:
            print(f"Error: {exc.detail}")
            sys.exit(1)

    print(f"Admin user created for {user.email}")


if __name__ == "__main__":
    main()
