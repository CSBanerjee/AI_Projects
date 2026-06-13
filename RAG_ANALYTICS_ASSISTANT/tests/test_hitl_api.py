"""
tests/test_hitl_api.py — Phase 5 Step 5.5

Tests for the HITL (Human in the Loop) API endpoints:
  - POST /ask/confirm-escalation (confirmed=True)
  - POST /ask/confirm-escalation (confirmed=False)
  - POST /ask/confirm-escalation (unknown ID → 404)
  - POST /ask/escalate
  - POST /ask/escalate (short question → 422)
  - POST /ask/confirm-escalation (full flow)

Total: 6 tests. No real Jira calls made.

Run from the project root:
    PYTHONPATH=. python -m pytest tests/test_hitl_api.py -v
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    """
    Shared TestClient fixture — same as test_api.py.
    Mocks lifespan dependencies so no real ChromaDB or API keys needed.
    """
    with patch("app.store.vector_store.count", return_value=36), \
         patch("app.config.settings.validate"), \
         patch("app.utils.db.init_db"):
        from api_server import app
        return TestClient(app)


def test_confirm_yes_creates_jira_story(client):
    """
    When confirmed=True, the endpoint must call jira_client.create_story()
    and return the jira_key in the response.
    """
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
        # Jira must have been called exactly once
        mock_jira.assert_called_once()


def test_confirm_no_never_calls_jira(client):
    """
    When confirmed=False, the endpoint must NOT call jira_client.create_story().
    The response must contain a polite decline message.
    """
    import main as pipeline
    eid = "test-no-id"
    pipeline.pending_escalations[eid] = {
        "question": "test question",
        "session_id": "s1",
        "confidence": 0.4,
        "chunks": []
    }
    with patch("app.hitl.jira_client.create_story") as mock_jira:
        r = client.post("/ask/confirm-escalation",
                        json={"escalation_id": eid, "confirmed": False})
        assert r.status_code == 200
        assert "no problem" in r.json()["message"].lower()
        # Jira must never have been called
        mock_jira.assert_not_called()


def test_confirm_unknown_id_returns_404(client):
    """
    When the escalation_id does not exist in pending_escalations,
    the endpoint must return HTTP 404 Not Found.
    """
    r = client.post("/ask/confirm-escalation",
                    json={"escalation_id": "nonexistent-id", "confirmed": True})
    assert r.status_code == 404


def test_escalate_returns_message_and_id(client):
    """
    POST /ask/escalate must return HTTP 200 with the escalation message.
    main.run() is mocked to return an escalation response.
    """
    with patch("main.run") as mock_run:
        mock_run.return_value = {
            "type": "escalation",
            "escalation_id": "abc123",
            "message": "Would you like me to create a Jira story?"
        }
        r = client.post("/ask/escalate",
                        json={"question": "What is the CEO salary structure?"})
        assert r.status_code == 200


def test_escalate_short_question_returns_422(client):
    """
    POST /ask/escalate with a short question must return HTTP 422.
    Same min_length=5 validation as /ask applies here.
    """
    r = client.post("/ask/escalate", json={"question": "Hi"})
    assert r.status_code == 422


def test_full_escalation_flow(client):
    """
    Full end-to-end escalation flow:
    1. Store a pending escalation in main.pending_escalations
    2. POST /ask/confirm-escalation with confirmed=True
    3. Verify jira_key is returned
    4. Verify the question was passed to jira_client.create_story()
    """
    import main as pipeline
    eid = "full-flow-test"
    pipeline.pending_escalations[eid] = {
        "question": "Full flow test question?",
        "session_id": "s1",
        "confidence": 0.3,
        "chunks": []
    }
    with patch("app.hitl.jira_client.create_story") as mock_jira:
        mock_jira.return_value = {
            "jira_key": "ANALYTICS-99",
            "jira_url": "http://test.atlassian.net/browse/ANALYTICS-99"
        }
        r = client.post("/ask/confirm-escalation",
                        json={"escalation_id": eid, "confirmed": True})
        assert r.status_code == 200
        assert r.json()["jira_key"] == "ANALYTICS-99"

        # verify the question was passed correctly to jira_client
        call_kwargs = mock_jira.call_args[1]
        assert "Full flow test question?" in call_kwargs["question"]