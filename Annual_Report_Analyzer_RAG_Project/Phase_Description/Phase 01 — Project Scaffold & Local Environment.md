# Phase 01 — Project Scaffold & Local Environment

**Deliverable:** Full stack wires together locally — `GET /health` → Streamlit button → `{"status": "ok"}`

---

## Directory layout

```
Annual_Report_Analyzer_RAG_Project/
├── backend/
│   ├── .venv/             ← backend virtual environment (git-ignored)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── routers/
│   │   │   └── __init__.py
│   │   └── services/
│   │       └── __init__.py
│   ├── tests/
│   │   └── test_health.py
│   ├── main.py            # FastAPI entry point
│   └── requirements.txt
├── frontend/
│   ├── .venv/             ← frontend virtual environment (git-ignored)
│   ├── app.py
│   └── requirements.txt
├── .env.example
├── .env                  ← you create this; never committed
├── .gitignore
└── README.md
```

---

## Step 1 — Create folder structure

Create all folders and empty `__init__.py` files manually in VS Code, or run this from the project root:

```bash
# Folders
mkdir -p backend/app/routers
mkdir -p backend/app/services
mkdir -p backend/tests
mkdir -p frontend

# Empty __init__.py files (marks folders as Python packages)
touch backend/app/__init__.py
touch backend/app/routers/__init__.py
touch backend/app/services/__init__.py
```

Verify in VS Code that the folder tree matches the layout above before moving on.

---

## Step 2 — Create `.gitignore`

Create `.gitignore` in the project root:

```gitignore
.env
__pycache__/
*.py[cod]
*.egg-info/
.venv/
dist/
build/
.streamlit/secrets.toml
.DS_Store
```

---

## Step 3 — Create `.env.example` and `.env`

Create `.env.example` in the project root (this gets committed):

```
OPENROUTER_API_KEY=       # from openrouter.ai → Keys
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=annual-report-analyzer
JIRA_URL=https://yoursite.atlassian.net
JIRA_PERSONAL_TOKEN=
JIRA_PROJECT_KEY=
JIRA_ASSIGNEE_ACCOUNT_ID=
BACKEND_URL=http://localhost:8000
```

Copy it and fill in your real values:

```bash
cp .env.example .env
```

Never commit `.env` — it is already git-ignored.

---

## Step 4 — Verify Python version for backend and frontend

Before creating any venv, check the Python version available on your machine:

```bash
python3 --version
```

**Requirements:**
- Version must be **less than 3.13** (3.11 or 3.12 recommended)
- Backend and frontend must use the **same version**

If your version is 3.13 or higher, or if backend and frontend have different versions, make them the same by specifying the version explicitly when creating venvs:

```bash
uv venv --python 3.12   # replace 3.12 with whichever version you have below 3.13
```

If you ever create a venv with the wrong version, fix it like this:

```bash
deactivate
rm -rf .venv
uv venv --python 3.12
source .venv/bin/activate
python --version   # confirm version before proceeding
```

---

## Step 5 — Create backend virtual environment

```bash
cd backend
uv venv --python 3.12
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python --version                 # must show 3.12.x
```

Your terminal prompt should show `(.venv)`.

---

## Step 6 — Backend files

### `backend/requirements.txt`

```
fastapi==0.111.0          # web framework for the REST API
uvicorn[standard]==0.29.0 # ASGI server to run FastAPI
pydantic-settings==2.2.1  # loads .env into typed Settings class
python-dotenv==1.0.1      # reads .env file into os.environ
httpx==0.27.0             # async HTTP client used by the test client
pytest==8.2.0             # test runner
pytest-asyncio==0.23.6    # allows async test functions with pytest
```

Install:

```bash
uv pip install -r requirements.txt
```

### `backend/app/config.py`

```python
# ── Import the tools that read .env and map values to this class ──────────────
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Define all the config variables the app needs ────────────────────────────
class Settings(BaseSettings):

    # Tell pydantic-settings where to find the .env file
    model_config = SettingsConfigDict(
        env_file=".env",               # look for .env in the project root
        env_file_encoding="utf-8",     # how to read the file
        extra="ignore",                # ignore any extra keys not listed below
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    openrouter_api_key: str = ""       # OPENROUTER_API_KEY in .env
    openrouter_model: str = ""         # OPENROUTER_MODEL in .env

    # ── Tracing ──────────────────────────────────────────────────────────────
    langchain_api_key: str = ""        # LANGCHAIN_API_KEY in .env
    langchain_project: str = ""        # LANGCHAIN_PROJECT in .env

    # ── Jira ─────────────────────────────────────────────────────────────────
    jira_url: str = ""                 # JIRA_URL in .env
    jira_personal_token: str = ""      # JIRA_PERSONAL_TOKEN in .env
    jira_project_key: str = ""         # JIRA_PROJECT_KEY in .env
    jira_assignee_account_id: str = "" # JIRA_ASSIGNEE_ACCOUNT_ID in .env


# ── Create one shared settings object — imported by all other files ───────────
settings = Settings()
```

### `backend/main.py`

```python
from fastapi import FastAPI
from app.config import settings  # noqa: F401

app = FastAPI(title="Annual Report Analyzer", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

### `backend/tests/test_health.py`

```python
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

---

## Step 7 — Frontend virtual environment and files

Open a **new terminal** for all frontend work — never use the backend terminal here.

### Create frontend virtual environment

```bash
cd frontend
uv venv --python 3.12
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python --version                 # must show 3.12.x — must match backend
```

Your terminal prompt should show `(.venv)`.

### `frontend/requirements.txt`

```
streamlit==1.45.0         # UI framework for the frontend
httpx==0.27.0             # HTTP client to call the backend
python-dotenv==1.0.1      # reads .env to get BACKEND_URL
```

Install:

```bash
pip install -r requirements.txt
```

### `frontend/app.py`

```python
import os
import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Annual Report Analyzer", layout="wide")
st.title("Annual Report Analyzer")

if st.button("Check backend"):
    try:
        r = httpx.get(f"{BACKEND_URL}/health", timeout=5)
        st.success(r.json())
    except Exception as exc:
        st.error(f"Backend unreachable: {exc}")
```

---

## Step 8 — Run locally and verify

> **Important — read before running:**
> - Always use `uv pip install` to install packages, never `uv add` — running `uv add` creates a `pyproject.toml` and root `.venv` that conflicts with the project.
> - Always run uvicorn with `--reload-dir .` — without it, watchfiles monitors `.venv` and causes endless reloading.
> - Always run uvicorn from inside `backend/` with the backend venv active.
> - Use `python -m pytest` instead of `pytest` to ensure the venv's pytest is used.

**Terminal 1 — Backend** (`.venv` already active)
```bash
cd backend
uvicorn main:app --reload --reload-dir . --port 8000
```

**Terminal 2 — Frontend**
```bash
cd frontend
streamlit run app.py
```

**Terminal 3 — Tests**
```bash
cd backend
python -m pytest -v
```

Expected: pytest passes, Streamlit "Check backend" button returns `{"status": "ok"}`.

Verify with curl:
```bash
curl http://localhost:8000/health
# expected: {"status":"ok"}
```

---

## Step 9 — Commit

```bash
git add .
git commit -m "Phase 01: project scaffold, health endpoint, Streamlit smoke test"
git push origin main
```

---

## Done when

- [ ] Folder structure matches the layout above
- [ ] All `__init__.py` files exist in `app/`, `app/routers/`, `app/services/`
- [ ] `.venv` created with Python 3.12 and active inside `backend/`
- [ ] `.venv` created with Python 3.12 and active inside `frontend/`
- [ ] `.env` filled with real values; `.env.example` committed with empty values
- [ ] `pytest` passes with `test_health` green
- [ ] "Check backend" button in Streamlit returns `{"status": "ok"}`
- [ ] Commit pushed to `Annual_Report_Analyzer_RAG_Project`