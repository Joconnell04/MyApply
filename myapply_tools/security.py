"""Security utilities enforcing request authentication."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from .deps import Settings, settings


@dataclass
class AuthContext:
    """Authenticated request context."""

    user_id: str


def require_auth(
    authorization: str = Header(default="", convert_underscores=False),
    user_id_header: str = Header(default="", alias="X-MyApply-User"),
    app_settings: Settings = Depends(lambda: settings),
) -> AuthContext:
    """Validate authorization headers and return the authenticated user context."""

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")
    if not user_id_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-MyApply-User header.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme.")
    if token != app_settings.myapply_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    return AuthContext(user_id=user_id_header)
