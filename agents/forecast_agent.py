"""
Agent Mesh – Plan-Forecast Agent
Answers questions about project planning, resource allocation,
hours estimates, and cost forecasts.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.state import AgentState
from orchestrator.llm_factory import get_llm
from tools.retrieval import similarity_search
from langchain_core.messages import SystemMessage, HumanMessage
import sqlite3

llm = get_llm()

COLLECTION = "plan-forecast_collection"
AGENT_NAME = "Plan-Forecast Agent"
PERSONA = "Programme Specialist – expert in project planning and resource forecasting"


def forecast_agent_node(state: AgentState) -> dict:
    query = state["query"]
    history = state.get("history", [])
    current_outputs = state.get("agent_outputs", [])
    debug = state.get("debug_log", "")

    db_context = ""
    try:
        db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
        if not os.path.isabs(db_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.abspath(os.path.join(project_root, db_path))
            
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Simple keyword match to find related projects
            cursor.execute("""
                SELECT p.ProjectNumber, p.customer, w.overview, w.engagement_summary, w.scope, w.tech_landscape, w.key_deliverables, w.missing_items, w.next_steps, w.quick_summary
                FROM Project p
                JOIN ProjectWorkPackage w ON p.project_id = w.project_id
            """)
            rows = cursor.fetchall()
            db_matched_content = ""
            for r in rows:
                pnum = str(r["ProjectNumber"] or "").lower()
                pcust = str(r["customer"] or "").lower()
                
                # Search in current query AND history for context
                combined_q = (query + " " + " ".join([m["content"] for m in history])).lower()
                
                # If the query/history mentions the project number or customer name, inject the WP fields!
                if (pnum and pnum in combined_q) or (pcust and pcust in combined_q) or any(word in combined_q for word in pcust.split() if len(word) > 3):
                    md = f"📊 **Project:** {r['ProjectNumber']} ({r['customer']})\n\n"
                    
                    if r['overview']: md += f"## 1. Project Overview\n{r['overview']}\n\n"
                    if r['engagement_summary']: md += f"## 2. Engagement Summary\n{r['engagement_summary']}\n\n"
                    if r['scope']: md += f"## 3. Scope & Work Packages\n{r['scope']}\n\n"
                    if r['tech_landscape']: md += f"## 4. Technical Landscape\n{r['tech_landscape']}\n\n"
                    if r['key_deliverables']: md += f"## 5. Key Deliverables\n{r['key_deliverables']}\n\n"
                    if r['missing_items']: md += f"## 6. Missing / Open Items\n{r['missing_items']}\n\n"
                    if r['next_steps']: md += f"## 7. Next Steps\n{r['next_steps']}\n\n"
                    if r['quick_summary']: md += f"### Quick Reference Summary\n{r['quick_summary']}\n\n"
                    
                    db_matched_content += md
                    
            conn.close()
            
            # If we found a direct DB match for the project details, return it immediately!
            if db_matched_content:
                report = f"--- {AGENT_NAME} Report (from Database) ---\n{db_matched_content}\n"
                return {
                    "agent_outputs": current_outputs + [report],
                    "debug_log": debug + f"\n✅ {AGENT_NAME}: answered directly from Database Work Packages.",
                }
    except Exception as e:
        debug += f"\n⚠️ Forecast Agent DB extraction error: {e}"

    context = similarity_search(COLLECTION, query, k=3)
    
    if not context.strip():
        msg = f"❌ {AGENT_NAME}: No relevant context found in planning documents or structured database."
        return {
            "agent_outputs": current_outputs + [msg],
            "debug_log": debug + f"\n❌ {AGENT_NAME}: no context.",
        }

    system_prompt = (
        f"You are the {PERSONA}.\n"
        "Answer the user query using ONLY the Context below. "
        "If the answer is not in the context, say you don't know — "
        "never invent figures.\n\n"
        f"Context:\n{context}"
    )

    messages = [SystemMessage(content=system_prompt)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            from langchain_core.messages import AIMessage
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=query))

    response = llm.invoke(messages)

    report = f"--- {AGENT_NAME} Report ---\n{response.content}\n"
    return {
        "agent_outputs": current_outputs + [report],
        "debug_log": debug + f"\n✅ {AGENT_NAME}: answered from {COLLECTION}.",
    }
