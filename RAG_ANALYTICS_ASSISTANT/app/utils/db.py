import sqlite3
from app.config import settings


def get_connection(db_path=None) -> sqlite3.Connection:
    # db_path: optional — if None uses default path at project root
    # -> sqlite3.Connection → live connection to the SQLite database

    path = db_path or (settings.BASE_DIR / "rag_analytics.db")
    # default: /Users/.../rag_analytics_assistant/rag_analytics.db
    # file is created automatically if it does not exist

    conn = sqlite3.connect(str(path))
    # str(path) converts Path object to string — sqlite3 requires a string

    conn.row_factory = sqlite3.Row
    # allows column access by name: row["total_cost_usd"] instead of row[5]

    return conn


def init_db(conn=None) -> None:
    # conn: optional — used in tests to pass an in-memory database
    # creates the query_log table if it does not already exist

    c = conn or get_connection()

    c.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            question_preview  TEXT,
            session_id        TEXT,
            embedding_tokens  INTEGER,
            llm_input_tokens  INTEGER,
            llm_output_tokens INTEGER,
            total_cost_usd    REAL,
            latency_ms        INTEGER,
            guardrail_passed  BOOLEAN,
            escalated         BOOLEAN,
            timestamp         DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.commit()
    # IF NOT EXISTS — safe to call multiple times without wiping existing data