
import sys
import os

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.risk_agent import risk_agent_node

def test_risk_context():
    state = {
        "query": "give me the summary of high priority risk",
        "history": [
            {"role": "user", "content": "Tell me about project 202021"},
            {"role": "assistant", "content": "Project 202021 is for Boston Property Limited."} # CONTEXT
        ],
        "debug_log": "",
        "agent_outputs": []
    }
    
    print("--- Running Risk Agent Node Context Test ---")
    result = risk_agent_node(state)
    
    print("\n[DEBUG LOG]")
    print(result.get("debug_log", ""))
    
    if "Retrieved for project: 202021" in result.get("response", "") or "Risk Analysis: 202021" in result.get("response", ""):
        print("\n✅ Context Inheritance Successful! Extracted 202021 from history.")
    else:
        print("\n❌ Context Inheritance Failed or Project not found.")

if __name__ == "__main__":
    test_risk_context()
