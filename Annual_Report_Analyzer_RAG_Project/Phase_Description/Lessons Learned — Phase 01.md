# Lessons Learned — Phase 01

---

## 1. Environment Setup

- Backend and frontend must each have their own `.venv` — never share or put it in the project root
- Both venvs must use the same Python version, below 3.13 (3.11 or 3.12 recommended)
- Always confirm the version after activating:
  ```bash
  python --version
  ```
- If the wrong version was used, fix it like this:
  ```bash
  deactivate
  rm -rf .venv
  uv venv --python 3.12
  source .venv/bin/activate
  python --version   # confirm before proceeding
  ```

---

## 2. Package Installation

- Always use `uv pip install` — never `uv add` from the project root
  ```bash
  uv pip install -r requirements.txt   # correct
  uv add -r requirements.txt           # wrong — creates pyproject.toml and root .venv
  ```
- `uv add` from the project root creates a `pyproject.toml` and root `.venv` that silently overrides the backend and frontend venvs
- Always check `requirements.txt` is not empty before installing:
  ```bash
  cat requirements.txt
  ```
- If `requirements.txt` is empty, fill it manually before running install

---

## 3. Running the Server

- Always run uvicorn with `--reload-dir .` to prevent endless reloading:
  ```bash
  uvicorn main:app --reload --reload-dir . --port 8000   # correct
  uvicorn main:app --reload --port 8000                  # wrong — watches .venv
  ```
- Without `--reload-dir .`, watchfiles monitors `.venv` and reloads the server endlessly as packages are written
- Always run uvicorn from inside `backend/` with the backend venv active
- Always use `python -m pytest` not `pytest`:
  ```bash
  python -m pytest -v   # correct — uses venv's pytest
  pytest -v             # wrong — may use system pytest (3.14)
  ```

---

## 4. Debugging Port Conflicts

- If the health endpoint returns unexpected fields, another backend is running on the same port
- Find all processes on port 8000:
  ```bash
  lsof -i :8000
  ```
- Find which project a process belongs to:
  ```bash
  lsof -p <PID> | grep cwd
  ```
- Kill all processes on a port:
  ```bash
  lsof -ti :8000 | xargs kill -9
  ```
- Always verify the backend directly before testing via Streamlit:
  ```bash
  curl http://localhost:8000/health
  # expected: {"status":"ok"}
  ```

---

## 5. Security

- Never share or expose `.env` contents — not in chat, not in screenshots, not in commits
- If `.env` contents are exposed, regenerate all keys immediately:
  - OpenRouter → openrouter.ai → Keys → delete and create new
  - LangChain → smith.langchain.com → Settings → API Keys → regenerate
  - Jira → id.atlassian.com → Security → API tokens → revoke and create new
- Always confirm `.env` is in `.gitignore` before committing

---

## 6. File Structure

- `test_health.py` belongs in `backend/tests/` — not inside `backend/app/tests/`
- `main.py` belongs in `backend/` root — not inside `backend/app/`
- `app/` folder is a Python package and must have `__init__.py` files in every subfolder

---

## 7. Python Version Compatibility

- Python 3.13 and 3.14 are too new — many packages (Pillow, etc.) don't have pre-built wheels yet
- Always use Python below 3.13 for this project
- Installing packages on 3.14 causes compilation errors due to missing system libraries (e.g. `libjpeg`)
- Streamlit 1.35.0 conflicts with `rich>=15` — use Streamlit 1.45.0 or higher