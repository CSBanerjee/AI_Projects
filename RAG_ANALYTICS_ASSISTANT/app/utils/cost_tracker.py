from app.utils.db import get_connection
# get_connection() returns a live SQLite connection to rag_analytics.db
# the query_log table was created by db.init_db() in Phase 1 Step 1.7

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "app.utils.cost_tracker" inside this file


# ── OpenAI pricing constants ──────────────────────────────────────────────────
# Prices are per 1 million tokens as of the model versions used in this project
# Update these if OpenAI changes pricing or if you switch to a different model

EMBEDDING_COST_PER_1M = 0.02
# text-embedding-3-small: $0.02 per 1 million tokens
# used when the question is converted to a vector in retriever.search()

GPT4O_INPUT_PER_1M = 5.00
# gpt-4o input tokens: $5.00 per 1 million tokens
# input = the full prompt sent to the LLM (system message + context + question)
# a typical prompt with 3 chunks is approximately 500-800 tokens

GPT4O_OUTPUT_PER_1M = 15.00
# gpt-4o output tokens: $15.00 per 1 million tokens
# output = the answer the LLM generated
# with MAX_TOKENS=400, output is at most 400 tokens per question
# output tokens cost 3x more than input tokens


# ── calculate_cost() ─────────────────────────────────────────────────────────

def calculate_cost(embedding_tokens: int,
                   input_tokens: int,
                   output_tokens: int) -> float:
    # embedding_tokens: int → number of tokens used to embed the question
    #                         typically 10-30 tokens per question
    # input_tokens: int     → number of tokens in the full prompt sent to the LLM
    #                         system message + context chunks + question
    #                         typically 400-800 tokens
    # output_tokens: int    → number of tokens in the LLM's answer
    #                         up to MAX_TOKENS=400
    # -> float              → total cost in US dollars for this one question

    return (
        (embedding_tokens / 1_000_000) * EMBEDDING_COST_PER_1M +
        # embedding cost: tokens used / 1M × price per 1M
        # e.g. 20 tokens → (20 / 1_000_000) * 0.02 = $0.0000004

        (input_tokens / 1_000_000) * GPT4O_INPUT_PER_1M +
        # input cost: tokens in prompt / 1M × price per 1M
        # e.g. 600 tokens → (600 / 1_000_000) * 5.00 = $0.003

        (output_tokens / 1_000_000) * GPT4O_OUTPUT_PER_1M
        # output cost: tokens in answer / 1M × price per 1M
        # e.g. 150 tokens → (150 / 1_000_000) * 15.00 = $0.00225
    )
    # typical total per question: ~$0.005 to $0.010
    # 1000 questions per month ≈ $5 to $10


# ── log_query() ──────────────────────────────────────────────────────────────

def log_query(question: str,
              session_id: str,
              embedding_tokens: int,
              llm_input_tokens: int,
              llm_output_tokens: int,
              latency_ms: int,
              guardrail_passed: bool,
              escalated: bool) -> None:
    # question: str         → the user's question — only first 80 chars stored
    #                         to avoid storing sensitive or very long questions
    # session_id: str       → UUID identifying the conversation session
    # embedding_tokens: int → tokens used in retriever.search()
    # llm_input_tokens: int → tokens in the prompt sent to llm_client.ask()
    # llm_output_tokens: int → tokens in the generated answer
    # latency_ms: int       → total time from question to answer in milliseconds
    # guardrail_passed: bool → did validator.validate() return passed=True
    # escalated: bool       → was this question sent to Jira via trigger.py

    cost = calculate_cost(embedding_tokens, llm_input_tokens, llm_output_tokens)
    # calculate the dollar cost for this question before writing to the database

    conn = get_connection()
    # get a live connection to rag_analytics.db
    # conn.row_factory = sqlite3.Row is already set in get_connection()
    # allowing column access by name: row["total_cost_usd"]

    conn.execute("""
        INSERT INTO query_log
        (question_preview, session_id, embedding_tokens, llm_input_tokens,
         llm_output_tokens, total_cost_usd, latency_ms, guardrail_passed, escalated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        question[:80],
        # question_preview — first 80 characters only
        # prevents storing a full long question or sensitive context in the DB

        session_id,
        # identifies which conversation this question belongs to
        # the /stats endpoint can filter by session_id for per-user reporting

        embedding_tokens,
        # tokens used for embedding — currently passed as 0 from main.py
        # because LangChain does not easily expose the token count from
        # similarity_search_with_score — a future improvement to add

        llm_input_tokens,
        # tokens in the prompt — currently passed as 0 from main.py
        # LangChain's response_metadata contains token counts
        # a future improvement: extract from response.response_metadata

        llm_output_tokens,
        # tokens in the answer — currently passed as 0 from main.py
        # same future improvement as above

        round(cost, 6),
        # total cost rounded to 6 decimal places
        # 6 decimal places captures costs as small as $0.000001

        latency_ms,
        # total pipeline latency in milliseconds
        # from when question arrived to when answer was returned

        guardrail_passed,
        # True  → answer passed validator.validate()
        # False → answer failed validation, likely escalated

        escalated
        # True  → trigger.should_escalate() fired, Jira story created
        # False → answer returned directly to user
    ))

    conn.commit()
    # commit() writes the row permanently to disk
    # without commit() the INSERT would be lost when the connection closes

    log_event(log, "info", "cost_logged",
              cost_usd=round(cost, 6),
              total_tokens=embedding_tokens + llm_input_tokens + llm_output_tokens)
    # log a structured summary of this cost entry
    # appears in logs as:
    #   event=cost_logged cost_usd=0.005125 total_tokens=770
    # useful for monitoring cost trends without querying the database