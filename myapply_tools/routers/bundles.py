"""Bundle-related API routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from .. import storage
from ..deps import get_rate_limiter_dependency, get_session
from ..models import BundleKind
from ..schemas import (
    BundleAck,
    BundlePayload,
    BundleResponse,
    GetBundleRequest,
    SetCoverLetterBundleRequest,
    SetGenerationBundleRequest,
)
from ..security import AuthContext, require_auth

router = APIRouter(prefix="/tools", tags=["Bundles"])


def _validate_user(auth: AuthContext, user_id: str) -> None:
    """Ensure the authenticated user matches the payload."""

    if auth.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User mismatch.")


def _bundle_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize bundle payload."""

    return body


@router.post(
    "/set_generation_bundle",
    response_model=BundleAck,
    status_code=status.HTTP_200_OK,
)
def set_generation_bundle(
    payload: SetGenerationBundleRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> BundleAck:
    """Upsert the resume-generation bundle."""

    _validate_user(auth, payload.user_id)
    get_rate_limiter_dependency(auth.user_id)
    try:
        storage.upsert_bundle(
            session,
            kind=BundleKind.RESUME,
            user_id=payload.user_id,
            hash_value=payload.hash,
            payload=_bundle_payload(
                {
                    "plan": payload.plan,
                    "resolved_jd": payload.resolved_jd,
                    "prefs": payload.prefs,
                },
            ),
            ttl_seconds=payload.ttl_seconds,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bundle conflict.") from exc
    return BundleAck()


@router.post(
    "/get_generation_bundle",
    response_model=BundleResponse,
    status_code=status.HTTP_200_OK,
)
def get_generation_bundle(
    payload: GetBundleRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> BundleResponse:
    """Fetch the resume-generation bundle."""

    _validate_user(auth, payload.user_id)
    get_rate_limiter_dependency(auth.user_id)
    record = storage.get_bundle(
        session,
        kind=BundleKind.RESUME,
        user_id=payload.user_id,
        hash_value=payload.hash,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found.")
    return BundleResponse(
        ok=True,
        bundle=BundlePayload(
            user_id=record.user_id,
            hash=record.hash,
            kind=record.kind,
            payload=record.payload,
            ttl_seconds=record.ttl_seconds,
        ),
    )


@router.post(
    "/set_cl_bundle",
    response_model=BundleAck,
    status_code=status.HTTP_200_OK,
)
def set_cover_letter_bundle(
    payload: SetCoverLetterBundleRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> BundleAck:
    """Upsert the cover-letter bundle."""

    _validate_user(auth, payload.user_id)
    get_rate_limiter_dependency(auth.user_id)
    try:
        storage.upsert_bundle(
            session,
            kind=BundleKind.COVER_LETTER,
            user_id=payload.user_id,
            hash_value=payload.hash,
            payload=_bundle_payload(
                {
                    "jd": payload.jd,
                    "story_plan": payload.story_plan,
                    "prefs": payload.prefs,
                },
            ),
            ttl_seconds=payload.ttl_seconds,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bundle conflict.") from exc
    return BundleAck()


@router.post(
    "/get_cl_bundle",
    response_model=BundleResponse,
    status_code=status.HTTP_200_OK,
)
def get_cover_letter_bundle(
    payload: GetBundleRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> BundleResponse:
    """Fetch the cover-letter bundle."""

    _validate_user(auth, payload.user_id)
    get_rate_limiter_dependency(auth.user_id)
    record = storage.get_bundle(
        session,
        kind=BundleKind.COVER_LETTER,
        user_id=payload.user_id,
        hash_value=payload.hash,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found.")
    return BundleResponse(
        ok=True,
        bundle=BundlePayload(
            user_id=record.user_id,
            hash=record.hash,
            kind=record.kind,
            payload=record.payload,
            ttl_seconds=record.ttl_seconds,
        ),
    )
