"""
Agent Mesh – Risk Agent
Extracts a project identifier (Project Number or Opportunity ID) from the query.
Checks SQLite for `ProjectWorkPackage` baseline risks and `RAIDitems` live operational risks.
If found, builds a risk analysis from the DB.
If not found, searches `contract_collection` via RAG and uses the risk markdown prompt.
"""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tools.retrieval import similarity_search

load_dotenv()

llm = get_llm()

# Prompt to extract the ID from the query
EXTRACTION_PROMPT = """You are an AI assistant that extracts project identifiers (Project Number, Opportunity ID, or SOW ID).

Analyze the conversation history and the current user query.
1. If the current query contains an identifier (e.g., '202021'), return it.
2. If the current query does NOT have an identifier, look at the RECENT conversation history for the most recently discussed project code.
3. Return ONLY the raw identifier string (e.g., '202021').
4. No extra text, markdown, or punctuation.
5. If no identifier is found in query or context, return: NONE"""

# Risk RAG Prompt requested by user
def _get_risk_prompt() -> str:
    return """
You are an expert contract analyst. Extract and analyze risk-related information from the contract document.

Based on the document text provided, identify and format risk information in a professional Markdown format.

Document Text: {document_text}

Extract risk analysis for SOW ID: {sow_id}

Format your response using the following Markdown structure EXACTLY:

# ⚠️ Contract Risk Analysis

**Document ID:** {sow_id}

## 🎯 Risk Assessment Summary
[Provide an overall risk assessment of the contract in 2-3 sentences]

## 📋 Identified Risks

### 🔴 High Risk Items
| Risk Category | Description | Impact | Probability | Mitigation Strategy |
|---------------|-------------|--------|-------------|-------------------|
| [Category] | [Description] | High | [High/Medium/Low] | [Mitigation approach] |

### 🟡 Medium Risk Items
| Risk Category | Description | Impact | Probability | Mitigation Strategy |
|---------------|-------------|--------|-------------|-------------------|
| [Category] | [Description] | Medium | [High/Medium/Low] | [Mitigation approach] |

### 🟢 Low Risk Items
| Risk Category | Description | Impact | Probability | Mitigation Strategy |
|---------------|-------------|--------|-------------|-------------------|
| [Category] | [Description] | Low | [High/Medium/Low] | [Mitigation approach] |

## 🛡️ Risk Mitigation Recommendations
1. **[Priority 1]:** [Detailed recommendation]
2. **[Priority 2]:** [Detailed recommendation]
3. **[Priority 3]:** [Detailed recommendation]

## 📊 Risk Matrix Summary
- **Total Risks Identified:** [Number]
- **High Priority:** [Number]
- **Medium Priority:** [Number]
- **Low Priority:** [Number]

---
*Risk analysis completed for SOW: {sow_id}*
"""


def _extract_identifier(query: str, history: list = None) -> str:
    try:
        messages = [SystemMessage(content=EXTRACTION_PROMPT)]
        if history:
            # Add last 4 turns for context
            for msg in history[-4:]:
                role = msg.get("role")
                content = msg.get("content")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
        
        messages.append(HumanMessage(content=f"Current Query: {query}"))
        
        response = llm.invoke(messages)
        result = response.content.strip()
        if result == "NONE" or not result:
            return ""
        return result
    except Exception:
        return ""


def _build_db_markdown(project: dict, wps: list, raids: list, identifier: str, query: str = "") -> str:
    """Builds the requested markdown format using data from SQLite tables."""
    
    project_number = project.get("ProjectNumber", identifier)
    query_lower = query.lower()
    
    # Identify if user asked for specific priorities
    only_high = "high" in query_lower and "summary" not in query_lower
    only_med = "medium" in query_lower
    only_low = "low" in query_lower
    has_specific_request = only_high or only_med or only_low

    # Basic metrics
    baseline_risk_count = len(wps)
    live_risk_count = sum(1 for r in raids if str(r.get("Type", "")).lower() == "risk")
    issue_count = sum(1 for r in raids if str(r.get("Type", "")).lower() == "issue")
    
    total_items = baseline_risk_count + len(raids)
    
    high_count = sum(1 for r in raids if str(r.get("Status", "")).lower() in ["open", "critical", "high"])
    med_count = sum(1 for r in raids if str(r.get("Status", "")).lower() in ["medium", "in-progress"])
    low_count = sum(1 for r in raids if str(r.get("Status", "")).lower() in ["low", "closed", "resolved"])

    md = f"# ⚠️ Risk Analysis: {project_number}\n\n"
    
    if not has_specific_request:
        md += f"## 🎯 Risk Assessment Summary\n"
        if total_items == 0:
            md += "No baseline risks or operational RAID items recorded.\n\n"
        else:
            md += f"Operational: **{live_risk_count} live risks**, **{issue_count} live issues**. "
            md += f"SOW Baseline: **{baseline_risk_count} risks** identified.\n\n"

    md += f"## 📋 Operational RAID Items\n"
    md += "> [!NOTE]\n"
    md += "> These items are project-level risks/issues and apply across all phases. They are not specific to individual Work Packages.\n\n"

    # Separate RAID items
    high_raids = [r for r in raids if str(r.get("Status", "")).lower() in ["open", "critical", "high"]]
    med_raids = [r for r in raids if str(r.get("Status", "")).lower() not in ["open", "critical", "high", "closed", "resolved", "low"]]
    low_raids = [r for r in raids if str(r.get("Status", "")).lower() in ["closed", "resolved", "low"]]

    def _raid_table(raid_list, impact_label):
        if not raid_list:
            return ""
        tbl = f"| Category | Description | Owner | Due Date | Status | Mitigation |\n"
        tbl += f"|----------|-------------|-------|----------|--------|------------|\n"
        for r in raid_list:
            cat = r.get("Category") or r.get("Type") or "General"
            desc = (r.get("Description") or "").replace("\n", " ").strip()
            owner = r.get("owner", "Unassigned")
            due_date = r.get("DueDate", "No Date")
            mit_action = r.get("MitigatingAction") or r.get("ROAM") or "No mitigation stated"
            tbl += f"| {cat} | {desc} | {owner} | {due_date} | {r.get('Status','Unknown')} | {mit_action} |\n"
        return tbl

    # High Priority Section
    if not has_specific_request or only_high:
        h_table = _raid_table(high_raids, "High")
        if h_table:
            md += f"### 🔴 High Priority\n{h_table}\n"
        elif only_high:
            md += "### 🔴 High Priority\nNo high priority items recorded.\n\n"

    # Medium Priority Section
    if not has_specific_request or only_med:
        m_table = _raid_table(med_raids, "Medium")
        if m_table:
            md += f"### 🟡 Medium Priority\n{m_table}\n"
        elif only_med:
            md += "### 🟡 Medium Priority\nNo medium priority items recorded.\n\n"

    # Low Priority Section
    if not has_specific_request or only_low:
        l_table = _raid_table(low_raids, "Low")
        if l_table:
            md += f"### 🟢 Low / Resolved Items\n{l_table}\n"
        elif only_low:
            md += "### 🟢 Low Priority\nNo low priority items recorded.\n\n"

    # Baseline Section
    if not has_specific_request:
        md += f"## 🛡️ SOW Baseline Risks (Phase-Specific)\n"
        if wps:
            for idx, wp in enumerate(wps):
                phase = wp.get("phase_name", f"Phase {idx+1}")
                r_and_m = wp.get("risks_mitigations", "None documented")
                if r_and_m and r_and_m.lower() != "none":
                    md += f"{idx+1}. **[{phase}]**: {r_and_m}\n"
        else:
            md += "- No baseline risks found.\n"
        md += "\n"

    md += f"---\n*Retrieved for project: {project_number}*"
    return md


def risk_agent_node(state: dict) -> dict:
    query = state.get("query", "")
    debug = state.get("debug_log", "")
    
    # 1. Extract identifier (using history for context)
    history = state.get("history", [])
    identifier = _extract_identifier(query, history)
    
    if not identifier:
        debug += "\n⚠️ Risk Agent: Could not find a clear Project or SOW ID in request. Falling back to semantic search."
        identifier = "Unknown Document"
    else:
        debug += f"\n🔍 Risk Agent: Extracted target ID '{identifier}'"
        
        # 2. Database connection check
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env_val = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
        db_path = env_val if os.path.isabs(env_val) else os.path.abspath(os.path.join(project_root, env_val))
        
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Fetch Project
                cursor.execute("SELECT * FROM Project WHERE ProjectNumber = ? OR OpportunityID = ?", (identifier, identifier))
                proj_row = cursor.fetchone()
                
                if proj_row:
                    proj_id = proj_row["project_id"]
                    
                    # Fetch WorkPackages (Baseline risks)
                    cursor.execute("SELECT phase_name, risks_mitigations FROM ProjectWorkPackage WHERE project_id = ?", (proj_id,))
                    wp_rows = [dict(r) for r in cursor.fetchall()]
                    
                    # Fetch RAIDitems (Operational risks)
                    # Suppressing errors if RAIDitems table doesn't exist yet in heavily modified testing sets
                    raid_rows = []
                    try:
                        cursor.execute("SELECT * FROM RAIDitems WHERE project_id = ?", (proj_id,))
                        raid_rows = [dict(r) for r in cursor.fetchall()]
                    except sqlite3.OperationalError:
                        debug += "\n⚠️ Risk Agent: RAIDitems table not found. Skipping live risks."
                    
                    conn.close()
                    
                    debug += f"\n✅ Risk Agent: Project found in SQLite database. Compiling structured risk report."
                    md_text = _build_db_markdown(dict(proj_row), wp_rows, raid_rows, identifier, query)
                    return {
                        "response": md_text,
                        "debug_log": debug
                    }
                else:
                    conn.close()
            except Exception as exc:
                debug += f"\n⚠️ Risk Agent DB error: {exc}"
    
    # 3. Fallback to RAG if not found in DB
    debug += f"\n⚠️ Risk Agent: '{identifier}' not found in SQLite. Falling back to Vector DB (contract_collection) RAG search."
    
    try:
        context_str = similarity_search("contract_collection", query, k=4)
        
        if not context_str:
            debug += "\n❌ Risk Agent: No relevant context found in ChromaDB either."
            return {
                "response": f"I couldn't find risk analysis information for {identifier} in the database or the uploaded contracts. Please ensure the project is created or the SOW is uploaded.",
                "debug_log": debug
            }
            
        
        rag_prompt = _get_risk_prompt().format(
            document_text=context_str,
            sow_id=identifier
        )
        
        response = llm.invoke([HumanMessage(content=rag_prompt)])
        final_answer = response.content.strip()
        
        # Append suggestion to create project
        suggestion = "\n\n> 💡 **Tip:** This baseline risk analysis was retrieved using semantic search from contract text. For robust live operational risk tracking, please use the **Create Project** flow and track via the RAID log!"
        final_answer += suggestion
        
        return {
            "response": final_answer,
            "debug_log": debug
        }
        
    except Exception as exc:
        debug += f"\n❌ Risk Agent RAG error: {exc}"
        return {
            "response": f"❌ An error occurred while retrieving risk analysis: {exc}",
            "debug_log": debug
        }
