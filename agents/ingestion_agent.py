"""
Agent Mesh – Ingestion Agent
Ingests uploaded project documents (contract, estimation-milestone)
into per-project ChromaDB collections, attaching project metadata
(project_name, project_code, opportunity_id) to every chunk.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resolve_path(env_val):
    if os.path.isabs(env_val):
        return env_val
    return os.path.abspath(os.path.join(PROJECT_ROOT, env_val))


CHROMA_DB_PATH = resolve_path(os.getenv("CHROMA_DB_PATH", "./data/chroma_db"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2")


def _ingest_file(
    file_path: str,
    collection_name: str,
    db_path: str = CHROMA_DB_PATH,
    metadata: dict | None = None,
) -> str:
    """
    Ingest a single file into a named ChromaDB collection.
    Attaches project metadata (project_name, project_code, opportunity_id)
    to every document chunk so it can be filtered or retrieved later.
    """
    import chromadb
    from langchain_community.document_loaders import UnstructuredFileLoader
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    if not os.path.exists(file_path):
        return f"❌ File not found: {file_path}"

    client = chromadb.PersistentClient(path=db_path)
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    # Delete stale collection if it exists
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    loader = UnstructuredFileLoader(file_path)
    docs = loader.load()
    if not docs:
        return f"❌ No content extracted from: {file_path}"

    splits = splitter.split_documents(docs)

    # Embed project metadata into each chunk's metadata dict
    if metadata:
        for doc in splits:
            if doc.metadata is None:
                doc.metadata = {}
            for key, val in metadata.items():
                if val is not None:
                    doc.metadata[key] = str(val)

    Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embeddings,
    ).add_documents(splits)

    return f"✅ Indexed {len(splits)} chunks → {collection_name} (with metadata: {list((metadata or {}).keys())})"


def ingestion_agent_node(state: dict) -> dict:
    """
    Ingest uploaded project documents into ChromaDB collections.

    Expects state keys:
      - uploaded_files: list of absolute file paths
      - project_code: used to namespace the collection names
      - project_name: embedded as metadata in every chunk
      - opportunity_id: embedded as metadata in every chunk
    """
    uploaded_files = state.get("uploaded_files", [])
    project_code = state.get("project_code", "unknown")
    project_name = state.get("project_name", "")
    opportunity_id = state.get("opportunity_id", "")
    debug = state.get("debug_log", "")

    if not uploaded_files:
        return {
            "debug_log": debug + "\n❌ Ingestion Agent: no files to ingest.",
            "collection_names": [],
        }

    safe_code = project_code.replace(" ", "_").replace("-", "_").lower()
    collection_names = []
    results = []

    # Metadata to attach to every document chunk
    chunk_metadata = {
        "project_name": project_name,
        "project_code": project_code,
        "opportunity_id": opportunity_id,
    }

    for fpath in uploaded_files:
        basename = os.path.splitext(os.path.basename(fpath))[0]
        ext = os.path.splitext(fpath)[1].lower()
        name_lower = basename.lower()

        if "estimat" in name_lower or "milestone" in name_lower or ext == ".xlsx":
            col_name = f"{safe_code}_estimation_milestone_collection"
            chunk_metadata["doc_type"] = "estimation-milestone"
        elif "contract" in name_lower or "sow" in name_lower or ext == ".docx":
            col_name = f"{safe_code}_contract_collection"
            chunk_metadata["doc_type"] = "contract"
        else:
            col_name = f"{safe_code}_{basename.replace(' ', '_').lower()}_collection"
            chunk_metadata["doc_type"] = "other"

        msg = _ingest_file(fpath, col_name, metadata=chunk_metadata)
        collection_names.append(col_name)
        results.append(msg)

    return {
        "debug_log": debug + "\n📥 Ingestion Agent:\n  " + "\n  ".join(results),
        "collection_names": collection_names,
    }
