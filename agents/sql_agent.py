"""
Agent Mesh – Text-to-SQL Dynamic Agent
First responder for all user queries. Infers intent against the SQLite schema.
Generates read-only SELECT queries. If the query cannot be answered by the DB,
it falls back to the RAG specialist router.
"""
import sys
import os
import sqlite3
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.state import AgentState
from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

llm = get_llm()

AGENT_NAME = "SQL Inference Agent"

# The precise schema layer representation of our database
SCHEMA_LAYER = """
Table: Project
Columns:
- project_id (TEXT, Primary Key)
- ProjectNumber (TEXT, e.g., 'P-123')
- OpportunityID (TEXT)
- customer (TEXT)
- end_customer (TEXT)
- startdateContract (DATETIME)
- endDateContract (DATETIME)
- total_project_cost (FLOAT, Total contractual cost)
- travel_cost (FLOAT)
- other_cost (FLOAT)
- ActiveCurrency (TEXT)
- Proj_Stage (TEXT, e.g. Open/Close)
- Project_Owner (TEXT)

Table: ProjectWorkPackage
Columns:
- wp_id (TEXT, Primary Key)
- project_id (TEXT, Foreign Key to Project)
- phase_name (TEXT)
- phase_order (INTEGER)
- scope (TEXT)
- deliverables (TEXT)
- activities (TEXT)
- tech_landscape (TEXT)
- quick_summary (TEXT)

Table: RAIDitems
Columns:
- raidID (TEXT, Primary Key)
- project_id (TEXT, Foreign Key to Project)
- LastupdateDate (DATETIME)
- Type (TEXT, e.g. Risk, Issue, Action, Decision)
- Category (TEXT, e.g. High, Medium, Low)
- owner (TEXT)
- Description (TEXT)
- MitigatingAction (TEXT)
- DueDate (DATETIME)
- Status (TEXT, Open, Closed)
- Status_summary (TEXT)

Table: ProjectWeeklySummary
Columns:
- WeeklyID (TEXT, Primary Key)
- project_id (TEXT, FK)
- date (DATETIME)
- Summary (TEXT)
- overallStatus (TEXT, Green/Amber/Red)
- FinancialPerformance (TEXT)
- Schedule (TEXT)

Table: MBRitems
Columns:
- mbr_id (TEXT, Primary Key)
- project_id (TEXT, FK)
- ForecastDateMonth (DATETIME)
- ForecastAmount (FLOAT)
- Status (TEXT)

Table: SemanticMap (Glossary)
Columns:
- keyword (TEXT, e.g. 'overdue', 'high priority')
- entity (TEXT, e.g. 'RAIDitems')
- attribute (TEXT, e.g. 'DueDate')
- filter_logic (TEXT, e.g. 'DueDate < date()')
"""

def _get_semantic_glossary() -> str:
    """Fetch user-enhanced semantic mappings to guide the LLM."""
    try:
        db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
        if not os.path.isabs(db_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.abspath(os.path.join(project_root, db_path))
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT keyword, entity, attribute, filter_logic FROM SemanticMap")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return ""
            
        glossary = "\nSEMANTIC GLOSSARY (Mapping user terms to DB schema):\n"
        for kw, ent, attr, filt in rows:
            logic = f" (Logic: {filt})" if filt else ""
            glossary += f"- '{kw}' -> Entity: {ent}, Attribute: {attr}{logic}\n"
        return glossary
    except:
        return ""

def _get_cached_sql(query: str) -> tuple[str, str] | None:
    """Check if a similar successful query exists in the RL cache. Returns (past_query, sql)."""
    try:
        db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
        if not os.path.isabs(db_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.abspath(os.path.join(project_root, db_path))
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT user_query, generated_sql FROM QueryFeedback WHERE feedback_score > 0 ORDER BY feedback_score DESC")
        rows = cursor.fetchall()
        
        words = set(query.lower().split())
        for q_text, sql_text in rows:
            past_words = set(q_text.lower().split())
            intersection = words.intersection(past_words)
            # If 70% of current query words match a past successful one, hint it
            if len(intersection) / max(len(words), 1) > 0.7:
                conn.close()
                return q_text, sql_text
        conn.close()
    except:
        pass
    return None

def get_generation_prompt(glossary: str) -> str:
    return f"""
You are an expert SQLite Database Administrator.
You have access to the following SQLite database schema:

{SCHEMA_LAYER}
{glossary}

Your task is to generate a dynamic SQL query to answer the user's question.

CRITICAL RULES:
1. ONLY USE COLUMNS LISTED IN THE SCHEMA ABOVE.
2. NEVER USE 'subtotal', 'total_contract_value', 'currency', 'status', or 'Priority'. These are DEPRECATED and will cause errors.
3. Use 'total_project_cost' for project financials.
4. Use 'Proj_Stage' instead of 'status'.
5. Use 'ActiveCurrency' instead of 'currency'.
6. Use 'Category' instead of 'Priority' for RAIDitems.
7. ALWAYS JOIN Project and ProjectWorkPackage on 'project_id'.
8. STRING COMPARISON: Always use `LIKE '%term%'` instead of `=` for customer names or project numbers.
9. DO NOT interpret project numbers (e.g. 202021) as years. Do NOT add `strftime('%Y', ...)` filters unless the user explicitly mentions a year (e.g. 'in 2021').
10. DO NOT output any markdown blocks (like ```sql). Output ONLY the raw SQL string or the word FALLBACK.
11. RESPONSE FORMAT: Raw SQL string only.
"""

SYNTHESIS_PROMPT = """
You are a Project Intelligence Analyst.
Write a professional response based ONLY on these database results. 

User Question: {query}
SQL Executed: {sql}
Results (JSON): {results}
"""

def sql_agent_node(state: AgentState) -> dict:
    query = state["query"]
    current_outputs = state.get("agent_outputs", [])
    debug = state.get("debug_log", "")
    
    # 1. Fetch Glossary and look for a pattern in RL Cache
    glossary = _get_semantic_glossary()
    cache_hit = _get_cached_sql(query)
    pattern_hint = ""
    if cache_hit:
        past_q, past_sql = cache_hit
        debug += f"\n🧠 {AGENT_NAME}: Found successful pattern from past query: '{past_q}'"
        pattern_hint = f"\nSUCCESSFUL PATTERN (Reference only):\nPast Query: {past_q}\nPast SQL: {past_sql}\n"
    
    # 2. Ask LLM to generate SQL dynamically
    history = state.get("history", [])
    # Limit history to prevent stale schema bias
    sanitized_history = history[-6:]
    messages = [SystemMessage(content=get_generation_prompt(glossary) + pattern_hint)]
    for msg in sanitized_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=f"PAST QUERY: {msg['content']}"))
        else:
            # Mask data to prevent LLM from thinking old column names in data are valid
            messages.append(SystemMessage(content="PAST RESPONSE: [Data provided based on past schema]"))
    
    messages.append(HumanMessage(content=f"Current Objective: {query}"))

    try:
        sql_response = llm.invoke(messages)
        generated_sql = sql_response.content.strip()
        
        # Strip markdown fences
        if "```" in generated_sql:
            generated_sql = generated_sql.split("```")[-2].split("\n", 1)[-1].strip()
        
    except Exception as e:
        debug += f"\n⚠️ {AGENT_NAME}: LLM SQL generation failed: {e}."
        generated_sql = "FALLBACK"

    if generated_sql == "FALLBACK" or not generated_sql.upper().startswith("SELECT"):
        return {
            "next_node": "router", # Route to the existing RAG AI Router
            "debug_log": debug + f"\n🔄 {AGENT_NAME}: Question cannot be answered purely via DB. Triggering RAG fallback.",
            # Only add to output if it's explicitly helpful
            # "agent_outputs": current_outputs + [f"*(SQL Agent passing to Specialized Agents: query does not match DB schema)*"]
        }

    debug += f"\n🔍 {AGENT_NAME} generated SQL:\n{generated_sql}"

    # 2. Execute SQL
    results = []
    try:
        db_path = os.getenv("SQLITE_DB_PATH", "./data/openclaw.db")
        if not os.path.isabs(db_path):
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            db_path = os.path.abspath(os.path.join(project_root, db_path))
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(generated_sql)
        rows = cursor.fetchall()
        for r in rows:
            results.append(dict(r))
            
        conn.close()
    except Exception as e:
        debug += f"\n❌ {AGENT_NAME}: SQL Execution failed: {e}. Falling back."
        return {
            "next_node": "router",
            "debug_log": debug,
            "agent_outputs": current_outputs + [f"*(SQL Agent attempted query but failed: {e}. Falling back to document search.)*"]
        }

    # 3. Handle Empty Results (Trigger Fallback)
    if not results:
        debug += f"\n⚠️ {AGENT_NAME}: SQL returned 0 results for '{generated_sql}'. Triggering RAG fallback."
        return {
            "next_node": "router",
            "debug_log": debug,
            "agent_outputs": current_outputs + [f"*(SQL Agent executed: `{generated_sql}` but found 0 matching records in the database. Falling back to document search.)*"]
        }

    # 4. Synthesize Results
    formatted_results = json.dumps(results, indent=2)
    final_prompt = SYNTHESIS_PROMPT.format(query=query, sql=generated_sql, results=formatted_results)
    
    try:
        messages = [HumanMessage(content=final_prompt)]
        final_response = llm.invoke(messages)
        report = final_response.content.strip()
    except Exception as e:
        report = f"Failed to synthesize SQL results: {e}"

    full_report = f"--- 🗄️ {AGENT_NAME} Report ---\n{report}\n\n**Executed SQL Query:**\n```sql\n{generated_sql}\n```\n"

    return {
        "response": report,
        "agent_outputs": current_outputs + [full_report],
        "debug_log": debug + f"\n✅ {AGENT_NAME}: Successfully answered directly from SQLite schema inference.",
        "next_node": "END" # Answered! Skip the RAG router.
    }
