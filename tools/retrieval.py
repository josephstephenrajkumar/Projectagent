"""
Tools: RAG retrieval helper – returns a LangChain retriever for a given
ChromaDB collection.
"""
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
def resolve_path(env_val):
    if os.path.isabs(env_val): return env_val
    return os.path.abspath(os.path.join(PROJECT_ROOT, env_val))

CHROMA_DB_PATH = resolve_path(os.getenv("CHROMA_DB_PATH", "./data/chroma_db"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2")

# Lazy singletons so embedding model is loaded only once
_client = None
_embeddings = None


def _get_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _client


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def get_retriever(collection_name: str, k: int = 3):
    """Return a LangChain retriever for the given ChromaDB collection."""
    from langchain_chroma import Chroma

    db = Chroma(
        client=_get_client(),
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
    )
    return db.as_retriever(search_kwargs={"k": k})


def similarity_search(collection_name: str, query: str, k: int = 3) -> str:
    """Convenience wrapper: returns raw context string for RAG agents."""
    try:
        retriever = get_retriever(collection_name, k=k)
        docs = retriever.invoke(query)
        return "\n\n".join(d.page_content for d in docs)
    except Exception as exc:
        return ""


def list_collections() -> list[str]:
    """Return all known collection names in the vector store."""
    try:
        return [c.name for c in _get_client().list_collections()]
    except Exception:
        return []
