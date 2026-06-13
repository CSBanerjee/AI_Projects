# LEARNING.md — RAG Analytics Assistant

Lessons, surprises, and technical insights gathered during the build.
Updated continuously throughout all phases.

---

## Phase 1 — Project setup

**uv is dramatically faster than pip.**
`uv pip install -r requirements.txt` completes in seconds vs 2–3 minutes
with standard pip. The speed difference matters most when iterating on
requirements or rebuilding Docker images in CI.

**settings.validate() pays for itself immediately.**
The first time you boot the pipeline and get a clear
"OPENAI_API_KEY not set — add it to .env" instead of a traceback
from inside langchain_openai, you appreciate the investment.

**__init__.py files are load-bearing.**
Forgetting even one of them produces a confusing `ModuleNotFoundError`
deep inside a totally unrelated import chain. Creating them all at
once in Step 1.2 is cheaper than debugging missing-package errors later.

---

### Step 1.6 — app/config/settings.py

**What does this file do in plain English?**  
`settings.py` is the first file the entire project is built on. Its job
is to read every configuration value — API keys, folder paths, model
names, chunk sizes — from the `.env` file once, in one place, and make
them available to every other module as named Python variables. Instead
of each module reaching into the environment directly with `os.getenv()`
scattered across dozens of files, every module simply does
`from app.config import settings` and reads `settings.OPENAI_API_KEY` or
`settings.CHUNK_SIZE`. If a value ever needs to change — say you want to
switch from `gpt-4o` to `gpt-4o-mini` — you change one line in `.env`
and every module that uses `settings.MODEL` picks it up automatically.
Nothing else needs to be touched.

**What was the hardest part to understand?**  
The `validate()` function. On the surface it looked straightforward —
check some keys, raise errors if they are missing. But reviewing it
closely revealed three problems that were not obvious at first glance.
`DATA_DIR` was defined but used nowhere. The ChromaDB folder was being
created but never checked for content — meaning a developer who forgot
to run `python ingest.py` would get no error at startup, only a silent
failure when the first question arrived. And the `docs/` folder existence
check and emptiness check were merged into a single `or` condition that
produced a vague "missing or empty" message, making it impossible to know
which problem actually occurred. Separating each check into its own block
with its own precise message made the function both clearer and genuinely
more useful. See `FINDINGS.md` — Phase 1 for the full breakdown.

**What would break if you removed this file?**  
Everything. Every other module in the project starts with
`from app.config import settings`. Remove `settings.py` and the entire
import chain collapses — not just one module but all of them
simultaneously. Beyond the import failure, there would be no central
place to validate that required keys are present before the pipeline
runs. Each module would have to do its own checks, or — worse — not
check at all and produce cryptic errors deep inside third-party libraries
when a key turns out to be missing. A missing `OPENAI_API_KEY` would not
produce "OPENAI_API_KEY not set — add it to .env". It would produce a
raw Anthropic or OpenAI HTTP 401 error buried inside a LangChain
traceback that points to a file you did not write. `settings.py` exists
precisely to prevent that — it is the one file that catches configuration
problems before the pipeline ever starts running.

---

## Phase 2 — Document ingestion
**What does this file do in plain English?**
Phase 2 helped me understand how the document ingestion pipeline works end-to-end — starting with loading source files, splitting them into smaller chunks, converting those chunks into embeddings (numeric vector representations), and finally storing those vectors in a vector database called ChromaDB. The entire workflow is orchestrated through a single entry-point file, ingest.py, which automates the pipeline from start to finish.

Resetting ChromaDB is similar to resetting a traditional database and rebuilding it from scratch. This becomes necessary when previously stored vectors are no longer useful or reliable—for example, after updating source documents, changing chunking configurations, modifying embedding models, or cleaning duplicate/corrupted data.

**What was the hardest part to understand?**
The test file as the coding was difficult.
**What would break if you removed this file?**
This is a complete pipeline. any of the files are not working means the entire process will fail.
---

## Phase 3 — Retrieval
Phase 3 helped me understand how a RAG system actually finds relevant knowledge from a vector database before passing context to an LLM.
I learned how semantic retrieval works by converting a user question into an embedding and searching the vector store for the most similar chunks using retriever.py. This showed me that retrieval is not keyword matching, but similarity search based on meaning.
I also learned why raw retrieval is not enough. By adding a similarity threshold, the system can reject weak or irrelevant matches instead of always returning something. This prevents bad context from reaching the LLM and reduces hallucination risk.
The metadata filter taught me how retrieval can be constrained to specific documents, allowing more targeted searches such as limiting results only to discount_policy.txt.
Through retrieval_test.py and eval_dataset.json, I learned how to evaluate retrieval quality quantitatively instead of guessing. By testing multiple questions against expected sources, I could calculate retrieval precision and validate whether the system performs above the required threshold of 0.70.
The chunk size experiment demonstrated how chunking directly impacts retrieval quality. Smaller chunks can fragment meaning, while larger chunks can introduce semantic noise. Running experiments with multiple chunk sizes helped me make a data-driven decision for the optimal chunk configuration.
Building session_store.py introduced the concept of short-term conversational memory, allowing the system to store recent user and assistant turns for future follow-up queries.
Finally, writing unit tests in tests/test_retrieval.py taught me the importance of validating retrieval logic independently from real OpenAI and ChromaDB calls. Mocking helped ensure that threshold logic, metadata filtering, warning handling, and session storage work reliably.
Overall, Phase 3 taught me a critical RAG principle:

A language model is only as good as the context retrieved for it.

Even a strong LLM cannot generate trustworthy answers if retrieval quality is poor. This phase established the foundation required before moving into generation and guardrails in Phase 4.

---

## Phase 4 — Generation + guardrails
(fill in after completing Phase 4)

---

## Phase 4B — Human in the loop
(fill in after completing Phase 4B)

---

## Phase 5 — FastAPI
(fill in after completing Phase 5)

---

## Phase 6 — Frontend
(fill in after completing Phase 6)

---

## Phase 7 — Evaluation
(fill in after completing Phase 7)

---

## Phase 8 — Deploy
(fill in after completing Phase 8)