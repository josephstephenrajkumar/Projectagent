"""
AgentState: shared state that flows through the LangGraph DAG.
Every node reads from and writes to this dictionary.
"""
from typing import TypedDict, List, Optional


class AgentState(TypedDict):
    # The user's input question
    query: str
    # Final synthesized answer returned to the user
    response: str
    # Router decision: which agent(s) to invoke
    next_node: str
    # Accumulated per-agent reports (for multi-agent synthesis)
    agent_outputs: List[str]
    # Execution trace for the "Thinking Process" panel in the UI
    debug_log: str
