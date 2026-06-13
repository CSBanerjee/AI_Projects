import os                      # lets us read environment variables from the system
from pathlib import Path       # gives us a clean, cross-platform way to work with file paths
from dotenv import load_dotenv # lets us load variables from a .env file into the environment

load_dotenv()  # reads the .env file and loads every KEY=VALUE into os.environ

# ── Paths ─────────────────────────────────────────────────────────────────────
# BASE_DIR resolves to the project root: rag_analytics_assistant/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

LOG_DIR  = BASE_DIR / "logs"   # where log files will be written
DOCS_DIR = BASE_DIR / "docs"   # where source PDF documents live
                                # used in validate() and loader.py
                                # defined once here — never rebuilt elsewhere

# Note: DATA_DIR was removed — it was defined but never used anywhere in the project

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # required — empty string triggers validate()

# ── LangSmith ─────────────────────────────────────────────────────────────────
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "rag-analytics-assistant")

# ── Jira ──────────────────────────────────────────────────────────────────────
JIRA_BASE_URL    = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL       = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN   = os.getenv("JIRA_API_TOKEN", "")   # required — empty string triggers validate()
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "ANALYTICS")

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_SIZE           = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP        = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K_RESULTS        = int(os.getenv("TOP_K_RESULTS", "3"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
# minimum similarity score (0-1) — chunks below this score are ignored
# float() converts the string "0.7" from .env into the number 0.7

# ── Models ────────────────────────────────────────────────────────────────────
MODEL           = os.getenv("MODEL", "gpt-4o")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ── LLM behaviour ─────────────────────────────────────────────────────────────
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
MAX_TOKENS     = int(os.getenv("MAX_TOKENS", "400"))
TEMPERATURE    = float(os.getenv("TEMPERATURE", "0.2"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE  = LOG_DIR / "rag_pipeline.log"


def validate() -> None:
    # ── Check 1: OpenAI API key ───────────────────────────────────────────────
    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY not set.\n"
            "Add it to your .env file: OPENAI_API_KEY=your-key-here\n"
            "Get a key at: https://platform.openai.com/api-keys"
        )

    # ── Check 2: Jira API token ───────────────────────────────────────────────
    if not JIRA_API_TOKEN:
        raise EnvironmentError(
            "JIRA_API_TOKEN not set.\n"
            "Get your token at: https://id.atlassian.com/manage-profile/security/api-tokens\n"
            "Then add it to .env: JIRA_API_TOKEN=your-token-here"
        )

    # ── Check 3: docs/ folder must exist on disk ──────────────────────────────
    # DOCS_DIR is the module-level variable defined above — no need to rebuild it
    if not DOCS_DIR.exists():
        raise FileNotFoundError(
            f"docs/ folder is missing: {DOCS_DIR}\n"
            "Create the folder and add your source documents (.pdf):\n"
            "  mkdir docs\n"
            "  cp your-documents.pdf docs/"
        )

    # ── Create logs/ folder ───────────────────────────────────────────────────
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print("logs/ folder created or already exists")

    # ── Check 4: docs/ folder must have at least one file inside ─────────────
    if not any(DOCS_DIR.iterdir()):
        raise FileNotFoundError(
            f"docs/ folder is empty: {DOCS_DIR}\n"
            "Add your source documents (.pdf) before running the pipeline."
        )

    # ── Check 5: ChromaDB folder ──────────────────────────────────────────────
    chroma_dir = Path(CHROMA_PERSIST_DIR)

    if not chroma_dir.exists():
        chroma_dir.mkdir(parents=True, exist_ok=True)
        print(f"chroma_db/ directory created at: {chroma_dir}")

    # ── Check 6: ChromaDB folder must not be empty ────────────────────────────
    if not any(chroma_dir.iterdir()):
        raise FileNotFoundError(
            f"ChromaDB folder is empty: {chroma_dir}\n"
            "You need to run ingestion before starting the pipeline:\n"
            "  python ingest.py\n"
            "This embeds your documents into ChromaDB so the pipeline can retrieve them."
        )