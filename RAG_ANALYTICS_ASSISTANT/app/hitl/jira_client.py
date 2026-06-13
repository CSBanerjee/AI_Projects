import base64
# base64 is Python's built-in library for Base64 encoding
# Jira's REST API uses HTTP Basic Authentication which requires
# credentials encoded as Base64: "email:api_token" → base64 string
# this is a standard web authentication scheme — not encryption

import requests
# requests is the standard Python HTTP library
# used to make the POST request to the Jira REST API
# installed via: uv pip install requests

from app.config import settings
# settings.JIRA_EMAIL        → your Atlassian account email
# settings.JIRA_API_TOKEN    → your Jira API token (not your password)
# settings.JIRA_BASE_URL     → your Atlassian domain e.g. https://yourcompany.atlassian.net
# settings.JIRA_PROJECT_KEY  → the Jira project where stories are created e.g. "ANALYTICS"

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "app.hitl.jira_client" inside this file


def _get_headers() -> dict:
    # -> dict → returns the HTTP headers required for every Jira API request
    #
    # The leading underscore _ signals this is a private helper function
    # only called by create_story() below — not intended to be imported
    # directly by other modules

    credentials = base64.b64encode(
        f"{settings.JIRA_EMAIL}:{settings.JIRA_API_TOKEN}".encode()
        # f-string builds: "your@email.com:your-api-token"
        # .encode() converts the string to bytes — base64 requires bytes input
    ).decode()
    # base64.b64encode() encodes the bytes to Base64 bytes
    # .decode() converts those bytes back to a regular string
    # result: "eW91ckBlbWFpbC5jb206eW91ci1hcGktdG9rZW4="

    return {
        "Authorization": f"Basic {credentials}",
        # "Basic " prefix is required by HTTP Basic Auth specification
        # Jira reads this header to authenticate the request

        "Content-Type": "application/json",
        # tells Jira the request body is JSON
        # without this header Jira may reject the payload
    }


def create_story(question: str,
                 session_id: str,
                 confidence: float,
                 chunks: list) -> dict:
    # question: str    → the original question the user asked
    #                    stored in the Jira story so the analyst knows what to investigate
    # session_id: str  → UUID of the conversation session
    #                    stored in the story for traceability
    # confidence: float → the confidence score from validator.validate()
    #                     stored in the story so the analyst knows how uncertain the AI was
    # chunks: list     → Document objects from retriever.search()
    #                    stored as context so the analyst sees what the AI retrieved
    #                    empty list [] if the retriever found nothing
    # -> dict          → {"jira_key": "ANALYTICS-142", "jira_url": "https://..."}

    url = f"{settings.JIRA_BASE_URL}/rest/api/3/issue"
    # Jira REST API v3 endpoint for creating issues
    # /rest/api/3/issue is the standard endpoint for all Jira Cloud instances
    # settings.JIRA_BASE_URL is e.g. "https://yourcompany.atlassian.net"

    chunk_summary = "\n".join(
        f"- [{c.metadata.get('source', 'unknown')}]: {c.page_content[:200]}"
        for c in chunks
    ) if chunks else "No relevant chunks retrieved."
    # build a bullet-point summary of the retrieved chunks
    # each line shows the source file and first 200 characters of content
    # example:
    #   - [discount_policy.txt]: APAC enterprise accounts receive 20% discount...
    #   - [kpi_definitions.txt]: Win rate is calculated as closed won divided by...
    #
    # [:200] limits each chunk preview to 200 characters to keep the story readable
    # if chunks is empty list → "No relevant chunks retrieved." as a fallback

    payload = {
        "fields": {
            "project": {"key": settings.JIRA_PROJECT_KEY},
            # which Jira project to create the story in
            # settings.JIRA_PROJECT_KEY is e.g. "ANALYTICS"
            # the project must already exist in Jira

            "summary": f"RAG escalation: {question[:80]}",
            # the story title — shown in the Jira board
            # "RAG escalation:" prefix makes it easy to filter AI-generated stories
            # question[:80] limits to 80 characters — Jira summary has a character limit

            "description": {
                "type": "doc",
                "version": 1,
                # Jira uses Atlassian Document Format (ADF) for rich text descriptions
                # "doc" with version 1 is the current ADF format

                "content": [{
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": (
                            f"Question: {question}\n\n"
                            # the full original question — not truncated
                            f"Confidence score: {confidence:.2f}\n\n"
                            # how confident the AI was — :.2f formats to 2 decimal places
                            # e.g. "Confidence score: 0.21"
                            f"Retrieved context:\n{chunk_summary}\n\n"
                            # what the AI retrieved from ChromaDB before failing
                            f"Session ID: {session_id}"
                            # for tracing the conversation in logs if needed
                        )
                    }]
                }]
            },

            "issuetype": {"name": "Story"},
            # creates a Story type issue (not Bug or Task)
            # Story is appropriate because this represents a business question
            # that needs human investigation

            "priority": {"name": "Medium"},
            # Medium priority — the user asked for help but it is not urgent
            # could be made configurable based on confidence score in a future version

            "labels": ["rag-escalation", "ai-assistant"],
            # labels make it easy to filter all AI-generated stories in Jira
            # "rag-escalation" → this came from the RAG pipeline
            # "ai-assistant"   → this came from the AI assistant product
        }
    }

    log_event(log, "info", "jira_create_start",
              project=settings.JIRA_PROJECT_KEY,
              question=question[:50])
    # log before making the API call in case the call hangs or fails
    # if the log shows jira_create_start but not jira_story_created
    # it means the API call timed out or was rejected

    response = requests.post(
        url,
        json=payload,
        # json= serialises the payload dict to JSON and sets Content-Type automatically
        # equivalent to: data=json.dumps(payload), headers={"Content-Type": "application/json"}
        headers=_get_headers(),
        # authentication and content type headers
        timeout=10
        # fail if Jira does not respond within 10 seconds
        # prevents the pipeline from hanging indefinitely on a Jira outage
    )

    # ── Error handling ────────────────────────────────────────────────────────
    # check specific status codes before the generic "not ok" check
    # this gives the developer a precise error message for the most common failures

    if response.status_code == 401:
        # 401 Unauthorized — credentials are wrong or token is expired
        raise RuntimeError(
            "Jira authentication failed.\n"
            "Check JIRA_EMAIL and JIRA_API_TOKEN in your .env file.\n"
            "Get a token from: https://id.atlassian.com/manage-profile/security/api-tokens"
        )

    if response.status_code == 404:
        # 404 Not Found — the project key or base URL is wrong
        raise RuntimeError(
            f"Jira project '{settings.JIRA_PROJECT_KEY}' not found.\n"
            "Check JIRA_PROJECT_KEY and JIRA_BASE_URL in your .env file."
        )

    if not response.ok:
        # catch any other non-2xx status code
        # response.ok is True for 200-299, False for everything else
        raise RuntimeError(
            f"Jira API error {response.status_code}: {response.text[:200]}"
            # response.text[:200] shows the first 200 chars of the error body
            # helps diagnose unexpected errors without logging the full response
        )

    # ── Success ───────────────────────────────────────────────────────────────

    data = response.json()
    # parse the JSON response body into a Python dict
    # successful Jira story creation returns: {"id": "12345", "key": "ANALYTICS-142", ...}

    jira_key = data["key"]
    # "key" is the human-readable story identifier e.g. "ANALYTICS-142"
    # shown to the user in the chat: "Done. ANALYTICS-142 created."

    jira_url = f"{settings.JIRA_BASE_URL}/browse/{jira_key}"
    # build the direct URL to the story in Jira
    # e.g. "https://yourcompany.atlassian.net/browse/ANALYTICS-142"
    # shown to the user as a clickable link in the Phase 6 frontend

    log_event(log, "info", "jira_story_created",
              key=jira_key,
              url=jira_url)
    # log success — key and URL recorded for audit trail
    # appears in logs as:
    #   event=jira_story_created key=ANALYTICS-142 url=https://yourcompany.../ANALYTICS-142

    return {"jira_key": jira_key, "jira_url": jira_url}
    # returned to api_server.py which sends it to the frontend
    # the frontend shows: "Done. ANALYTICS-142 created. [View story →]"