# Phase 5 — FastAPI Service

**Steps:** 6  
**Goal:** Wrap the RAG pipeline as an HTTP API. After this phase your assistant has a URL. Test every endpoint with Swagger UI before building the frontend.

---

## Step 5.1 — Build app/api/routes.py — all endpoints

**What you do:**

```python
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import main as pipeline
from app.store import vector_store
from app.utils import cost_tracker
from app.utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class AskResponse(BaseModel):
    type: str
    answer: str = None
    sources: list = []
    session_id: str = None
    escalation_id: str = None
    message: str = None

class ConfirmRequest(BaseModel):
    escalation_id: str
    confirmed: bool

class ConfirmResponse(BaseModel):
    jira_key: str = None
    jira_url: str = None
    message: str

class HealthResponse(BaseModel):
    status: str
    chunk_count: int
    model: str


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    result = pipeline.run(request.question, request.session_id)
    return AskResponse(**result)


@router.post("/ask/stream")
def ask_stream(request: AskRequest):
    from app.generation import prompt as p, llm_client
    from app.retrieval import retriever
    from app.guardrails import input_guard
    from app.utils import session_store

    guard = input_guard.check(request.question)
    if not guard.is_safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    chunks  = retriever.search(request.question)
    history = session_store.get_history(request.session_id)
    messages = p.build(request.question, chunks, history)

    def generate():
        for token in llm_client.stream(messages):
            if token:
                yield token

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/ask/escalate")
def escalate(request: AskRequest):
    result = pipeline.run(request.question, request.session_id)
    if result["type"] != "escalation":
        return {"type": "answer", "message": "This question was answered directly."}
    return result


@router.post("/ask/confirm-escalation", response_model=ConfirmResponse)
def confirm_escalation(request: ConfirmRequest):
    escalation = pipeline.pending_escalations.get(request.escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found.")

    if not request.confirmed:
        del pipeline.pending_escalations[request.escalation_id]
        return ConfirmResponse(message="Okay, no problem. Feel free to ask another question.")

    from app.hitl import jira_client
    result = jira_client.create_story(
        question=escalation["question"],
        session_id=escalation["session_id"],
        confidence=escalation["confidence"],
        chunks=escalation["chunks"],
    )
    del pipeline.pending_escalations[request.escalation_id]
    return ConfirmResponse(
        jira_key=result["jira_key"],
        jira_url=result["jira_url"],
        message=f"Done. Jira story {result['jira_key']} has been created. "
                f"Your analytics team will investigate and respond there."
    )


@router.post("/ingest")
def ingest():
    import ingest as ingest_pipeline
    ingest_pipeline.main(reset=False)
    return {"message": "Ingestion complete.", "chunks": vector_store.count()}


@router.get("/health", response_model=HealthResponse)
def health():
    from app.config import settings
    return HealthResponse(
        status="ok",
        chunk_count=vector_store.count(),
        model=settings.MODEL
    )


@router.get("/stats")
def stats():
    from app.utils.db import get_connection
    conn = get_connection()
    row = conn.execute("""
        SELECT COUNT(*) as total_queries,
               COALESCE(SUM(total_cost_usd), 0) as total_cost,
               COALESCE(AVG(latency_ms), 0) as avg_latency
        FROM query_log
        WHERE date(timestamp) = date('now')
    """).fetchone()
    return {
        "queries_today": row["total_queries"],
        "cost_today_usd": round(row["total_cost"], 4),
        "avg_latency_ms": round(row["avg_latency"]),
    }
```

**Verify:**
```bash
uvicorn api_server:app --reload
```
Open `localhost:8000/docs` — all endpoints visible.

---

## Step 5.2 — Build app/api/middleware.py

**What you do:**

```python
import uuid
import time
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)


def add_middleware(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.time()
        response = await call_next(request)
        latency = int((time.time() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        log_event(log, "info", "request_handled",
                  method=request.method,
                  path=request.url.path,
                  status=response.status_code,
                  latency_ms=latency,
                  request_id=request_id)
        return response
```

**Verify:**

Make a request → check browser dev tools → response should have `X-Request-ID` header.

---

## Step 5.3 — Streaming endpoint

Already built in Step 5.1 as `POST /ask/stream`. Test it in the terminal:

```bash
curl -X POST localhost:8000/ask/stream \
     -H "Content-Type: application/json" \
     -d '{"question": "What is our APAC discount policy?"}' \
     --no-buffer
```

Watch tokens appear one by one. If they all arrive at once — the streaming is not working. Debug `llm_client.stream()`.

**Verify:** Tokens appear with visible individual delays, not all at once.

---

## Step 5.4 — Build api_server.py — server entry point

**What you do:**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.api.middleware import add_middleware
from app.config import settings
from app.utils import db
from app.store import vector_store
from app.utils.logger import get_logger
import uvicorn

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    settings.validate()
    db.init_db()
    count = vector_store.count()
    log.info(f"RAG service ready. Chunks loaded: {count}")
    yield
    # shutdown
    log.info("RAG service shutting down.")


app = FastAPI(
    title="RAG Analytics Assistant",
    version="1.0.0",
    lifespan=lifespan
)

add_middleware(app)
app.include_router(router)

# serve frontend from root — GET / returns index.html
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)
```

**Start the server:**
```bash
python api_server.py
```

**Verify:**
- Startup log: `RAG service ready. Chunks loaded: 87`
- `localhost:8000/health` returns `{"status": "ok", "chunk_count": 87, ...}`
- `localhost:8000` returns the frontend HTML page

---

## Step 5.5 — Write tests/test_api.py and tests/test_hitl_api.py — 11 tests

**What you do:**

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

@pytest.fixture
def client():
    from api_server import app
    return TestClient(app)

def test_ask_valid_question_returns_200(client):
    with patch("main.run") as mock_run:
        mock_run.return_value = {
            "type": "answer",
            "answer": "The APAC discount is 20%.",
            "sources": [],
            "session_id": "test"
        }
        r = client.post("/ask", json={"question": "What is APAC discount?"})
        assert r.status_code == 200
        assert "answer" in r.json()

def test_ask_short_question_returns_422(client):
    r = client.post("/ask", json={"question": "Hi"})
    assert r.status_code == 422

def test_health_returns_chunk_count(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "chunk_count" in r.json()

def test_stats_returns_cost_and_queries(client):
    r = client.get("/stats")
    assert r.status_code == 200
    assert "queries_today" in r.json()
    assert "cost_today_usd" in r.json()

def test_ingest_returns_200(client):
    with patch("ingest.main"):
        r = client.post("/ingest")
        assert r.status_code == 200
```

```python
# tests/test_hitl_api.py
def test_confirm_yes_creates_jira_story(client):
    import main as pipeline
    eid = "test-escalation-id"
    pipeline.pending_escalations[eid] = {
        "question": "test question",
        "session_id": "s1",
        "confidence": 0.4,
        "chunks": [],
    }
    with patch("app.hitl.jira_client.create_story") as mock_jira:
        mock_jira.return_value = {
            "jira_key": "ANALYTICS-1",
            "jira_url": "https://example.atlassian.net/browse/ANALYTICS-1"
        }
        r = client.post("/ask/confirm-escalation",
                        json={"escalation_id": eid, "confirmed": True})
        assert r.status_code == 200
        assert r.json()["jira_key"] == "ANALYTICS-1"

def test_confirm_no_never_calls_jira(client):
    import main as pipeline
    eid = "test-no-id"
    pipeline.pending_escalations[eid] = {
        "question": "test", "session_id": "s1", "confidence": 0.4, "chunks": []
    }
    with patch("app.hitl.jira_client.create_story") as mock_jira:
        r = client.post("/ask/confirm-escalation",
                        json={"escalation_id": eid, "confirmed": False})
        assert r.status_code == 200
        assert "no problem" in r.json()["message"].lower()
        mock_jira.assert_not_called()

def test_confirm_unknown_id_returns_404(client):
    r = client.post("/ask/confirm-escalation",
                    json={"escalation_id": "nonexistent", "confirmed": True})
    assert r.status_code == 404

def test_escalate_returns_message_and_id(client):
    with patch("main.run") as mock_run:
        mock_run.return_value = {
            "type": "escalation",
            "escalation_id": "abc123",
            "message": "Would you like me to create a Jira story?"
        }
        r = client.post("/ask/escalate", json={"question": "What is the CEO salary?"})
        assert r.status_code == 200

def test_escalate_short_question_returns_422(client):
    r = client.post("/ask/escalate", json={"question": "Hi"})
    assert r.status_code == 422

def test_full_escalation_flow(client):
    import main as pipeline
    eid = "full-flow-test"
    pipeline.pending_escalations[eid] = {
        "question": "Full flow test question?",
        "session_id": "s1", "confidence": 0.3, "chunks": []
    }
    with patch("app.hitl.jira_client.create_story") as mock_jira:
        mock_jira.return_value = {"jira_key": "ANALYTICS-99", "jira_url": "http://test"}
        r = client.post("/ask/confirm-escalation",
                        json={"escalation_id": eid, "confirmed": True})
        assert r.json()["jira_key"] == "ANALYTICS-99"
        call_args = mock_jira.call_args[1]
        assert "Full flow test question?" in call_args["question"]
```

**Run:**
```bash
python -m pytest tests/test_api.py tests/test_hitl_api.py -v
```

**Verify:** 11 tests pass. No real server started. No real Jira calls made.

---

## Step 5.6 — Manual API testing via Swagger UI

Open `localhost:8000/docs` and test every endpoint manually:

1. `GET /health` — chunk count matches ingest.py output
2. `POST /ask` — confident question returns answer with sources
3. `POST /ask/stream` — tokens visible in curl output one by one
4. `POST /ask/escalate` — borderline question returns escalation message
5. `POST /ask/confirm-escalation confirmed=true` — Jira story URL returned
6. `POST /ask/confirm-escalation confirmed=false` — polite message, check Jira for no new story
7. `GET /stats` — query count has incremented

**Verify:** All seven endpoints work correctly before moving to Phase 6.

---

## Phase 5 complete checklist

- [ ] All 7 endpoints defined with Pydantic models
- [ ] Short questions return 422 automatically
- [ ] CORS middleware enabled
- [ ] `X-Request-ID` header on every response
- [ ] Streaming endpoint — tokens arrive one by one in curl
- [ ] Startup log shows chunk count
- [ ] `GET /` returns frontend HTML via StaticFiles
- [ ] 11 tests pass: `python -m pytest tests/test_api.py tests/test_hitl_api.py -v`
- [ ] All 7 endpoints manually verified in Swagger UI

**Next:** Phase 6 — Frontend chat UI
