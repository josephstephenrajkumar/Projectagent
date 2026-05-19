import os
import sys
import time
import json
import uuid
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add project root to sys.path so we can import orchestrator modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("❌ Critical Error: The 'mcp' Python SDK is not installed.")
    print("Please install it: pip install mcp")
    sys.exit(1)


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")))
PROCESSED_DATA_FILE = os.path.join(PROJECT_ROOT, "data", "processed_gmail_ids.json")

POLL_INTERVAL_MINUTES = 5


def load_processed_ids() -> set:
    if os.path.exists(PROCESSED_DATA_FILE):
        try:
            with open(PROCESSED_DATA_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_processed_ids(processed: set):
    os.makedirs(os.path.dirname(PROCESSED_DATA_FILE), exist_ok=True)
    with open(PROCESSED_DATA_FILE, "w") as f:
        json.dump(list(processed), f)


def get_active_projects():
    """Fetches ProjectNumber, customer, and project_id for active projects."""
    if not os.path.exists(DB_PATH):
        return []
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT project_id, ProjectNumber, customer FROM Project")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_raid_item(raid_data: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    raid_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO RAIDitems (
            raidID, project_id, LastupdateDate, Type, Category, owner, 
            Description, MitigatingAction, DueDate, Status, Statusdate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        raid_id,
        raid_data.get("project_id"),
        now,
        raid_data.get("Type", "Issue"),
        raid_data.get("Category", "General"),
        raid_data.get("owner", "Unassigned"),
        raid_data.get("Description", ""),
        raid_data.get("MitigatingAction", ""),
        raid_data.get("DueDate", ""),
        "Open",
        now
    ))
    conn.commit()
    conn.close()
    
    print(f"✅ Created RAID item {raid_id} for project {raid_data.get('project_id')} ({raid_data.get('Type')}).")


def classify_email(email_content: str, projects: list) -> dict:
    llm = get_llm()
    
    projects_str = "\n".join([f"- ID: {p['project_id']}, Number: {p['ProjectNumber']}, Customer: {p['customer']}" for p in projects])
    
    sys_prompt = f"""You are an intelligent project management assistant. Your job is to read an intercepted email, determine if it belongs to any of the active projects, and if so, classify it as a RAID item (Risk, Action, Issue, Decision).

ACTIVE PROJECTS:
{projects_str}

Analyze the email. If the email describes an issue, a risk, a pending action, or a recorded decision for ONE of the related projects above, return a JSON object with this exact schema:
{{
    "is_project_related": true,
    "project_id": "the_matching_project_id",
    "Type": "Risk" | "Action" | "Issue" | "Decision",
    "Category": "string (e.g., Technical, Financial, Schedule, Resource)",
    "owner": "string (who should handle this or who is assigned)",
    "Description": "string (a clear summary of the issue/action)",
    "MitigatingAction": "string (any proposed workaround or mitigation mentioned)",
    "DueDate": "YYYY-MM-DD (extract if mentioned, otherwise empty string)"
}}

If the email does not clearly relate to any active project, or is just spam/marketing/unrelated chatter, return:
{{
    "is_project_related": false
}}

OUTPUT ONLY THE PURE JSON FORMATTED TEXT. No markdown fences.
"""

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"EMAIL CONTENT:\n{email_content}")
    ]
    
    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Clean markdown
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "").strip()
        elif "```" in content:
            content = content.replace("```", "").strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"❌ Failed to classify email: {e}")
        return {"is_project_related": False}


async def run_poller():
    print("🚀 Starting Gmail RAID Poller Client...")
    
    processed_ids = load_processed_ids()
    
    # We use uvx mcp-gmail as our server transport. 
    # Ensure uv is installed on the system map it.
    # Use mcp-gmail directly as it is installed via pip
    server_params = StdioServerParameters(
        command="python3",
        args=["/home/joseph/projectAgent/tools/run_mcp_gmail.py"]
    )
    
    while True:
        try:
            print(f"[{datetime.now().isoformat()}] Polling Gmail via MCP...")
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Search for recent emails (last 1 day to be safe, we filter via local state)
                    # The tool 'list_message' returns both snippets and bodies as JSON.
                    search_result = await session.call_tool("list_message", {"query": "newer_than:1d", "max_results": 20})
                    
                    if not search_result or search_result.isError:
                        print("⚠️ Error searching emails:", search_result.content if search_result else 'Unknown')
                    else:
                        text_content = ""
                        for block in search_result.content:
                            if block.type == "text":
                                text_content += block.text + "\n"
                        
                        try:
                            # list_message tool may return a JSON dump of the message list
                            emails_data = json.loads(text_content)
                            if not isinstance(emails_data, list):
                                emails_data = []
                        except ValueError:
                            emails_data = []

                        unprocessed = [msg for msg in emails_data if msg.get("id") and msg.get("id") not in processed_ids]
                        
                        if not unprocessed:
                            print("   No new emails to process.")
                        
                        active_projects = get_active_projects()
                        
                        for msg in unprocessed:
                            eid = msg.get("id")
                            print(f"   Reading email: {eid}")
                            
                            email_text = f"Subject: {msg.get('subject')}\nFrom: {msg.get('sender')}\nDate: {msg.get('date')}\n\n{msg.get('body')}"
                            
                            # Classify with LLM
                            classification = classify_email(email_text, active_projects)
                            
                            if classification.get("is_project_related"):
                                print(f"   ✅ Identified as related! Logging RAID item...")
                                insert_raid_item(classification)
                            else:
                                print(f"   ❌ Not related to any active project.")
                                
                            processed_ids.add(eid)
                            save_processed_ids(processed_ids)
                            
        except Exception as e:
            print(f"❌ Poller Error: {e}")
            
        print(f"💤 Sleeping for {POLL_INTERVAL_MINUTES} minutes...")
        await asyncio.sleep(POLL_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    try:
        asyncio.run(run_poller())
    except KeyboardInterrupt:
        print("\nPoller manually stopped.")
