"""
Tools: Knowledge base ingestion – loads documents from SOURCE_DATA_DIR,
chunks them, and persists embeddings into ChromaDB.
"""
import os
from dotenv import load_dotenv

load_dotenv()

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
SOURCE_DATA_DIR = os.getenv("SOURCE_DATA_DIR", "./data/docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-mpnet-base-v2")


def build_knowledge_base(
    source_dir: str = SOURCE_DATA_DIR,
    db_path: str = CHROMA_DB_PATH,
    embedding_model: str = EMBEDDING_MODEL,
):
    """
    Ingests every file / sub-folder in `source_dir` into ChromaDB.
    Each top-level item becomes its own collection, named after the file stem.
    """
    import chromadb
    from langchain_community.document_loaders import (
        DirectoryLoader,
        UnstructuredFileLoader,
    )
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    if not os.path.exists(source_dir):
        print(f"❌ Source directory '{source_dir}' not found.")
        return {}

    client = chromadb.PersistentClient(path=db_path)
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    # Wipe stale collections so we always start fresh
    for col in client.list_collections():
        try:
            client.delete_collection(col.name)
        except Exception:
            pass

    collections: dict[str, str] = {}
    print("\n🚀 Starting ingestion …")

    for item_name in os.listdir(source_dir):
        if item_name.startswith("."):
            continue
        file_path = os.path.join(source_dir, item_name)
        safe_name = (
            os.path.splitext(item_name)[0].replace(" ", "_").lower()
            + "_collection"
        )

        try:
            if os.path.isdir(file_path):
                loader = DirectoryLoader(
                    file_path, glob="**/*", loader_cls=UnstructuredFileLoader
                )
            else:
                loader = UnstructuredFileLoader(file_path)

            docs = loader.load()
            if not docs:
                continue

            splits = splitter.split_documents(docs)
            Chroma(
                client=client,
                collection_name=safe_name,
                embedding_function=embeddings,
            ).add_documents(splits)
            collections[item_name] = safe_name
            print(f"   ✅ Indexed: {item_name} → {safe_name}")

        except Exception as exc:
            print(f"   ❌ Error on {item_name}: {exc}")

    return collections


if __name__ == "__main__":
    build_knowledge_base()
