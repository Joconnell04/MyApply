#!/usr/bin/env python3
"""
List all available AgentKit workflows from OpenAI.
"""
import os
import sys
import httpx
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import get_settings

def list_workflows():
    """List all available workflows from OpenAI API."""
    settings = get_settings()

    if not settings.OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY is not configured in your environment.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "OpenAI-Beta": "workflows=v1",
    }

    base_url = "https://api.openai.com/v1"

    print("Fetching workflows from OpenAI...\n")

    try:
        response = httpx.get(
            f"{base_url}/workflows",
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            print(f"ERROR: Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)

        data = response.json()

        # Handle different response formats
        workflows = data.get("data", []) if isinstance(data, dict) else data

        if not workflows:
            print("No workflows found in your OpenAI account.")
            print("\nYou need to create a workflow in the OpenAI AgentKit dashboard:")
            print("https://platform.openai.com/workflows")
            return

        print(f"Found {len(workflows)} workflow(s):\n")
        print("=" * 80)

        for i, workflow in enumerate(workflows, 1):
            wf_id = workflow.get("id", "N/A")
            name = workflow.get("name", "Unnamed")
            description = workflow.get("description", "No description")
            version = workflow.get("version", "N/A")

            print(f"\n{i}. {name}")
            print(f"   ID: {wf_id}")
            print(f"   Version: {version}")
            print(f"   Description: {description}")

            # Show how to use it in workflow_constants.py
            if i == 1:
                print(f"\n   To use this workflow, update workflow_constants.py:")
                print(f'   WORKFLOW_RESUME_BUILDER_V2_ID = "{wf_id}"')
                print(f'   WORKFLOW_RESUME_BUILDER_V2_VER = "{version}"')

        print("\n" + "=" * 80)

    except httpx.HTTPError as exc:
        print(f"ERROR: HTTP request failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Unexpected error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    list_workflows()
