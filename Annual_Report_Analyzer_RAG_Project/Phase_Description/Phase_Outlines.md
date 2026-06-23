# Phase Outlines — Annual_Report_Analyzer_RAG_Project

## Project Summary

A RAG system that enables querying of company annual reports through a
conversational chat interface. When an answer cannot be located within
the ingested documents, a Jira story is automatically created via MCP
and assigned to the admin. The system is structured in phases, each
independently testable before the next begins.

**Stack:** Claude API · LangGraph · ChromaDB · sentence-transformers ·
mcp-atlassian · FastAPI · Streamlit · LangSmith · Render ·
Streamlit Community Cloud

---

## Phase Map

```
Phase 00 → Phase 01 → Phase 02 → Phase 03 → Phase 03b
                                                  ↓
Phase 08 ← Phase 07 ← Phase 06 ← Phase 05 ← Phase 04 → Phase 04b
```

---

## Phase 00 — Accounts & Credentials

**Type:** Checklist, no code
**Deliverable:** All secrets are in hand before any code is written

**What is required:**
- Anthropic account is created → `ANTHROPIC_API_KEY` is obtained
- LangSmith account is created → `LANGCHAIN_API_KEY` and project name are noted
- Jira project is configured → PAT, project key, and assignee `accountId` are retrieved
- GitHub repo (`Annual_Report_Analyzer_RAG_Project`) is initialised (empty)
- Render account is created (free tier — backend host, no config yet)
- Streamlit Community Cloud account is created (frontend host, no config yet)

**Jira sub-steps:**
- A Jira project is created (Software or Business template); the project key
  is noted (visible in any issue URL, e.g. `SUPPORT` from `yoursite.atlassian.net/browse/SUPPORT-123`)
- The "Story" issue type is confirmed as available in the project
- A Personal Access Token is generated at `id.atlassian.com/manage-profile/security/api-tokens`
- The assignee `accountId` is retrieved via:
  ```bash
  curl -u email@example.com:API_TOKEN \
    "https://yoursite.atlassian.net/rest/api/3/user/search?query=email@example.com"
  ```

**Credentials to be stored privately (never committed):**
```
ANTHROPIC_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=annual-report-analyzer
JIRA_URL=https://yoursite.atlassian.net
JIRA_PERSONAL_TOKEN=
JIRA_PROJECT_KEY=
JIRA_ASSIGNEE_ACCOUNT_ID=
```

**Done when:**
- [ ] All 6 accounts exist
- [ ] All 5 secret values are noted privately
- [ ] Jira "Story" issue type is confirmed
- [ ] GitHub repo is created (empty is sufficient)

**Blocks:** All subsequent phases

---

## Phase 01 — Project Setup

**Type:** Scaffolding, configuration
**Deliverable:** The project imports cleanly and environment variables are
validated on startup

**Files established:**
- `app/config/settings.py` — pydantic-settings model; startup fails loudly if required keys are absent
- `requirements.txt` — all dependencies pinned
- `.env.example` — every required key documented, no real values present
- `.gitignore` — `venv/`, `.env`, `data/chroma_db/`, `data/uploads/` excluded
- `README.md` — stub (finalised Phase 08)
- `playbook.md` — stub (finalised Phase 08)

**Key settings established in this phase:**
```
langchain_project                = "annual-report-analyzer"
embedding_model_name             = "BAAI/bge-small-en-v1.5"
max_escalations_per_user_per_day = 5
```

**Done when:**
- [ ] `pip install -r requirements.txt` completes without errors
- [ ] `settings` object loads with a valid `.env`, errors clearly with missing keys
- [ ] Deliberate removal of one key from `.env` produces a clear validation error
- [ ] Repo is pushed to GitHub; `.env` is confirmed absent from git history

**Blocks:** All subsequent phases

---

## Phase 02 — Ingestion Pipeline

**Type:** Core feature
**Deliverable:** An annual report PDF is uploaded, chunked, embedded, and
stored in ChromaDB with full metadata; deletion by `doc_id` is supported;
all ingested documents are listable

**Files established:**
- `app/ingestion/filename_parser.py` — validates the `{Company}-FY{YY}-Annual-Report.pdf` naming convention; extracts `company_slug`, `fiscal_year`, `doc_id`
- `app/ingestion/loader.py` — multi-format text extraction: PDF (pypdf), plain text, DOCX (python-docx)
- `app/ingestion/chunker.py` — sliding-window character chunker, configurable size and overlap
- `app/store/vector_store.py` — ChromaDB wrapper: `add_documents()`, `delete_by_doc_id()`, `list_documents()`, `search()`

**Metadata attached to every chunk:**
```
doc_id           = "{company_slug}_fy{year}"
company_slug     = e.g. "Salesforce"
company_display  = e.g. "Salesforce"
fiscal_year      = e.g. 2025
page_number      = integer, from source PDF
source_filename  = original uploaded filename
content_hash     = SHA-256 short hash, used for dedup detection
```

**Storage — where uploaded documents land:**

| Step | Location | Purpose |
|------|----------|---------|
| Raw file saved first | `data/uploads/{filename}` | Source of truth; allows re-ingestion without re-upload |
| Chunks + embeddings stored | `data/chroma_db/` (ChromaDB) | Searched at query time |
| Document list derived from | ChromaDB chunk metadata | Powers frontend delete panel via `list_documents()` |

Both `data/uploads/` and `data/chroma_db/` are gitignored locally and
remapped to Render's persistent disk on deploy — neither is lost on
container sleep or restart.

**Key decisions:**
- Files not matching the naming convention are rejected before ingestion begins
- Re-ingestion of an existing `doc_id` is rejected unless the document is deleted first
- Deletion is atomic: all chunks for a `doc_id` are removed in one operation

**Done when:**
- [ ] A real annual report PDF is ingested and chunks appear in Chroma with correct metadata
- [ ] Deletion by `doc_id` removes all associated chunks
- [ ] A duplicate upload is rejected with a clear error message
- [ ] A wrongly-named file is rejected before reaching the ingestion pipeline

**Blocks:** Phase 03 (retrieval requires a populated store)

---

## Phase 03 — Retrieval

**Type:** Core feature
**Deliverable:** A user query returns the most relevant document chunks from
ChromaDB, with page number and document attribution attached to every result

**Files established:**
- `app/tools/search_kb_tool.py` — query is embedded at search time, Chroma similarity search is run, top-k results are returned with full metadata

**Return contract (every result carries):**
```
text             = the chunk text
doc_id           = source document identifier
company_display  = human-readable company name
fiscal_year      = integer
page_number      = integer
score            = similarity score
```

**Why `page_number` is a first-class field:**
The citation panel in the Phase 06 frontend displays exactly which page an
answer is drawn from ("Salesforce FY25 Annual Report — Pages 42, 67").
This field must not be dropped in any subsequent layer.

**Done when:**
- [ ] A query against an ingested annual report returns relevant chunks
- [ ] Every result includes `page_number`, `doc_id`, `company_display`
- [ ] A query against an empty store returns an empty list, not an exception

**Blocks:** Phase 03b (agents require a working tool to call)

---

## Phase 03b — Multi-Agent Orchestration

**Type:** Architecture
**Deliverable:** A three-agent LangGraph graph routes a query end-to-end;
in-session memory is maintained across follow-up questions

**Files established:**
- `app/states/agent_state.py` — `RAGAgentState` typed dict: `messages`, `retrieved_chunks`, `route`, `confidence`, `username`, `session_id`
- `app/states/checkpointer.py` — `MemorySaver` checkpointer; scoped to username + session; resets on page refresh
- `app/llms/rag_llm.py` — `ChatAnthropic` instance loaded from settings, tool-calling enabled
- `app/observability/langsmith_client.py` — LangSmith trace initialisation; `get_trace_url()` utility used when Jira tickets are created
- `app/agents/supervisor_agent.py` — routing node: in-docs → retrieval, not-in-docs → escalation
- `app/agents/retrieval_agent.py` — calls `search_kb_tool`, generates grounded answer with citations
- `app/agents/support_agent.py` — calls `escalate_tool` (Phase 04b); handles rate-limit-exceeded messaging

**Routing logic:**
```
query received
  → search_kb_tool
      chunks found + confidence above threshold  →  retrieval_agent  →  answer + citations
      no chunks / low confidence                 →  support_agent    →  Jira story created
```

**Done when:**
- [ ] An answerable query returns an answer with citations
- [ ] An unanswerable query is routed to the support agent
- [ ] A follow-up question within the same session uses prior context
- [ ] A LangSmith trace appears for every run

**Blocks:** Phases 04 and 04b

---

## Phase 04 — Generation Guardrails

**Type:** Safety layer
**Deliverable:** User inputs are sanitised before reaching the LLM;
retrieved document content is treated as reference data, not as instructions

**Files established:**
- `app/guardrails/input_guard.py` — known injection patterns are stripped from user input; inputs exceeding length limits are rejected
- `app/guardrails/validator.py` — retrieved chunks are wrapped in a system-prompt boundary; document content cannot override agent instructions

**Done when:**
- [ ] A prompt-injection attempt in the user query is neutralised
- [ ] A manipulative string embedded in a PDF chunk cannot override the system prompt
- [ ] Normal queries pass through guardrails without modification

**Blocks:** Phase 05 (guardrails are wired into the API layer)

---

## Phase 04b — Human-in-the-Loop (Jira Escalation via MCP)

**Type:** Integration
**Deliverable:** Unanswerable queries result in a Jira story created via
`mcp-atlassian`, assigned to the admin, with the LangSmith trace URL in
the ticket body; maximum 5 tickets per username per 24 hours is enforced

**Files established:**
- `app/store/rate_limiter.py` — SQLite-backed counter keyed by username; `check_and_increment(username)` returns `(allowed: bool, remaining: int)`; state survives container restarts
- `app/tools/escalate_tool.py` — `mcp-atlassian` is spawned as a subprocess via `uvx` (stdio transport); `create_issue` MCP tool is called with query, username, and LangSmith trace URL; rate limit is checked before the call is made
- `app/agents/support_agent.py` — rate-limit-exceeded case is surfaced to the user as "5/5 escalations used today"; the agent never fails silently

**MCP setup (no Docker required):**
```bash
pip install mcp-atlassian
```

**Jira story contents:**
```
Summary:      Unanswerable query: {first 60 chars of query}
Description:  Username: {username}
              Query: {full query}
              LangSmith trace: {trace_url}
Assignee:     {JIRA_ASSIGNEE_ACCOUNT_ID}
Issue type:   Story
```

**Done when:**
- [ ] An unanswerable query creates a real Jira story assigned to the admin
- [ ] Ticket body contains the original query and LangSmith trace URL
- [ ] The 6th escalation attempt within 24 hours returns a limit-reached message, not a ticket
- [ ] Rate-limit counter persists across a backend restart

**Blocks:** Phase 05 (rate limiter state is surfaced via an API endpoint)

---

## Phase 05 — FastAPI Backend

**Type:** Integration layer
**Deliverable:** All backend logic is exposed via HTTP endpoints callable
by the Streamlit frontend over HTTPS

**Files established:**
- `app/api/routes.py`

  | Endpoint | Method | Purpose |
  |----------|--------|---------|
  | `/chat` | POST | Accepts `{username, session_id, query}`; runs LangGraph graph; returns answer + citations |
  | `/documents` | GET | Returns list of ingested documents for the frontend delete panel |
  | `/documents/upload` | POST | Validates filename, runs ingestion pipeline, returns `doc_id` |
  | `/documents/{doc_id}` | DELETE | Atomic removal: all Chroma chunks for `doc_id` deleted AND raw file removed from `data/uploads/` in one operation; if either fails, neither is committed |
  | `/escalations/remaining` | GET | Returns escalations remaining today for a given username |

- `app/api/middleware.py` — CORS (Streamlit Community Cloud origin allowed), error handling, request logging forwarded to LangSmith; username format validated against `^[a-zA-Z0-9_]+$` (3–30 chars) on every request that carries a username field — returns HTTP 422 if invalid

**Done when:**
- [ ] All endpoints respond correctly via local `uvicorn`
- [ ] `/chat` returns answer + citations for an answerable query
- [ ] `/chat` triggers Jira escalation for an unanswerable query
- [ ] `/documents/upload` rejects a wrongly-named file with a 400 response
- [ ] `DELETE /documents/{doc_id}` removes chunks from Chroma and the raw file

**Blocks:** Phase 06 (frontend calls these endpoints)

---

## Phase 06 — Frontend

**Type:** User interface
**Deliverable:** A Streamlit application covering all user-facing features,
deployable to Streamlit Community Cloud without modification

**File established:**
- `frontend/main.py`

**Interface sections:**

| Section | Description |
|---------|-------------|
| **Username entry** | Text field shown on first load; gates the rest of the UI; used as the rate-limit key (no auth, no password). Full specification below. |
| **Document upload** | File uploader accepts PDF, TXT, DOCX; filename is validated against `{Company}-FY{YY}-Annual-Report.pdf` before the file is sent to the backend; ingestion progress is shown; the uploaded document appears immediately in the document list |
| **Document list + delete** | All ingested reports are listed by display name and fiscal year; a delete button per row triggers `DELETE /documents/{doc_id}` after confirmation; the list refreshes immediately |
| **Chat UI** | Query input; streamed response; conversation history for the current session (resets on page refresh) |
| **Source citation panel** | Per-answer display of which document and pages the answer is drawn from ("Salesforce FY25 Annual Report — Pages 42, 67") |
| **Escalation indicator** | Shows current usage ("3 / 5 escalations used today"); updates after each escalation; displays "limit reached" when 5 is reached |

**Username specification:**

| Property | Rule |
|----------|------|
| **Allowed characters** | Letters (a–z, A–Z), numbers (0–9), underscores (`_`) only |
| **Pattern** | `^[a-zA-Z0-9_]+$` |
| **Minimum length** | 3 characters |
| **Maximum length** | 30 characters |
| **Case sensitivity** | Case-sensitive — `John` and `john` are treated as different users |
| **Spaces** | Not permitted |
| **Special characters** | Not permitted (no hyphens, dots, @, etc.) |
| **Persistence** | Stored in `st.session_state` for the duration of the browser session; cleared on page refresh |
| **Where it is used** | Rate-limiter key in `rate_limiter.db`, `username` field in Jira ticket body, `username` field in `/chat` request payload |

**Valid examples:** `john_doe`, `Salesforce1`, `alice`, `RAG_User_01`

**Invalid examples:** `jo` (too short), `john doe` (space), `john-doe` (hyphen),
`john.doe` (dot), `@john` (special character)

**Frontend validation behaviour:**
- The submit button remains disabled until the username passes the pattern check
- A red inline error is shown if the pattern is violated: *"Username must be 3–30 characters, letters, numbers, and underscores only"*
- On valid submission the username field is locked for the rest of the session — the user cannot change it without refreshing the page
- No lookup is performed against any database — any valid-format username is accepted immediately

**Server-side validation (Phase 05):**
The `/chat` and `/escalations/remaining` endpoints also validate the username
against the same regex before processing — client-side validation alone is
not relied upon.

**Sharable URL:** Streamlit Community Cloud automatically provides a public
URL at `https://{username}.streamlit.app/annual-report-analyzer` on deploy.
No additional configuration is required for public access.

**Done when:**
- [ ] Chat works end-to-end in a browser against the live Render backend
- [ ] A PDF is uploadable from the UI and appears in the document list
- [ ] A document is deletable from the UI and disappears from the list
- [ ] Citation panel shows correct document name and page numbers
- [ ] Escalation count updates correctly after each escalation
- [ ] Sharable URL is accessible without a local server running

**Blocks:** Phase 07 (evaluation uses the same backend endpoints)

---

## Phase 07 — Evaluation

**Type:** Quality assurance
**Deliverable:** A reproducible evaluation suite that scores retrieval
and answer quality; results are logged to LangSmith

**Files established:**
- `app/ingestion/eval_generator.py` — post-ingestion: synthetic Q&A pairs are generated from document chunks using Claude; output is written to `eval/eval_dataset.json`
- `eval/eval_dataset.json` — 50–100 entries: `{question, ground_truth_answer, source_doc_id}`
- `eval/ragas_eval.py` — RAGAS metrics: faithfulness, answer relevancy, context recall, context precision
- `eval/llm_judge.py` — LLM-as-judge: each answer is scored on correctness and groundedness
- `eval/run_eval.py` — entry point: full suite is run; results are logged to LangSmith under `annual-report-analyzer`

**Done when:**
- [ ] `python eval/run_eval.py` completes without error
- [ ] RAGAS scores appear in LangSmith
- [ ] At least one failing case is identified and documented

**Blocks:** Phase 08 (a system is deployed only after quality is measured)

---

## Phase 08 — Deploy

**Type:** Deployment
**Deliverable:** A live, publicly accessible system with a sharable
frontend URL; README and playbook are finalised

**Files established:**
- `Dockerfile` — Python 3.12 base image; dependencies installed; embedding
  model weights baked in at build time so the deployed container requires
  no runtime access to huggingface.co

**Deployment steps:**
1. Persistent disk is added to the Render service (Chroma, uploads, and rate-limiter SQLite all write here)
2. All env vars from `.env.example` are set in the Render dashboard
3. GitHub repo is connected to Render; auto-deploy from main branch is enabled
4. `frontend/` is connected to Streamlit Community Cloud; auto-deploy from main branch is enabled
5. `BACKEND_URL` (the Render service URL) is set in Streamlit secrets
6. End-to-end smoke test is run: upload → query → cite → escalate → confirm Jira ticket
7. `README.md` is finalised: architecture diagram, quickstart, sample queries
8. `playbook.md` is finalised: ingestion steps, escalation management, LangSmith monitoring, Jira PAT rotation

**Hosting summary:**

| Component | Host | Free tier | Notes |
|-----------|------|-----------|-------|
| FastAPI backend | Render | Yes | Sleeps after 15 min inactivity |
| Streamlit frontend | Streamlit Community Cloud | Yes | Sleeps after 12 hr inactivity |
| ChromaDB + uploads | Render persistent disk | Yes | Included with free web service |
| Rate limiter (SQLite) | Render persistent disk | Yes | Same disk as Chroma |

**Cold-start note:** `mcp-atlassian` is spawned on-demand per escalation
request (not once at startup) so it is not lost when the container wakes
from sleep.

**Done when:**
- [ ] Frontend sharable URL opens in a browser with no local server running
- [ ] Full flow completes on the live deployment (upload → query → cite → escalate)
- [ ] Jira ticket appears in the correct project, assigned to the admin
- [ ] README and playbook reflect the deployed system, not the planned one