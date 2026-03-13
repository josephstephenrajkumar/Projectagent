import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from orchestrator.llm_factory import get_llm
from tools.retrieval import similarity_search
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.document_loaders import UnstructuredFileLoader

llm = get_llm()

WORK_PACKAGE_PROMPT = """You are an expert contract analyst. From the SOW/contract context below,
identify every distinct phase or work package (e.g. WP001 Design, WP002 Deployment, WP003 Pilot, etc.).
Try to find ALL of them (there should be around 11). Look specifically in Appendix A or the work packages section.

Return ONLY a JSON array of objects with simply the "phase_name" to prove you found them:
[
  {{
    "phase_name": "string"
  }}
]

--- Contract Document Context ---
{contract_context}
"""

def test_rag(k=10):
    print(f"\n--- Testing RAG with k={k} ---")
    query = "appendix A work packages phases scope deliverables list of all work packages phase 1 phase 2"
    
    # We need the contract collection name
    # Boston_Property_SMAX_Migration_SOW_v0.4.docx -> project code was 202021
    col_name = "202021_contract_collection"
    
    context = similarity_search(col_name, query, k=k)
    print(f"Retrieved Context Length: {len(context)} chars")
    
    prompt = WORK_PACKAGE_PROMPT.format(contract_context=context)
    res = llm.invoke([SystemMessage(content=prompt), HumanMessage(content="extract the work packages")])
    print(res.content)


def test_full_doc():
    print(f"\n--- Testing Full Document Load ---")
    path = "data/docs/projects/202021/Boston_Property_SMAX_Migration_SOW_v0.4.docx"
    if not os.path.exists(path):
        print("File not found:", path)
        return
        
    loader = UnstructuredFileLoader(path)
    docs = loader.load()
    text = "\n".join(d.page_content for d in docs)
    print(f"Full text length: {len(text)} chars")
    
    prompt = WORK_PACKAGE_PROMPT.format(contract_context=text)
    try:
        res = llm.invoke([SystemMessage(content=prompt), HumanMessage(content="extract the work packages")])
        print(res.content)
    except Exception as e:
        print("LLM Error:", e)

if __name__ == "__main__":
    test_rag(k=10)
    test_rag(k=30)
    test_full_doc()
