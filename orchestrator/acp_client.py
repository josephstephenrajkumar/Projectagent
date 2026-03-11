"""
ACP Client Bridge – used by LangGraph agent nodes to call agents
via the ACP REST protocol instead of direct Python function calls.

Uses acp_sdk.Client (the official IBM ACP client) when calling agents
that are registered on the ACP server. Falls back to direct call if
the ACP server is unavailable (development mode).
"""
import asyncio
import json
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

ACP_BASE_URL = f"http://{os.getenv('ORCHESTRATOR_HOST', 'localhost')}:{os.getenv('ACP_PORT', '8100')}"


def _call_acp_agent(agent_name: str, query: str, agent_outputs: list[str] = None) -> str:
    """
    Synchronously call an ACP agent via the /runs endpoint.
    Returns the text content from the first output MessagePart.
    """
    agent_outputs = agent_outputs or []
    parts = [{"content_type": "text/plain", "content": query}]
    if agent_outputs:
        parts.append({
            "content_type": "application/json",
            "content": json.dumps(agent_outputs),
        })

    payload = {
        "agent_name": agent_name,
        "input": [{"parts": parts}],
    }

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{ACP_BASE_URL}/runs", json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Extract text from first output MessagePart
            for msg in data.get("output", []):
                for part in msg.get("parts", []):
                    if part.get("content_type") == "text/plain":
                        return part["content"]
            return "No output from agent."
    except httpx.ConnectError:
        raise ConnectionError(
            f"ACP server unreachable at {ACP_BASE_URL}. "
            "Start it with: python agents/acp_agent_server.py"
        )
    except Exception as exc:
        raise RuntimeError(f"ACP call to '{agent_name}' failed: {exc}")


def list_acp_agents() -> list[dict]:
    """Return list of registered ACP agents (AgentManifest dicts)."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{ACP_BASE_URL}/agents")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return []


def acp_server_healthy() -> bool:
    """Quick health check for the ACP server."""
    try:
        with httpx.Client(timeout=3) as client:
            resp = client.get(f"{ACP_BASE_URL}/agents")
            return resp.status_code == 200
    except Exception:
        return False
