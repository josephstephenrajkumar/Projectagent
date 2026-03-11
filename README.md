# OpenClaw Multi-Agent System

A production-ready, locally-runnable multi-agent RAG system converted from the `Project_Management_MultiAgentV2` notebook.

## Architecture

```
User
 ↓
Chat UI  (ui/)
 ↓ HTTP / REST
OpenClaw Runtime — Node.js Gateway  (runtime/gateway/)
 │         │                │
Skills   Connectors       Gateway
 ↓
LangGraph Orchestrator  (orchestrator/)
 ↓
Agent Mesh  (agents/)
 │─────────────────┬──────────────────┐
 Plan-Forecast     Contract          General
 Agent             Agent             Agent
 │                 │
 └────────────────┘
          ↓
      Synthesizer
 ↓
Tools / APIs  (tools/)
 ↓
Groq LLM  (openai/gpt-oss-120b)   +   ChromaDB  (data/chroma_db/)
```

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Node.js 18+
- A [Groq](https://console.groq.com) account with an API key

### 2. Set up environment

```bash
cd /home/joseph/projectAgent/openclaw-multiagent
cp .env.example .env
# Edit .env if needed (model name, paths, etc.)
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your documents

Place documents (PDF, DOCX, XLSX) into `data/docs/`.  
Each **top-level file or folder** becomes its own agent collection:

```
data/docs/
├── contract.pdf          → contract_collection
└── plan-forecast.xlsx    → plan-forecast_collection
```

### 5. Ingest documents

```bash
cd /home/joseph/projectAgent/openclaw-multiagent
python tools/ingestion.py
```

Or use the **Re-Ingest Docs** button in the Chat UI.

### 6. Start the Python orchestrator

```bash
cd orchestrator
python main.py
# → FastAPI on http://localhost:8000
```

### 7. Install and start the Node.js gateway

```bash
cd runtime
npm install
node gateway/server.js
# → Chat UI on http://localhost:3000
```

### 8. Open the Chat UI

Navigate to **http://localhost:3000**

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | _(required)_ | Groq cloud API key |
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | HuggingFace embedding model |
| `CHROMA_DB_PATH` | `./data/chroma_db` | ChromaDB persistence path |
| `SOURCE_DATA_DIR` | `./data/docs` | Document source folder |
| `ORCHESTRATOR_PORT` | `8000` | FastAPI server port |
| `GATEWAY_PORT` | `3000` | Node.js gateway port |

---

## Agent Routing Logic

| Query type | Agent | Collection |
|---|---|---|
| Planning, hours, forecast, resources | **Plan-Forecast Agent** | `plan-forecast_collection` |
| Contracts, SOW, milestones, pricing | **Contract Agent** | `contract_collection` |
| Both / compare / synthesise | **Both → Synthesizer** | All collections |
| General / off-topic | **General Agent** | _(no RAG)_ |

The Router **dynamically discovers** collection topics on startup using the LLM — no hardcoded keywords.

---

## API Reference

### FastAPI Orchestrator (port 8000)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | `{"query": "..."}` → `{"response", "debug_log", "agent"}` |
| `POST` | `/ingest` | Trigger document re-ingestion |

### Node.js Gateway (port 3000)

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `GET` | `/health` | Gateway health |
| `POST` | `/chat` | Proxied to FastAPI `/chat` |
| `POST` | `/ingest` | Proxied to FastAPI `/ingest` |

---

## Project Structure

```
openclaw-multiagent/
├── ui/                      # Chat UI (HTML/CSS/JS)
├── runtime/                 # OpenClaw Node.js Runtime
│   ├── gateway/server.js    # HTTP Gateway + static server
│   ├── skills/ragSkill.js   # RAG skill wrapper
│   └── connectors/          # Data source connectors
├── orchestrator/            # Python LangGraph
│   ├── main.py              # FastAPI app
│   ├── graph.py             # LangGraph StateGraph
│   ├── router.py            # Dynamic router node
│   ├── state.py             # AgentState TypedDict
│   └── llm_factory.py       # Groq LLM factory
├── agents/                  # Agent Mesh nodes
│   ├── forecast_agent.py
│   ├── contract_agent.py
│   ├── general_agent.py
│   └── synthesizer.py
├── tools/                   # RAG Tools / APIs
│   ├── ingestion.py         # Document ingestion
│   └── retrieval.py         # ChromaDB retrieval
├── data/
│   ├── docs/                # ← Put your documents here
│   └── chroma_db/           # Auto-created vector store
├── .env.example
└── requirements.txt
```
