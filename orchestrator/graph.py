"""
LangGraph Orchestrator – StateGraph with ACP agent calls.

Flow:
  router_node
      ↓ (conditional edges)
  ┌───┴───────────────┐
  │                   │
  forecast-agent   contract-agent   general-agent
  (via ACP)        (via ACP)        (via ACP)
  └────────┬──────────┘
      synthesizer
      (via ACP)
          ↓
         END

Each specialist call goes through the ACP client → ACP Agent Server (port 8100).
Falls back to direct Python call if ACP server is unavailable.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import StateGraph, END
from orchestrator.state import AgentState
from orchestrator.router import router_node
from orchestrator.acp_client import _call_acp_agent, acp_server_healthy

# Direct imports as fallback when ACP server is down
from agents.forecast_agent import forecast_agent_node as _forecast_direct
from agents.contract_agent import contract_agent_node as _contract_direct
from agents.general_agent import general_agent_node as _general_direct
from agents.synthesizer import synthesizer_node as _synthesizer_direct

_ACP_AVAILABLE: bool | None = None   # cached after first check


def _use_acp() -> bool:
    global _ACP_AVAILABLE
    if _ACP_AVAILABLE is None:
        _ACP_AVAILABLE = acp_server_healthy()
        mode = "ACP" if _ACP_AVAILABLE else "direct (ACP server offline)"
        print(f"🔌 Agent call mode: {mode}")
    return _ACP_AVAILABLE


# ── ACP-enabled agent wrappers ─────────────────────────────────────────────

def forecast_agent_node(state: AgentState) -> dict:
    if _use_acp():
        text = _call_acp_agent("plan-forecast-agent", state["query"])
        current = state.get("agent_outputs", [])
        debug   = state.get("debug_log", "")
        return {
            "agent_outputs": current + [f"--- Plan-Forecast Agent Report (ACP) ---\n{text}\n"],
            "debug_log":     debug + "\n✅ Plan-Forecast Agent: answered via ACP.",
        }
    return _forecast_direct(state)


def contract_agent_node(state: AgentState) -> dict:
    if _use_acp():
        text = _call_acp_agent("contract-agent", state["query"])
        current = state.get("agent_outputs", [])
        debug   = state.get("debug_log", "")
        return {
            "agent_outputs": current + [f"--- Contract Agent Report (ACP) ---\n{text}\n"],
            "debug_log":     debug + "\n✅ Contract Agent: answered via ACP.",
        }
    return _contract_direct(state)


def general_agent_node(state: AgentState) -> dict:
    if _use_acp():
        text  = _call_acp_agent("general-agent", state["query"])
        debug = state.get("debug_log", "")
        return {
            "response":  text,
            "debug_log": debug + "\n💬 General Agent: free-form response via ACP.",
        }
    return _general_direct(state)


def synthesizer_node(state: AgentState) -> dict:
    if _use_acp():
        outputs = state.get("agent_outputs", [])
        text    = _call_acp_agent("synthesizer-agent", state["query"], outputs)
        debug   = state.get("debug_log", "")
        return {
            "response":  text,
            "debug_log": debug + "\n🤖 Synthesizer: merged via ACP.",
        }
    return _synthesizer_direct(state)


# ── Conditional edge ───────────────────────────────────────────────────────

def _route_decision(state: AgentState):
    decision = state["next_node"]
    if decision == "both":
        return ["plan-forecast_agent", "contract_agent"]
    if decision == "plan-forecast_agent":
        return ["plan-forecast_agent"]
    if decision == "contract_agent":
        return ["contract_agent"]
    return "general_agent"


# ── Build Graph ────────────────────────────────────────────────────────────

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("router",               router_node)
    workflow.add_node("plan-forecast_agent",  forecast_agent_node)
    workflow.add_node("contract_agent",       contract_agent_node)
    workflow.add_node("general_agent",        general_agent_node)
    workflow.add_node("synthesizer",          synthesizer_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges(
        "router",
        _route_decision,
        {
            "plan-forecast_agent": "plan-forecast_agent",
            "contract_agent":      "contract_agent",
            "general_agent":       "general_agent",
        },
    )

    workflow.add_edge("plan-forecast_agent", "synthesizer")
    workflow.add_edge("contract_agent",      "synthesizer")
    workflow.add_edge("synthesizer",         END)
    workflow.add_edge("general_agent",       END)

    return workflow.compile()


app = build_graph()
