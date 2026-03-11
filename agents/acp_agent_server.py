"""
ACP Agent Server – runs all specialist agents as ACP-compliant HTTP endpoints.

Architecture:
  LangGraph Orchestrator (ACP Client)
       ↓  ACP REST  (POST /runs)
  This server (port 8100)
       ├── /agents/plan-forecast-agent
       ├── /agents/contract-agent
       ├── /agents/general-agent
       └── /agents/synthesizer-agent

Wire format follows ACP v1 spec:
  POST /runs  { agent_name, input: [Message{parts:[MessagePart{content}]}] }
  → 200       { status, output: [Message{parts:[MessagePart{content}]}] }

Also exposes:
  GET  /agents           → list of AgentManifest
  GET  /agents/{name}    → single AgentManifest
  GET  /.well-known/agent.json  → A2A Agent Card (root agent)
"""
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import uvicorn, uuid

load_dotenv()

# ── Local imports ──────────────────────────────────────────────────────────
from agents.forecast_agent import forecast_agent_node
from agents.contract_agent import contract_agent_node
from agents.general_agent import general_agent_node
from agents.synthesizer import synthesizer_node

ACP_PORT = int(os.getenv("ACP_PORT", "8100"))

# ── ACP Wire-format models (subset of ACP v1) ─────────────────────────────
class AcpMessagePart(BaseModel):
    content_type: str = "text/plain"
    content: str

class AcpMessage(BaseModel):
    parts: List[AcpMessagePart]

class AcpRunRequest(BaseModel):
    agent_name: str
    input: List[AcpMessage]
    session_id: Optional[str] = None

class AcpRunResponse(BaseModel):
    run_id: str
    agent_name: str
    status: str      # "completed" | "failed"
    output: List[AcpMessage]

class AcpAgentManifest(BaseModel):
    name: str
    description: str
    input_content_types: List[str] = ["text/plain"]
    output_content_types: List[str] = ["text/plain"]

# ── Agent registry ─────────────────────────────────────────────────────────
AGENT_REGISTRY: dict[str, dict] = {
    "plan-forecast-agent": {
        "description": "RAG agent for project planning, resource forecasting, hours, and cost data.",
        "handler": lambda q, outputs, debug: forecast_agent_node({
            "query": q, "agent_outputs": outputs, "debug_log": debug,
            "response": "", "next_node": "",
        }),
    },
    "contract-agent": {
        "description": "RAG agent for contracts, SOWs, milestones, and pricing terms.",
        "handler": lambda q, outputs, debug: contract_agent_node({
            "query": q, "agent_outputs": outputs, "debug_log": debug,
            "response": "", "next_node": "",
        }),
    },
    "general-agent": {
        "description": "General-purpose conversational agent; free-form LLM without RAG.",
        "handler": lambda q, outputs, debug: general_agent_node({
            "query": q, "agent_outputs": outputs, "debug_log": debug,
            "response": "", "next_node": "",
        }),
    },
    "synthesizer-agent": {
        "description": "Supervisor agent that merges multiple specialist reports into one answer.",
        "handler": lambda q, outputs, debug: synthesizer_node({
            "query": q, "agent_outputs": outputs, "debug_log": debug,
            "response": "", "next_node": "",
        }),
    },
}

# ── FastAPI App ────────────────────────────────────────────────────────────
app = FastAPI(
    title="OpenClaw ACP Agent Server",
    description="ACP-compliant multi-agent server for the OpenClaw system",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/agents", response_model=List[AcpAgentManifest])
def list_agents():
    return [
        AcpAgentManifest(name=name, description=meta["description"])
        for name, meta in AGENT_REGISTRY.items()
    ]


@app.get("/agents/{agent_name}", response_model=AcpAgentManifest)
def get_agent(agent_name: str):
    if agent_name not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")
    meta = AGENT_REGISTRY[agent_name]
    return AcpAgentManifest(name=agent_name, description=meta["description"])


@app.post("/runs", response_model=AcpRunResponse)
def create_run(req: AcpRunRequest):
    """
    ACP v1 /runs endpoint.
    The orchestrator posts here with { agent_name, input: [Message] }.
    We invoke the corresponding agent node and return the result.
    """
    agent_name = req.agent_name
    if agent_name not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")

    # Extract text query from the first message part
    query = ""
    agent_outputs: list[str] = []
    for msg in req.input:
        for part in msg.parts:
            if part.content_type == "text/plain":
                query += part.content + "\n"
            elif part.content_type == "application/json":
                # Pass-through serialised agent_outputs from synthesizer calls
                import json
                try:
                    agent_outputs = json.loads(part.content)
                except Exception:
                    pass
    query = query.strip()

    try:
        handler = AGENT_REGISTRY[agent_name]["handler"]
        result = handler(query, agent_outputs, "")
        # Collect the output text
        if "response" in result and result["response"]:
            text = result["response"]
        elif "agent_outputs" in result and result["agent_outputs"]:
            text = "\n".join(result["agent_outputs"])
        else:
            text = "No output."

        output_msg = AcpMessage(parts=[AcpMessagePart(content=text)])
        return AcpRunResponse(
            run_id=str(uuid.uuid4()),
            agent_name=agent_name,
            status="completed",
            output=[output_msg],
        )
    except Exception as exc:
        err_msg = AcpMessage(parts=[AcpMessagePart(content=f"Agent error: {exc}")])
        return AcpRunResponse(
            run_id=str(uuid.uuid4()),
            agent_name=agent_name,
            status="failed",
            output=[err_msg],
        )


# ── A2A Agent Card (root agent) ────────────────────────────────────────────
@app.get("/.well-known/agent.json")
def a2a_agent_card():
    """Google A2A Agent Card – describes this ACP server to A2A clients."""
    host = os.getenv("ORCHESTRATOR_HOST", "localhost")
    return JSONResponse({
        "name": "openclaw-agent-mesh",
        "description": (
            "OpenClaw Multi-Agent System: routes queries to Plan-Forecast, "
            "Contract, General, or Synthesizer agents using ACP protocol."
        ),
        "version": "1.0.0",
        "url": f"http://{host}:{ACP_PORT}",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": name,
                "name": name,
                "description": meta["description"],
                "tags": ["rag", "project-management"],
                "examples": [],
            }
            for name, meta in AGENT_REGISTRY.items()
        ],
    })


if __name__ == "__main__":
    print(f"\n🤖 OpenClaw ACP Agent Server starting on port {ACP_PORT} …")
    uvicorn.run("acp_agent_server:app", host="0.0.0.0", port=ACP_PORT, reload=True)
