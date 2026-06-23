# Reusability Guide — Annual Report Analyzer RAG Scaffold

This project scaffold is designed to be reused for any RAG-based project.
The structure, environment setup, and configuration patterns are generic
and can be adapted with minimal changes.

---

## How to Reuse

On GitHub, go to the repo settings and check **"Template repository"**.
For any new project, click **"Use this template"** to get a fresh repo
with the same structure but no git history.

---

## Points to Note When Reusing

### Step 1 — Folder Structure
- Keep the `backend/` and `frontend/` split — it maps cleanly to Render and Streamlit Cloud deployments
- Always create `__init__.py` in `app/`, `app/routers/`, and `app/services/` — without them Python won't treat them as packages
- Add new domain-specific folders (e.g. `app/agents/`, `app/prompts/`) inside `app/` as the project grows
- `data/uploads/` and `data/vectorstore/` are added later — do not create them in Phase 01

### Step 2 — `.gitignore`
- Never modify the `.gitignore` — `.env`, `.venv`, and `__pycache__` must always be ignored
- If you add new secret files (e.g. service account JSON), add them to `.gitignore` immediately

### Step 3 — `.env` and `.env.example`
- `.env.example` is committed — always keep it updated with every new key added
- `.env` is never committed — fill it locally with real values
- If switching LLM providers, update both `.env.example` and `config.py` together
- Credentials exposed accidentally must be regenerated immediately

### Step 4 — Python Version
- Always use Python below 3.13 — packages like Pillow don't have pre-built wheels for 3.13+
- Backend and frontend must use the same Python version
- Always confirm with `python --version` after activating each venv

### Step 5 — Backend Virtual Environment
- Always create the venv inside `backend/` — never in the project root
- Always use `uv venv --python 3.12` — never `uv add` from the project root
- `uv add` creates a `pyproject.toml` and root `.venv` that silently overrides everything
- Use `uv pip install -r requirements.txt` for all installs

### Step 6 — Backend Files
- `config.py` is the single source of truth for all credentials — add new keys here first
- All fields in `config.py` default to `""` — actual values always come from `.env`
- `main.py` stays in `backend/` root — not inside `app/`
- When adding new routes, create them in `app/routers/` and register them in `main.py`

### Step 7 — Frontend Virtual Environment and Files
- Always create a separate venv inside `frontend/` — never share with backend
- Use `uv pip install` for frontend packages too
- Streamlit 1.45.0 or higher is required — 1.35.0 conflicts with `rich>=15`
- `app.py` stays directly in `frontend/` — no subfolder needed

### Step 8 — Running Locally
- Always start uvicorn with `--reload-dir .`:
  ```bash
  uvicorn main:app --reload --reload-dir . --port 8000
  ```
- Always use `python -m pytest` not `pytest` to use the venv's pytest
- Always verify the backend directly before testing via Streamlit:
  ```bash
  curl http://localhost:8000/health
  ```
- If the health endpoint returns unexpected fields, another backend is running on port 8000:
  ```bash
  lsof -i :8000
  lsof -ti :8000 | xargs kill -9
  ```

### Step 9 — Commit
- Commit only after all Done When checklist items are verified
- Never commit `.env` — always double check with `git status` before pushing

---

## What to Change Per New Project

| Item | Location | What to change |
|------|----------|----------------|
| Project name | `main.py` | `title` in `FastAPI()` |
| Credentials | `.env` and `.env.example` | Replace with new project's keys |
| Config fields | `app/config.py` | Add/remove fields to match new credentials |
| Streamlit title | `frontend/app.py` | `st.title()` and `st.set_page_config()` |
| GitHub repo name | GitHub | New repo from template |

---

## What Stays the Same

- Folder structure
- Venv setup approach
- `pydantic-settings` pattern for config
- Health endpoint smoke test
- Pytest async test client setup
- Render + Streamlit Cloud deployment pattern