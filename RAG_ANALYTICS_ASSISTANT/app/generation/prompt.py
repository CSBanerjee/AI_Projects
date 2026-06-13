from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# ChatPromptTemplate — builds a structured prompt from a list of messages
#   each message has a role (system, human, assistant) and content
#   LangChain uses this to format the full conversation before sending to OpenAI
#
# MessagesPlaceholder — inserts a dynamic list of messages at a specific position
#   used here to inject conversation history between the system prompt and
#   the current user question — this is what enables multi-turn conversation

from app.utils.logger import get_logger
# get_logger → returns a named logger for this module (app.generation.prompt)

log = get_logger(__name__)
# __name__ is "app.generation.prompt" inside this file


# ── RAG_PROMPT ────────────────────────────────────────────────────────────────
# Used when the retriever found relevant chunks (the normal case)
# The system message contains three critical anti-hallucination instructions:
#   1. Answer using ONLY the context — no training data
#   2. If context does not contain the answer — say so explicitly
#   3. Do not use training data — only the context

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior commercial analytics advisor.
Answer the question using ONLY the context provided below.
If the context does not contain the answer, say: 
"I don't have reliable information on that in the current knowledge base."
Do not use your training data — only use the context.

Context:
{context}"""),
    # role="system" → sets the LLM's behaviour and constraints for this session
    # {context} is a placeholder — replaced by the actual retrieved chunks
    # in the build() function below

    MessagesPlaceholder(variable_name="history"),
    # inserts the conversation history here — between system and human messages
    # history is a list of previous {"role": "user"/"assistant", "content": "..."} dicts
    # this allows the LLM to reference earlier questions and answers
    # e.g. user asks "What is APAC discount?" then "Can you give more detail on that?"
    # the second question only makes sense if history is present

    ("human", "{question}"),
    # role="human" → the current question from the user
    # {question} is replaced by the actual question string in build()
])


# ── NO_CONTEXT_PROMPT ─────────────────────────────────────────────────────────
# Used when the retriever returned no chunks — either:
#   a) The question is completely unrelated to the knowledge base
#   b) All chunks scored below SIMILARITY_THRESHOLD
# The system message instructs the LLM to acknowledge it cannot answer
# rather than attempting to answer from its training data (hallucination)

NO_CONTEXT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior commercial analytics advisor.
The knowledge base does not contain relevant information for this question.
Respond with: "I was unable to find relevant information on that topic in 
the knowledge base." Do not attempt to answer from memory."""),
    # "Do not attempt to answer from memory" is the key instruction here
    # without this the LLM would use its training data and hallucinate

    MessagesPlaceholder(variable_name="history"),
    # history still included so the LLM has conversation context
    # even when it cannot answer the current question

    ("human", "{question}"),
    # the current question — shown to the LLM even though it cannot answer it
    # this helps the LLM frame its "I cannot answer" response correctly
])


# ── build() ───────────────────────────────────────────────────────────────────

def build(question: str, chunks: list, history: list) -> list:
    # question: str  → the user's question as a plain string
    # chunks: list   → list of Document objects returned by retriever.search()
    #                  each Document has .page_content (text) and .metadata (source etc.)
    #                  empty list [] if retriever found nothing
    # history: list  → list of previous conversation turns from session_store
    #                  format: [{"role": "user", "content": "..."}, {"role": "assistant", ...}]
    #                  empty list [] for the first question in a session
    # -> list        → returns a list of formatted LangChain message objects
    #                  ready to be sent to llm_client.ask()

    if not chunks:
        # no relevant chunks were retrieved — use the no-context prompt
        # this path is taken when:
        #   - the question is completely unrelated to the knowledge base
        #   - all chunks scored below SIMILARITY_THRESHOLD
        # the LLM will respond with a polite "I cannot find this information"
        log.debug("event=no_context_prompt_used")
        # log at DEBUG — not a warning, just informational
        # no_context is an expected outcome for out-of-scope questions

        return NO_CONTEXT_PROMPT.format_messages(
            question=question,
            # replaces {question} placeholder in the template
            history=history
            # replaces MessagesPlaceholder — inserts conversation history
        )

    # ── Build context string from chunks ──────────────────────────────────────
    # chunks were retrieved — format them into a numbered context block
    # each chunk is labelled with its source file so the LLM can attribute answers

    context_parts = []
    # starts empty — one string per chunk will be added

    for i, chunk in enumerate(chunks, 1):
        # enumerate(chunks, 1) gives:
        #   i=1 for the first chunk, i=2 for the second, i=3 for the third
        # starting at 1 not 0 because "[Source 1]" is more natural than "[Source 0]"

        source = chunk.metadata.get("source", "unknown")
        # chunk.metadata["source"] is the full file path e.g.
        #   /Users/.../docs/discount_policy.txt
        # .get("source", "unknown") returns "unknown" if the key is missing
        # the full path is shown — the frontend can truncate it for display

        context_parts.append(f"[Source {i}] (from: {source})\n{chunk.page_content}")
        # format each chunk as:
        #   [Source 1] (from: /path/to/discount_policy.txt)
        #   APAC enterprise accounts receive a 20% discount...
        #
        # the [Source N] label allows the LLM to cite sources in its answer
        # and allows the frontend to highlight which source was used

    context = "\n\n".join(context_parts)
    # join all chunk strings with a blank line between each one
    # "\n\n" creates visual separation making it easier for the LLM to
    # distinguish where one chunk ends and the next begins

    # ── Format and return the RAG prompt ─────────────────────────────────────
    return RAG_PROMPT.format_messages(
        question=question,
        # replaces {question} placeholder in the human message

        context=context,
        # replaces {context} placeholder in the system message
        # this is the numbered list of retrieved chunks built above

        history=history
        # replaces MessagesPlaceholder — inserts the full conversation history
        # between the system message and the current human question
    )
    # the returned list of message objects is passed directly to:
    #   llm_client.ask(messages)  →  ChatOpenAI.invoke(messages)  →  OpenAI API