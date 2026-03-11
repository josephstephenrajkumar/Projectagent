"""
A2A Agent Cards – per-agent JSON descriptors following Google's A2A spec.
These are served by the ACP agent server at /.well-known/agent.json
but this module also provides helpers to generate individual cards.

Reference: https://google.github.io/A2A/
"""

ACP_PORT = 8100
ORCHESTRATOR_PORT = 8000

A2A_CARDS: dict[str, dict] = {
    "plan-forecast-agent": {
        "name": "plan-forecast-agent",
        "description": (
            "RAG-powered specialist for project planning data. "
            "Answers questions about resource hours, cost estimates, "
            "monthly forecasts, and staffing (Singapore / COE India)."
        ),
        "version": "1.0.0",
        "url": f"http://localhost:{ACP_PORT}",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "rag-planning",
                "name": "Planning RAG",
                "description": "Retrieves plan/forecast documents from ChromaDB and answers with grounded context.",
                "tags": ["rag", "planning", "forecast", "hours", "cost"],
                "examples": [
                    "Give me plan and forecast for Boston?",
                    "How many hours are allocated for April?",
                ],
            }
        ],
    },

    "contract-agent": {
        "name": "contract-agent",
        "description": (
            "RAG-powered specialist for contractual documents. "
            "Answers questions about SOWs, milestones, pricing, and parties."
        ),
        "version": "1.0.0",
        "url": f"http://localhost:{ACP_PORT}",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "rag-contract",
                "name": "Contract RAG",
                "description": "Retrieves contract/SOW documents from ChromaDB and answers with grounded context.",
                "tags": ["rag", "contract", "sow", "milestones", "pricing"],
                "examples": [
                    "Give details of Boston contract?",
                    "What are the payment milestones?",
                ],
            }
        ],
    },

    "general-agent": {
        "name": "general-agent",
        "description": (
            "General-purpose conversational agent. "
            "Handles off-topic queries, greetings, and questions not covered by RAG agents."
        ),
        "version": "1.0.0",
        "url": f"http://localhost:{ACP_PORT}",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "general-chat",
                "name": "General Chat",
                "description": "Free-form LLM response without document grounding.",
                "tags": ["chat", "general", "llm"],
                "examples": ["Write a haiku about AI.", "What is LangGraph?"],
            }
        ],
    },

    "synthesizer-agent": {
        "name": "synthesizer-agent",
        "description": (
            "Supervisor agent that receives reports from multiple specialist agents "
            "and synthesises them into a single, coherent answer."
        ),
        "version": "1.0.0",
        "url": f"http://localhost:{ACP_PORT}",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "synthesis",
                "name": "Report Synthesis",
                "description": "Merges multiple agent reports into one structured answer, highlighting discrepancies.",
                "tags": ["synthesis", "multi-agent", "supervisor"],
                "examples": ["Compare plan and contract for Boston."],
            }
        ],
    },
}


def get_a2a_card(agent_name: str) -> dict | None:
    return A2A_CARDS.get(agent_name)


def get_root_a2a_card(host: str = "localhost") -> dict:
    """Root A2A card for the entire OpenClaw Agent Mesh."""
    return {
        "name": "openclaw-agent-mesh",
        "description": (
            "OpenClaw Multi-Agent System: LangGraph orchestrator + ACP specialist agents. "
            "Routes queries to planning, contract, general, or synthesizer agents."
        ),
        "version": "2.0.0",
        "url": f"http://{host}:{ACP_PORT}",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": name,
                "name": card["name"],
                "description": card["description"],
                "tags": card["skills"][0]["tags"] if card.get("skills") else [],
            }
            for name, card in A2A_CARDS.items()
        ],
    }
