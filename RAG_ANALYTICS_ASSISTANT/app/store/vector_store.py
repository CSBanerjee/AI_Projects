from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from pathlib import Path
from app.config import settings
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)

COLLECTION_NAME = "analytics_docs"


def get() -> Chroma:
    embeddings = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.OPENAI_API_KEY
    )
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=settings.CHROMA_PERSIST_DIR
    )


def add_documents(chunks: list) -> None:
    vs = get()
    vs.add_documents(chunks)
    log_event(log, "info", "documents_stored", count=len(chunks))


def count() -> int:
    # count chunks without connecting to ChromaDB or OpenAI
    # reads the SQLite file that ChromaDB uses internally to store data
    # this is instant — no network calls, no embedding model needed
    try:
        import sqlite3
        chroma_dir = Path(settings.CHROMA_PERSIST_DIR)

        # ChromaDB stores its data in a SQLite file called chroma.sqlite3
        sqlite_path = chroma_dir / "chroma.sqlite3"

        if not sqlite_path.exists():
            return 0
            # ChromaDB not initialised yet — ingest.py has not been run

        conn = sqlite3.connect(str(sqlite_path))
        # query the embeddings table directly
        # ChromaDB stores one row per chunk in this table
        row = conn.execute(
            "SELECT COUNT(*) FROM embeddings"
        ).fetchone()
        conn.close()
        return row[0] if row else 0

    except Exception:
        return 0
        # any error — return 0 rather than crashing the server


def reset() -> None:
    vs = get()
    vs.delete_collection()
    log.warning("event=vector_store_reset collection=analytics_docs")