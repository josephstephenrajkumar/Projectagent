"""
Agent Mesh – Plan-Forecast Agent
Answers questions about project hours, milestones, estimations, and forecasting.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.state import AgentState
from orchestrator.llm_factory import get_llm
from tools.retrieval import similarity_search
from langchain_core.messages import SystemMessage, HumanMessage

llm = get_llm()

# Dynamically search estimation collections
AGENT_NAME = "Plan & Forecast Agent"
PERSONA = "Delivery Manager – expert in forecasts. CRITICAL: You must prioritize the 'Context' provided below over any past conversation history. Project 202021 is ACTIVE; if you see data for it, it exists."

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

def forecast_agent_node(state: AgentState) -> dict:
    query = state["query"]
    history = state.get("history", [])
    current_outputs = state.get("agent_outputs", [])
    debug = state.get("debug_log", "")
    
    # 1. Try to find a target project to filter RAG
    target_project = _extract_project_code_for_filter(query, history)
    where_filter = {"project_code": target_project} if target_project else None
    
    context = ""
    
    if target_project:
        debug += f"\n🔍 {AGENT_NAME}: Filtering RAG search for project '{target_project}'"
        safe_code = target_project.replace(" ", "_").replace("-", "_").lower()
        target_collection = f"{safe_code}_estimation_milestone_collection"
        context = similarity_search(target_collection, query, k=5, where=where_filter)
    else:
        from tools.retrieval import list_collections
        all_cols = list_collections()
        target_cols = [c for c in all_cols if "estimation_milestone_collection" in c]
        for c in target_cols:
            c_ctx = similarity_search(c, query, k=2)
            if c_ctx:
                context += f"\n--- From {c} ---\n{c_ctx}"
    
    if not context.strip():
        msg = f"❌ {AGENT_NAME}: No relevant estimation context found. Please specify a Project Code."
        return {
            "agent_outputs": current_outputs + [msg],
            "debug_log": debug + f"\n❌ {AGENT_NAME}: no context found.",
        }

    system_prompt = (
        f"You are the {PERSONA}.\n"
        "Answer the user query using ONLY the Context below. "
        "If the answer is not in the context, say you don't know.\n\n"
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

    report_source = f" (Filtered to {target_project})" if target_project else " (Across all estimations)"
    report = f"--- 📊 {AGENT_NAME} Report{report_source} ---\n{response.content}\n"
    
    return {
        "agent_outputs": current_outputs + [report],
        "debug_log": debug + f"\n✅ {AGENT_NAME}: answered using RAG metadata filtering.",
    }
