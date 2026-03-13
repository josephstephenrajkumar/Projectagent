"""
FastAPI server – exposes the LangGraph orchestrator over HTTP.
The Node.js OpenClaw Gateway proxies requests here.
"""
import sys
import os
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from dotenv import load_dotenv

load_dotenv()

from orchestrator.graph import app as langgraph_app

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECTS_DIR = os.path.join(PROJECT_ROOT, "data", "docs", "projects")

server = FastAPI(
    title="OpenClaw – LangGraph Orchestrator",
    description=(
        "Multi-agent RAG system: User → Chat UI → Node Gateway → "
        "FastAPI → LangGraph Orchestrator → Agent Mesh → Tools → Groq (openai/gpt-oss-120b)"
    ),
    version="3.0.0",
)

server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Chat models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

# ── Persistent Session Store ────────────────────────────────────────────────
SESSION_FILE = os.path.join(PROJECT_ROOT, "data", "sessions.json")

def _load_sessions() -> dict[str, List[dict]]:
    if not os.path.exists(SESSION_FILE):
        return {}
    try:
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_sessions(sessions: dict[str, List[dict]]):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(sessions, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save sessions: {e}")

# session_id -> List[dict] (history)
SESSION_STORE = _load_sessions()

class ChatResponse(BaseModel):
    response: str
    debug_log: str
    agent: str  # which agent(s) handled this



# ── Health ─────────────────────────────────────────────────────────────────

@server.get("/health")
def health():
    return {"status": "ok", "service": "openclaw-orchestrator"}


# ── Chat endpoint ──────────────────────────────────────────────────────────

@server.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    session_id = req.session_id or "default"
    history = SESSION_STORE.get(session_id, [])

    # ── History Sanity Anchor ─────────────────────────────────────────────
    # Fetch live project list to override stale conversation history
    db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    db_abs = db_path if os.path.isabs(db_path) else os.path.abspath(os.path.join(PROJECT_ROOT, db_path))
    project_fact_check = "FACT CHECK: The following projects are CURRENTLY ACTIVE in the system:\n"
    try:
        import sqlite3
        conn = sqlite3.connect(db_abs)
        cursor = conn.cursor()
        cursor.execute("SELECT ProjectNumber, customer FROM Project")
        projects = cursor.fetchall()
        for p_num, cust in projects:
            project_fact_check += f"- Project {p_num} (Customer: {cust}) is ACTIVE and AVAILABLE.\n"
        conn.close()
    except Exception:
        project_fact_check += "- (Unable to reach database for fact check)\n"
    
    # Prepend this anchor to the history for this invocation (don't save it to session)
    augmented_history = [{"role": "system", "content": project_fact_check}] + history

    initial_state = {
        "query": req.query,
        "response": "",
        "next_node": "",
        "agent_outputs": [],
        "history": augmented_history,
        "debug_log": "",
    }

    try:
        result = langgraph_app.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Update history in session store
    new_response = result.get("response", "No response generated.")
    updated_history = history + [
        {"role": "user", "content": req.query},
        {"role": "assistant", "content": new_response}
    ]
    # Keep history at reasonable length
    SESSION_STORE[session_id] = updated_history[-20:]
    _save_sessions(SESSION_STORE)

    debug = result.get("debug_log", "")
    agent_tag = "general_agent"
    for line in debug.splitlines():
        if "Router →" in line:
            agent_tag = line.split("Router →")[-1].strip()
            break

    return ChatResponse(
        response=new_response,
        debug_log=debug,
        agent=agent_tag,
    )


class FeedbackRequest(BaseModel):
    user_query: str
    generated_sql: str
    score: int  # +1 for helpful, -1 for unhelpful

@server.post("/chat/feedback")
def submit_feedback(req: FeedbackRequest):
    """Store successful/failed SQL queries in the QueryFeedback table."""
    db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    db_abs = db_path if os.path.isabs(db_path) else os.path.abspath(os.path.join(PROJECT_ROOT, db_path))
    
    import sqlite3
    import uuid
    from datetime import datetime
    try:
        conn = sqlite3.connect(db_abs)
        # Check if this exact SQL already exists
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM QueryFeedback WHERE generated_sql = ?", (req.generated_sql,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute(
                "UPDATE QueryFeedback SET feedback_score = feedback_score + ?, last_used = ? WHERE id = ?",
                (req.score, datetime.utcnow().isoformat(), existing[0])
            )
        else:
            cursor.execute(
                "INSERT INTO QueryFeedback (id, user_query, generated_sql, feedback_score, last_used) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), req.user_query, req.generated_sql, req.score, datetime.utcnow().isoformat())
            )
        conn.commit()
        conn.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Document ingestion ────────────────────────────────────────────────────

@server.post("/ingest")
def ingest():
    """Trigger re-ingestion of documents from SOURCE_DATA_DIR."""
    from tools.ingestion import build_knowledge_base
    collections = build_knowledge_base()
    return {"status": "ok", "indexed": collections}


# ── Project Creation: Phase A (upload → extract) ──────────────────────────

@server.post("/project/create")
async def create_project(
    project_name: str = Form(...),
    project_code: str = Form(...),
    opportunity_id: str = Form(""),
    contract_file: UploadFile = File(...),
    estimation_file: UploadFile = File(...),
    erp_file: UploadFile = File(None),
):
    """
    Upload contract + estimation-milestone (+ optional ERP) files,
    ingest into ChromaDB, and extract structured project data for user confirmation.
    The opportunity_id is optional — it can be extracted from the contract .docx.
    """
    from fastapi import HTTPException

    # ── Validate file types for each collection ──────────────────────────────
    VALID_CONTRACT_EXT = {".docx", ".doc", ".pdf"}
    VALID_EXCEL_EXT = {".xlsx", ".xls"}

    contract_ext = os.path.splitext(contract_file.filename)[1].lower()
    if contract_ext not in VALID_CONTRACT_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Contract file must be {', '.join(VALID_CONTRACT_EXT)}. Got: '{contract_ext}'"
        )

    estimation_ext = os.path.splitext(estimation_file.filename)[1].lower()
    if estimation_ext not in VALID_EXCEL_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Estimation-Milestone file must be {', '.join(VALID_EXCEL_EXT)}. Got: '{estimation_ext}'"
        )

    if erp_file and erp_file.filename:
        erp_ext = os.path.splitext(erp_file.filename)[1].lower()
        if erp_ext not in VALID_EXCEL_EXT:
            raise HTTPException(
                status_code=400,
                detail=f"ERP/Project file must be {', '.join(VALID_EXCEL_EXT)}. Got: '{erp_ext}'"
            )

    # 1. Save uploaded files to data/docs/projects/<project_code>/
    safe_code = project_code.replace(" ", "_").replace("-", "_").lower()
    project_dir = os.path.join(PROJECTS_DIR, safe_code)
    os.makedirs(project_dir, exist_ok=True)
    
    with open(os.path.join(project_dir, "status.txt"), "w") as f:
        f.write("Initializing Project Extraction...")

    saved_files = []
    uploads = [contract_file, estimation_file]
    if erp_file and erp_file.filename:
        uploads.append(erp_file)

    for upload in uploads:
        dest = os.path.join(project_dir, upload.filename)
        with open(dest, "wb") as f:
            shutil.copyfileobj(upload.file, f)
        saved_files.append(dest)

    # 2. Run the extraction graph
    from orchestrator.project_graph import extraction_app

    initial_state = {
        "query": f"Create project: {project_name}",
        "response": "",
        "next_node": "",
        "agent_outputs": [],
        "debug_log": "",
        "project_name": project_name,
        "project_code": project_code,
        "opportunity_id": opportunity_id,
        "uploaded_files": saved_files,
        "extracted_data": None,
        "user_confirmed": False,
        "operation_mode": "create_project",
        "collection_names": [],
    }

    try:
        result = extraction_app.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")

    extracted = result.get("extracted_data")
    if not extracted:
        raise HTTPException(
            status_code=422,
            detail="Could not extract project data. " + result.get("debug_log", ""),
        )

    return {
        "status": "pending_confirmation",
        "project_name": project_name,
        "project_code": project_code,
        "opportunity_id": opportunity_id,
        "extracted_data": extracted,
        "debug_log": result.get("debug_log", ""),
    }


@server.get("/project/status/{project_code}")
def get_project_status(project_code: str):
    """Return live extraction status for a running project creation task."""
    safe_code = project_code.replace(" ", "_").replace("-", "_").lower()
    status_file = os.path.join(PROJECTS_DIR, safe_code, "status.txt")
    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            return {"status": f.read().strip()}
    return {"status": "Initializing..."}


# ── Project Creation: Phase B (confirm → persist) ────────────────────────

class ProjectConfirmRequest(BaseModel):
    project_name: str
    project_code: str
    opportunity_id: str
    extracted_data: dict


@server.post("/project/confirm")
def confirm_project(req: ProjectConfirmRequest):
    """
    Confirm the extracted data and persist to the database.
    The user may have edited the extracted_data before confirming.
    """
    from orchestrator.project_graph import persistence_app

    initial_state = {
        "query": f"Confirm project: {req.project_name}",
        "response": "",
        "next_node": "",
        "agent_outputs": [],
        "debug_log": "",
        "project_name": req.project_name,
        "project_code": req.project_code,
        "opportunity_id": req.opportunity_id,
        "uploaded_files": [],
        "extracted_data": req.extracted_data,
        "user_confirmed": True,
        "operation_mode": "create_project",
        "collection_names": [],
    }

    try:
        result = persistence_app.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")

    return {
        "status": "created" if "✅" in result.get("response", "") else "error",
        "response": result.get("response", ""),
        "debug_log": result.get("debug_log", ""),
    }


@server.get("/raid/alerts")
def get_raid_alerts():
    """
    Returns ALL open/in-progress RAID items that are past their DueDate.
    Requires local SQLite tracking active.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    db_abs = db_path if os.path.isabs(db_path) else os.path.abspath(os.path.join(project_root, db_path))
    
    if not os.path.exists(db_abs):
        return {"alerts": []}
        
    import sqlite3
    try:
        conn = sqlite3.connect(db_abs)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check DueDate < today. Status NOT IN closed/resolved.
        # Ensure DueDate isn't blank or null.
        cursor.execute("""
            SELECT R.raidID, R.project_id, R.Description, R.owner, R.DueDate, R.Status, P.ProjectNumber, P.customer
            FROM RAIDitems R
            JOIN Project P ON R.project_id = P.project_id
            WHERE R.DueDate != '' 
              AND R.DueDate IS NOT NULL
              AND date(R.DueDate) < date('now')
              AND LOWER(R.Status) NOT IN ('closed', 'resolved')
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        alerts = [dict(r) for r in rows]
        return {"alerts": alerts}
        
    except Exception as e:
        print(f"Error fetching RAID alerts: {e}")
        return {"alerts": []}


# ── Database Management Endpoints ──────────────────────────────────────────

@server.get("/db/tables")
def get_db_tables():
    """Returns a list of all tables in the database."""
    db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    db_abs = os.path.abspath(os.path.join(PROJECT_ROOT, db_path))
    if not os.path.exists(db_abs):
        raise HTTPException(status_code=404, detail="Database file not found.")
    
    import sqlite3
    try:
        conn = sqlite3.connect(db_abs)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@server.get("/db/table/{table_name}")
def get_table_data(table_name: str):
    """Returns columns and rows for a specific table."""
    db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    db_abs = os.path.abspath(os.path.join(PROJECT_ROOT, db_path))
    
    import sqlite3
    try:
        conn = sqlite3.connect(db_abs)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Validate table name safely
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Table not found.")
            
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        
        conn.close()
        return {
            "columns": columns,
            "rows": [dict(r) for r in rows]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DBUpdateRequest(BaseModel):
    table_name: str
    pk_column: str
    pk_value: str
    updates: dict


@server.post("/db/update")
def update_table_data(req: DBUpdateRequest):
    """Update a row in the database."""
    db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    db_abs = os.path.abspath(os.path.join(PROJECT_ROOT, db_path))
    
    import sqlite3
    try:
        conn = sqlite3.connect(db_abs)
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{col} = ?" for col in req.updates.keys()])
        values = list(req.updates.values()) + [req.pk_value]
        
        query = f"UPDATE {req.table_name} SET {set_clause} WHERE {req.pk_column} = ?"
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        return {"status": "ok", "message": "Row updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("ORCHESTRATOR_HOST", "localhost")
    port = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    uvicorn.run("main:server", host=host, port=port, reload=True)
