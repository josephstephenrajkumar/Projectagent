"""
Agent Mesh – Synthesizer
Merges outputs from all specialist agents into a single coherent answer.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.state import AgentState
from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

llm = get_llm()

SUPERVISOR_PROMPT = """You are a Project Manager Supervisor.
Synthesise the following specialist reports into a single, clear, and
structured answer for the client. Highlight any discrepancies between 
reports if present. Do not invent information not found in the reports.

Team Reports:
{reports}"""


def synthesizer_node(state: AgentState) -> dict:
    outputs = state.get("agent_outputs", [])
    debug = state.get("debug_log", "")
    query = state["query"]

    if not outputs:
        return {
            "response": "I could not retrieve information from the agents.",
            "debug_log": debug + "\n⚠️ Synthesizer: no agent outputs to merge.",
        }

    combined = "\n".join(outputs)
    prompt = SUPERVISOR_PROMPT.format(reports=combined)

    response = llm.invoke(
        [SystemMessage(content=prompt), HumanMessage(content=query)]
    )

    return {
        "response": response.content,
        "debug_log": debug + "\n🤖 Synthesizer: merged outputs.",
    }
