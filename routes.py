"""
REST API routes for AgentKit workflow integration.

This module exposes minimal REST endpoints for the MyApply UI and implements
the orchestration layer that coordinates workflow calls. The backend acts as
the conductor, passing outputs from one workflow as explicit inputs to another.

IMPORTANT: Workflows do NOT call each other. All cross-workflow communication
happens in this backend orchestration layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from agentkit import run_workflow
from app import get_session, require_user
from models import Artifact, User, WorkflowRun, utc_now


# Workflow configuration constants
WORKFLOW_INTENT_ROUTER = {
    "id": "wf_68e8215242b881909e95dda286109e500a969132ff1ebcdb",
    "version": "2",
}

WORKFLOW_JD_TO_STRUCTURED = {
    "id": "wf_68e80e14fad48190a83d85460325ba7f072fbeb74efb9546",
    "version": "4",
}

WORKFLOW_RESUME_BUILDER = {
    "id": "wf_68e969c7da408190b3d046774e86e50700467750faf0f87a",
    "version": "4",
}

router = APIRouter(prefix="/api", tags=["agentkit"])


# Request/Response models
class IntentRouteRequest(BaseModel):
    """Request model for intent routing."""
    user_id: str
    choice: str = Field(..., pattern="^(resume|cover_letter|both)$")
    jd_text: Optional[str] = None

    model_config = {"extra": "forbid"}


class JDStructureRequest(BaseModel):
    """Request model for job description structuring."""
    user_id: str
    jd_text: str = Field(..., min_length=1, max_length=50000)

    model_config = {"extra": "forbid"}


class ResumeBuildRequest(BaseModel):
    """Request model for resume building."""
    user_id: str
    jd_structured: Optional[Dict[str, Any]] = None
    jd_text: Optional[str] = Field(None, max_length=50000)
    target_role: Optional[str] = Field(None, max_length=200)

    model_config = {"extra": "forbid"}


def _persist_workflow_run(
    session: Session,
    user_id: int,
    workflow_id: str,
    version: str,
    input_json: Dict[str, Any],
    output_json: Dict[str, Any],
    status_val: str = "success",
) -> WorkflowRun:
    """
    Persist a workflow run to the database.

    Args:
        session: Database session
        user_id: User ID who initiated the run
        workflow_id: AgentKit workflow ID
        version: Workflow version
        input_json: Input variables passed to the workflow
        output_json: Output returned by the workflow
        status_val: Run status ("success", "error", "invalid")

    Returns:
        The persisted WorkflowRun instance
    """
    now = utc_now()
    run = WorkflowRun(
        workflow_id=workflow_id,
        version=version,
        status=status_val,
        user_id=user_id,
        input_json=input_json,
        output_json=output_json,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _persist_artifact(
    session: Session,
    run_id: str,
    kind: str,
    payload_json: Dict[str, Any],
    label: Optional[str] = None,
) -> Artifact:
    """
    Persist a workflow artifact to the database.

    Args:
        session: Database session
        run_id: ID of the parent WorkflowRun
        kind: Artifact type (e.g., "structured_jd", "resume_bullets")
        payload_json: Artifact data
        label: Optional human-readable label

    Returns:
        The persisted Artifact instance
    """
    artifact = Artifact(
        run_id=run_id,
        kind=kind,
        label=label,
        payload_json=payload_json,
        created_at=utc_now(),
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


@router.post("/intent/route")
def api_intent_route(
    payload: IntentRouteRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Route user intent based on their document choice.

    Calls the Intent_Routerv0 workflow to determine the next steps based on
    whether the user wants to generate a resume, cover letter, or both.

    Args:
        payload: Request containing user_id, choice, and optional jd_text
        current_user: Authenticated user
        session: Database session

    Returns:
        Dict containing router result with routing decision
    """
    # Prepare workflow input
    input_vars = {
        "user_id": payload.user_id,
        "choice": payload.choice,
        "jd_present": bool(payload.jd_text and payload.jd_text.strip()),
    }

    try:
        # Call the Intent Router workflow
        result = run_workflow(
            workflow_id=WORKFLOW_INTENT_ROUTER["id"],
            version=WORKFLOW_INTENT_ROUTER["version"],
            input_vars=input_vars,
        )

        # Persist the run
        run = _persist_workflow_run(
            session=session,
            user_id=current_user.id,
            workflow_id=WORKFLOW_INTENT_ROUTER["id"],
            version=WORKFLOW_INTENT_ROUTER["version"],
            input_json=input_vars,
            output_json=result,
            status_val="success",
        )

        return {
            "ok": True,
            "run_id": run.id,
            "result": result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        # Persist failed run
        _persist_workflow_run(
            session=session,
            user_id=current_user.id,
            workflow_id=WORKFLOW_INTENT_ROUTER["id"],
            version=WORKFLOW_INTENT_ROUTER["version"],
            input_json=input_vars,
            output_json={"error": str(exc)},
            status_val="error",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Intent routing failed: {str(exc)}",
        ) from exc


@router.post("/jd/structure")
def api_jd_structure(
    payload: JDStructureRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Structure a job description into a standardized format.

    Calls the JD_to_StructuredJD_v0 workflow to parse and structure a raw
    job description. The structured output is persisted as an artifact.

    Args:
        payload: Request containing user_id and jd_text
        current_user: Authenticated user
        session: Database session

    Returns:
        Dict containing structured job description and run_id
    """
    # Prepare workflow input
    input_vars = {
        "user_id": payload.user_id,
        "jd_text": payload.jd_text,
    }

    try:
        # Call the JD structuring workflow
        result = run_workflow(
            workflow_id=WORKFLOW_JD_TO_STRUCTURED["id"],
            version=WORKFLOW_JD_TO_STRUCTURED["version"],
            input_vars=input_vars,
        )

        # Persist the run
        run = _persist_workflow_run(
            session=session,
            user_id=current_user.id,
            workflow_id=WORKFLOW_JD_TO_STRUCTURED["id"],
            version=WORKFLOW_JD_TO_STRUCTURED["version"],
            input_json=input_vars,
            output_json=result,
            status_val="success",
        )

        # Extract and persist the structured JD as an artifact
        structured_jd = result.get("output_parsed", {})
        if structured_jd:
            _persist_artifact(
                session=session,
                run_id=run.id,
                kind="structured_jd",
                label="Structured Job Description",
                payload_json=structured_jd,
            )

        return {
            "ok": True,
            "run_id": run.id,
            "structured_jd": structured_jd,
        }

    except HTTPException:
        raise
    except Exception as exc:
        # Persist failed run
        _persist_workflow_run(
            session=session,
            user_id=current_user.id,
            workflow_id=WORKFLOW_JD_TO_STRUCTURED["id"],
            version=WORKFLOW_JD_TO_STRUCTURED["version"],
            input_json=input_vars,
            output_json={"error": str(exc)},
            status_val="error",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JD structuring failed: {str(exc)}",
        ) from exc


@router.post("/resume/build")
def api_resume_build(
    payload: ResumeBuildRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Build a tailored resume using the Resume Builder workflow.

    This endpoint implements orchestration logic: if jd_structured is not
    provided but jd_text is, it first calls the JD structuring workflow,
    then passes the result to the Resume Builder workflow.

    Args:
        payload: Request containing user_id, optional jd_structured, jd_text, target_role
        current_user: Authenticated user
        session: Database session

    Returns:
        Dict containing resume builder output and run_id(s)
    """
    jd_structured = payload.jd_structured
    jd_structure_run_id: Optional[str] = None

    # ORCHESTRATION STEP 1: Structure the JD if needed
    if not jd_structured and payload.jd_text:
        # Call the JD structuring workflow first
        try:
            jd_input = {
                "user_id": payload.user_id,
                "jd_text": payload.jd_text,
            }

            jd_result = run_workflow(
                workflow_id=WORKFLOW_JD_TO_STRUCTURED["id"],
                version=WORKFLOW_JD_TO_STRUCTURED["version"],
                input_vars=jd_input,
            )

            # Persist the JD structuring run
            jd_run = _persist_workflow_run(
                session=session,
                user_id=current_user.id,
                workflow_id=WORKFLOW_JD_TO_STRUCTURED["id"],
                version=WORKFLOW_JD_TO_STRUCTURED["version"],
                input_json=jd_input,
                output_json=jd_result,
                status_val="success",
            )
            jd_structure_run_id = jd_run.id

            # Extract the structured JD for the next step
            jd_structured = jd_result.get("output_parsed", {})

            # Persist as artifact
            if jd_structured:
                _persist_artifact(
                    session=session,
                    run_id=jd_run.id,
                    kind="structured_jd",
                    label="Structured JD (from orchestration)",
                    payload_json=jd_structured,
                )

        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"JD structuring (orchestration step) failed: {str(exc)}",
            ) from exc

    # Validate we have structured JD data
    if not jd_structured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either jd_structured or jd_text must be provided.",
        )

    # ORCHESTRATION STEP 2: Build the resume
    resume_input = {
        "user_id": payload.user_id,
        "jd_structured": jd_structured,
        "target_role": payload.target_role or jd_structured.get("title", ""),
    }

    try:
        # Call the Resume Builder workflow
        resume_result = run_workflow(
            workflow_id=WORKFLOW_RESUME_BUILDER["id"],
            version=WORKFLOW_RESUME_BUILDER["version"],
            input_vars=resume_input,
        )

        # Persist the resume building run
        resume_run = _persist_workflow_run(
            session=session,
            user_id=current_user.id,
            workflow_id=WORKFLOW_RESUME_BUILDER["id"],
            version=WORKFLOW_RESUME_BUILDER["version"],
            input_json=resume_input,
            output_json=resume_result,
            status_val="success",
        )

        # Extract and persist artifacts
        output_parsed = resume_result.get("output_parsed", {})

        # Persist resume sections as artifacts
        if "experience" in output_parsed:
            _persist_artifact(
                session=session,
                run_id=resume_run.id,
                kind="resume_experience",
                label="Resume Experience Section",
                payload_json={"experience": output_parsed["experience"]},
            )

        if "skills" in output_parsed:
            _persist_artifact(
                session=session,
                run_id=resume_run.id,
                kind="resume_skills",
                label="Resume Skills",
                payload_json={"skills": output_parsed["skills"]},
            )

        # Build response
        response = {
            "ok": True,
            "resume_run_id": resume_run.id,
            "resume_bundle": resume_result,
        }

        # Include JD structuring info if it was part of orchestration
        if jd_structure_run_id:
            response["jd_structure_run_id"] = jd_structure_run_id
            response["structured_jd"] = jd_structured

        return response

    except HTTPException:
        raise
    except Exception as exc:
        # Persist failed run
        _persist_workflow_run(
            session=session,
            user_id=current_user.id,
            workflow_id=WORKFLOW_RESUME_BUILDER["id"],
            version=WORKFLOW_RESUME_BUILDER["version"],
            input_json=resume_input,
            output_json={"error": str(exc)},
            status_val="error",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Resume building failed: {str(exc)}",
        ) from exc


@router.get("/runs/{run_id}")
def api_get_run(
    run_id: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Retrieve a stored workflow run and its artifacts.

    Args:
        run_id: The workflow run ID
        current_user: Authenticated user
        session: Database session

    Returns:
        Dict containing run metadata, input, output, and artifacts

    Raises:
        HTTPException: 404 if run not found or not owned by user
    """
    # Fetch the run
    run = session.get(WorkflowRun, run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )

    # Verify ownership
    if run.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own workflow runs.",
        )

    # Fetch associated artifacts
    artifacts_stmt = select(Artifact).where(Artifact.run_id == run_id)
    artifacts = session.exec(artifacts_stmt).all()

    # Serialize artifacts
    artifacts_data = [
        {
            "id": artifact.id,
            "kind": artifact.kind,
            "label": artifact.label,
            "payload": artifact.payload_json,
            "created_at": artifact.created_at.isoformat(),
        }
        for artifact in artifacts
    ]

    return {
        "ok": True,
        "run": {
            "id": run.id,
            "workflow_id": run.workflow_id,
            "version": run.version,
            "status": run.status,
            "input": run.input_json,
            "output": run.output_json,
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
        },
        "artifacts": artifacts_data,
    }


def build_resume_orchestrated(
    user_id: str,
    jd_text: str,
    target_role: Optional[str] = None,
    session: Session = None,
    user: User = None,
) -> Dict[str, Any]:
    """
    Orchestrate the full resume building flow.

    This function demonstrates backend-level orchestration:
    1. Call JD_to_StructuredJD_v0 to structure the job description
    2. Call Resume_Builder_v1 using the structured JD as input

    This is the conductor pattern: workflows do NOT call each other.
    The backend explicitly passes outputs as inputs between workflows.

    Args:
        user_id: User identifier
        jd_text: Raw job description text
        target_role: Optional target role override
        session: Database session (required)
        user: User object (required)

    Returns:
        Dict containing:
            - structured_jd: Output from JD structuring workflow
            - resume_bundle: Output from Resume Builder workflow
            - jd_run_id: ID of the JD structuring run
            - resume_run_id: ID of the Resume Builder run

    Raises:
        HTTPException: If any workflow step fails
    """
    if not session or not user:
        raise ValueError("session and user are required for orchestrated build")

    # STEP 1: Structure the JD
    jd_input = {
        "user_id": user_id,
        "jd_text": jd_text,
    }

    try:
        jd_result = run_workflow(
            workflow_id=WORKFLOW_JD_TO_STRUCTURED["id"],
            version=WORKFLOW_JD_TO_STRUCTURED["version"],
            input_vars=jd_input,
        )

        jd_run = _persist_workflow_run(
            session=session,
            user_id=user.id,
            workflow_id=WORKFLOW_JD_TO_STRUCTURED["id"],
            version=WORKFLOW_JD_TO_STRUCTURED["version"],
            input_json=jd_input,
            output_json=jd_result,
            status_val="success",
        )

        structured_jd = jd_result.get("output_parsed", {})

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JD structuring failed in orchestration: {str(exc)}",
        ) from exc

    # STEP 2: Build the resume using the structured JD
    resume_input = {
        "user_id": user_id,
        "jd_structured": structured_jd,
        "target_role": target_role or structured_jd.get("title", ""),
    }

    try:
        resume_result = run_workflow(
            workflow_id=WORKFLOW_RESUME_BUILDER["id"],
            version=WORKFLOW_RESUME_BUILDER["version"],
            input_vars=resume_input,
        )

        resume_run = _persist_workflow_run(
            session=session,
            user_id=user.id,
            workflow_id=WORKFLOW_RESUME_BUILDER["id"],
            version=WORKFLOW_RESUME_BUILDER["version"],
            input_json=resume_input,
            output_json=resume_result,
            status_val="success",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Resume building failed in orchestration: {str(exc)}",
        ) from exc

    return {
        "structured_jd": structured_jd,
        "resume_bundle": resume_result,
        "jd_run_id": jd_run.id,
        "resume_run_id": resume_run.id,
    }
