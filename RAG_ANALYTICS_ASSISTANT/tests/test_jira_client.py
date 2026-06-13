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