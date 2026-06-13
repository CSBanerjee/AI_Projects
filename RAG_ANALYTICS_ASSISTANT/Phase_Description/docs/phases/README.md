# Phase Documentation — RAG Analytics Assistant

One markdown file per phase. Read the phase file before starting that phase.
Every step has a verify command — do not move to the next step until it passes.

**uv is used throughout all phases** — for creating the virtual environment,
installing packages locally, inside Docker, and in GitHub Actions CI.

---

## Phase index

| File | Phase | Steps | What you build |
|------|-------|-------|----------------|
| [phase_01_project_setup.md](phase_01_project_setup.md) | Phase 1 — Project setup | 8 | Folders, uv venv, settings, logger, db, docs, git |
| [phase_02_ingestion.md](phase_02_ingestion.md) | Phase 2 — Document ingestion | 7 | LangChain loaders, chunker, embedder, ChromaDB, ingest.py, tests |
| [phase_03_retrieval.md](phase_03_retrieval.md) | Phase 3 — Retrieval | 5 | Retriever, threshold, metadata filter, eval dataset, session store, tests |
| [phase_04_generation_guardrails.md](phase_04_generation_guardrails.md) | Phase 4 — Generation + guardrails | 6 | Input guard, prompt, LLM client, validator, cost tracker, main.py, tests |
| [phase_04b_human_in_the_loop.md](phase_04b_human_in_the_loop.md) | Phase 4B — Human in the loop | 6 | Trigger, agent prompt, Jira client, wire into main.py, tests, conftest |
| [phase_05_fastapi.md](phase_05_fastapi.md) | Phase 5 — FastAPI service | 6 | All API endpoints, middleware, streaming, server, full test suite |
| [phase_06_frontend.md](phase_06_frontend.md) | Phase 6 — Frontend chat UI | 5 | Chat UI, streaming display, citations, Jira case card, session history |
| [phase_07_evaluation.md](phase_07_evaluation.md) | Phase 7 — Evaluation framework | 5 | run_eval, RAGAS, LLM-as-judge, before/after guardrails, failure analysis |
| [phase_08_deploy.md](phase_08_deploy.md) | Phase 8 — Deploy, monitor, CI/CD | 7 | Docker with uv, GitHub Actions with uv, LangSmith, Railway, README, portfolio |

**Total: 55 steps across 9 phases**

---

## uv command reference

| Situation | Command |
|-----------|---------|
| Create virtual environment | `uv venv` |
| Activate (Mac/Linux) | `source .venv/bin/activate` |
| Activate (Windows) | `.venv\Scripts\activate` |
| Install all dependencies | `uv pip install -r requirements.txt` |
| Add a single new package | `uv pip install package-name` |
| List installed packages | `uv pip list` |
| Inside Dockerfile | `uv pip install --system -r requirements.txt` |
| Inside GitHub Actions | `uv pip install --system -r requirements.txt` |

---

## The rule that applies to every step

Do not move to the next step until the verify command at the bottom of the
current step passes. Every verify command catches the most common mistake
made at that step. A broken foundation makes every step after it harder to debug.
