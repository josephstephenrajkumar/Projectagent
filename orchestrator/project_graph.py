"""
Project Creation LangGraph – a dedicated sub-flow for creating projects.

Phase A (called by /project/create):
  ingestion_agent → data_extraction_agent → return extracted DTO

Phase B (called by /project/confirm):
  db_agent → END
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langgraph.graph import StateGraph, END
from orchestrator.state import AgentState
from agents.ingestion_agent import ingestion_agent_node
from agents.data_extraction_agent import data_extraction_agent_node
from agents.db_agent import db_agent_node


# ── Phase A graph: Ingest → Extract ──────────────────────────────────────

def build_extraction_graph():
    """
    Build a graph that ingests uploaded documents and extracts structured
    project data. Returns the compiled graph.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("ingestion_agent", ingestion_agent_node)
    workflow.add_node("data_extraction_agent", data_extraction_agent_node)

    workflow.set_entry_point("ingestion_agent")
    workflow.add_edge("ingestion_agent", "data_extraction_agent")
    workflow.add_edge("data_extraction_agent", END)

    return workflow.compile()


# ── Phase B graph: DB Agent (confirm & persist) ──────────────────────────

def build_persistence_graph():
    """
    Build a graph that validates and persists confirmed project data.
    Returns the compiled graph.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("db_agent", db_agent_node)

    workflow.set_entry_point("db_agent")
    workflow.add_edge("db_agent", END)

    return workflow.compile()


# Pre-compiled graphs
extraction_app = build_extraction_graph()
persistence_app = build_persistence_graph()
