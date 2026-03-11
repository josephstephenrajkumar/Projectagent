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

llm = get_llm()

COLLECTION = "plan-forecast_collection"
AGENT_NAME = "Plan-Forecast Agent"
PERSONA = "Programme Specialist – expert in project planning and resource forecasting"


def forecast_agent_node(state: AgentState) -> dict:
    query = state["query"]
    current_outputs = state.get("agent_outputs", [])
    debug = state.get("debug_log", "")

    context = similarity_search(COLLECTION, query, k=3)

    if not context.strip():
        msg = f"❌ {AGENT_NAME}: No relevant context found in planning documents."
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

    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=query)]
    )

    report = f"--- {AGENT_NAME} Report ---\n{response.content}\n"
    return {
        "agent_outputs": current_outputs + [report],
        "debug_log": debug + f"\n✅ {AGENT_NAME}: answered from {COLLECTION}.",
    }
