"""
Agent Mesh – Delete Project Agent
Extracts a project identifier (Project Number or Opportunity ID) from the query,
finds it in the database, and permanently deletes it and all associated data.
"""
import sys
import os
import sqlite3
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

llm = get_llm()

DELETE_EXTRACTION_PROMPT = """You are an AI assistant that extracts project identifiers from text.
The user wants to delete a project.
Extract either the Project Number (e.g., 202021) or Opportunity ID (e.g., O-1932849) mentioned in the query.
If multiple are found, just return the most obvious one.
Return ONLY the raw identifier string, with no extra text, markdown, or punctuation.
If no clear identifier is found, return exactly: NONE"""

def _extract_identifier(query: str) -> str:
    try:
        response = llm.invoke([
            SystemMessage(content=DELETE_EXTRACTION_PROMPT),
            HumanMessage(content=query)
        ])
        result = response.content.strip()
        if result == "NONE" or not result:
            return ""
        return result
    except Exception:
        return ""

def delete_project_agent_node(state: dict) -> dict:
    query = state.get("query", "")
    debug = state.get("debug_log", "")
    
    # 1. Extract identifier
    identifier = _extract_identifier(query)
    
    if not identifier:
        debug += "\n⚠️ Delete Agent: Could not find a Project Number or Opportunity ID in the request."
        return {
            "response": "Could not identify a clear Project Number or Opportunity ID to delete from your request. Please reply with the exact ID.",
            "debug_log": debug
        }
    
    debug += f"\n🔍 Delete Agent: Extracted identifier '{identifier}'"
    
    # 2. Database connection
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_val = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    db_path = env_val if os.path.isabs(env_val) else os.path.abspath(os.path.join(project_root, env_val))
    
    if not os.path.exists(db_path):
        return {
            "response": "Database not found.",
            "debug_log": debug + "\n❌ Delete Agent: Database not found."
        }
    
    # 3. Locate and delete
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT project_id FROM Project WHERE ProjectNumber = ? OR OpportunityID = ?",
            (identifier, identifier)
        )
        rows = cursor.fetchall()
        
        if not rows:
            conn.close()
            debug += f"\n⚠️ Delete Agent: No project found matching {identifier}."
            return {
                "response": f"❌ Could not find any project with Project Number or Opportunity ID matching '{identifier}'.",
                "debug_log": debug
            }
            
        deleted_count = 0
        for row in rows:
            pid = row[0]
            # Delete child tables
            cursor.execute("DELETE FROM ProjectWorkPackage WHERE project_id = ?", (pid,))
            cursor.execute("DELETE FROM ProjectWeeklySummary WHERE project_id = ?", (pid,))
            # Delete main project
            cursor.execute("DELETE FROM Project WHERE project_id = ?", (pid,))
            deleted_count += 1
            
        conn.commit()
        conn.close()
        
        debug += f"\n✅ Delete Agent: Deleted {deleted_count} project(s) matching '{identifier}'."
        return {
            "response": f"✅ Successfully deleted project '{identifier}' and all its associated work packages.",
            "debug_log": debug
        }
        
    except Exception as exc:
        debug += f"\n❌ Delete Agent error: {exc}"
        return {
            "response": f"❌ An error occurred while trying to delete the project: {exc}",
            "debug_log": debug
        }
