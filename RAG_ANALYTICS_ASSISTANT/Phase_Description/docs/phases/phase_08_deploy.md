# Phase 8 — Deploy, Monitor, CI/CD

**Steps:** 7  
**Goal:** Make the system production-ready. Get a public URL. Automate testing on every push. The live URL is the interview.

---

## Step 8.1 — Build Dockerfile and docker-compose.yml

**What you do:**

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# install uv for fast dependency installation
RUN pip install uv

COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/chroma_db

# ingest documents first, then start API
CMD ["sh", "-c", "python ingest.py && python api_server.py"]
```

**Why `uv pip install --system`:**
Inside Docker there is no virtual environment — packages go directly into the system Python. The `--system` flag tells uv to install there. This is the correct way to use uv in a Docker container.

**docker-compose.yml:**
```yaml
version: "3.9"

services:
  api:
    build: .
    container_name: rag_analytics_api
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./chroma_db:/app/chroma_db
      - ./logs:/app/logs
      - ./docs:/app/docs
    restart: on-failure

  chroma:
    image: chromadb/chroma:latest
    container_name: rag_chroma
    ports:
      - "8001:8000"
    volumes:
      - ./chroma_db:/chroma/chroma
    restart: on-failure
```

**Build and run:**
```bash
docker compose up --build
```

**Verify:**
- Both containers start without errors
- `localhost:8000/health` returns `{"status": "ok", "chunk_count": 87}`
- `localhost:8001` shows ChromaDB running

---

## Step 8.2 — Build .github/workflows/test.yml — GitHub Actions CI

**What you do:**

```yaml
name: Test suite

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv pip install --system -r requirements.txt

      - name: Run pytest
        run: python -m pytest tests/ -v --tb=short

      - name: Check eval dataset exists
        run: |
          if [ ! -f eval/eval_dataset.json ]; then
            echo "eval/eval_dataset.json missing"
            exit 1
          fi
          echo "Eval dataset present: $(python -c "import json; print(len(json.load(open('eval/eval_dataset.json'))), 'questions')")"
```

**Why `uv pip install --system` in CI:**
GitHub Actions runners do not have a virtual environment active. `--system` installs into the runner's Python directly, same as the Docker approach.

**Verify:**

Push to main → GitHub Actions tab shows green checkmark. Intentionally break a test → red X → fix → green again.

---

## Step 8.3 — Verify LangSmith monitoring is complete

**What you do:**

Open `https://smith.langchain.com` → project `rag-analytics-assistant`.

Run 10 test questions through the API. Verify in LangSmith each trace shows:

| What to check | Where to find it |
|---|---|
| Full prompt sent to GPT-4o | Inputs tab of each trace |
| Full response received | Outputs tab |
| Input + output token count | Metadata tab |
| Latency in milliseconds | Top of trace |
| Validator call nested inside | Child runs section |

**Set up a latency alert:**
LangSmith → Alerts → New alert → P95 latency > 10,000ms → email notification.

**Verify:** 10 traces visible. Each has prompt, response, and token counts recorded.

---

## Step 8.4 — Deploy to Railway — get a public URL

**What you do:**

1. Go to `https://railway.app` → New Project → Deploy from GitHub repo
2. Select your repository → set root directory to `rag_analytics_assistant/`
3. Railway auto-detects your Dockerfile
4. Add environment variables — copy every line from `.env` into Railway's Variables section
5. Deploy

Railway builds the Docker image, runs `python ingest.py`, then starts `python api_server.py`. Your public URL will be something like:
```
https://rag-analytics-assistant-production.up.railway.app
```

**After deployment:**
```bash
# test your live URL
curl https://your-railway-url.railway.app/health
```

**Verify:**
- Health endpoint returns 200 with chunk count on the public URL
- Open the URL on your phone — chat UI loads
- Ask one question through the live system — full pipeline works

---

## Step 8.5 — Write complete README.md

**What you do:**

Replace the skeleton README with the complete version. Structure:

```markdown
# RAG Analytics Assistant

> A production-grade RAG system that answers questions from commercial analytics
> documents using LangChain, ChromaDB, OpenAI GPT-4o, and FastAPI.

**Live demo:** https://your-url.railway.app  
**LangSmith:** https://smith.langchain.com/your-project

![Tests passing](github-actions-badge)

## What it does
[2 paragraphs on use case — VP asks questions, RAG answers from documents,
low confidence triggers Jira escalation]

## Architecture
[simple text diagram showing: docs → ChromaDB → retriever → LLM → guardrails → API → UI]

## Project structure
[full tree with one-line comment on every file]

## Setup

### Prerequisites
- Python 3.11+
- uv (`pip install uv`)
- OpenAI API key
- Jira account and API token (for HITL escalation)
- LangSmith account (for observability)

### Installation
git clone https://github.com/YOUR_USERNAME/AI_Projects.git
cd AI_Projects/rag_analytics_assistant
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
# edit .env with your keys

### Run ingestion (first time and when docs change)
python ingest.py

### Start the API
python api_server.py
# open localhost:8000

## Running tests
python -m pytest tests/ -v

## Running evaluation
python eval/run_eval.py    # retrieval precision + keyword recall
python eval/ragas_eval.py  # RAGAS faithfulness, relevancy, precision, recall
python eval/llm_judge.py   # GPT-4o quality scoring

## Docker
docker compose up --build

## RAGAS scores achieved
| Metric | Score |
|--------|-------|
| Faithfulness | 0.78 |
| Answer relevancy | 0.74 |
| Context precision | 0.81 |
| Context recall | 0.72 |

## Key decisions
[3 entries from FINDINGS.md with the reasoning behind each]

## Known limitations
[2-3 honest limitations with proposed solutions]
```

**Verify:**

Give the README to someone who has never seen the project. They should set it up in under 30 minutes using only the README.

---

## Step 8.6 — Final git push and update docs/README.md

**What you do:**

Update `docs/README.md` with the knowledge base documentation table (already started in Phase 1).

Add the GitHub Actions badge to `README.md`:
```markdown
![Tests](https://github.com/YOUR_USERNAME/AI_Projects/actions/workflows/test.yml/badge.svg)
```

Final push:
```bash
git add .
git commit -m "Phase 8: Docker, GitHub Actions, Railway deploy, complete README"
git push origin main
```

Confirm Railway auto-deploys from the push. Check Railway deployment logs — no errors.

**Verify:**
- GitHub repo shows green Actions badge
- `docs/README.md` has all five source files documented
- Public URL still works after the push

---

## Step 8.7 — Update portfolio — PDF, LinkedIn, interview stories

**What you do:**

**Portfolio PDF — Project 2 entry:**

```
Project: RAG Analytics Assistant
Problem: VPs spend hours searching internal documents for analytics answers
Solution: RAG system answering questions from sales playbooks and strategy docs

Stack: LangChain · ChromaDB · GPT-4o · FastAPI · Docker · LangSmith · Railway

Results:
  Faithfulness: 0.78   Answer relevancy: 0.74
  Context precision: 0.81   Context recall: 0.72
  Human-in-the-loop via Jira for low-confidence escalations
  43 automated tests · GitHub Actions CI · Live deployment

Live: https://your-url.railway.app
Code: https://github.com/YOUR_USERNAME/AI_Projects/rag_analytics_assistant

What I would do differently:
  Add hybrid search (dense + sparse) to improve recall on keyword queries
  Add document versioning so outdated chunks are automatically flagged
```

**Three interview stories to rehearse out loud:**

**Story 1 — The chunk size experiment:**
"I ran three ingestion experiments with chunk sizes 200, 500, and 800 tokens — each time measuring retrieval precision against a 20-question eval set. At 200 tokens precision was 0.61 because individual chunks were too small to contain complete policy statements. At 500 it jumped to 0.78. At 800 it dropped slightly because chunks became too broad and retrieved irrelevant content alongside the target passage. I chose 500 with 50-token overlap."

**Story 2 — A production bug:**
"During Phase 4 the faithfulness validator was flagging good answers as hallucinations because I was using exact phrase matching. A phrase like 'enterprise pricing' would fail if the chunk said 'pricing for enterprise accounts'. I switched from exact matching to embedding cosine similarity between answer claims and chunk content. Faithfulness score went from 0.62 to 0.78."

**Story 3 — The HITL simplification decision:**
"I originally designed a full case management system with SLA timers, reviewer dashboards, status flows, and an audit trail. Then I stepped back and asked: what does the user actually need? When the AI cannot answer confidently, ask them if they want a human to look into it. That became three files and one Jira API call. The simpler design deployed in one sprint."

**Verify:**

Tell all three stories out loud in under 2 minutes each without looking at notes. The live demo works when opened on a phone you have never touched before.

---

## Phase 8 complete checklist

- [ ] `Dockerfile` uses `uv pip install --system` — `docker compose up --build` succeeds
- [ ] `docker compose up` starts both services — `/health` returns 200
- [ ] `.github/workflows/test.yml` uses `uv pip install --system`
- [ ] GitHub Actions green badge on repo after push
- [ ] LangSmith shows 10+ traces with prompt and token counts
- [ ] Latency alert configured in LangSmith
- [ ] Public Railway URL live and responding
- [ ] Health endpoint returns correct chunk count on live URL
- [ ] Three demo questions rehearsed on live URL
- [ ] Complete `README.md` — setup possible in 30 minutes
- [ ] `docs/README.md` documents all five knowledge base files
- [ ] GitHub Actions badge in `README.md`
- [ ] Portfolio PDF updated with Project 2
- [ ] Three interview stories rehearsed without notes

---

## Project complete

You have built a production-grade RAG system:

- **33 Python files** across 9 modules
- **4 frontend files** — chat UI, streaming, citations, Jira escalation
- **43 automated tests** — zero real API calls in the test suite
- **5 evaluation scripts** — RAGAS, LLM-as-judge, retrieval precision, chunk experiments
- **Full observability** — LangSmith traces, structured logs, cost tracking per query
- **Continuous deployment** — GitHub Actions → Railway via Docker

**uv is used throughout:**
- `uv venv` — create virtual environment
- `uv pip install -r requirements.txt` — install dependencies locally
- `uv pip install --system -r requirements.txt` — install in Docker and GitHub Actions
- `uv pip install package-name` — add individual packages

**Next project:** Project 3 — Multi-agent system with LangGraph
