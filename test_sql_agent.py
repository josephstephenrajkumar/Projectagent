
import sys
import os
import json

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock AgentState
from orchestrator.state import AgentState
from agents.sql_agent import sql_agent_node

def test_sql_generation():
    # 1. Test Project financials (subtotal vs total_project_cost)
    state_proj = {
        "query": "What is the total planned cost for Boston?",
        "history": [
            {"role": "user", "content": "What is the status of Boston?"},
            {"role": "assistant", "content": "The project subtotal is 139000 and status is Open."}
        ],
        "agent_outputs": [],
        "debug_log": "",
        "next_node": ""
    }
    
    # 2. Test RAID Priority (Priority vs Category)
    state_raid = {
        "query": "give me the summary of high priority risk for 202021",
        "history": [],
        "agent_outputs": [],
        "debug_log": "",
        "next_node": ""
    }
    
    print("--- Running SQL Agent Project Test ---")
    res_proj = sql_agent_node(state_proj)
    print(res_proj.get("debug_log", ""))
    
    print("\n--- Running SQL Agent RAID Test ---")
    res_raid = sql_agent_node(state_raid)
    print(res_raid.get("debug_log", ""))
    
    if "total_project_cost" in res_proj.get("debug_log", "") and "Category" in res_raid.get("debug_log", ""):
        print("\n✅ SQL Constraints Working! Corrected both Project and RAID hallucinations.")
    else:
        print("\n❌ SQL Constraints Failed.")

if __name__ == "__main__":
    test_sql_generation()
