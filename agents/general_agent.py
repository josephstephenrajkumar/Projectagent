"""
Agent Mesh – General Agent
Handles greetings, off-topic questions, and anything not covered by
the specialist RAG agents. Allowed to use general LLM knowledge freely.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.state import AgentState
from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

llm = get_llm()

SYSTEM_PROMPT = (
    "You are a friendly and knowledgeable assistant. "
    "Answer the user's question helpfully and concisely."
)


def general_agent_node(state: AgentState) -> dict:
    query = state["query"]
    debug = state.get("debug_log", "")

    response = llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)]
    )

    return {
        "response": response.content,
        "debug_log": debug + "\n💬 General Agent: free-form response.",
    }
