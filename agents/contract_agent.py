"""
Agent Mesh – Contract Agent
Answers questions about SOWs, contract terms, milestones, and pricing.
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

# We no longer hardcode a single collection. We search all contract collections, 
# or a specific one if a project code is found.
AGENT_NAME = "Contract Agent"
PERSONA = "Project Manager – expert in contractual terms. CRITICAL: You must prioritize the 'Context' provided below over any past conversation history. Project 202021 is ACTIVE; ignore any historical mentions of it being deleted."

def _extract_project_code_for_filter(query: str, history: list) -> str:
    from langchain_core.messages import SystemMessage, HumanMessage
    prompt = "Extract the Project Code (e.g. BOSTON-001) from the query or history if present. Return ONLY the code, or NONE."
    try:
        combined = query + " ".join([m.get("content", "") for m in history])
        res = llm.invoke([SystemMessage(content=prompt), HumanMessage(content=combined)])
        val = res.content.strip()
        return "" if val == "NONE" else val
    except:
        return ""

def contract_agent_node(state: AgentState) -> dict:
    query = state["query"]
    history = state.get("history", [])
    current_outputs = state.get("agent_outputs", [])
    debug = state.get("debug_log", "")
    
    # 1. Try to find a target project to filter RAG
    target_project = _extract_project_code_for_filter(query, history)
    where_filter = {"project_code": target_project} if target_project else None
    
    if target_project:
        debug += f"\n🔍 {AGENT_NAME}: Filtering RAG search for project '{target_project}'"
    
    # 2. Search ChromaDB
    # Ingestion names contract collections as <safe_code>_contract_collection
    # If we know the project, we can target it directly. If not, we'd have to search all.
    # For simplicity, if we have a target, we construct the exact collection name:
    context = ""
    target_collection = ""
    
    if target_project:
        safe_code = target_project.replace(" ", "_").replace("-", "_").lower()
        target_collection = f"{safe_code}_contract_collection"
        context = similarity_search(target_collection, query, k=5, where=where_filter)
    else:
        # Fallback: without a specific project, we can't easily guess which of the N collections to search
        # unless we iterate them. For this demo, we'll try a default or warn the user.
        from tools.retrieval import list_collections
        all_cols = list_collections()
        contract_cols = [c for c in all_cols if "contract_collection" in c]
        for c in contract_cols:
            c_ctx = similarity_search(c, query, k=2)
            if c_ctx:
                context += f"\n--- From {c} ---\n{c_ctx}"
    
    if not context.strip():
        msg = f"❌ {AGENT_NAME}: No relevant contract context found. Please specify a Project Code."
        return {
            "agent_outputs": current_outputs + [msg],
            "debug_log": debug + f"\n❌ {AGENT_NAME}: no context found.",
        }

    system_prompt = (
        f"You are the {PERSONA}.\n"
        "Answer the user query using ONLY the Context below. "
        "If the answer is not in the context, say you don't know — "
        "never fabricate contract terms.\n\n"
        f"Context:\n{context}"
    )

    messages = [SystemMessage(content=system_prompt)]
    for msg in history:
        from langchain_core.messages import AIMessage
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
            
    messages.append(HumanMessage(content=query))
    response = llm.invoke(messages)

    report_source = f" (Filtered to {target_project})" if target_project else " (Across all contracts)"
    report = f"--- 📜 {AGENT_NAME} Report{report_source} ---\n{response.content}\n"
    
    return {
        "agent_outputs": current_outputs + [report],
        "debug_log": debug + f"\n✅ {AGENT_NAME}: answered using RAG metadata filtering.",
    }
