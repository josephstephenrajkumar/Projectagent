"""
Agent Mesh – Email Agent
Extracts recipient email addresses and content from the user query and chat history.
Simulates sending an email from joseph.stephenr@gmail.com.
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.state import AgentState
from orchestrator.llm_factory import get_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

llm = get_llm()

EMAIL_EXTRACTION_PROMPT = """You are an AI assistant that prepares emails based on chat summaries.

Your task is to:
1. Identify the list of recipient email addresses from the user's current query.
2. Identify the content to be emailed. 
   - If the user says "this" or "the summary", use the MOST RECENT comprehensive report or summary from the assistant in the conversation history.
   - If the user provides specific text, use that.
3. Generate a professional subject line.

Return ONLY a JSON object with this format:
{
  "recipients": ["email1@example.com", "email2@example.com"],
  "subject": "string",
  "body": "string"
}

If no recipients are found, return: {"error": "No recipients found"}
"""

def email_agent_node(state: AgentState) -> dict:
    query = state["query"]
    history = state.get("history", [])
    debug = state.get("debug_log", "")

    # 1. Prepare messages for extraction
    messages = [SystemMessage(content=EMAIL_EXTRACTION_PROMPT)]
    
    # Add relevant history for context (last 6 messages)
    for msg in history[-6:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
            
    messages.append(HumanMessage(content=f"Current Instruction: {query}"))

    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Strip markdown fences if present
        if "```json" in content:
            content = content.split("```json")[-1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[-2].strip()
            
        data = json.loads(content)
        
        if "error" in data:
            return {
                "response": f"❌ Email Error: {data['error']}",
                "debug_log": debug + f"\n❌ Email Agent extraction failed: {data['error']}"
            }
            
        recipients = data.get("recipients", [])
        subject = data.get("subject", "Project Intelligence Summary")
        body = data.get("body", "")
        
        if not recipients:
             return {
                "response": "❌ I couldn't find any email addresses in your request. Please specify who I should send this to.",
                "debug_log": debug + "\n❌ No recipients found."
            }

        # 2. Simulate Sending (Production would use smtplib here)
        from_addr = "joseph.stephenr@gmail.com"
        
        # Log simulation to debug
        debug += f"\n📧 Email Agent simulating send from {from_addr} to {', '.join(recipients)}"
        debug += f"\n   Subject: {subject}"
        
        # 3. Formulate Response
        success_msg = f"✅ **Email Sent Successfully!**\n\n"
        success_msg += f"- **From:** `{from_addr}`\n"
        success_msg += f"- **To:** {', '.join([f'`{r}`' for r in recipients])}\n"
        success_msg += f"- **Subject:** {subject}\n\n"
        success_msg += "---\n"
        success_msg += f"**Content Sent:**\n\n{body[:500]}{'...' if len(body) > 500 else ''}"

        return {
            "response": success_msg,
            "debug_log": debug + "\n✅ Email Agent successfully simulated send.",
            "next_node": "END"
        }

    except Exception as e:
        debug += f"\n❌ Email Agent error: {e}"
        return {
            "response": f"❌ Failed to process email request: {e}",
            "debug_log": debug
        }
