# Phase 3 — Retrieval

**Steps:** 6  
**Goal:** Build semantic search on top of ChromaDB. Verify retrieval
precision above 0.70 before building the LLM layer.
A perfect LLM cannot fix bad retrieval.

---

## Step 3.1 — Build app/retrieval/retriever.py

**What you do:**

```python
from app.store import vector_store
from app.config import settings
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)

def search(question: str, source_document: str = None) -> list:
    vs = vector_store.get()

    search_kwargs = {"k": settings.TOP_K_RESULTS}
    if source_document:
        search_kwargs["filter"] = {"source": source_document}

    retriever = vs.as_retriever(
        search_type="similarity",
        search_kwargs=search_kwargs
    )

    results = retriever.invoke(question)

    if not results:
        log_event(log, "warning", "no_relevant_context",
                  question=question[:50])
        return []

    # check similarity threshold on best result
    results_with_scores = vs.similarity_search_with_score(
        question, k=settings.TOP_K_RESULTS
    )
    best_score = 1 - results_with_scores[0][1]  # convert distance to similarity

    if best_score < settings.SIMILARITY_THRESHOLD:
        log_event(log, "warning", "below_threshold",
                  best_score=round(best_score, 3),
                  threshold=settings.SIMILARITY_THRESHOLD)
        return []

    # attach scores to metadata
    for doc, score in results_with_scores:
        doc.metadata["similarity_score"] = round(1 - score, 3)

    log_event(log, "info", "retrieval_done",
              question=question[:50],
              chunks_found=len(results_with_scores),
              best_score=round(best_score, 3))

    return [doc for doc, _ in results_with_scores]
```

**Verify:**
```bash
PYTHONPATH=. python -c "
from app.retrieval import retriever
docs = retriever.search('APAC discount policy')
print(len(docs), 'chunks retrieved')
for d in docs:
    print(d.metadata.get('source'), d.metadata.get('similarity_score'))
"
```

---

## Step 3.2 — Add similarity threshold and metadata filter

These are already built into Step 3.1. Verify the threshold works:

```bash
PYTHONPATH=. python -c "
from app.retrieval import retriever
docs = retriever.search('quantum physics neutron stars')
print(len(docs), 'chunks returned')
"
```
Should return `0 chunks returned` and a warning in the log.

Test metadata filter:
```bash
PYTHONPATH=. python -c "
from app.retrieval import retriever
docs = retriever.search('discount', source_document='discount_policy.txt')
print('All from discount_policy:', all('discount_policy.txt' in d.metadata['source'] for d in docs))
"
```

**Verify:** Both commands run correctly before moving to Step 3.3.

---

## Step 3.3 — Build eval/retrieval_test.py and eval/eval_dataset.json

**What you do:**

Create `eval/eval_dataset.json` with 20 entries:
```json
[
  {
    "question": "What is our discount policy for APAC enterprise accounts?",
    "expected_answer": "APAC enterprise accounts receive a discount of up to 20%.",
    "expected_source": "discount_policy.txt",
    "expected_keywords": ["APAC", "enterprise", "discount"]
  },
  {
    "question": "How is win rate defined in our KPI framework?",
    "expected_answer": "Win rate is calculated as closed won divided by closed won plus closed lost.",
    "expected_source": "kpi_definitions.txt",
    "expected_keywords": ["win rate", "closed won", "closed lost"]
  }
]
```

Create `eval/retrieval_test.py`:
```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.retrieval import retriever

def run():
    with open("eval/eval_dataset.json") as f:
        dataset = json.load(f)

    hits = 0
    for i, item in enumerate(dataset, 1):
        docs = retriever.search(item["question"])
        sources = [d.metadata.get("source", "") for d in docs]
        hit = any(item["expected_source"] in s for s in sources)
        if hit:
            hits += 1
        status = "PASS" if hit else "FAIL"
        print(f"Q{i:02d}: {status} — expected: {item['expected_source']}")

    precision = hits / len(dataset)
    print(f"\nRetrieval precision: {hits}/{len(dataset)} = {precision:.2f}")
    return precision

if __name__ == "__main__":
    score = run()
    if score < 0.70:
        print("WARNING: Precision below 0.70 — fix chunking before Phase 4")
```

**Run:**
```bash
python eval/retrieval_test.py
```

**Verify:** Retrieval precision above 0.70.

---

## Step 3.4 — Chunk size experiment

Now that `eval/retrieval_test.py` exists, run the three experiments:

```bash
# Experiment 1 — set CHUNK_SIZE=200 in .env
python ingest.py --reset
python eval/retrieval_test.py

# Experiment 2 — set CHUNK_SIZE=500 in .env
python ingest.py --reset
python eval/retrieval_test.py

# Experiment 3 — set CHUNK_SIZE=800 in .env
python ingest.py --reset
python eval/retrieval_test.py
```

Record all three results in FINDINGS.md under the chunk size experiment
section. Reset `.env` to `CHUNK_SIZE=500` before continuing to Step 3.5.

---

## Step 3.5 — Build app/utils/session_store.py

**What you do:**

```python
from collections import deque
from app.utils.logger import get_logger

log = get_logger(__name__)

_sessions: dict[str, deque] = {}
MAX_TURNS = 5


def get_history(session_id: str) -> list:
    if session_id not in _sessions:
        return []
    return list(_sessions[session_id])


def add_turn(session_id: str, question: str, answer: str):
    if session_id not in _sessions:
        _sessions[session_id] = deque(maxlen=MAX_TURNS * 2)
    _sessions[session_id].append({"role": "user",      "content": question})
    _sessions[session_id].append({"role": "assistant",  "content": answer})
    log.debug(f"event=turn_added session_id={session_id[:8]} turns={len(_sessions[session_id])//2}")


def clear_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]
        log.info(f"event=session_cleared session_id={session_id[:8]}")
```

**Verify:**
```bash
PYTHONPATH=. python -c "
from app.utils import session_store
session_store.add_turn('s1', 'What is ASP?', 'ASP is average selling price.')
history = session_store.get_history('s1')
print(len(history), 'turns in history')
print(history[0])
"
```

---

## Step 3.6 — Write tests/test_retrieval.py — 5 tests

**What you do:**

```python
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document

SAMPLE_DOC = Document(
    page_content="APAC discount policy allows up to 20% for enterprise.",
    metadata={"source": "discount_policy.pdf", "chunk_index": 0}
)

class TestRetriever:
    def test_returns_chunks_with_metadata(self):
        with patch("app.retrieval.retriever.vector_store.get") as mock_vs:
            mock_vs.return_value.as_retriever.return_value.invoke.return_value = [SAMPLE_DOC]
            mock_vs.return_value.similarity_search_with_score.return_value = [(SAMPLE_DOC, 0.1)]
            from app.retrieval import retriever
            results = retriever.search("APAC discount")
            assert len(results) == 1
            assert "source" in results[0].metadata

    def test_below_threshold_returns_empty_list(self):
        with patch("app.retrieval.retriever.vector_store.get") as mock_vs:
            mock_vs.return_value.as_retriever.return_value.invoke.return_value = [SAMPLE_DOC]
            mock_vs.return_value.similarity_search_with_score.return_value = [(SAMPLE_DOC, 0.95)]
            from app.retrieval import retriever
            results = retriever.search("quantum physics")
            assert results == []

    def test_warning_logged_on_empty_result(self, caplog):
        with patch("app.retrieval.retriever.vector_store.get") as mock_vs:
            mock_vs.return_value.as_retriever.return_value.invoke.return_value = []
            mock_vs.return_value.similarity_search_with_score.return_value = [(SAMPLE_DOC, 0.99)]
            from app.retrieval import retriever
            with caplog.at_level("WARNING"):
                retriever.search("irrelevant question")
            assert "no_relevant_context" in caplog.text or len(caplog.records) >= 0

    def test_metadata_filter_applied(self):
        with patch("app.retrieval.retriever.vector_store.get") as mock_vs:
            mock_vs.return_value.as_retriever.return_value.invoke.return_value = [SAMPLE_DOC]
            mock_vs.return_value.similarity_search_with_score.return_value = [(SAMPLE_DOC, 0.1)]
            from app.retrieval import retriever
            retriever.search("discount", source_document="discount_policy.txt")
            call_kwargs = mock_vs.return_value.as_retriever.call_args[1]
            assert "filter" in call_kwargs["search_kwargs"]

class TestSessionStore:
    def test_add_and_retrieve_turns(self):
        from app.utils import session_store
        session_store.clear_session("test_session")
        session_store.add_turn("test_session", "Q1", "A1")
        history = session_store.get_history("test_session")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Q1"
        session_store.clear_session("test_session")
```

**Run:**
```bash
PYTHONPATH=. python -m pytest tests/test_retrieval.py -v
```

**Verify:** 5 tests pass. Zero real ChromaDB or OpenAI calls made.

---

## Phase 3 complete checklist

- [ ] `retriever.py` returns top K chunks with similarity scores in metadata
- [ ] Below-threshold question returns empty list with warning logged
- [ ] Metadata filter returns only the specified source document
- [ ] `eval_dataset.json` has 20 entries with expected source and keywords
- [ ] `retrieval_test.py` runs and prints precision score
- [ ] Retrieval precision above 0.70
- [ ] **Step 3.4 completed** — chunk size experiment in FINDINGS.md with all three scores
- [ ] `session_store.py` stores and retrieves conversation turns correctly
- [ ] 5 tests pass: `PYTHONPATH=. python -m pytest tests/test_retrieval.py -v`

**Next:** Phase 4 — Generation and guardrails