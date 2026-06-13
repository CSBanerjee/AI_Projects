# Phase 1 — Project Setup

**Steps:** 8  
**Goal:** Create the complete folder structure, virtual environment, configuration, logging, and source documents. Get this right once — every phase builds on top of it.

---

## Step 1.1 — Create project folder and activate virtual environment

**What you do:**
```bash
mkdir rag_analytics_assistant
cd rag_analytics_assistant
uv venv
```

Activate the virtual environment:
```bash
# Mac / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

**Why uv instead of python -m venv:**
`uv venv` creates the virtual environment significantly faster than the standard Python tool. It also ensures the correct Python version is used automatically.

**Verify:**
```bash
uv --version
```
Terminal prompt shows `(.venv)` at the start after activation.

---

## Step 1.2 — Create all folders and __init__.py files

**What you do:**
```bash
mkdir -p app/config app/ingestion app/store app/retrieval \
         app/generation app/guardrails app/hitl app/api app/utils \
         frontend docs eval/results tests logs chroma_db
```

Create an empty `__init__.py` in every folder under `app/` and in `tests/`:
```
app/__init__.py
app/config/__init__.py
app/ingestion/__init__.py
app/store/__init__.py
app/retrieval/__init__.py
app/generation/__init__.py
app/guardrails/__init__.py
app/hitl/__init__.py
app/api/__init__.py
app/utils/__init__.py
tests/__init__.py
```

In VS Code: right-click each folder → New File → type `__init__.py` → leave empty → save.

**Why `__init__.py` files:**
They tell Python that each folder is a package that can be imported. Without them `from app.retrieval import retriever` throws `ModuleNotFoundError`.

**Verify:**
```bash
python -c "import app"
```
No error means `__init__.py` files are in the right places.

---

## Step 1.3 — Create requirements.txt and install with uv

**What you do:**

Create `requirements.txt`:
```
# LangChain ecosystem
langchain
langchain-openai
langchain-community
langchain-chroma
langchain-text-splitters

# Vector store
chromadb

# PDF processing
pdfplumber
pypdf

# API and server
fastapi
uvicorn

# OpenAI
openai
tiktoken

# Observability
langsmith

# Evaluation
ragas
datasets

# Data
pandas
numpy

# Utilities
python-dotenv
requests

# Testing
pytest
```


Install all dependencies:
```bash
uv pip install -r requirements.txt
```

**Why uv pip instead of pip:**
`uv pip install` is 10-100x faster than standard pip. What takes pip 2-3 minutes installs in under 10 seconds with uv.

**Verify:**
```bash
uv pip list
```
All packages appear in the list.

If you need to add a single package later:
```bash
uv pip install package-name
```

---

## Step 1.4 — Create .env and .env.example

**What you do:**

Create `.env` with your real values — no spaces around `=`:
```
OPENAI_API_KEY=your-openai-key-here
LANGCHAIN_API_KEY=ls__your-langsmith-key-here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=rag-analytics-assistant
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=ANALYTICS
CHROMA_PERSIST_DIR=./chroma_db
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RESULTS=3
SIMILARITY_THRESHOLD=0.3
MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-3-small
LOG_LEVEL=INFO
MAX_RETRIES=2
```



Create `.env.example` with placeholder values — this is the file you commit to GitHub:
```
OPENAI_API_KEY=your-openai-key-here
LANGCHAIN_API_KEY=ls__your-langsmith-key-here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=rag-analytics-assistant
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token-here
JIRA_PROJECT_KEY=ANALYTICS
CHROMA_PERSIST_DIR=./chroma_db
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RESULTS=3
SIMILARITY_THRESHOLD=0.3
MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-3-small
LOG_LEVEL=INFO
MAX_RETRIES=2
```

**Why `.env.example`:**
`.env` holds your real secrets and is never committed. `.env.example` shows teammates exactly which keys to set without exposing real values.

**Verify:**
```bash
cat .env
```
No spaces around the `=` sign on any line. No quotes around values.

---

## Step 1.5 — Create .gitignore and .dockerignore

**What you do:**

Create `.gitignore`:
```
# API keys — NEVER commit
.env
.env.local

# Virtual environment — uv creates this
.venv

# ChromaDB vector store — rebuilt by ingest.py
chroma_db/

# Log files
logs/

# Python cache
__pycache__/
*.pyc
*.pyo

# Eval results — generated files
eval/results/

# Pytest cache
.pytest_cache/

# OS files
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
```

Create `.dockerignore`:
```
.env
.env.local
.venv
logs/
__pycache__/
*.pyc
.pytest_cache/
.git/
.gitignore
.vscode/
.idea/
.DS_Store
```

**Why separate files:**
`.gitignore` protects your API keys from GitHub. `.dockerignore` keeps the Docker image small — the `.venv` folder alone is hundreds of megabytes and must never be copied into the container.

**Verify:**
```bash
git status
```
`.env` does not appear in the untracked files list.

---

## Step 1.6 — Build app/config/settings.py

**What you do:**

All configuration read from environment variables using `os.getenv()`. Paths built with `pathlib.Path`. A `validate()` function checks everything is in place before the pipeline runs.

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

LOG_DIR  = BASE_DIR / "logs"
DOCS_DIR = BASE_DIR / "docs"   # used by validate() and loader.py — defined once here

# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── LangSmith ─────────────────────────────────────────────────────────────────
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "rag-analytics-assistant")

# ── Jira ──────────────────────────────────────────────────────────────────────
JIRA_BASE_URL    = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL       = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN   = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "ANALYTICS")

# ── ChromaDB ──────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# ── Chunking ──────────────────────────────────────────────────────────────────
CHUNK_SIZE           = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP        = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K_RESULTS        = int(os.getenv("TOP_K_RESULTS", "3"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))

# ── Models ────────────────────────────────────────────────────────────────────
MODEL           = os.getenv("MODEL", "gpt-4o")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ── LLM behaviour ─────────────────────────────────────────────────────────────
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE  = LOG_DIR / "rag_pipeline.log"


def validate() -> None:
    # Check 1: OpenAI API key
    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY not set.\n"
            "Add it to your .env file: OPENAI_API_KEY=your-key-here\n"
            "Get a key at: https://platform.openai.com/api-keys"
        )

    # Check 2: Jira API token
    if not JIRA_API_TOKEN:
        raise EnvironmentError(
            "JIRA_API_TOKEN not set.\n"
            "Get your token at: https://id.atlassian.com/manage-profile/security/api-tokens\n"
            "Then add it to .env: JIRA_API_TOKEN=your-token-here"
        )

    # Check 3: docs/ folder must exist
    if not DOCS_DIR.exists():
        raise FileNotFoundError(
            f"docs/ folder is missing: {DOCS_DIR}\n"
            "Create the folder and add your source documents (.txt)."
        )

    # Create logs/ folder
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print("logs/ folder created or already exists")

    # Check 4: docs/ folder must not be empty
    if not any(DOCS_DIR.iterdir()):
        raise FileNotFoundError(
            f"docs/ folder is empty: {DOCS_DIR}\n"
            "Add your source documents (.txt) before running the pipeline."
        )

    # Check 5: ChromaDB folder — create if missing
    chroma_dir = Path(CHROMA_PERSIST_DIR)
    if not chroma_dir.exists():
        chroma_dir.mkdir(parents=True, exist_ok=True)
        print(f"chroma_db/ directory created at: {chroma_dir}")

    # Check 6: ChromaDB must not be empty (ingest.py must have been run)
    if not any(chroma_dir.iterdir()):
        raise FileNotFoundError(
            f"ChromaDB folder is empty: {chroma_dir}\n"
            "Run ingestion first: python ingest.py"
        )
```

**Verify:**
```bash
python -c "from app.config import settings; settings.validate(); print('Settings OK')"
```

---

## Step 1.7 — Build app/utils/logger.py and app/utils/db.py

**What you do:**

**logger.py:**
```python
import logging
from logging.handlers import RotatingFileHandler
from app.config import settings

_configured = False

def setup_logging():
    global _configured
    if _configured:
        return
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    console.setFormatter(formatter)
    root.addHandler(console)
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    _configured = True

def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)

def log_event(logger, level: str, event: str, **kwargs):
    details = " ".join(f"{k}={v}" for k, v in kwargs.items())
    message = f"event={event} {details}".strip()
    getattr(logger, level.lower())(message)
```

**db.py:**
```python
import sqlite3
from app.config import settings

def get_connection(db_path=None):
    path = db_path or (settings.BASE_DIR / "rag_analytics.db")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn=None):
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
```

**Verify:**
```bash
python app/utils/logger.py
```
Log line appears in terminal AND `logs/rag_pipeline.log` is created.

---

## Step 1.8 — Create source documents, pyproject.toml, documentation files, and git init

**What you do:**

Create five `.txt` files in `docs/`:
- `docs/sales_playbook.txt` — sales methodology, qualification, closing techniques
- `docs/kpi_definitions.txt` — ASP, win rate, pipeline coverage, quota attainment
- `docs/discount_policy.txt` — discount tiers by region and deal size, approval process
- `docs/regional_strategy_apac.txt` — APAC market priorities, key accounts, growth targets
- `docs/regional_strategy_emea.txt` — EMEA market priorities, key accounts, growth targets


Create `docs/README.md`:
```markdown
# Knowledge Base Documentation

| File | Format | Topics | Last updated | Owner |
|------|--------|--------|-------------|-------|
| sales_playbook.txt | txt | Sales methodology, qualification, closing | 2024-01 | Sales ops |
| kpi_definitions.txt | txt | ASP, win rate, pipeline coverage | 2024-01 | Analytics |
| discount_policy.txt | txt | Discount rules by region and deal size | 2024-01 | Finance |
| regional_strategy_apac.txt | txt | APAC strategy and targets | 2024-01 | APAC VP |
| regional_strategy_emea.txt | txt | EMEA strategy and targets | 2024-01 | EMEA VP |

To re-ingest after any change: `python ingest.py --reset`
```

Create `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"

[project]
name = "rag-analytics-assistant"
version = "0.1.0"
requires-python = ">=3.11"
description = "Production-grade RAG system for commercial analytics Q&A"
```

Create skeleton files:
- `README.md` — title + "Full documentation in Phase 8"
- `FINDINGS.md` — section headers only, content added throughout
- `LEARNING.md` — lessons learned, updated after each phase

Git setup is handled via the parent `AI_Projects` repository:
```bash
# from inside AI_Projects/
git add rag_analytics_assistant/
git commit -m "Phase 1: project structure, settings, logger, source documents"
git push origin main
```

**Verify:**
```bash
git log --oneline
```
First commit visible. `.env` is NOT in the file list.

---

## Phase 1 complete checklist

- [ ] `.venv` created with `uv venv` — terminal shows `(.venv)` after activation
- [ ] All folders created with `__init__.py` files — `python -c "import app"` passes
- [ ] `uv pip install -r requirements.txt` — `uv pip list` shows all packages
- [ ] `.env` has all keys with no spaces around `=`
- [ ] `SIMILARITY_THRESHOLD=0.3` set in `.env`
- [ ] `MAX_RETRIES=2` set in `.env`
- [ ] `.gitignore` protects `.env` — not visible in `git status`
- [ ] `settings.validate()` passes with no error
- [ ] `logger.py` writes to console and `logs/rag_pipeline.log`
- [ ] `db.py` creates SQLite connection without error
- [ ] Five `.txt` source documents in `docs/`
- [ ] `docs/README.md` documents all five files
- [ ] `pyproject.toml` created with pytest config
- [ ] `LEARNING.md`, `README.md`, `FINDINGS.md` in project root
- [ ] First git commit pushed — `.env` not included

**Next:** Phase 2 — Document ingestion pipeline