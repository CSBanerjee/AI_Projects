import re
# re is Python's built-in regular expressions library
# re.search(pattern, text) returns a match object if the pattern is found
# or None if not found — used to scan question text for forbidden patterns

from dataclasses import dataclass
# dataclass decorator automatically generates __init__, __repr__ etc.
# used here to create a clean GuardResult object with two fields

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "app.guardrails.input_guard" inside this file


# ── Injection patterns ────────────────────────────────────────────────────────
# These patterns detect prompt injection attacks — attempts by a user to
# override the system prompt and make the LLM behave differently.
# \s+ matches one or more whitespace characters (space, tab, newline)
# (your\s+)? makes "your" optional — matches both "reveal system prompt"
# and "reveal your system prompt"

INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    # "ignore previous instructions" — classic injection attempt
    r"reveal\s+(your\s+)?system\s+prompt",
    # "reveal system prompt" or "reveal your system prompt"
    r"pretend\s+you\s+are",
    # "pretend you are" — attempts to make LLM adopt a different persona
    r"as\s+a\s+dan",
    # "as a DAN" — Do Anything Now jailbreak pattern
    r"forget\s+everything",
    # "forget everything" — attempts to clear the system prompt
    r"you\s+are\s+now",
    # "you are now" — attempts to redefine the LLM's identity
    r"disregard\s+(all\s+)?previous",
    # "disregard previous" or "disregard all previous" instructions
]


# ── PII patterns ──────────────────────────────────────────────────────────────
# These patterns detect Personally Identifiable Information (PII).
# If a user accidentally pastes sensitive data into the chat it would flow
# to the OpenAI API (a third party), be stored in logs, and appear in
# LangSmith traces — all of which are compliance and privacy violations.
# We block the input before it reaches any external service.

PII_PATTERNS = [
    r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
    # credit card number — 16 digits optionally separated by spaces or dashes
    # matches: 4111 1111 1111 1111 or 4111-1111-1111-1111 or 4111111111111111

    r"\b\d{3}-\d{2}-\d{4}\b",
    # US Social Security Number — format: XXX-XX-XXXX
    # matches: 123-45-6789

    r"\b[A-Z]{1,2}\d{6,9}\b",
    # passport number — 1-2 letters followed by 6-9 digits
    # matches: A1234567 or AB123456789

    r"\b\d{3}[\s\.\-]?\d{3}[\s\.\-]?\d{4}\b",
    # US phone number — 10 digits optionally separated by spaces, dots, or dashes
    # matches: 555-867-5309 or 555.867.5309 or 5558675309
]


# ── Toxicity patterns ─────────────────────────────────────────────────────────
# These patterns detect abusive, threatening, or harmful language.
# An enterprise RAG system used by senior leadership must not allow
# toxic input to reach the LLM, appear in logs, or flow to LangSmith.
# These are basic patterns — a production system would use a dedicated
# toxicity classification model for more comprehensive coverage.

TOXIC_PATTERNS = [
    r"\b(murder|bomb|shoot|stab|threaten)\b",
    # violent language — threats or references to physical harm
    # NOTE: "kill" and "attack" are intentionally excluded because they are
    # common business terms — "kill the deal", "attack the market"
    # including them causes false positives on legitimate business questions

    r"\b(hate\s+speech|racial\s+slur)\b",
    # explicit hate speech references

    r"\b(harass|abuse|bully|intimidate)\b",
    # harassment and intimidation language
]


# ── GuardResult dataclass ─────────────────────────────────────────────────────

@dataclass
class GuardResult:
    is_safe: bool
    # True  → question passed all checks and can proceed to retrieval
    # False → question was blocked by one of the checks below

    reason: str
    # empty string ""                    when is_safe=True
    # "Input flagged for security review" when injection detected
    # "Input contains sensitive data"     when PII detected
    # "Input contains inappropriate content" when toxicity detected


# ── check() function ──────────────────────────────────────────────────────────

def check(question: str) -> GuardResult:
    # question: str → the raw question text submitted by the user
    # -> GuardResult → returns is_safe=True to proceed or is_safe=False to block

    q_lower = question.lower()
    # convert to lowercase once before all pattern checks
    # re.search() is case-sensitive by default
    # lowercasing ensures "Ignore Previous Instructions" is caught
    # just like "ignore previous instructions"

    # ── Check 1: Injection detection ─────────────────────────────────────────
    # Run before PII and toxicity — injection is the highest priority threat
    # A successful injection could compromise the entire pipeline
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, q_lower):
            # re.search() scans the entire string for the pattern
            # returns a match object (truthy) if found, None (falsy) if not
            log_event(log, "warning", "injection_detected",
                      pattern=pattern,
                      question=question[:50])
            # log at WARNING — injection attempt is a security event
            # question[:50] logs only the first 50 characters to avoid
            # storing the full malicious input in the log file
            return GuardResult(
                is_safe=False,
                reason="Input flagged for security review."
                # deliberately vague — do not tell the attacker which pattern triggered
            )

    # ── Check 2: PII detection ────────────────────────────────────────────────
    # Only reached if no injection pattern was found
    # PII detection uses the original question (not lowercased) because
    # passport numbers contain uppercase letters e.g. "A1234567"
    for pattern in PII_PATTERNS:
        if re.search(pattern, question):
            log_event(log, "warning", "pii_detected",
                      question=question[:50])
            # log at WARNING — PII detection is a compliance event
            # we do NOT log which pattern matched to avoid logging
            # a partial version of the sensitive data itself
            return GuardResult(
                is_safe=False,
                reason="Input contains sensitive data. Please do not share personal or financial information."
            )

    # ── Check 3: Toxicity detection ───────────────────────────────────────────
    # Only reached if no injection or PII pattern was found
    for pattern in TOXIC_PATTERNS:
        if re.search(pattern, q_lower):
            log_event(log, "warning", "toxicity_detected",
                      question=question[:50])
            # log at WARNING — toxic content is a policy violation
            return GuardResult(
                is_safe=False,
                reason="Input contains inappropriate content and cannot be processed."
            )

    # ── All checks passed ─────────────────────────────────────────────────────
    # If we reach here, the question passed all three checks
    # It is safe to proceed to retriever.search()
    return GuardResult(is_safe=True, reason="")