# LEARNING.md
## What this project teaches you — and how to make it yours

This file is not a tutorial summary. It is a guide to ensure you understand every
decision made in this project rather than copying code and moving on. Read it before
you start each phase and again after you finish it.

---

## How to use this file

After you finish each file in the project, write three sentences at the top of that
file answering these three questions:

- What does this file do in plain English?
- What was the hardest part to understand?
- What would break if you removed this file?

Nobody else will have those comments. They are the proof that you understood the code,
not just ran it.

---

## 1. Reading and modifying framework code

Most developers use LangChain by copying examples from the documentation. This project
teaches you to read what LangChain generates, understand what every parameter controls,
and change it deliberately for your specific use case.

When `RecursiveCharacterTextSplitter` returns chunks that are too large or too small,
you will not search Stack Overflow for a fix — you will read the parameter names,
understand what `chunk_size` and `chunk_overlap` do, and adjust them based on your
eval scores. That is the difference between using a tool and understanding one.

Before you write any LangChain code, read the relevant section of the LangChain
documentation and write a one-paragraph explanation of what that class does in your
own words. If you cannot explain it without the documentation, you are not ready to
use it yet.

---

## 2. Chunking strategy — learning from your own data

Every tutorial uses the same default chunk size of 1000 characters. Nobody explains
why, and nobody tells you what happens when it is wrong.

In this project you will run your eval dataset three times with chunk sizes 200, 500,
and 800 tokens. You will see different RAGAS scores for each run. You will notice that
smaller chunks give more precise retrieval but sometimes miss the full context of an
answer. Larger chunks give more context but sometimes retrieve irrelevant content
alongside the relevant part.

The learning is not the number you end up with. The learning is the ability to look at
a retrieval failure, identify whether it is a chunk size problem or a missing document
problem, and make a deliberate change to fix it. Write your findings in FINDINGS.md
before you move to the next phase.

---

## 3. How embeddings work — from a number to an understanding

An embedding is a list of numbers that represents the meaning of a piece of text. Two
pieces of text with similar meaning produce similar lists of numbers, even if they use
completely different words.

You will experience this directly when you search for "APAC discount policy" and
retrieve a chunk that talks about "Asia Pacific pricing guidelines". The words do not
match but the meanings are close — and that is why the retrieval works. That moment
of seeing semantic similarity in action, on your own documents, with your own
questions, is something no definition can give you.

After you build the embedder, take ten minutes to embed five different questions and
five document chunks manually. Print the similarity scores. Find a pair that surprises
you — either a match you did not expect or a miss you did not expect. Write down why
you think it happened.

---

## 4. Debugging across multiple modules

When something goes wrong in a single-file script, the error is usually obvious. When
something goes wrong in a seven-module pipeline, the error message tells you what
broke but not why — because the failure in one module was caused by a bad output from
a different module three steps earlier.

This project teaches you to debug a distributed system. You will read structured log
lines and find the stage where the pipeline deviated from expected behaviour. You will
use LangSmith traces to see the exact prompt that was sent and the exact response that
came back. You will learn to work backwards from the symptom to the cause.

Every time you fix a bug in this project, write one sentence in FINDINGS.md describing
what broke, what caused it, and how you found the root cause. After ten bugs you will
have a personal debugging methodology that no interview question can surprise.

---

## 5. Measuring quality with numbers

The most common mistake in AI projects is evaluating quality with feelings. "It seems
to work well" is not a measurement. "Faithfulness score 0.81, answer relevancy 0.74,
context precision 0.79" is a measurement.

This project teaches you to build a ground truth dataset before you build the system,
run that dataset against every version of the system, and track how each change moves
the scores. When you add a guardrail and faithfulness goes from 0.62 to 0.78, you
know the guardrail is working. When you change the prompt and answer relevancy drops,
you know the change was wrong.

The habit to build here is: never change two things at the same time. Change one thing,
run the eval, record the score, then change the next thing. This is how you build
evidence for your decisions rather than guesses.

---

## 6. The difference between a script and a service

In Project 1 you ran `python main.py` and the program finished. In this project you
run `uvicorn api_server:app` and the program stays alive waiting for requests. This
is a fundamental shift in how you think about software.

A script runs once and exits. A service runs continuously, handles multiple requests
at the same time, recovers from errors without crashing, and needs to be monitored
over time. Building `api_server.py` with startup events, shutdown handlers, and
middleware teaches you how production software actually behaves — not as a sequence
of steps but as a living system that responds to the outside world.

Pay attention to what happens in `api_server.py` at startup. Notice that ChromaDB is
initialised once and reused across all requests, not initialised fresh for every
question. Understand why that matters for performance and then explain it out loud
without looking at the code.

---

## 7. Integrating external systems via API

ChromaDB and Jira are both external systems with their own APIs. The pattern for
calling them is identical even though they do completely different things: authenticate
using a key, send a structured request, validate the response, handle errors with
specific messages, retry on failure.

Once you understand this pattern from `jira_client.py`, you can apply it to any
enterprise system — Salesforce, ServiceNow, Databricks, SAP. The pattern does not
change. Only the base URL and the request structure change.

Before you write `jira_client.py`, read the Jira REST API documentation for creating
an issue. Find the endpoint, the required fields, the authentication method, and one
example error response. Understanding the API before writing the code means you will
write it correctly the first time rather than debugging by trial and error.

---

## 8. Writing tests that protect you

Unit tests in tutorials check whether a function returns the right value on a
happy-path input. That is the minimum. The tests in this project go further — they
check whether your code handles failures from external services correctly.

When the Jira API returns a 401 authentication error, does your code give a clear
message explaining what is wrong and how to fix it? When ChromaDB returns no results
above the similarity threshold, does your pipeline route to the escalation flow rather
than returning a blank answer? These are the tests that actually protect you in
production.

The habit to build is writing the failure test before the happy-path test. Ask
yourself: what is the worst thing that could happen to this function? Write a test for
that first. Then write the test for the normal case. This order forces you to think
about failure modes before you write the implementation.

---

## 9. Documenting decisions in FINDINGS.md

FINDINGS.md is not a report about what the project does. It is a record of decisions
you made, why you made them, and what you observed as a result.

A good entry looks like this:

```
Chunk size experiment — 2024-01-20
Ran eval dataset with chunk_size=200, 500, 800.
Results: faithfulness 0.61 / 0.78 / 0.72
Decision: chose 500 because faithfulness peaked and context_recall
stayed above 0.70. At 800 the chunks were too broad and retrieved
irrelevant context alongside the target passage.
What I would try next: chunk_size=600 with overlap=80.
```

A bad entry looks like this: "Chunk size 500 worked best."

The difference is specificity. The good entry shows that you made an observation,
formed a hypothesis, ran an experiment, and drew a conclusion. That is the reasoning
an interviewer at a Fortune 500 company is looking for when they ask you to walk
through a project.

---

## 10. How the full AI engineering stack connects

Before this project, you knew about embeddings, vector databases, LLMs, APIs, and
Docker as separate concepts from separate tutorials. After this project, you will have
personally connected all of them in one working system.

You will know that a question enters as text, becomes a vector, is compared to stored
vectors, retrieves matching document chunks, is combined with those chunks into a
prompt, is sent to an LLM, comes back as text, is validated by guardrails, and either
reaches the user or creates a Jira story. You will know this not because you read it
but because you built every link in that chain yourself.

When an interviewer asks you to design an AI system for a commercial analytics team,
you will not describe a concept. You will describe a system you built, the decisions
you made, the failures you encountered, and the metrics you used to measure success.
That is the answer that gets you the job.

---

## Questions to ask yourself after each phase

After Phase 2 — ingestion:
- If I added a new document to docs/ right now, what exact commands would I run to
  make it searchable?
- What happens if the document has no text — does my pipeline fail gracefully?

After Phase 3 — retrieval:
- Why did I choose a similarity threshold of 0.7 and not 0.5 or 0.9?
- Can I explain the difference between semantic search and keyword search to someone
  who has never heard of embeddings?

After Phase 4 — generation and guardrails:
- What specific words in my prompt make the LLM cite sources rather than answering
  from memory?
- If the faithfulness guardrail is failing on 30% of answers, what would I change
  first — the prompt, the chunk size, or the threshold?

After Phase 5 — FastAPI:
- What is the difference between a 422 error and a 500 error and when would each
  occur in my API?
- If two users ask different questions at exactly the same time, does my API handle
  both correctly?

After Phase 7 — evaluation:
- Which of my 20 eval questions produced the lowest faithfulness score and why?
- If I had to remove 5 questions from my eval set to make it more representative,
  which 5 would I remove and why?

---

## The one thing that makes all of this real

The difference between a developer who copies code and a developer who understands
it is the ability to explain it out loud without looking at the screen.

After you finish each module, close your laptop and explain what that module does,
why it exists, and what would break without it — out loud, to yourself or to someone
else. If you cannot do it, open the file again, read it more carefully, and try again.

This is the habit that turns a portfolio project into genuine expertise.
