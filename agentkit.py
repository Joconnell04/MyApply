"""
AgentKit workflow runner for MyApply.

This module provides a simple wrapper around AgentKit workflows via the
OpenAI SDK. The backend orchestrator uses this to call workflows
synchronously and handle results.

IMPORTANT: Workflows do NOT call each other. The backend is the conductor
that passes outputs from one workflow as explicit inputs to another.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from fastapi import HTTPException, status
from openai import OpenAI


def get_openai_client() -> OpenAI:
    """
    Initialize and return an OpenAI client configured with the API key
    from the environment.

    Raises:
        HTTPException: If OPENAI_API_KEY is not set.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY not configured. AgentKit workflows unavailable.",
        )
    return OpenAI(api_key=api_key)


def run_workflow(workflow_id: str, version: str, input_vars: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute an AgentKit workflow synchronously and return the parsed result.

    This function is the single point of integration with AgentKit workflows.
    The backend orchestrator calls this function to run workflows and then
    passes outputs between workflows as needed.

    Args:
        workflow_id: The AgentKit workflow ID (e.g., wf_68e969c7da408190...)
        version: The workflow version string (e.g., "4")
        input_vars: Input variables dictionary for the workflow

    Returns:
        Dict containing the workflow output. The structure depends on the
        specific workflow being called. Typically includes:
        - output_parsed: Parsed structured output
        - output_text: Raw text output (if available)

    Raises:
        HTTPException: If the workflow call fails or returns invalid JSON.
            Status 502 (Bad Gateway) indicates an issue with the workflow execution.
            Status 503 (Service Unavailable) indicates configuration issues.

    Examples:
        >>> result = run_workflow(
        ...     workflow_id="wf_68e80e14fad48190a83d85460325ba7f072fbeb74efb9546",
        ...     version="4",
        ...     input_vars={"user_id": "123", "jd_text": "Senior Python Developer..."}
        ... )
        >>> structured_jd = result.get("output_parsed", {})
    """
    client = get_openai_client()

    try:
        # Call the AgentKit workflow
        # NOTE: This is a simplified implementation. In production, you would use
        # the actual OpenAI AgentKit Workflow Runs API, which might look like:
        # response = client.workflows.runs.create(
        #     workflow_id=workflow_id,
        #     version=version,
        #     input=input_vars
        # )
        #
        # For now, we'll use a chat completion with function calling to simulate
        # the workflow execution. Replace this with the actual API when available.

        # Prepare the workflow input as a JSON string
        input_json = json.dumps(input_vars)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are executing AgentKit workflow {workflow_id} "
                        f"version {version}. Process the input and return the result."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Input: {input_json}",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        # Parse the response
        if not response.choices:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Workflow returned no response choices.",
            )

        message = response.choices[0].message
        if not message.content:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Workflow returned empty content.",
            )

        # Parse the JSON result
        try:
            result = json.loads(message.content)
        except json.JSONDecodeError as json_err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Workflow returned invalid JSON: {str(json_err)}",
            ) from json_err

        return result

    except HTTPException:
        # Re-raise our own exceptions
        raise
    except Exception as exc:
        # Sanitize and wrap any other errors
        error_msg = str(exc)
        # Remove sensitive information from error messages
        if "api" in error_msg.lower() and "key" in error_msg.lower():
            error_msg = "Authentication error with AgentKit service."

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Workflow execution failed: {error_msg}",
        ) from exc
