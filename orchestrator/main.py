"""
FastAPI server – exposes the LangGraph orchestrator over HTTP.
The Node.js OpenClaw Gateway proxies requests here.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from orchestrator.graph import app as langgraph_app

server = FastAPI(
    title="OpenClaw – LangGraph Orchestrator",
    description=(
        "Multi-agent RAG system: User → Chat UI → Node Gateway → "
        "FastAPI → LangGraph Orchestrator → Agent Mesh → Tools → Groq (openai/gpt-oss-120b)"
    ),
    version="2.0.0",
)

server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    response: str
    debug_log: str
    agent: str  # which agent(s) handled this


@server.get("/health")
def health():
    return {"status": "ok", "service": "openclaw-orchestrator"}


@server.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    initial_state = {
        "query": req.query,
        "response": "",
        "next_node": "",
        "agent_outputs": [],
        "debug_log": "",
    }

    try:
        result = langgraph_app.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    debug = result.get("debug_log", "")
    # Extract the agent decision from the debug log for UI badge
    agent_tag = "general_agent"
    for line in debug.splitlines():
        if "Router →" in line:
            agent_tag = line.split("Router →")[-1].strip()
            break

    return ChatResponse(
        response=result.get("response", "No response generated."),
        debug_log=debug,
        agent=agent_tag,
    )


@server.post("/ingest")
def ingest():
    """Trigger re-ingestion of documents from SOURCE_DATA_DIR."""
    from tools.ingestion import build_knowledge_base
    collections = build_knowledge_base()
    return {"status": "ok", "indexed": collections}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("ORCHESTRATOR_HOST", "localhost")
    port = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    uvicorn.run("main:server", host=host, port=port, reload=True)
