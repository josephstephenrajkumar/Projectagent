"""
Agent Mesh – RAID Update Agent
Parses natural language input to automatically create or update RAID items in the SQLite database.
"""
import sys
import os
import sqlite3
import json
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

llm = get_llm()

RAID_EXTRACTION_PROMPT = """You are an expert project management assistant.
The user wants to record or update a RAID (Risk, Action, Issue, Decision, Assumption, Dependency) item for a project.

Extract the details from the user's message into a strict JSON format. 
If a field is not mentioned, use null.
For dates, use 'YYYY-MM-DD' format if mentioned (e.g. DueDate). If "today" is mentioned, use today's date.
For Status, use 'Open', 'WIP', 'Closed', 'Resolved' or whatever is stated. Default to 'Open' if not stated for new items.
For Priority/Category, try to infer (High, Medium, Low) or the specific topic (e.g., API, Integration).
For ROAM, (Resolved, Owned, Accepted, Mitigated).

You must also determine the INTENT: "CREATE" (new item) or "UPDATE" (amending an existing one).
If updating, try to extract the specific RAID ID or a very clear description of what is being updated.
ALWAYS extract the Project Number or Opportunity ID if mentioned.

SPECIAL CASE: If the user states that a "PO is not yet received" or "missing PO" or similar for a project (like "Boston Project"):
- Set Type to "Risk"
- Set Priority to "High"
- Description should mention that without a PO, the project start date is at risk.
- Ensure the project identifier (e.g. "Boston") is extracted to project_identifier.


Return ONLY valid JSON with this exact schema:
{
  "intent": "CREATE" or "UPDATE",
  "project_identifier": "string or null",
  "raid_id_to_update": "string or null",
  "Type": "Risk/Action/Issue/Decision/Assumption/Dependency or null",
  "Priority": "string or null",
  "owner": "string or null",
  "Description": "string or null",
  "MitigatingAction": "string or null",
  "DueDate": "YYYY-MM-DD or null",
  "ROAM": "string or null",
  "Status": "string or null",
  "Status_summary_append": "string or null (Any new update message to append to the log)"
}
"""

def _extract_raid_data(query: str) -> dict:
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prompt = RAID_EXTRACTION_PROMPT + f"\nNote: Today's date is {today_str}."
    
    try:
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query)
        ])
        content = response.content.strip()
        # Clean markdown code blocks if the LLM wraps the JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content.strip())
    except Exception as e:
        print(f"Extraction error: {e}")
        return None

def _get_db_path():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_val = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
    return env_val if os.path.isabs(env_val) else os.path.abspath(os.path.join(project_root, env_val))

def _find_project(cursor, identifier):
    if not identifier: return None
    # 1. Try exact matches first
    cursor.execute("SELECT project_id, startdateContract FROM Project WHERE ProjectNumber = ? OR OpportunityID = ?", (identifier, identifier))
    row = cursor.fetchone()
    if row: return row
    
    # 2. Try fuzzy match on customer name with full identifier
    cursor.execute("SELECT project_id, startdateContract FROM Project WHERE LOWER(customer) LIKE ?", (f"%{identifier.lower()}%",))
    row = cursor.fetchone()
    if row: return row

    # 3. If identifier contains multiple words, try matching them individually (prioritizing ID-like strings)
    parts = identifier.replace(",", " ").split()
    if len(parts) > 1:
        # Prioritize parts that look like IDs (contain numbers or dashes)
        for p in sorted(parts, key=lambda x: (any(c.isdigit() for c in x), "-" in x), reverse=True):
            if len(p) < 3: continue
            cursor.execute("SELECT project_id, startdateContract FROM Project WHERE ProjectNumber = ? OR OpportunityID = ?", (p, p))
            row = cursor.fetchone()
            if row: return row
            
        # Then try fuzzy match on names for each part
        for p in parts:
            if len(p) < 3: continue
            cursor.execute("SELECT project_id, startdateContract FROM Project WHERE LOWER(customer) LIKE ?", (f"%{p.lower()}%",))
            row = cursor.fetchone()
            if row: return row
            
    return None

def raid_update_agent_node(state: dict) -> dict:
    query = state.get("query", "")
    debug = state.get("debug_log", "")
    
    debug += "\n🧠 RAID Update Agent: Parsing natural language for RAID fields..."
    extracted = _extract_raid_data(query)
    
    if not extracted:
        return {
            "response": "❌ I couldn't clearly understand the RAID item details from your message. Could you clarify what you'd like to add or update?",
            "debug_log": debug + "\n❌ Failed to extract JSON."
        }
        
    intent = extracted.get("intent", "CREATE")
    identifier = extracted.get("project_identifier")
    
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return {"response": "Database not found.", "debug_log": debug}
        
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        proj_row = _find_project(cursor, identifier) if identifier else None
        project_id = proj_row["project_id"] if proj_row else None
        
        if not project_id and intent == "CREATE":
            debug += "\n⚠️ Could not find a matching project to attach the RAID item to."
            conn.close()
            return {
                "response": f"⚠️ I couldn't find a project matching '{identifier}'. **Please provide the Opportunity ID or exact Project Number** so I can accurately log this risk/issue.",
                "debug_log": debug
            }
            
        # Special logic check: Missing PO and Start Date comparison
        if intent == "CREATE" and proj_row and "po" in str(extracted.get("Description", "")).lower() and extracted.get("Priority") == "High":
            start_date = proj_row["startdateContract"]
            if start_date:
                extracted["Description"] = f"{extracted.get('Description', '')} Project start date is {start_date}, creating immediate schedule risk."
                extracted["MitigatingAction"] = "Confirm with client procurement and delay kickoff if necessary."
                
        now_str = datetime.now(timezone.utc).isoformat()
        
        if intent == "CREATE":
            # INSERT NEW
            new_id = f"RAID-{str(uuid.uuid4())[:8].upper()}"
            
            # Formulate initial status summary
            init_summary = f"[{now_str}] Item Created.\n"
            if extracted.get("Status_summary_append"):
                init_summary += f"[{now_str}] {extracted.get('Status_summary_append')}\n"
                
            cursor.execute("""
                INSERT INTO RAIDitems (
                    raidID, project_id, LastupdateDate, Type, Category, owner, 
                    Description, MitigatingAction, DueDate, ROAM, StartDate, Status, Status_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                new_id,
                project_id,
                now_str,
                extracted.get("Type", "Risk"),
                extracted.get("Priority", "Medium"),
                extracted.get("owner", "Unassigned"),
                extracted.get("Description", "No description provided."),
                extracted.get("MitigatingAction", ""),
                extracted.get("DueDate", ""),
                extracted.get("ROAM", ""),
                now_str, # StartDate
                extracted.get("Status", "Open"),
                init_summary
            ))
            
            conn.commit()
            conn.close()
            
            debug += f"\n✅ RAID Update Agent: Created new item {new_id}."
            
            md = f"✅ **Successfully created new RAID item:**\n\n"
            md += f"- **ID:** `{new_id}`\n"
            md += f"- **Type:** {extracted.get('Type', 'Risk')} | **Priority:** {extracted.get('Priority', 'Medium')}\n"
            md += f"- **Owner:** {extracted.get('owner', 'Unassigned')}\n"
            md += f"- **Due Date:** {extracted.get('DueDate', 'Not set')}\n"
            md += f"- **Description:** {extracted.get('Description')}\n"
            if extracted.get("MitigatingAction"):
                md += f"- **Action/Mitigation:** {extracted.get('MitigatingAction')}\n"
                
            return {"response": md, "debug_log": debug}
            
        elif intent == "UPDATE":
            # UPDATE EXISTING
            # We need raid_id_to_update, or we have to guess it based on description + project_id
            raid_id = extracted.get("raid_id_to_update")
            desc_search = extracted.get("Description", "")
            
            if not raid_id and project_id and desc_search:
                # Try to find by description matching
                cursor.execute("SELECT raidID, Status_summary FROM RAIDitems WHERE project_id = ? AND Description LIKE ?", (project_id, f"%{desc_search[:15]}%"))
                rows = cursor.fetchall()
                if len(rows) == 1:
                    raid_id = rows[0]["raidID"]
            
            if not raid_id:
                # Still don't have it, try global search if they just gave the ID but no project
                cursor.execute("SELECT raidID FROM RAIDitems WHERE raidID = ?", (extracted.get("raid_id_to_update"),))
                res = cursor.fetchone()
                if res: raid_id = res["raidID"]
                
            if not raid_id:
                conn.close()
                return {
                    "response": "⚠️ Please specify exactly which RAID item you want to update (e.g. 'Update RAID-A1B2C3D4') or provide enough description to match it uniquely.",
                    "debug_log": debug + "\n⚠️ Update failed: raidID could not be deduced."
                }
                
            # Fetch current to append summary
            cursor.execute("SELECT Status_summary FROM RAIDitems WHERE raidID = ?", (raid_id,))
            curr_row = cursor.fetchone()
            curr_summary = curr_row["Status_summary"] if curr_row and curr_row["Status_summary"] else ""
            
            new_summary = curr_summary
            if extracted.get("Status_summary_append"):
                new_summary += f"[{now_str}] {extracted.get('Status_summary_append')}\n"
                
            # Build dynamic update query 
            updates = []
            params = []
            
            fields_to_check = ["Type", "Priority", "owner", "Description", "MitigatingAction", "DueDate", "ROAM", "Status"]
            db_fields = ["Type", "Category", "owner", "Description", "MitigatingAction", "DueDate", "ROAM", "Status"]
            
            for f_in, f_db in zip(fields_to_check, db_fields):
                val = extracted.get(f_in)
                if val is not None:
                    updates.append(f"{f_db} = ?")
                    params.append(val)
                    
            updates.append("Status_summary = ?")
            params.append(new_summary)
            
            updates.append("LastupdateDate = ?")
            params.append(now_str)
            
            # If nothing to update besides timestamp
            if len(updates) == 2:
                conn.close()
                return {"response": "No fields were detected to update.", "debug_log": debug}
                
            query_str = f"UPDATE RAIDitems SET {', '.join(updates)} WHERE raidID = ?"
            params.append(raid_id)
            
            cursor.execute(query_str, tuple(params))
            conn.commit()
            conn.close()
            
            debug += f"\n✅ RAID Update Agent: Updated item {raid_id}."
            
            md = f"✅ **Successfully updated RAID item `{raid_id}`.**\n\nFields modified included:\n"
            for f in fields_to_check:
                if extracted.get(f) is not None:
                    md += f"- **{f}:** {extracted.get(f)}\n"
            if extracted.get("Status_summary_append"):
                md += f"- Added to Status Log.\n"
                
            return {"response": md, "debug_log": debug}

    except Exception as e:
        debug += f"\n❌ Agent DB Error: {e}"
        return {
            "response": f"❌ Failed to access RAID database: {e}",
            "debug_log": debug
        }
