"""Cover letter helper routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..deps import get_rate_limiter_dependency, get_session
from ..schemas import CompanyInsightsRequest, CompanyInsightsResponse
from ..security import AuthContext, require_auth

router = APIRouter(prefix="/tools", tags=["Cover Letter"])


@router.post(
    "/get_company_insights",
    response_model=CompanyInsightsResponse,
)
def get_company_insights(
    payload: CompanyInsightsRequest,
    auth: AuthContext = Depends(require_auth),
    session: Session = Depends(get_session),
) -> CompanyInsightsResponse:
    """Return a stubbed list of company insights."""

    get_rate_limiter_dependency(auth.user_id)
    del session  # Placeholder for future data sources.
    insights = [
        f"{payload.company_name} emphasizes customer-centric innovation.",
        f"Recent initiatives at {payload.company_name} focus on sustainable operations.",
        f"{payload.company_name} highlights cross-functional collaboration in quarterly briefings.",
    ][: payload.limit]
    return CompanyInsightsResponse(company_name=payload.company_name, insights=insights)
