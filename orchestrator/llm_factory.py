"""
LLM factory: returns a Groq-hosted LLM (openai/gpt-oss-120b).
"""
import os
from dotenv import load_dotenv

load_dotenv()


def get_llm():
    from langchain_groq import ChatGroq
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in .env")
    return ChatGroq(model="openai/gpt-oss-120b", temperature=0.3)
