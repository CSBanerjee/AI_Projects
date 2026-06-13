import uuid
# uuid is Python's built-in library for generating unique identifiers
# used to create a unique escalation_id for each pending escalation
# and a unique session_id when none is provided by the caller

from app.config import settings
# settings.validate() checks all required keys and folders at startup
# settings.SIMILARITY_THRESHOLD → used by trigger.should_escalate() in Stage 6

from app.guardrails import input_guard, validator
# input_guard.check()    → Stage 1: blocks injection, PII, toxicity
# validator.validate()   → Stage 5: checks answer quality

from app.retrieval import retriever
# retriever.search() → Stage 2: finds relevant chunks from ChromaDB

from app.generation import prompt, llm_client
# prompt.build()      → Stage 3: formats the prompt with context and history
# llm_client.ask()    → Stage 4: sends prompt to GPT-4o, returns answer

from app.utils import session_store, cost_tracker
# session_store.get_history() → retrieves conversation history for multi-turn
# session_store.add_turn()    → saves question and answer to history
# cost_tracker.log_query()    → writes cost and latency to SQLite

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "__main__" when run directly, "main" when imported
# every log line from this file shows that name as the source

pending_escalations = {}
# module-level dictionary storing escalations waiting for user confirmation
# key:   escalation_id (UUID string)
# value: dict with question, session_id, confidence, chunks
#
# When the user asks a low-confidence question:
#   main.py stores the escalation here with a UUID key
#   returns the UUID to the frontend
#
# When the user clicks Yes on the escalation card:
#   routes.py looks up the UUID in this dict
#   calls jira_client.create_story() with the stored details
#   deletes the entry from this dict
#
# When the user clicks No:
#   routes.py deletes the entry without calling Jira


def run(question: str, session_id: str = None, history: list = None) -> dict:
    # question: str       → the user's question as plain text
    # session_id: str     → UUID identifying the conversation session
    #                       if None, a new UUID is generated automatically
    #                       the same session_id must be sent for follow-up questions
    # -> dict             → always contains "type" key with one of:
    #                         "blocked"    → input guard rejected the question
    #                         "escalation" → low confidence, asking user to escalate
    #                         "answer"     → successful answer with sources

    session_id = session_id or str(uuid.uuid4())
    # if no session_id was provided, generate a new UUID
    # str(uuid.uuid4()) → e.g. "550e8400-e29b-41d4-a716-446655440000"

    log_event(log, "info", "pipeline_start",
              session_id=session_id[:8],
              question=question[:50])
    # log the start of this pipeline run
    # session_id[:8] logs only the first 8 characters to keep the log readable
    # question[:50] logs only the first 50 characters
    # appears in logs as:
    #   event=pipeline_start session_id=550e8400 question=What is our APAC discount...

    # ── Stage 1: Input guard ──────────────────────────────────────────────────
    # First line of defence — check before any API calls or retrieval
    # Blocks: prompt injection, PII (credit cards, SSN), toxicity
    # If blocked: return immediately without touching ChromaDB or OpenAI

    guard = input_guard.check(question)
    if not guard.is_safe:
        return {"type": "blocked", "message": guard.reason}
        # guard.reason is deliberately vague for injection
        # more specific for PII: "Input contains sensitive data"
        # more specific for toxicity: "Input contains inappropriate content"

    # ── Stage 2: Retrieval ────────────────────────────────────────────────────
    # Search ChromaDB for the most relevant chunks
    # Returns up to TOP_K_RESULTS chunks whose similarity score >= SIMILARITY_THRESHOLD
    # Returns [] (empty list) if no relevant chunks found

    chunks = retriever.search(question)
    # chunks is a list of Document objects, each with:
    #   .page_content → the text of the chunk
    #   .metadata     → source file, page number, similarity_score

    # ── Stage 3: Build prompt ─────────────────────────────────────────────────
    # Get conversation history for multi-turn context
    # Build the formatted prompt using RAG_PROMPT (with chunks) or NO_CONTEXT_PROMPT

    history = history if history is not None else session_store.get_history(session_id)
    # use history from frontend (localStorage) if provided
    # fallback to server-side session_store
    # returns a list of previous turns: [{"role": "user", "content": "..."}, ...]
    # empty list [] for the first question in a session

    messages = prompt.build(question, chunks, history)
    # if chunks is empty → NO_CONTEXT_PROMPT → LLM will say "I cannot find this"
    # if chunks exist    → RAG_PROMPT → LLM answers from the retrieved context

    # ── Stage 4: Generate ─────────────────────────────────────────────────────
    # Send the formatted prompt to GPT-4o and get the answer
    # Retries up to MAX_RETRIES times on rate limit errors

    response = llm_client.ask(messages)
    # response is a dict: {"text": "The answer...", "latency_ms": 1243}

    answer = response["text"]
    # the raw answer string from GPT-4o

    # ── Stage 5: Validate ─────────────────────────────────────────────────────
    # Check the answer quality before returning it
    # Check 1: format (word count)
    # Check 2: relevance (cosine similarity between question and answer)
    # Check 3: faithfulness (word overlap between answer and chunks)

    validation = validator.validate(answer, question, chunks)
    # validation.passed           → True/False
    # validation.confidence_score → 0.0 to 1.0
    # validation.failure_reason   → None or description of what failed

    # ── Stage 6: Escalation check ─────────────────────────────────────────────
    # If confidence is below SIMILARITY_THRESHOLD → ask user if they want Jira story
    # The user clicks Yes or No in the frontend — handled by /ask/confirm-escalation

    from app.hitl import trigger, agent_prompt
    # imported here to avoid circular imports at module load time
    # trigger and agent_prompt are only needed in Stage 6

    if trigger.should_escalate(validation.confidence_score):
        # confidence_score < SIMILARITY_THRESHOLD → escalate

        escalation_id = str(uuid.uuid4())
        # generate a unique ID for this escalation
        # used by the frontend to identify which escalation the user is confirming

        pending_escalations[escalation_id] = {
            "question": question,
            # the full original question — stored for the Jira story
            "session_id": session_id,
            # stored for traceability in the Jira story
            "confidence": validation.confidence_score,
            # stored so the analyst knows how uncertain the AI was
            "chunks": chunks,
            # stored so the analyst sees what the AI retrieved
            # even if retrieval found nothing, chunks=[] is stored
        }

        message = agent_prompt.build_escalation_message(question)
        # builds the human-readable message asking the user to confirm escalation
        # e.g. "I was unable to find a reliable answer... Would you like me to create a Jira story?"

        log_event(log, "info", "escalation_triggered",
                  confidence=validation.confidence_score)
        # log at INFO — escalation is expected behaviour, not an error

        return {
            "type": "escalation",
            "escalation_id": escalation_id,
            # sent to the frontend so it knows which escalation to confirm
            "message": message,
            # shown to the user as the escalation card
        }

    # ── Stage 7: Save history and log cost ────────────────────────────────────
    # Only reached if validation passed — answer is trustworthy enough to return

    session_store.add_turn(session_id, question, answer)
    # saves this question/answer pair to the in-memory session history
    # the next question from this session will include this turn as history

    cost_tracker.log_query(
        question=question,
        session_id=session_id,
        embedding_tokens=0,
        # embedding token count is not currently tracked
        # LangChain does not expose it easily from similarity_search_with_score
        # a future improvement: extract from response metadata
        llm_input_tokens=0,
        # LLM input token count — same limitation as embedding_tokens
        llm_output_tokens=0,
        # LLM output token count — same limitation as above
        latency_ms=response["latency_ms"],
        # total time for the LLM call in milliseconds
        guardrail_passed=validation.passed,
        # True if validator said the answer is good quality
        escalated=False
        # False — if we reach Stage 7, no escalation happened
    )

    sources = [
        {
            "source": c.metadata.get("source"),
            # full path to the source file e.g. "/path/to/discount_policy.txt"
            "score": c.metadata.get("similarity_score")
            # similarity score added by retriever.py e.g. 0.45
        }
        for c in chunks
    ]
    # list comprehension builds one dict per retrieved chunk
    # the frontend uses this to populate the source cards in the right panel

    return {
        "type": "answer",
        "answer": answer,
        # the LLM generated answer — shown in the chat bubble
        "sources": sources,
        # list of source dicts — shown as citation cards in the right panel
        "session_id": session_id
        # echoed back so the frontend can store it for the next question
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # this block runs ONLY when main.py is executed directly:
    #   python main.py
    # it does NOT run when main.py is imported by routes.py
    # used as a smoke test to verify the full pipeline works end to end

    settings.validate()
    # check all required keys and folders before running the pipeline
    # raises a clear error if OPENAI_API_KEY is missing or ChromaDB is empty

    result = run("What is our APAC discount policy?")
    # run one real question through all 7 stages
    # this makes a real OpenAI API call and searches real ChromaDB data
    print(result)
    # print the full result dict to the terminal
    # expected: {"type": "answer", "answer": "...", "sources": [...], "session_id": "..."}
    # or:       {"type": "escalation", "escalation_id": "...", "message": "..."}