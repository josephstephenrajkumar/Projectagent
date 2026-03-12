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
    # Conversation history (list of OpenClaw messages)
    history: List[dict]
    # Execution trace for the "Thinking Process" panel in the UI
    debug_log: str
    # ── Project-creation fields ──────────────────────────────────
    project_name: Optional[str]
    project_code: Optional[str]
    opportunity_id: Optional[str]
    uploaded_files: Optional[List[str]]       # file paths from upload
    extracted_data: Optional[dict]            # extracted project DTO
    user_confirmed: Optional[bool]            # user confirmed extraction
    operation_mode: Optional[str]             # "chat" | "create_project"
    collection_names: Optional[List[str]]     # collections created by ingestion
