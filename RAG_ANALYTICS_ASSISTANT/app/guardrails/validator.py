from dataclasses import dataclass
# dataclass decorator automatically generates __init__, __repr__ etc.
# used to create a clean ValidationResult object with three fields

from langchain_openai import OpenAIEmbeddings
# OpenAIEmbeddings converts text into 1536-dimensional vectors
# used in Check 2 to measure semantic similarity between question and answer
# same model used in embedder.py and vector_store.py — must be consistent

import numpy as np
# numpy provides efficient mathematical operations on arrays
# used in _cosine_similarity() to compute the dot product and vector norms

from app.config import settings
# settings.EMBEDDING_MODEL    → which OpenAI model converts text to vectors
# settings.OPENAI_API_KEY     → authenticates requests to OpenAI
# settings.SIMILARITY_THRESHOLD → minimum confidence score to pass validation

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "app.guardrails.validator" inside this file


# ── ValidationResult dataclass ────────────────────────────────────────────────

@dataclass
class ValidationResult:
    passed: bool
    # True  → confidence_score >= SIMILARITY_THRESHOLD AND no failure reasons
    #         answer is trustworthy — return it to the user
    # False → confidence_score < SIMILARITY_THRESHOLD OR at least one check failed
    #         answer is not trustworthy — escalate to Jira

    confidence_score: float
    # average of all check scores — a number between 0.0 and 1.0
    # 1.0 = perfect answer — correct length, highly relevant, grounded in chunks
    # 0.0 = completely failed — too short, irrelevant, or hallucinated

    failure_reason: str
    # None when passed=True — no issues found
    # "Answer too short (3 words); Low answer relevance (0.32)" when failed
    # semicolon-separated list of all failure reasons for debugging


# ── _cosine_similarity() ──────────────────────────────────────────────────────

def _cosine_similarity(a: list, b: list) -> float:
    # a: list → first vector  (question vector from OpenAI)
    # b: list → second vector (answer vector from OpenAI)
    # -> float → similarity score between 0.0 and 1.0
    #
    # Cosine similarity measures the angle between two vectors.
    # Two vectors pointing in the same direction → angle=0° → similarity=1.0
    # Two vectors perpendicular                  → angle=90° → similarity=0.0
    # Two vectors pointing opposite directions   → angle=180° → similarity=-1.0
    #
    # Formula: cos(θ) = (a · b) / (|a| × |b|)
    #   a · b  = dot product = sum of element-wise products
    #   |a|    = L2 norm = square root of sum of squared elements

    a, b = np.array(a), np.array(b)
    # convert Python lists to numpy arrays for efficient matrix operations

    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    # np.dot(a, b)          → dot product of the two vectors
    # np.linalg.norm(a)     → L2 norm (magnitude) of vector a
    # np.linalg.norm(b)     → L2 norm (magnitude) of vector b
    # dividing dot product by product of norms normalises the result to [-1, 1]
    # float() converts numpy float64 to a plain Python float


# ── validate() ────────────────────────────────────────────────────────────────

def validate(answer: str, question: str, chunks: list) -> ValidationResult:
    # answer:   str  → the text the LLM generated in llm_client.ask()
    # question: str  → the original user question — used in Check 2
    # chunks:   list → Document objects from retriever.search()
    #                  used in Check 3 — empty list [] if retriever found nothing
    # -> ValidationResult → passed, confidence_score, failure_reason

    scores = []
    # collects one score per check — averaged at the end into confidence_score

    reasons = []
    # collects failure messages — joined with semicolons into failure_reason

    # ── Check 1: Format ───────────────────────────────────────────────────────
    # Is the answer a reasonable length?
    # Too short → LLM gave a useless one-word or partial answer
    # Too long  → LLM went off topic or ignored the max_tokens guidance
    # Just right → full sentence with substance

    word_count = len(answer.split())
    # answer.split() splits on whitespace and returns a list of words
    # len() counts how many words are in the answer

    if word_count < 10:
        reasons.append(f"Answer too short ({word_count} words)")
        # a 3-word answer like "Yes, it is." cannot contain useful information
        scores.append(0.0)
        # score 0.0 — this check completely failed

    elif word_count > 500:
        reasons.append(f"Answer too long ({word_count} words)")
        # very long answers usually indicate the LLM ignored context constraints
        scores.append(0.5)
        # score 0.5 — partial failure, not complete failure

    else:
        scores.append(1.0)
        # score 1.0 — answer is a reasonable length, this check passed


    # ── Check 2: Relevance ────────────────────────────────────────────────────
    # Does the answer actually address the question?
    # We convert both the question and the answer to vectors and measure
    # how similar they are. A relevant answer should point in a similar
    # direction to the question in vector space.
    #
    # Example:
    #   question: "What is the APAC discount?"
    #   answer A: "The APAC discount is 20% for enterprise accounts." → high similarity
    #   answer B: "The sales cycle target is 95 days."               → low similarity

    try:
        emb_model = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            # must be the same model used throughout — text-embedding-3-small
            openai_api_key=settings.OPENAI_API_KEY
        )

        q_vec = emb_model.embed_query(question)
        # converts the question string to a 1536-dimensional vector
        # embed_query() is used for search queries (vs embed_documents() for storage)

        a_vec = emb_model.embed_query(answer)
        # converts the answer string to a 1536-dimensional vector
        # using the same model ensures the vectors are in the same space

        relevance = _cosine_similarity(q_vec, a_vec)
        # measures how similar the question and answer vectors are
        # high score → answer is semantically close to the question
        # low score  → answer is about something different

        scores.append(relevance)

        if relevance < 0.5:
            reasons.append(f"Low answer relevance ({relevance:.2f})")
            # relevance below 0.5 means the answer is more different than
            # similar to the question — likely off topic

    except Exception as e:
        log.warning(f"Relevance check skipped: {e}")
        # if the OpenAI API call fails (network error, rate limit etc.)
        # we skip this check rather than failing the whole validation
        scores.append(0.7)
        # assume the answer is probably okay — neutral-positive score
        # 0.7 is above SIMILARITY_THRESHOLD so it does not cause escalation alone


    # ── Check 3: Faithfulness ─────────────────────────────────────────────────
    # Does the answer use words from the retrieved chunks?
    # If the answer contains many words that never appeared in any chunk,
    # it is likely hallucinating — drawing from training data instead of context.
    #
    # Method: measure word overlap between answer and all chunks combined.
    # This is a simple lexical check — not semantic — but effective as a
    # first-pass hallucination detector.
    #
    # Example:
    #   chunk text:  "APAC enterprise accounts receive a 20% discount"
    #   answer:      "APAC enterprise accounts get a 20 percent discount"
    #   overlap:     APAC, enterprise, accounts, discount → high overlap → faithful
    #
    #   answer:      "The capital of France is Paris"
    #   overlap:     none of these words appear in the chunk → hallucination

    if chunks:
        chunk_text = " ".join(c.page_content.lower() for c in chunks)
        # concatenate the page_content of all chunks into one long string
        # .lower() normalises case so "APAC" and "apac" are treated the same

        answer_words = set(answer.lower().split())
        # convert answer to a set of unique lowercase words
        # set() removes duplicates — "the the the discount" → {"the", "discount"}

        chunk_words = set(chunk_text.split())
        # convert all chunk text to a set of unique lowercase words

        overlap = len(answer_words & chunk_words) / max(len(answer_words), 1)
        # answer_words & chunk_words → intersection — words in BOTH sets
        # divided by answer word count → proportion of answer words in chunks
        # max(..., 1) prevents division by zero for empty answers

        scores.append(min(overlap * 5, 1.0))
        # multiply overlap by 5 to scale it to 0-1 range
        # raw overlap is typically low (0.1-0.3) because answers use
        # different sentence structure than the source text
        # multiplying by 5 gives: 0.2 overlap → 1.0 score (capped at 1.0)
        # min(..., 1.0) ensures the score never exceeds 1.0

        if overlap < 0.1:
            reasons.append("Answer appears disconnected from retrieved context")
            # less than 10% word overlap strongly suggests hallucination
            # the answer is drawing from somewhere other than the chunks

    else:
        scores.append(0.5)
        # no chunks were retrieved — we cannot measure faithfulness
        # 0.5 is a neutral score — neither passing nor failing
        # the no-context path is handled upstream in retriever.py


    # ── Calculate final confidence score ──────────────────────────────────────

    confidence = sum(scores) / len(scores)
    # average all check scores into one confidence score
    # Check 1 contributes 1 score, Check 2 contributes 1 score, Check 3 contributes 1 score
    # equal weighting — all three checks matter equally

    passed = confidence >= settings.SIMILARITY_THRESHOLD and not reasons
    # passed is True only when BOTH conditions are met:
    #   1. confidence score is above SIMILARITY_THRESHOLD (default 0.3)
    #   2. no failure reasons were collected
    # even a high confidence score fails if there are explicit failure reasons
    # this ensures edge cases like "long answer but irrelevant" are caught

    log_event(log, "info", "validation_result",
              passed=passed,
              confidence=round(confidence, 3),
              reasons=";".join(reasons) if reasons else "none")
    # log a structured summary of the validation
    # appears in logs as:
    #   event=validation_result passed=True confidence=0.847 reasons=none
    # or:
    #   event=validation_result passed=False confidence=0.234 reasons=Answer too short (3 words)

    return ValidationResult(
        passed=passed,
        confidence_score=round(confidence, 3),
        # round to 3 decimal places — 0.847 not 0.8472981...
        failure_reason="; ".join(reasons) if reasons else None
        # None when passed — no issues
        # "reason 1; reason 2" when failed — semicolon separated
    )
    # this ValidationResult is used by trigger.py in Phase 4B:
    #   if trigger.should_escalate(result.confidence_score):
    #       → create Jira story
    #       → ask user if they want human help