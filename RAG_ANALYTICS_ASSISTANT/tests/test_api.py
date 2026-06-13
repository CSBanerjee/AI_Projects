"""
tests/test_api.py — Phase 5 Step 5.5

Tests for the core API endpoints:
  - POST /ask
  - GET  /health
  - GET  /stats
  - POST /ingest

Total: 5 tests. No real server started. No real API calls made.

Run from the project root:
    PYTHONPATH=. python -m pytest tests/test_api.py -v
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    """
    Creates a FastAPI TestClient wrapping the api_server app.
    TestClient runs the app in-process — no real HTTP server is started.
    The lifespan (startup/shutdown) events are triggered automatically.
    """
    with patch("app.store.vector_store.count", return_value=36), \
         patch("app.config.settings.validate"), \
         patch("app.utils.db.init_db"):
        # mock validate(), init_db(), and count() so the lifespan
        # startup does not require real ChromaDB or real API keys
        from api_server import app
        return TestClient(app)


def test_ask_valid_question_returns_200(client):
    """
    A valid question (5+ characters) must return HTTP 200.
    The response must contain an "answer" field.
    main.run() is mocked — no real OpenAI call made.
    """
    with patch("main.run") as mock_run:
        mock_run.return_value = {
            "type": "answer",
            "answer": "The APAC discount is 20 percent.",
            "sources": [],
            "session_id": "test-session"
        }
        r = client.post("/ask", json={"question": "What is APAC discount?"})
        assert r.status_code == 200
        assert "answer" in r.json()


def test_ask_short_question_returns_422(client):
    """
    A question shorter than 5 characters must return HTTP 422.
    FastAPI validates this automatically via the Field(min_length=5) constraint.
    No pipeline code runs — validation happens before the endpoint function.
    """
    r = client.post("/ask", json={"question": "Hi"})
    assert r.status_code == 422
    # 422 Unprocessable Entity — FastAPI's standard response for validation errors


def test_health_returns_chunk_count(client):
    """
    GET /health must return HTTP 200 with a chunk_count field.
    Used by Docker health checks and Railway to confirm the server is alive.
    """
    r = client.get("/health")
    assert r.status_code == 200
    assert "chunk_count" in r.json()
    assert "status" in r.json()
    assert r.json()["status"] == "ok"


def test_stats_returns_cost_and_queries(client):
    """
    GET /stats must return HTTP 200 with queries_today and cost_today_usd.
    Reads from SQLite query_log table — returns 0 if no queries yet today.
    """
    r = client.get("/stats")
    assert r.status_code == 200
    assert "queries_today" in r.json()
    assert "cost_today_usd" in r.json()
    assert "avg_latency_ms" in r.json()


def test_ingest_returns_200(client):
    """
    POST /ingest must return HTTP 200.
    ingest.main() is mocked — no real ingestion happens.
    """
    with patch("ingest.main"), \
         patch("app.store.vector_store.count", return_value=36):
        r = client.post("/ingest")
        assert r.status_code == 200
        assert "message" in r.json()