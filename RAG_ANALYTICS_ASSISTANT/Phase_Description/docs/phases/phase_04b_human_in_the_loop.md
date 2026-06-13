# Phase 4B — Human in the Loop via Jira

**Steps:** 6  
**Goal:** When the pipeline cannot answer confidently, the agent asks the user whether to create a Jira story. Yes → story created. No → polite decline.

---

## The flow

```
Validator returns low confidence score
      ↓
trigger.should_escalate() → True
      ↓
Agent asks: "I could not find a reliable answer.
Would you like me to create a Jira story?"
      ↓
User: Yes → POST /ask/confirm-escalation confirmed=true
             → Jira story created → "Done. ANALYTICS-142 created."
User: No  → POST /ask/confirm-escalation confirmed=false
             → "Okay, no problem." — Jira never called
```

---

## Step 4B.1 — Build app/hitl/trigger.py

**What you do:**

```python
from app.config import settings
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)


def should_escalate(confidence_score: float) -> bool:
    threshold = settings.SIMILARITY_THRESHOLD
    result = confidence_score < threshold

    log_event(log, "info", "escalation_check",
              confidence=round(confidence_score, 3),
              threshold=threshold,
              will_escalate=result)
    return result
```

**Verify:**
```bash
python -c "
from app.hitl import trigger
print(trigger.should_escalate(0.5))   # True
print(trigger.should_escalate(0.85))  # False
print(trigger.should_escalate(0.7))   # False — at threshold, not below
print(trigger.should_escalate(0.0))   # True
"
```

---

## Step 4B.2 — Build app/hitl/agent_prompt.py

**What you do:**

```python
def build_escalation_message(question: str) -> str:
    return (
        f'I was unable to find a reliable answer to your question:\n\n'
        f'"{question}"\n\n'
        f'Would you like me to create a Jira story so the analytics team '
        f'can investigate and get back to you?\n\n'
        f'Reply **Yes** to create a story or **No** to skip.'
    )
```

**Verify:**
```bash
python -c "
from app.hitl import agent_prompt
msg = agent_prompt.build_escalation_message('What is the CFO bonus structure?')
print(msg)
"
```
Read the output out loud. It must sound like a helpful colleague, not a technical error.

---

## Step 4B.3 — Build app/hitl/jira_client.py

**What you do:**

```python
import base64
import requests
from app.config import settings
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)


def _get_headers() -> dict:
    credentials = base64.b64encode(
        f"{settings.JIRA_EMAIL}:{settings.JIRA_API_TOKEN}".encode()
    ).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }


def create_story(question: str, session_id: str,
                 confidence: float, chunks: list) -> dict:
    url = f"{settings.JIRA_BASE_URL}/rest/api/3/issue"

    chunk_summary = "\n".join(
        f"- [{c.metadata.get('source', 'unknown')}]: {c.page_content[:200]}"
        for c in chunks
    ) if chunks else "No relevant chunks retrieved."

    payload = {
        "fields": {
            "project":     {"key": settings.JIRA_PROJECT_KEY},
            "summary":     f"RAG escalation: {question[:80]}",
            "description": {
                "type":    "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": (
                            f"Question: {question}\n\n"
                            f"Confidence score: {confidence:.2f}\n\n"
                            f"Retrieved context:\n{chunk_summary}\n\n"
                            f"Session ID: {session_id}"
                        )
                    }]
                }]
            },
            "issuetype": {"name": "Story"},
            "priority":  {"name": "Medium"},
            "labels":    ["rag-escalation", "ai-assistant"],
        }
    }

    log_event(log, "info", "jira_create_start",
              project=settings.JIRA_PROJECT_KEY,
              question=question[:50])

    response = requests.post(url, json=payload, headers=_get_headers(), timeout=10)

    if response.status_code == 401:
        raise RuntimeError(
            "Jira authentication failed.\n"
            "Check JIRA_EMAIL and JIRA_API_TOKEN in your .env file.\n"
            "Get a token from: https://id.atlassian.com/manage-profile/security/api-tokens"
        )
    if response.status_code == 404:
        raise RuntimeError(
            f"Jira project '{settings.JIRA_PROJECT_KEY}' not found.\n"
            "Check JIRA_PROJECT_KEY and JIRA_BASE_URL in your .env file."
        )
    if not response.ok:
        raise RuntimeError(
            f"Jira API error {response.status_code}: {response.text[:200]}"
        )

    data = response.json()
    jira_key = data["key"]
    jira_url = f"{settings.JIRA_BASE_URL}/browse/{jira_key}"

    log_event(log, "info", "jira_story_created",
              key=jira_key, url=jira_url)

    return {"jira_key": jira_key, "jira_url": jira_url}
```

**Get your Jira API token:**
Go to `https://id.atlassian.com/manage-profile/security/api-tokens` → Create API token → Copy it into `.env`.

**Verify:**
Test with your real credentials:
```bash
python -c "
from app.hitl import jira_client
result = jira_client.create_story(
    question='Test RAG escalation',
    session_id='test-123',
    confidence=0.45,
    chunks=[]
)
print(result)
"
```
A story with label `rag-escalation` should appear on your Jira board.

---

## Step 4B.4 — Wire HITL into main.py

The trigger and escalation flow are already wired in the `main.py` from Phase 4.5. Verify it works by forcing a low confidence threshold:

```bash
# Temporarily set in .env: SIMILARITY_THRESHOLD=0.99
python main.py
# Should return escalation message instead of answer
# Reset SIMILARITY_THRESHOLD=0.7 after testing
```

**Verify:**
With threshold at 0.99, `python main.py` returns `"type": "escalation"` not `"type": "answer"`.

---

## Step 4B.5 — Write tests — 12 tests across 3 files

**What you do:**

**tests/test_trigger.py:**
```python
from app.hitl import trigger

def test_low_confidence_returns_true():
    assert trigger.should_escalate(0.5) is True

def test_high_confidence_returns_false():
    assert trigger.should_escalate(0.85) is False

def test_exactly_at_threshold_returns_false():
    # 0.7 is not below 0.7
    assert trigger.should_escalate(0.7) is False

def test_zero_confidence_returns_true():
    assert trigger.should_escalate(0.0) is True
```

**tests/test_agent_prompt.py:**
```python
from app.hitl import agent_prompt

def test_prompt_contains_original_question():
    msg = agent_prompt.build_escalation_message("What is ASP?")
    assert "What is ASP?" in msg

def test_prompt_contains_yes_and_no():
    msg = agent_prompt.build_escalation_message("test")
    assert "Yes" in msg
    assert "No" in msg

def test_prompt_is_non_empty_string():
    msg = agent_prompt.build_escalation_message("test")
    assert isinstance(msg, str)
    assert len(msg.strip()) > 0
```

**tests/test_jira_client.py:**
```python
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document

SAMPLE_CHUNKS = [Document(page_content="content", metadata={"source": "test.txt"})]

def make_mock_response(status_code, json_data=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.ok = 200 <= status_code < 300
    mock.json.return_value = json_data or {}
    mock.text = str(json_data)
    return mock

def test_creates_story_with_correct_summary():
    with patch("app.hitl.jira_client.requests.post") as mock_post:
        mock_post.return_value = make_mock_response(201, {"key": "ANALYTICS-1"})
        from app.hitl import jira_client
        result = jira_client.create_story("What is ASP?", "s1", 0.5, SAMPLE_CHUNKS)
        call_args = mock_post.call_args[1]["json"]
        assert call_args["fields"]["summary"].startswith("RAG escalation:")

def test_creates_story_with_correct_labels():
    with patch("app.hitl.jira_client.requests.post") as mock_post:
        mock_post.return_value = make_mock_response(201, {"key": "ANALYTICS-1"})
        from app.hitl import jira_client
        jira_client.create_story("test", "s1", 0.5, [])
        call_args = mock_post.call_args[1]["json"]
        labels = call_args["fields"]["labels"]
        assert "rag-escalation" in labels
        assert "ai-assistant" in labels

def test_returns_jira_key_on_201():
    with patch("app.hitl.jira_client.requests.post") as mock_post:
        mock_post.return_value = make_mock_response(201, {"key": "ANALYTICS-142"})
        from app.hitl import jira_client
        result = jira_client.create_story("test", "s1", 0.5, [])
        assert result["jira_key"] == "ANALYTICS-142"
        assert "ANALYTICS-142" in result["jira_url"]

def test_raises_runtime_error_on_401():
    with patch("app.hitl.jira_client.requests.post") as mock_post:
        mock_post.return_value = make_mock_response(401)
        from app.hitl import jira_client
        with pytest.raises(RuntimeError, match="authentication"):
            jira_client.create_story("test", "s1", 0.5, [])

def test_raises_runtime_error_on_404():
    with patch("app.hitl.jira_client.requests.post") as mock_post:
        mock_post.return_value = make_mock_response(404)
        from app.hitl import jira_client
        with pytest.raises(RuntimeError, match="not found"):
            jira_client.create_story("test", "s1", 0.5, [])
```

**Run:**
```bash
python -m pytest tests/test_trigger.py tests/test_agent_prompt.py tests/test_jira_client.py -v
```

**Verify:** 12 tests pass. Zero real Jira API calls made.

---

## Step 4B.6 — Write tests/conftest.py — shared fixtures

**What you do:**

```python
import pytest
import sqlite3
from unittest.mock import MagicMock
from langchain_core.documents import Document
from app.utils import db


@pytest.fixture
def sample_document():
    return Document(
        page_content="APAC discount policy allows up to 20% for enterprise accounts.",
        metadata={"source": "discount_policy.txt", "chunk_index": 0}
    )

@pytest.fixture
def sample_chunks(sample_document):
    return [sample_document]

@pytest.fixture
def mock_openai_chat_response():
    mock = MagicMock()
    mock.content = "The APAC discount policy allows up to 20% for enterprise accounts."
    return mock

@pytest.fixture
def mock_jira_201():
    mock = MagicMock()
    mock.status_code = 201
    mock.ok = True
    mock.json.return_value = {"key": "ANALYTICS-999"}
    return mock

@pytest.fixture
def in_memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.init_db(conn)
    yield conn
    conn.close()

@pytest.fixture
def sample_session_id():
    return "test-session-abc123"
```

**Run:**
```bash
python -m pytest tests/ -v
```

**Verify:** All tests from all phases still pass. Conftest fixtures load automatically.

---

## Phase 4B complete checklist

- [ ] `trigger.py` — `should_escalate(0.5)` True, `should_escalate(0.85)` False, `should_escalate(0.7)` False
- [ ] `agent_prompt.py` — VP-readable message with Yes and No options
- [ ] `jira_client.py` — creates story, returns key, raises on 401 and 404
- [ ] `main.py` — escalation triggers on low confidence, normal answer on high confidence
- [ ] 12 tests pass: `python -m pytest tests/test_trigger.py tests/test_agent_prompt.py tests/test_jira_client.py -v`
- [ ] `conftest.py` created — all tests still pass: `python -m pytest tests/ -v`

**Next:** Phase 5 — FastAPI service
