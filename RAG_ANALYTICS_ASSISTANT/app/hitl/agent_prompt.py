# agent_prompt.py — Phase 4B Step 4B.2
#
# This file has one job: build the escalation message shown to the user
# when the pipeline cannot answer a question confidently.
#
# It is kept as a separate file rather than a string inside main.py because:
#   1. The message can be updated without touching pipeline logic
#   2. It can be tested independently
#   3. In a more advanced version, different message templates could be
#      selected based on the type of question or the confidence score


def build_escalation_message(question: str) -> str:
    # question: str → the original question the user asked
    #                 included in the message so the user knows exactly
    #                 which question is being escalated
    # -> str        → a formatted message string shown to the user in the chat
    #                 the frontend renders **Yes** and **No** as clickable buttons

    return (
        f'I was unable to find a reliable answer to your question:\n\n'
        # opening sentence — honest and direct
        # "I was unable to find" not "An error occurred" — human not technical

        f'"{question}"\n\n'
        # the original question in quotes — shows the user exactly what was asked
        # double newline after creates visual separation before the offer

        f'Would you like me to create a Jira story so the analytics team '
        f'can investigate and get back to you?\n\n'
        # the offer — explains what will happen if the user says Yes
        # "analytics team" — specific, not generic "our team" or "support"
        # "investigate and get back to you" — sets expectation of what happens next

        f'Reply **Yes** to create a story or **No** to skip.'
        # clear call to action — two explicit options
        # **Yes** and **No** are rendered as bold by the frontend
        # the frontend in Phase 6 renders these as clickable buttons
        # so the user does not have to type — they just click
    )
    # the full message reads:
    #
    # I was unable to find a reliable answer to your question:
    #
    # "What is the CFO bonus structure?"
    #
    # Would you like me to create a Jira story so the analytics team
    # can investigate and get back to you?
    #
    # Reply **Yes** to create a story or **No** to skip.
    #
    # this must sound like a helpful colleague — not a technical error message
    # no stack traces, no error codes, no technical jargon