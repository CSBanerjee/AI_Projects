from app.config import settings
# settings.SIMILARITY_THRESHOLD → the minimum confidence score an answer must reach
#                                  to be returned directly to the user
#                                  default: 0.3 (set in .env)
#                                  if confidence is below this → escalate to Jira

from app.utils.logger import get_logger, log_event
# get_logger  → returns a named logger for this module (app.hitl.trigger)
# log_event   → writes a structured key=value log line

log = get_logger(__name__)
# __name__ is "app.hitl.trigger" inside this file


def should_escalate(confidence_score: float) -> bool:
    # confidence_score: float → the score returned by validator.validate()
    #                           a number between 0.0 and 1.0
    #                           produced by averaging 3 check scores:
    #                             Check 1: format (word count)
    #                             Check 2: relevance (cosine similarity)
    #                             Check 3: faithfulness (word overlap with chunks)
    #
    # -> bool → True  if confidence_score is BELOW threshold → escalate to Jira
    #           False if confidence_score is AT OR ABOVE threshold → return answer

    threshold = settings.SIMILARITY_THRESHOLD
    # read from settings every time — not cached at module level
    # this means changing SIMILARITY_THRESHOLD in .env takes effect immediately
    # without restarting the server (if hot reload is enabled)

    result = confidence_score < threshold
    # True  → score is strictly below threshold → escalate
    # False → score is at or above threshold   → do not escalate
    #
    # Note: "at threshold" does NOT escalate — only strictly below
    # e.g. confidence=0.3 and threshold=0.3 → 0.3 < 0.3 = False → no escalation
    # e.g. confidence=0.29 and threshold=0.3 → 0.29 < 0.3 = True → escalate

    log_event(log, "info", "escalation_check",
              confidence=round(confidence_score, 3),
              threshold=threshold,
              will_escalate=result)
    # log every escalation check so you can monitor the escalation rate
    # appears in logs as:
    #   event=escalation_check confidence=0.234 threshold=0.3 will_escalate=True
    # or:
    #   event=escalation_check confidence=0.847 threshold=0.3 will_escalate=False
    #
    # useful for tuning SIMILARITY_THRESHOLD in .env:
    # if too many questions escalate → lower threshold
    # if too many bad answers return → raise threshold

    return result
    # returned to main.py which decides what to do next:
    #   if trigger.should_escalate(validation.confidence_score):
    #       → store question in pending_escalations
    #       → ask user if they want a Jira story created
    #   else:
    #       → return the answer directly to the user