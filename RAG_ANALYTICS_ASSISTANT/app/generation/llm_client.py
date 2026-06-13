import time
# time is Python's built-in library for measuring elapsed time
# used to calculate latency_ms — how long the LLM took to respond

from langchain_openai import ChatOpenAI
# ChatOpenAI is LangChain's wrapper around the OpenAI Chat Completions API
# it handles authentication, request formatting, and response parsing

from langsmith import traceable
# traceable is a LangSmith decorator that wraps the function in a trace
# every call to ask() appears as a named span in the LangSmith dashboard
# showing the full prompt, response, and latency

from app.config import settings
# settings.MODEL           → which OpenAI model to use (e.g. gpt-4o)
# settings.OPENAI_API_KEY  → authenticates every request to OpenAI
# settings.MAX_RETRIES     → how many times to retry on rate limit
# settings.MAX_TOKENS      → maximum length of the LLM response
# settings.TEMPERATURE     → controls creativity of the response (0.0–1.0)

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "app.generation.llm_client" inside this file


def build_client() -> ChatOpenAI:
    # creates and returns a configured ChatOpenAI client
    # called by both ask() and stream() to get a fresh client each time
    # kept as a separate function so tests can mock it easily

    return ChatOpenAI(
        model=settings.MODEL,
        # which OpenAI model to use — set in .env as MODEL=gpt-4o
        # gpt-4o is the recommended model for business Q&A quality

        temperature=settings.TEMPERATURE,
        # controls how creative or random the response is
        # range: 0.0 (fully deterministic) to 1.0 (highly creative)
        # set in .env as TEMPERATURE=0.2 — very low creativity
        # low temperature keeps answers factual and consistent
        # previously hardcoded as 0.2 — now configurable via .env

        max_tokens=settings.MAX_TOKENS,
        # maximum number of tokens the LLM can produce in one response
        # set in .env as MAX_TOKENS=400
        # 400 is suitable for factual Q&A answers
        # increase to 600-800 for detailed summaries
        # previously hardcoded as 400 — now configurable via .env

        openai_api_key=settings.OPENAI_API_KEY
        # the secret key from .env that authenticates requests to OpenAI
        # validate() in settings.py confirms this is set at startup
    )


@traceable(name="generate_answer")
# @traceable wraps ask() so every call is recorded in LangSmith
# name="generate_answer" is the label shown in the LangSmith trace dashboard
# the full prompt, response, and token counts appear in the trace
def ask(messages: list) -> dict:
    # messages: list → the list of formatted prompt messages from prompt.py
    #                  built by prompt.build() which injects the question,
    #                  retrieved chunks as context, and conversation history
    # -> dict        → returns {"text": answer_string, "latency_ms": int}

    client = build_client()
    # create a fresh client for this request
    # we call build_client() here not at module level so the client
    # is only created when ask() is actually called — not at import time

    start = time.time()
    # record the start time so we can calculate latency after the response

    for attempt in range(1, settings.MAX_RETRIES + 1):
        # loop from 1 to MAX_RETRIES inclusive
        # MAX_RETRIES=2 means: attempt 1, then attempt 2 if attempt 1 fails
        # we retry only on rate limit errors — not on auth or general errors
        try:
            response = client.invoke(messages)
            # client.invoke() sends the messages to OpenAI and waits for the response
            # this is a blocking call — it waits until OpenAI responds
            # the response object has a .content attribute with the answer text

            latency_ms = int((time.time() - start) * 1000)
            # calculate how long the request took in milliseconds
            # time.time() returns seconds as a float
            # subtract start time, multiply by 1000 to convert to ms
            # int() rounds to a whole number

            log_event(log, "info", "llm_response",
                      model=settings.MODEL,
                      latency_ms=latency_ms,
                      temperature=settings.TEMPERATURE,
                      max_tokens=settings.MAX_TOKENS)
            # log a structured line recording the response details
            # now includes temperature and max_tokens so every log line
            # shows exactly which settings produced this response
            # appears in logs as:
            #   event=llm_response model=gpt-4o latency_ms=1243 temperature=0.2 max_tokens=400

            return {
                "text": response.content,
                # response.content is the raw answer string from the LLM
                # e.g. "The APAC enterprise discount is 20% for accounts above USD 150,000 ACV."

                "latency_ms": latency_ms,
                # how long this request took — used by cost_tracker.py
                # also logged in LangSmith for performance monitoring
            }

        except Exception as e:
            if "rate" in str(e).lower():
                # rate limit error — OpenAI is throttling our requests
                # wait 15 seconds then retry
                log.warning(f"Rate limit hit. Waiting 15s... (attempt {attempt}/{settings.MAX_RETRIES})")
                time.sleep(15)
                # time.sleep(15) pauses execution for 15 seconds before the next attempt

            elif "auth" in str(e).lower():
                # authentication error — OPENAI_API_KEY is wrong or expired
                # no point retrying — raise immediately with a clear message
                raise RuntimeError(
                    "OpenAI authentication failed. Check OPENAI_API_KEY in .env"
                )

            else:
                # any other error — log it and retry up to MAX_RETRIES times
                log.error(f"LLM error attempt {attempt}: {e}")
                if attempt >= settings.MAX_RETRIES:
                    # we have used all our retries — give up and raise
                    raise RuntimeError(f"LLM call failed after {settings.MAX_RETRIES} attempts: {e}")

    raise RuntimeError("LLM call failed after all retries.")
    # safety net — should never be reached because the loop always
    # either returns successfully or raises inside the loop


def stream(messages: list):
    # stream() is used by the FastAPI /ask/stream endpoint in Phase 5
    # instead of waiting for the full response, it yields tokens one by one
    # this allows the frontend to display the answer as it is being generated
    #
    # messages: list → same format as ask() — built by prompt.build()
    # yields: str    → one token at a time as the LLM generates them

    client = build_client()
    # create a fresh client — same as ask()

    for chunk in client.stream(messages):
        # client.stream() returns a generator that yields chunks as they arrive
        # each chunk is a partial response object with a .content attribute
        # .content is a string — usually one word or part of a word
        yield chunk.content
        # yield sends each token to the caller immediately
        # the FastAPI StreamingResponse in Phase 5 picks these up and
        # sends them to the browser as they arrive