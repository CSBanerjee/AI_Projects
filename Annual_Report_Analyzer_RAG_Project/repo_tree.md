# Repository Tree — Annual_Report_Analyzer_RAG_Project

## Full Structure

```
Annual_Report_Analyzer_RAG_Project/
│
├── app/
│   │
│   ├── config/
│   │   └── settings.py              # Env-based config, pydantic validation on startup
│   │
│   ├── ingestion/
│   │   ├── filename_parser.py       # Parses {Company}-FY{YY}-Annual-Report.pdf convention
│   │   ├── loader.py                # Multi-format: pdf, txt, docx
│   │   ├── chunker.py               # Sliding-window character chunker with overlap
│   │   └── eval_generator.py        # Synthetic eval set generator (post-ingestion)
│   │
│   ├── store/
│   │   ├── vector_store.py          # ChromaDB: add_documents(), delete(), list(), search()
│   │   └── rate_limiter.py          # 5 Jira escalations per username per 24hr, persistent
│   │
│   ├── states/
│   │   ├── agent_state.py           # RAGAgentState: messages, chunks, route, confidence, username
│   │   └── checkpointer.py          # In-session LangGraph memory (resets on refresh)
│   │
│   ├── tools/
│   │   ├── search_kb_tool.py        # LangGraph tool: wraps vector_store search
│   │   └── escalate_tool.py         # LangGraph tool: calls mcp-atlassian create_issue
│   │
│   ├── llms/
│   │   └── rag_llm.py               # ChatAnthropic, env-configured via settings.py
│   │
│   ├── agents/
│   │   ├── supervisor_agent.py      # 2-branch routing: in-docs OR escalate
│   │   ├── retrieval_agent.py       # Calls search_kb_tool, formats answer + citations
│   │   └── support_agent.py         # Calls escalate_tool, enforces rate limit
│   │
│   ├── guardrails/
│   │   ├── input_guard.py           # Sanitizes user input before it hits the LLM
│   │   └── validator.py             # Treats retrieved chunks as data, not instructions
│   │
│   ├── observability/
│   │   └── langsmith_client.py      # LangSmith trace init, trace URL extractor for Jira tickets
│   │
│   └── api/
│       ├── routes.py                # /chat, /documents (list/upload/delete)
│       └── middleware.py            # CORS, error handling, request logging
│
├── eval/
│   ├── eval_dataset.json            # 50–100 hand-labeled Q&A pairs from annual reports
│   ├── run_eval.py                  # Entry point: runs full eval suite, writes results
│   ├── ragas_eval.py                # RAGAS metrics: faithfulness, answer relevancy, context recall
│   └── llm_judge.py                 # LLM-as-judge scoring on LangSmith trace outputs
│
├── frontend/
│   └── main.py                      # Streamlit app, deployed to Streamlit Community Cloud
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   ├── test_agents.py
│   ├── test_guardrails.py
│   └── test_rate_limiter.py
│
├── data/                            # Runtime data — gitignored entirely
│   ├── uploads/                     # Raw uploaded files (PDF, TXT, DOCX)
│   │   └── Salesforce-FY25-Annual-Report.pdf  # example — created at upload time
│   ├── chroma_db/                   # ChromaDB vector store (chunks + embeddings)
│   └── rate_limiter.db              # SQLite: escalation counters per username
│
│   # NOTE — local vs deployed storage:
│   # Local dev  → these directories live inside the project folder, gitignored
│   # Render     → all three paths remapped to persistent disk mount so they
│   #              survive container sleep / restart / redeploy
│
├── docs/
│   └── sample_reports/              # Sample annual reports for local demo/testing
│
├── docs_phases/
│   ├── repo_tree.md                 # This file
│   ├── phase_outlines.md            # One-page summary of all phases
│   ├── phase_00_accounts_and_credentials.md
│   ├── phase_01_project_setup.md
│   ├── phase_02_ingestion.md
│   ├── phase_03_retrieval.md
│   ├── phase_03b_multi_agent_orchestration.md
│   ├── phase_04_generation_guardrails.md
│   ├── phase_04b_human_in_the_loop.md
│   ├── phase_05_fastapi.md
│   ├── phase_06_frontend.md
│   ├── phase_07_evaluation.md
│   └── phase_08_deploy.md
│
├── Dockerfile                       # ONE job only: bake BAAI/bge-small-en-v1.5 at build time
├── docker-compose.yml               # Optional, local-dev convenience only
├── requirements.txt                 # Pinned deps, single source of truth for venv + Docker build
├── .env.example                     # All required keys documented, no real values
├── .gitignore                       # venv/, .env, data/chroma_db/, data/uploads/, *.log
├── playbook.md                      # Operator guide: ingest, query, manage escalations
└── README.md                        # Project overview, architecture diagram, quickstart
```

---

## File-to-Phase mapping

| Phase | File | What it does |
|-------|------|--------------|
| **Phase 01 — Project Setup** | `app/config/settings.py` | Loads and validates all env vars on startup via pydantic-settings; fails loudly if required keys are absent |
| | `requirements.txt` | All dependencies pinned; single source of truth for venv and Docker build |
| | `.env.example` | Documents every required key with no real values; safe to commit |
| | `README.md` | Project overview stub; finalised in Phase 08 |
| | `playbook.md` | Operator guide stub; finalised in Phase 08 |
| **Phase 02 — Ingestion** | `app/ingestion/filename_parser.py` | Validates `{Company}-FY{YY}-Annual-Report.pdf` naming convention; extracts `company_slug`, `fiscal_year`, `doc_id` |
| | `app/ingestion/loader.py` | Extracts text from PDF (pypdf), plain text, and DOCX (python-docx) |
| | `app/ingestion/chunker.py` | Splits extracted text into overlapping character-window chunks |
| | `app/store/vector_store.py` | ChromaDB wrapper: stores chunks with metadata, searches by query embedding, deletes by `doc_id`, lists all ingested documents |
| **Phase 03 — Retrieval** | `app/tools/search_kb_tool.py` | LangGraph tool: embeds query, runs Chroma similarity search, returns top-k chunks with `page_number`, `doc_id`, `company_display` |
| **Phase 03b — Multi-Agent Orchestration** | `app/states/agent_state.py` | Typed dict defining shared graph state: messages, retrieved chunks, routing decision, confidence, username, session ID |
| | `app/states/checkpointer.py` | MemorySaver checkpointer scoped to username + session; enables follow-up questions within one browser session |
| | `app/llms/rag_llm.py` | ChatAnthropic instance loaded from settings with tool-calling enabled |
| | `app/observability/langsmith_client.py` | Initialises LangSmith tracing; exposes `get_trace_url()` so Jira tickets contain a direct link to the trace |
| | `app/agents/supervisor_agent.py` | Routing node: sends query to retrieval agent if relevant chunks are found, escalation agent otherwise |
| | `app/agents/retrieval_agent.py` | Calls `search_kb_tool`, generates a grounded answer, formats citations |
| | `app/agents/support_agent.py` | Calls `escalate_tool`; surfaces rate-limit-exceeded message to user when 5/5 is reached |
| **Phase 04 — Guardrails** | `app/guardrails/input_guard.py` | Strips known injection patterns from user input; rejects inputs over length limit |
| | `app/guardrails/validator.py` | Wraps retrieved chunks in a system-prompt boundary so document content cannot override agent instructions |
| **Phase 04b — Human-in-the-Loop** | `app/store/rate_limiter.py` | SQLite-backed counter keyed by username; enforces max 5 Jira escalations per 24 hours; persists across restarts |
| | `app/tools/escalate_tool.py` | Spawns `mcp-atlassian` subprocess via `uvx`; calls `create_issue` MCP tool with query, username, and LangSmith trace URL |
| **Phase 05 — FastAPI** | `app/api/routes.py` | HTTP endpoints: `/chat`, `GET /documents`, `POST /documents/upload`, `DELETE /documents/{doc_id}`, `GET /escalations/remaining` |
| | `app/api/middleware.py` | CORS for Streamlit Cloud origin, error handling, request logging; validates username format (`^[a-zA-Z0-9_]+$`, 3–30 chars) on every request — returns HTTP 422 if invalid |
| **Phase 06 — Frontend** | `frontend/main.py` | Streamlit app: username entry, chat UI, document upload, document delete list, citation panel, escalation indicator |
| **Phase 07 — Evaluation** | `app/ingestion/eval_generator.py` | Post-ingestion: generates synthetic Q&A pairs from chunks using Claude; writes to `eval/eval_dataset.json` |
| | `eval/eval_dataset.json` | 50–100 hand-labeled question/answer/source entries used as eval ground truth |
| | `eval/ragas_eval.py` | Scores faithfulness, answer relevancy, context recall, context precision via RAGAS |
| | `eval/llm_judge.py` | LLM-as-judge: scores each answer on correctness and groundedness against retrieved chunks |
| | `eval/run_eval.py` | Entry point: runs full eval suite and logs results to LangSmith |
| **Phase 08 — Deploy** | `Dockerfile` | Bakes `BAAI/bge-small-en-v1.5` model weights into the image at build time; the deployed container requires no runtime access to huggingface.co |
| **Every phase** | `tests/` | Unit tests added alongside each phase's files |

---

## Storage — where uploaded documents live

When a document is uploaded three things happen, in order:

| Step | What is stored | Where | Survives restart? |
|------|---------------|-------|-------------------|
| 1 | Raw file saved as-is | `data/uploads/` | Yes (persistent disk on Render) |
| 2 | File parsed, chunked, embedded | ChromaDB `data/chroma_db/` | Yes (persistent disk on Render) |
| 3 | Document metadata queryable | ChromaDB chunk metadata | Yes (same as step 2) |

**No separate document registry table is needed.** The document list shown
in the frontend delete panel is derived entirely from ChromaDB chunk
metadata via `list_documents()` — ChromaDB is the single source of truth
for what is currently ingested.

**Deletion is atomic.** When a document is deleted, both the raw file in
`data/uploads/` and all Chroma chunks for that `doc_id` are removed in the
same request handler. If either operation fails, neither is committed — the
two stores never drift out of sync.

**`data/rate_limiter.db`** is a separate SQLite file on the same persistent
disk. It stores escalation timestamps per username and is read/written by
`app/store/rate_limiter.py` independently of the vector store.