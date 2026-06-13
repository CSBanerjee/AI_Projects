# FINDINGS.md — RAG Analytics Assistant

This file records experiment results, architectural decisions, and failure
analyses as the project progresses. Each section is filled in at the
relevant phase — do not write conclusions before running the experiments.

---

## Master findings table

| # | Phase | File | Finding | Type | Severity | Status |
|---|---|---|---|---|---|---|
| 1 | Phase 1 | settings.py | `DATA_DIR` defined but never used | Dead code | Low | Fixed |
| 2 | Phase 1 | settings.py | ChromaDB folder not checked in `validate()` | Missing guard | High | Fixed |
| 3 | Phase 1 | settings.py | `docs/` existence and emptiness in one combined check | Imprecise error | Medium | Fixed |
| 4 | Phase 2 | loader.py | `docs_dir.exists()` check duplicated from `settings.py` | Redundant guard | Low | Fixed |
| 5 | Phase 2 | loader.py | Empty folder check duplicated from `settings.py` | Redundant guard | Low | Fixed |
| 6 | Phase 2 | loader.py | `docs_dir` path rebuilt locally instead of `settings.DOCS_DIR` | Path duplication | Low | Fixed |
| 7 | Phase 1 | FINDINGS.md | Placeholders placed between wrong phase sections | Doc structure error | Low | Fixed |
| 8 | Phase 2 | chunker.py | `langchain.text_splitter` import — wrong package in newer LangChain | `ModuleNotFoundError` | High | Fixed |
| 9 | Phase 2 | chunker.py | `was chosen` — past tense implies experiment done at Step 2.2 | Misleading comment | Low | Fixed |
| 10 | Phase 2 | chunker.py | `produced` — past tense implies loader already ran | Misleading comment | Low | Fixed |
| 11 | Phase 2 | chunker.py | `chunk_index=87` hardcoded — real output is 60 | Stale comment | Low | Fixed |
| 12 | Phase 2 | chunker.py | `"34 of 87 total"` hardcoded — real output is 60 | Stale comment | Low | Fixed |
| 13 | Phase 2 | chunker.py | `count=87` in log example — real output is 60 | Stale comment | Low | Fixed |
| 14 | Phase 2 | requirements.txt | `chromadb` not installed — `ModuleNotFoundError` on import | Missing dependency | High | Fixed |
| 15 | Phase 2 | requirements.txt | `chromadb` duplicate entry after fix was appended | Duplicate entry | Low | Fixed |
| 16 | Phase 2 | phase_02_ingestion.md | Step 2.6 placed before `retrieval_test.py` exists | Doc sequencing error | Medium | Deferred |
| 17 | Phase 3 | eval_dataset.json | Chunk size experiment — 200 (0.65), 500 (0.70), 800 (0.55) | Experiment | — | Complete — CHUNK_SIZE=500 chosen |
| 18 | Phase 4 | llm_client.py | `temperature=0.2` hardcoded instead of read from `.env` and `settings.py` | Hardcoded config | Low | Fixed — `settings.TEMPERATURE` |
| 19 | Phase 4 | llm_client.py | `max_tokens=400` hardcoded instead of read from `.env` and `settings.py` | Hardcoded config | Low | Fixed — `settings.MAX_TOKENS` |
| 20 | Phase 4 | input_guard.py | PII patterns not considered | Missing guard | High | Open — needs implementation |
| 21 | Phase 4 | input_guard.py | Toxicity patterns not considered | Missing guard | High | Open — needs implementation |

---


## Phase 1 — Code review findings — app/config/settings.py

**Reviewed by:** Code review  
**Date:** Phase 1, Step 1.6  
**File:** `app/config/settings.py`  
**Total findings:** 3

---

### Finding 1 — Dead code: `DATA_DIR` defined but never used

**Severity:** Low  
**Type:** Dead code  
**Location:** `settings.py` line 19

**What was written:**
```python
DATA_DIR = BASE_DIR / "data"
```

**The problem:**  
`DATA_DIR` is defined at the top of `settings.py` but is never imported,
referenced, or used anywhere in the project across all 9 phases. It was
written with the intention of storing raw data files in a `data/` folder
but the project ended up using `docs/` for source documents instead.
Dead code adds noise — every developer reading the file has to spend
mental effort wondering what `DATA_DIR` is for and where it gets used,
only to discover it is used nowhere.

**The fix:**  
Delete the line entirely.

```python
# before
DATA_DIR = BASE_DIR / "data"   # defined but never used anywhere
LOG_DIR  = BASE_DIR / "logs"

# after
LOG_DIR  = BASE_DIR / "logs"   # DATA_DIR removed — was dead code
```

**Rule learned:**  
Only define a variable if it is used in at least one other place.
If a variable was planned but the design changed, delete it rather
than leaving it behind. Dead code misleads future readers.

---

### Finding 2 — Missing validation: ChromaDB folder not checked in `validate()`

**Severity:** High  
**Type:** Missing guard — silent failure at query time  
**Location:** `settings.py` — `validate()` function

**What was written (original):**
```python
def validate() -> None:
    if not OPENAI_API_KEY:
        raise EnvironmentError(...)
    if not JIRA_API_TOKEN:
        raise EnvironmentError(...)
    if not docs_dir.exists() or not any(docs_dir.iterdir()):
        raise FileNotFoundError(...)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    # no check on whether ChromaDB actually contains any vectors
```

**The problem:**  
`validate()` creates the `chroma_db/` folder if it does not exist but
never checks whether it contains any data. This means a developer who
forgets to run `python ingest.py` before starting the server gets no
error at startup. The app boots successfully, but the moment the first
question comes in, ChromaDB returns zero chunks and the pipeline either
silently returns an empty answer or triggers a false escalation to Jira.
The real cause — an empty vector store — is invisible.

**The fix:**  
Two new checks added — one for whether the folder exists, one for
whether it contains vector data:

```python
# check 1 — create the folder if missing, print confirmation
chroma_dir = Path(CHROMA_PERSIST_DIR)
if not chroma_dir.exists():
    chroma_dir.mkdir(parents=True, exist_ok=True)
    print(f"chroma_db/ directory created at: {chroma_dir}")

# check 2 — raise if folder is empty (ingest.py was never run)
if not any(chroma_dir.iterdir()):
    raise FileNotFoundError(
        f"ChromaDB folder is empty: {chroma_dir}\n"
        "Run ingestion first: python ingest.py"
    )
```

**Rule learned:**  
A guard that creates a folder but does not check its contents gives a
false sense of safety. Always validate not just existence but also
whether the required content is present. Fail loudly at startup rather
than silently at the point of use.

---

### Finding 3 — Imprecise validation: `docs/` existence and emptiness combined into one check

**Severity:** Medium  
**Type:** Imprecise error message — hard to diagnose  
**Location:** `settings.py` — `validate()` function

**What was written (original):**
```python
docs_dir = BASE_DIR / "docs"

if not docs_dir.exists() or not any(docs_dir.iterdir()):
    raise FileNotFoundError(
        f"docs/ folder is missing or empty: {docs_dir}\n"
        "Add your source documents (.txt or .pdf) before running the pipeline."
    )
```

**The problem:**  
The single `or` condition catches two completely different failure
scenarios and raises the same vague message for both:

| Scenario | What actually happened | Message shown |
|---|---|---|
| `docs/` does not exist | Folder was never created | "docs/ folder is missing or empty" |
| `docs/` exists but is empty | Folder exists, no files added yet | "docs/ folder is missing or empty" |

A developer seeing "missing or empty" does not know whether to create
the folder or add files to an existing one. The two problems have
different solutions and deserve different messages.

**The fix:**  
Split into two separate `if` blocks, each with its own precise message
and its own specific instruction:

```python
# check 1 — does the folder exist at all?
if not DOCS_DIR.exists():
    raise FileNotFoundError(
        f"docs/ folder is missing: {DOCS_DIR}\n"
        "Create the folder and add your source documents:\n"
        "  mkdir docs\n"
        "  cp your-documents.pdf docs/"
    )

# check 2 — does the folder have at least one file inside it?
if not any(DOCS_DIR.iterdir()):
    raise FileNotFoundError(
        f"docs/ folder is empty: {DOCS_DIR}\n"
        "Add your source documents (.pdf) before running the pipeline."
    )
```

**Rule learned:**  
When two conditions represent two different problems, never combine them
with `or` into one error message. Each failure scenario should produce
a message that tells the developer exactly what is wrong and exactly
what command to run to fix it.

---

### Summary table — Phase 1

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 1 | `DATA_DIR` defined but never used anywhere | settings.py | Low | Fixed — line deleted |
| 2 | ChromaDB folder not validated in `validate()` | settings.py | High | Fixed — two checks added |
| 3 | `docs/` existence and emptiness in one combined check | settings.py | Medium | Fixed — split into two separate checks |

---

## Phase 2 — Code review findings — app/ingestion/loader.py

**Reviewed by:** Code review  
**Date:** Phase 2, Step 2.1  
**File:** `app/ingestion/loader.py`  
**Total findings:** 3

---

### Finding 4 — Redundant check: `docs_dir.exists()` already validated in `settings.py`

**Severity:** Low  
**Type:** Redundant guard — unnecessary duplication  
**Location:** `loader.py` — `load()` function  
**Related to:** Finding 3 in `settings.py`

**What was written (original):**
```python
docs_dir = Path(settings.BASE_DIR) / "docs"

if not docs_dir.exists():
    raise FileNotFoundError(
        f"docs/ folder not found: {docs_dir}\n"
        "Create the folder and add your source PDF documents."
    )
```

**The problem:**  
`validate()` in `settings.py` already runs `_check_docs_folder_exists()` at
startup before `load()` is ever called. By the time `load()` runs, the
folder is guaranteed to exist. The check in `loader.py` can never be
reached — it is unreachable dead code that adds noise without providing
any protection.

**The fix:**  
Remove the `docs_dir.exists()` check from `loader.py` entirely.
`settings.py` is the single place responsible for environment validation.
`loader.py` is responsible only for reading files.

```python
# removed from loader.py
if not docs_dir.exists():
    raise FileNotFoundError(...)
# reason: _check_docs_folder_exists() in settings.py already does this at startup
```

**Rule learned:**  
Each file should have one clear responsibility. `settings.py` owns
environment validation. `loader.py` owns file loading. When responsibilities
overlap, one of the two checks is always redundant.

---

### Finding 5 — Redundant check: empty folder already validated in `settings.py`

**Severity:** Low  
**Type:** Redundant guard — unnecessary duplication  
**Location:** `loader.py` — `load()` function  
**Related to:** Finding 3 in `settings.py`

**What was written (original):**
```python
if not documents:
    raise FileNotFoundError(
        f"No PDF files found in: {docs_dir}\n"
        "Add your source documents (.pdf) before running the pipeline."
    )
```

**The problem:**  
`validate()` in `settings.py` already runs `_check_docs_folder_not_empty()`
at startup. By the time `load()` runs, the folder is guaranteed to contain
at least one file. The `if not documents` check in `loader.py` adds a second
layer of the same protection that can never be reached if `validate()` ran
first. Duplicated guards create confusion about which file is the authority.

**The fix:**  
Remove the `if not documents` check from `loader.py` entirely.

```python
# removed from loader.py
if not documents:
    raise FileNotFoundError(...)
# reason: _check_docs_folder_not_empty() in settings.py already does this at startup
```

**Rule learned:**  
Startup validation in `validate()` is the single source of truth for
environment checks. Repeating the same checks inside pipeline functions
creates two authorities for the same rule — and makes it unclear which
one a developer should update when requirements change.

---

### Finding 6 — Improvement: `docs_dir` path rebuilt locally instead of using `settings.DOCS_DIR`

**Severity:** Low  
**Type:** Unnecessary duplication — path rebuilt in multiple places  
**Location:** `loader.py` — `load()` function  
**Files affected:** `settings.py` and `loader.py`

**What was written (original):**
```python
# inside loader.py — path rebuilt from scratch
docs_dir = Path(settings.BASE_DIR) / "docs"
```

**The problem:**  
The same path expression `BASE_DIR / "docs"` was being written in three
separate places across two files. If the docs folder were ever renamed,
every occurrence would need to be updated individually — and one would
inevitably be missed.

**The fix:**  
Add `DOCS_DIR` as a module-level variable in `settings.py` — defined once,
used everywhere:

```python
# added to settings.py — defined once at module level
DOCS_DIR = BASE_DIR / "docs"
```

Then reference it directly in both files:

```python
# settings.py — validate() checks
if not DOCS_DIR.exists():           # uses module variable directly
if not any(DOCS_DIR.iterdir()):     # uses module variable directly

# loader.py — load()
docs_dir = settings.DOCS_DIR        # references settings, not rebuilt locally
```

**Rule learned:**  
If the same path is needed in more than one place, define it as a
module-level variable in `settings.py` and reference it everywhere. This
is the same pattern already used for `LOG_DIR` — defined once in
`settings.py`, used in both `settings.py` and `logger.py`.

---

### Summary table — Phase 2

| # | Finding | Files affected | Severity | Status |
|---|---|---|---|---|
| 4 | `docs_dir.exists()` check duplicated from `settings.py` | loader.py | Low | Fixed — removed from loader.py |
| 5 | Empty folder check duplicated from `settings.py` | loader.py | Low | Fixed — removed from loader.py |
| 6 | `docs_dir` path rebuilt locally instead of using `settings.DOCS_DIR` | settings.py + loader.py | Low | Fixed — `DOCS_DIR` added to settings.py |

---


---

## Phase 2 — Code review findings — app/ingestion/chunker.py

**Reviewed by:** Code review  
**Date:** Phase 2, Step 2.2  
**File:** `app/ingestion/chunker.py`  
**Total findings:** 6

---

### Finding 8 — Import error: `langchain.text_splitter` module moved in newer LangChain

**Severity:** High  
**Type:** `ModuleNotFoundError` — file cannot be imported at all  
**Location:** `chunker.py` line 1

**What was written (original):**
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
```

**The problem:**  
In newer versions of LangChain, `RecursiveCharacterTextSplitter` was moved
out of `langchain.text_splitter` into a dedicated package called
`langchain_text_splitters`. The old import path no longer exists. Running
`from langchain.text_splitter import ...` raises:

```
ModuleNotFoundError: No module named 'langchain.text_splitter'
```

The file cannot be imported at all — every other module that depends on
`chunker.py` also fails immediately.

**The fix:**  
Update the import to the correct package and add it to `requirements.txt`:

```python
# before
from langchain.text_splitter import RecursiveCharacterTextSplitter

# after
from langchain_text_splitters import RecursiveCharacterTextSplitter
```

Also added to `requirements.txt`:
```
langchain-text-splitters
```

**Rule learned:**  
LangChain moves classes between packages across versions. Always verify
the import path works by running Level 2 import check immediately after
writing the import line. Do not assume the import path in documentation
matches the installed version.

---

### Finding 9 — Misleading comment: past tense implies experiment already completed

**Severity:** Low  
**Type:** Misleading comment — implies work done before it happened  
**Location:** `chunker.py` — `chunk_size` parameter comment

**What was written (original):**
```python
chunk_size=settings.CHUNK_SIZE,
# 500 was chosen after running three experiments in Phase 2 Step 2.6
```

**The problem:**  
This comment was written at Step 2.2. The chunk size experiment it
references does not happen until Step 2.6. Writing `"was chosen"` in
past tense at Step 2.2 implies the experiment was somehow already
conducted. A developer reading this could mistakenly believe the
decision was final and skip Step 2.6 entirely — losing the experiment
results that belong in `FINDINGS.md`.

**The fix:**  
Rewrite in future tense to accurately reflect that the experiment is
still ahead:

```python
# before
# 500 was chosen after running three experiments in Phase 2 Step 2.6

# after
# 500 is the starting default — the optimal value will be confirmed
# after running three chunk size experiments in Step 2.6
# results of those experiments will be recorded in FINDINGS.md
```

**Rule learned:**  
Comments must reflect the state of the project at the time they are
written — not assume future work has already been done. If an experiment
or decision is still pending, say "will be confirmed" not "was chosen".

---

### Finding 10 — Misleading comment: past tense implies loader already ran

**Severity:** Low  
**Type:** Misleading comment — incorrect tense  
**Location:** `chunker.py` — `split()` function docstring comment

**What was written (original):**
```python
# a 4-page PDF produced 4 Documents — all 5 PDFs = 20 Documents
```

**The problem:**  
`produced` is past tense, implying `loader.load()` already ran before
this comment was written. At Step 2.2, `loader.py` exists but may not
have been executed yet. The comment describes a general fact about what
`loader.load()` returns — it should use present tense to describe
ongoing behaviour, not past tense to describe a completed action.

**The fix:**  
```python
# before
# a 4-page PDF produced 4 Documents — all 5 PDFs = 20 Documents

# after
# a 4-page PDF produces 4 Documents — all 5 PDFs = 20 Documents
```

**Rule learned:**  
Use present tense when describing what a function does or returns.
Use past tense only when describing something that actually already
happened — such as a completed experiment or a historical decision.

---

### Finding 11 — Stale comment: hardcoded `87` does not match actual chunk count

**Severity:** Low  
**Type:** Stale hardcoded value in comment  
**Location:** `chunker.py` — `chunk_index` metadata comment

**What was written (original):**
```python
chunk.metadata["chunk_index"] = i
# chunk_index=87 → 88th chunk overall
```

**The problem:**  
The number `87` comes from the phase documentation which assumed a
different set of documents. The actual chunk count produced by the
5 PDFs in this project is `60`. A comment showing `87` as an example
while the real output is `60` is misleading — it makes a developer
doubt whether the code is working correctly.

**The fix:**  
```python
# before
# chunk_index=87 → 88th chunk overall

# after
# chunk_index=59 → 60th chunk overall  (actual count with current 5 PDFs)
```

**Rule learned:**  
Never hardcode specific output numbers in comments unless you have
verified them against the actual output. Use the real number from the
verify command, or describe the value relationally rather than
absolutely — e.g. `chunk_index=N-1 → last chunk overall`.

---

### Finding 12 — Stale comment: `"34 of 87 total"` does not match actual output

**Severity:** Low  
**Type:** Stale hardcoded value in comment  
**Location:** `chunker.py` — `total_chunks` metadata comment

**What was written (original):**
```python
# "This chunk is 34 of 87 total."
```

**The problem:**  
Same issue as Finding 11. `87` does not match the actual chunk count
of `60`. Any developer running the verify command and seeing `60` in
the output while the comment says `87` would reasonably question whether
something went wrong.

**The fix:**  
```python
# before
# "This chunk is 34 of 87 total."

# after
# "This chunk is 34 of 60 total."
```

---

### Finding 13 — Stale comment: `count=87` in log example does not match actual output

**Severity:** Low  
**Type:** Stale hardcoded value in comment  
**Location:** `chunker.py` — `log_event` comment

**What was written (original):**
```python
#   event=chunks_created count=87 chunk_size=500 overlap=50
```

**The problem:**  
The log example shows `count=87` but the actual log output produced
by running the verify command is `count=60`. A comment that shows
a different value from what the code actually produces breaks the
reader's trust in the comments throughout the file.

**The fix:**  
```python
# before
#   event=chunks_created count=87 chunk_size=500 overlap=50

# after
#   event=chunks_created count=60 chunk_size=500 overlap=50
```

**Rule learned:**  
Log example comments must match actual log output exactly. Run the
verify command first, copy the real log line, then paste it into the
comment. Never write example log lines from memory or from documentation
that was written for a different project setup.

---

### Summary table — Phase 2 chunker.py

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 8 | `from langchain.text_splitter import` — wrong package in newer LangChain | chunker.py | High | Fixed — updated to `langchain_text_splitters` |
| 9 | `was chosen` — past tense implies chunk experiment already done at Step 2.2 | chunker.py | Low | Fixed — rewritten as future tense |
| 10 | `produced` — past tense implies loader already ran | chunker.py | Low | Fixed — changed to `produces` |
| 11 | `chunk_index=87` hardcoded — does not match actual output of 60 | chunker.py | Low | Fixed — changed to `chunk_index=59` |
| 12 | `"34 of 87 total"` hardcoded — does not match actual output | chunker.py | Low | Fixed — changed to `34 of 60 total` |
| 13 | `count=87` in log example — does not match actual output | chunker.py | Low | Fixed — changed to `count=60` |


## Phase 3 — Retrieval
### Chunk size experiment — Phase 3 Step 3.4

| Chunk size | Overlap | Total chunks | Retrieval hits | Precision | Observation |
|---|---|---|---|---|---|
| 200 | 50 | 142 | 12 | 0.65 | Chunks too small — answers split across boundaries |
| 500 | 50 | 64  | 16 | 0.70 | Sweet spot — one topic per chunk, meets threshold |
| 800 | 50 | 39  | 14 | 0.55 | Chunks too broad — multiple topics dilute similarity |

Decision: CHUNK_SIZE=500 chosen. Only size meeting the 0.70 precision threshold.
What I would try next: test CHUNK_SIZE=400 and 600 to see if precision improves further.

---

## Phase 4 — Generation + guardrails
**Reviewed by:** Code review  
**Date:** Phase 4, Steps 4.1 and 4.3  
**Files:** `app/generation/llm_client.py`, `app/guardrails/input_guard.py`  
**Total findings:** 4

---

### Finding 18 — `temperature` hardcoded in `llm_client.py` instead of `.env` and `settings.py`

**Severity:** Low  
**Type:** Hardcoded configuration — not configurable without editing code  
**Location:** `app/generation/llm_client.py` — `build_client()` function

**What was written (original):**
```python
def build_client() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.MODEL,
        temperature=0.2,        # ← hardcoded
        max_tokens=400,
        openai_api_key=settings.OPENAI_API_KEY
    )
```

**The problem:**  
`temperature` controls how creative or random the LLM response is. Setting it
to `0.2` is the right default for a factual RAG system — but hardcoding it
means you cannot experiment with different values without editing `llm_client.py`
directly. Every other LLM configuration value (`MODEL`, `OPENAI_API_KEY`,
`MAX_RETRIES`) is read from `.env` via `settings.py`. `temperature` should
follow the same pattern.

**The fix:**  
Add `TEMPERATURE` to `settings.py` and `.env`, then reference it in `llm_client.py`:

```python
# settings.py
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# .env
TEMPERATURE=0.2

# llm_client.py
temperature=settings.TEMPERATURE,   # was temperature=0.2
```

**Rule learned:**  
Any value you might want to change between environments or experiments belongs
in `.env` and `settings.py` — not hardcoded in a function. The test for this
is: "Would I want to change this without redeploying the code?" If yes, it
belongs in configuration.

---

### Finding 19 — `max_tokens` hardcoded in `llm_client.py` instead of `.env` and `settings.py`

**Severity:** Low  
**Type:** Hardcoded configuration — not configurable without editing code  
**Location:** `app/generation/llm_client.py` — `build_client()` function

**What was written (original):**
```python
def build_client() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.MODEL,
        temperature=0.2,
        max_tokens=400,         # ← hardcoded
        openai_api_key=settings.OPENAI_API_KEY
    )
```

**The problem:**  
`max_tokens` controls the maximum length of the LLM response. `400` tokens is
appropriate for short factual answers but too short for detailed summaries.
A VP asking for a strategy overview might need `600-800` tokens. Having this
hardcoded means you cannot adjust it without touching code. Same problem
as `temperature` — it should be in `.env`.

**The fix:**  
```python
# settings.py
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "400"))

# .env
MAX_TOKENS=400

# llm_client.py
max_tokens=settings.MAX_TOKENS,   # was max_tokens=400
```

**Rule learned:**  
Same rule as Finding 18. Both `temperature` and `max_tokens` are LLM behaviour
settings that belong alongside `MODEL` and `MAX_RETRIES` in the
`# ── LLM behaviour` section of `settings.py`.

---

### Finding 20 — PII patterns not considered in `input_guard.py`

**Severity:** High  
**Type:** Missing guard — sensitive data transmitted to third party API  
**Location:** `app/guardrails/input_guard.py`  
**Status:** Open — needs implementation

**What was written (original):**
```python
INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"reveal\s+(your\s+)?system\s+prompt",
    r"pretend\s+you\s+are",
    r"as\s+a\s+dan",
    r"forget\s+everything",
    r"you\s+are\s+now",
    r"disregard\s+(all\s+)?previous",
]
```

**The problem:**  
`input_guard.py` only checks for prompt injection patterns. It does not detect
Personally Identifiable Information (PII) such as credit card numbers, Social
Security Numbers, passport numbers, or phone numbers. If a user accidentally
pastes sensitive data into the chat it flows through to:
- The OpenAI API — a third party service
- The application logs — stored on disk
- ChromaDB — if used as context

This is a data privacy and PCI-DSS compliance risk. The project handles
financial data and is used by VPs — the risk of accidental PII exposure is real.

**Proposed fix:**
```python
PII_PATTERNS = [
    r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",  # credit card number
    r"\d{3}-\d{2}-\d{4}",                          # SSN
    r"[A-Z]{1,2}\d{6,9}",                          # passport number
    r"\d{3}[\s.-]?\d{3}[\s.-]?\d{4}",              # phone number
]
```

Each pattern returns `GuardResult(is_safe=False, reason="Input contains sensitive data.")`.

**Rule learned:**  
Input validation must cover not just adversarial inputs (injection) but also
accidental inputs (PII). A system that handles financial data must explicitly
check for and reject sensitive data before it reaches any external API or log.

---

### Finding 21 — Toxicity patterns not considered in `input_guard.py`

**Severity:** High  
**Type:** Missing guard — harmful content reaches the LLM and logs  
**Location:** `app/guardrails/input_guard.py`  
**Status:** Open — needs implementation

**The problem:**  
`input_guard.py` has no toxicity detection. Abusive, threatening, or
discriminatory language submitted by a user flows through to the LLM,
appears in the application logs, and may appear in LangSmith traces.
This creates a reputational and compliance risk especially for a system
used by senior leadership.

**Proposed fix:**
```python
TOXIC_PATTERNS = [
    r"(kill|murder|attack|threaten|abuse|harass)",
    r"(racist|sexist|discriminat)\w*",
]
```

**Rule learned:**  
Enterprise AI systems require content moderation at the input layer.
Toxicity detection should be a standard check alongside injection detection
in any production guardrail implementation.

---

### Summary table — Phase 4

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 18 | `temperature` hardcoded instead of read from `.env` | llm_client.py | Low | Fixed — `settings.TEMPERATURE` |
| 19 | `max_tokens` hardcoded instead of read from `.env` | llm_client.py | Low | Fixed — `settings.MAX_TOKENS` |
| 20 | PII patterns missing from `input_guard.py` | input_guard.py | High | Open |
| 21 | Toxicity patterns missing from `input_guard.py` | input_guard.py | High | Open |

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

### Chunk size experiment — (fill in after Phase 7, Step 7.4)

| Chunk size | Chunks created | Retrieval precision | Notes |
|------------|----------------|---------------------|-------|
| 200        |                |                     |       |
| 500        |                |                     |       |
| 800        |                |                     |       |

Decision: chose ___ because ___
What I would try next: ___

### Guardrail impact on RAGAS scores — (fill in after Phase 7, Step 7.4)

| Metric             | Without guardrails | With guardrails | Change |
|--------------------|--------------------|-----------------|---------| 
| Faithfulness       |                    |                 |         |
| Answer relevancy   |                    |                 |         |
| Context precision  |                    |                 |         |
| Context recall     |                    |                 |         |

Conclusion: ___

### Top 3 evaluation failures — (fill in after Phase 7, Step 7.5)

#### Failure 1
Question:
Expected source:
Retrieved:
Root cause:
Proposed fix:

#### Failure 2
Question:
Expected source:
Retrieved:
Root cause:
Proposed fix:

#### Failure 3
Question:
Expected source:
Retrieved:
Root cause:
Proposed fix:

---

## Phase 8 — Deploy
(fill in after completing Phase 8)

---

## FINDINGS.md — Document structure findings

**Reviewed by:** Code review  
**Date:** Phase 1, Step 1.8  
**File:** `FINDINGS.md`  
**Total findings:** 1

---

### Finding 7 — Structural error: placeholders placed in wrong phase sections

**Severity:** Low  
**Type:** Document structure error — content placed out of chronological order  
**Location:** `FINDINGS.md` — original skeleton

**What was written (original):**

The original `FINDINGS.md` skeleton was created with three placeholders
inserted between the Phase 1 findings and the Phase 2 findings:

```
## Phase 1 — Code review findings — settings.py
   Finding 1 ...
   Finding 2 ...
   Finding 3 ...

── Chunk size experiment — (fill in after Phase 2, Step 2.6)    ← out of place
── Guardrail impact on RAGAS scores — (fill in after Phase 7)   ← out of place
── Top 3 evaluation failures — (fill in after Phase 7, Step 7.5)← out of place

## Phase 2 — Code review findings — loader.py
   Finding 4 ...
```

**The problem:**  
Three placeholders were placed between Phase 1 and Phase 2 with no phase
heading above them. This created three issues:

First — the chunk size experiment belongs to Phase 2 Step 2.6, not
between Phase 1 and Phase 2. Placing it before Phase 2 findings were
even documented broke the chronological flow of the file.

Second — the RAGAS scores and top 3 evaluation failures both belong to
Phase 7. Placing them between Phase 1 and Phase 2 meant they were
separated from the rest of the Phase 7 content by six phases worth of
future findings.

Third — the placeholders had no parent phase section heading. A reader
scanning the file by phase heading would find Phase 1 and Phase 2 but
never find these three sections because they sat between phases with no
clear ownership.

**The fix:**  
Restructure `FINDINGS.md` so every section lives under its correct
phase heading, in strict chronological order from Phase 1 to Phase 8:

```
## Phase 1  →  Findings 1, 2, 3       (settings.py)
## Phase 2  →  Findings 4, 5, 6       (loader.py)
## Phase 3  →  placeholder
## Phase 4  →  placeholder
## Phase 4B →  placeholder
## Phase 5  →  placeholder
## Phase 6  →  placeholder
## Phase 7  →  chunk size experiment
               RAGAS scores
               top 3 evaluation failures
## Phase 8  →  placeholder
```

The chunk size experiment moved to Phase 2 Step 2.6 where it is
actually performed. The RAGAS scores and evaluation failures moved to
Phase 7 where they belong.

**Rule learned:**  
A findings document should mirror the project's phase structure exactly.
Every placeholder belongs under its correct phase heading — not floating
between phases. If a section has no clear phase heading above it, it has
no clear owner and will be skipped or misread.

---

### Summary table — FINDINGS.md structure

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 7 | Chunk size, RAGAS, and failure placeholders placed between Phase 1 and Phase 2 with no phase heading | FINDINGS.md | Low | Fixed — all three moved to their correct phase sections |

---

## Phase 2 — Documentation findings — phase_02_ingestion.md

**Reviewed by:** Code review  
**Date:** Phase 2, Step 2.6  
**File:** `phase_02_ingestion.md`  
**Total findings:** 1

---

### Finding 16 — Sequencing error: chunk size experiment placed before its dependency exists

**Severity:** Medium  
**Type:** Documentation sequencing error — step cannot be completed when it appears  
**Location:** `phase_02_ingestion.md` — Step 2.6

**What the documentation says:**

Step 2.6 instructs you to run the chunk size experiment immediately after
building `ingest.py` in Step 2.5:

```
Phase 2
  Step 2.1 — loader.py
  Step 2.2 — chunker.py
  Step 2.3 — embedder.py
  Step 2.4 — vector_store.py
  Step 2.5 — ingest.py
  Step 2.6 — chunk size experiment   ← placed here
  Step 2.7 — test_ingestion.py
```

The experiment requires running:

```bash
python ingest.py --reset
python eval/retrieval_test.py   # measure precision for each chunk size
```

**The problem:**  
`eval/retrieval_test.py` is built in **Phase 3 Step 3.3** — an entire
phase later. At Step 2.6 this file does not exist. Running the experiment
at Step 2.6 is impossible because:

- `eval/retrieval_test.py` → does not exist until Phase 3 Step 3.3
- `retriever.py`           → does not exist until Phase 3 Step 3.1
- Without `retriever.py`, `retrieval_test.py` cannot search ChromaDB
- Without `retrieval_test.py`, there is no way to measure retrieval precision

The phase documentation acknowledges this indirectly with a small note:

> Note: Run these after building eval/retrieval_test.py in Phase 3 Step 3.3.
> Come back and fill in the results.

But placing Step 2.6 before Phase 3 while noting it requires Phase 3 is
contradictory. A developer following the steps in order would stop at
Step 2.6, find that `eval/retrieval_test.py` does not exist, and not
know whether to continue or wait.

**The correct sequence:**

```
Phase 2 Step 2.5 — ingest.py                  ← build
Phase 2 Step 2.7 — test_ingestion.py           ← build and test

Phase 3 Step 3.1 — retriever.py                ← build
Phase 3 Step 3.3 — retrieval_test.py           ← build

← return here to run the chunk experiment
Phase 2 Step 2.6 — chunk size experiment       ← should be done here
                   document results in FINDINGS.md
```

**The fix:**  
Step 2.6 should be treated as a deferred step. Skip it during Phase 2,
complete all of Phase 3 first, then return to run the three chunk size
experiments once `eval/retrieval_test.py` exists.

The chunk size experiment placeholder in `FINDINGS.md` under Phase 7
has been moved to Phase 2 where it belongs — it will be filled in
after Phase 3 Step 3.3 is complete.

**Rule learned:**  
Every step in a phase document must be executable at the point it
appears, using only files that already exist. If a step depends on
something built in a later phase, it must either be moved to after
that dependency is built, or clearly marked as a deferred step with
an explicit instruction to skip and return.

---

### Summary table — Phase 2 documentation

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 16 | Step 2.6 chunk experiment placed before `retrieval_test.py` exists | phase_02_ingestion.md | Medium | Deferred — complete after Phase 3 Step 3.3 |


---

## Phase 2 — Dependency findings — requirements.txt

**Reviewed by:** Code review  
**Date:** Phase 2, Step 2.4  
**File:** `requirements.txt`  
**Total findings:** 2

---

### Finding 14 — Missing dependency: `chromadb` not installed despite being in requirements.txt

**Severity:** High  
**Type:** `ModuleNotFoundError` — import fails at runtime  
**Location:** `requirements.txt` and `app/store/vector_store.py`

**What happened:**

```python
# vector_store.py line 1
from langchain_chroma import Chroma
```

Running this produced:

```
ModuleNotFoundError: No module named 'langchain_chroma'
```

Even though `langchain-chroma` was listed in `requirements.txt`, the
import still failed.

**The problem:**  
`langchain-chroma` is a LangChain wrapper around `chromadb`. It depends
on `chromadb` being installed underneath it. When `chromadb` is absent,
`langchain-chroma` cannot function — even if it is itself installed.
`chromadb` was not listed as an explicit dependency in `requirements.txt`
so it was never installed.

This is the same pattern as Finding 8 (`langchain-text-splitters`) —
LangChain has split its functionality across many sub-packages, each of
which must be installed explicitly. Assuming they are bundled together
leads to `ModuleNotFoundError` at runtime.

**The fix:**

```bash
# install both the wrapper and the underlying package
pip install langchain-chroma chromadb
```

Added `chromadb` explicitly to `requirements.txt`:

```
# before
langchain-chroma          # wrapper present, underlying package missing

# after
langchain-chroma          # wrapper
chromadb                  # underlying package — must be explicit
```

**Verified working after fix:**

```bash
python -c "from langchain_chroma import Chroma; print('OK')"
# OK

PYTHONPATH=. python -c "from app.store import vector_store; print('OK')"
# OK
```

**Rule learned:**  
When a LangChain sub-package wraps another library, both must be listed
explicitly in `requirements.txt`. Never assume that installing the wrapper
automatically installs the underlying library it wraps. Always run
`uv pip install -r requirements.txt` in a fresh environment to catch
missing transitive dependencies before they surface at runtime.

---

### Finding 15 — Duplicate entry: `chromadb` appeared twice in requirements.txt

**Severity:** Low  
**Type:** Duplicate entry — messy but not breaking  
**Location:** `requirements.txt`

**What happened:**  
`chromadb` was already listed at the top of `requirements.txt` from the
original Phase 1 setup. When it was appended again as a fix for
Finding 14, it appeared twice:

```
chromadb        ← line 1 — original entry
openai
langchain
...
langchain-chroma
chromadb        ← appended again — duplicate
```

**The problem:**  
`pip` and `uv` handle duplicate entries gracefully — the package is just
installed once. But duplicate entries make `requirements.txt` harder to
read and maintain. A developer scanning the file would see `chromadb`
near the top and assume it was intentionally there — then find it again
near the bottom and not know which entry to trust or update.

**The fix:**  
Rewrote `requirements.txt` from scratch with grouped comments and no
duplicates:

```
# LangChain ecosystem
langchain
langchain-openai
langchain-community
langchain-chroma
langchain-text-splitters

# Vector store
chromadb

# PDF processing
pdfplumber
pypdf

# API and server
fastapi
uvicorn

# OpenAI
openai
tiktoken

# Observability
langsmith

# Evaluation
ragas
datasets

# Data
pandas
numpy

# Utilities
python-dotenv
requests

# Testing
pytest
```

**Rule learned:**  
When adding a missing package to `requirements.txt`, always check
whether it already exists in the file before appending. If the file
has grown messy, rewrite it cleanly with grouped comments rather than
continuing to append.

---

### Summary table — requirements.txt

| # | Finding | File | Severity | Status |
|---|---|---|---|---|
| 14 | `chromadb` not installed — `ModuleNotFoundError` on `langchain_chroma` import | requirements.txt | High | Fixed — `chromadb` added explicitly |
| 15 | `chromadb` duplicate entry after fix was appended | requirements.txt | Low | Fixed — requirements.txt rewritten cleanly |