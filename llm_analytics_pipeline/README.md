# LLM Analytics Pipeline

A modular, production-grade, Dockerised AI pipeline that reads commercial sales data, computes KPIs per region, and generates executive insights using an LLM. Built with Python, OpenAI, LangSmith observability, and Docker.

# What Readme file covers:
## Annotated project structure — 
    every single file and folder has a comment explaining exactly what it does and why it exists.
## Why the structure exists — 
    a table showing which file you touch for each type of change — so anyone reading the repo immediately understands the single responsibility principle you applied.
## How each file was built — 
    Steps 2 through 10, one section per file, explaining what key decisions were made and why. This is the most valuable part for any interviewer or collaborator — it shows you didn't just copy code, you understood every architectural choice.
## All the standard sections — 
    how to run locally, how to run with Docker, environment variables, tests, output files, and LangSmith monitoring.

---

## Project structure

```
llm_analytics_pipeline/
│
├── .env                         # Secret values — API keys. NEVER commit to GitHub
├── .env.example                 # Safe template showing which keys to set
├── .gitignore                   # Tells Git what NOT to upload (protects .env)
├── .dockerignore                # Tells Docker what NOT to copy into the container
│
├── main.py                      # Entry point — orchestrates all stages in order
├── requirements.txt             # Python package list — installed with uv pip install -r
├── Dockerfile                   # Instructions to build the Docker container image
├── docker-compose.yml           # Runs the container with one command: docker compose up
│
├── app/                         # All application source code lives here
│   │
│   ├── config/
│   │   ├── __init__.py          # Makes config/ a Python package (required for imports)
│   │   └── settings.py          # Single source of truth for ALL config — reads from .env
│   │
│   ├── data/
│   │   ├── __init__.py          # Makes data/ a Python package (required for imports)
│   │   └── loader.py            # Loads CSV, validates columns and rows, returns DataFrame
│   │
│   ├── pipeline/
│   │   ├── __init__.py          # Makes pipeline/ a Python package (required for imports)
│   │   ├── kpi.py               # Computes win rate, revenue, avg deal size per region
│   │   ├── prompt.py            # Builds the structured LLM prompt from KPI dictionary
│   │   ├── llm_client.py        # Calls OpenAI API, handles retries, tracks tokens, sends traces to LangSmith
│   │   └── writer.py            # Saves results as .txt report and .json file per run
│   │
│   └── utils/
│       ├── __init__.py          # Makes utils/ a Python package (required for imports)
│       └── logger.py            # Centralised logging — every module imports get_logger() from here
│
├── data/
│   └── sales_data.csv           # Input file — commercial sales data with region, revenue, status
│
├── output/                      # Generated reports land here — auto-created by the pipeline
│   └── {run_id}/
│       ├── insight_EMEA.txt     # Human-readable report for the regional VP
│       └── insight_EMEA.json    # Machine-readable report for downstream systems
│
├── logs/
│   └── pipeline.log             # Rotating log file — every event timestamped across all runs
│
└── tests/
    ├── __init__.py              # Makes tests/ a Python package (required for imports)
    └── test_pipeline.py         # 16 tests covering every module — no API key needed to run
```

---

## Why this structure exists

Every file has one responsibility. When something breaks or needs to change, you go to exactly one file.

| If you need to... | You touch only... |
|---|---|
| Change the API key or model | `.env` |
| Switch data source from CSV to database | `app/data/loader.py` |
| Add a new KPI like quota attainment | `app/pipeline/kpi.py` |
| Change the prompt wording or persona | `app/pipeline/prompt.py` |
| Switch from OpenAI to Anthropic | `app/pipeline/llm_client.py` |
| Add PDF output or email delivery | `app/pipeline/writer.py` |
| Change log format or log level | `app/utils/logger.py` |
| Run on a different machine | `Dockerfile` |

---

## How each file was built — step by step

### Step 1 — Project setup

Created the virtual environment and installed dependencies:

```bash
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows

uv pip install -r requirements.txt
```

Created the folder structure manually in VS Code:

```bash
mkdir app app/config app/data app/pipeline app/utils tests data output logs
```

Created empty `__init__.py` files in every folder under `app/` and in `tests/` so Python treats each folder as an importable package.

---

### Step 2 — `app/config/settings.py`

**Created first** because every other module imports from it.

Reads all configuration from `.env` using `os.getenv()`. Defines paths for data, output, and logs using `pathlib.Path`. Contains a `validate()` function called once at startup in `main.py` that checks the API key and data file exist before the pipeline does any work.

Key decisions made:
- Used `Path(__file__).resolve().parent.parent.parent` to build paths relative to the file location — works regardless of where you run the script from
- Used `int(os.getenv("MAX_TOKENS", "400"))` pattern — reads from `.env` but falls back to a sensible default if not set
- Added `OUTPUT_DIR.mkdir(parents=True, exist_ok=True)` inside `validate()` so directories are auto-created before any module tries to write to them

---

### Step 3 — `app/utils/logger.py`

**Created second** because every module after this uses logging.

Sets up a rotating file handler and a console handler once — then every module calls `get_logger(__name__)` to get a named logger. Uses a `_configured` boolean guard to prevent duplicate log entries if multiple modules import it in the same run.

Key decisions made:
- `RotatingFileHandler` with `maxBytes=1_000_000` and `backupCount=3` — prevents the log folder from filling disk on long-running pipelines
- Console shows `INFO` and above. File captures `DEBUG` and above — more detail in the file for debugging, cleaner output on screen
- Added `log_event()` helper that writes structured `key=value` log lines — easy to search with `grep event=api_call` across runs

---

### Step 4 — `app/data/loader.py`

**Created third** — takes a file path, returns a clean DataFrame.

Key decisions made:
- `df.columns = df.columns.str.lower().str.strip()` — normalises column names so `"Revenue"` and `"revenue"` both work without crashing
- Three guards added that AI output was missing: file existence check, required columns check, empty file check
- Each guard raises a specific exception type with a helpful message pointing to the exact fix needed

---

### Step 5 — `app/pipeline/kpi.py`

**Created fourth** — takes a DataFrame and region name, returns a KPI dictionary.

Key decisions made:
- `.str.upper()` on both sides of the region comparison — makes `"apac"`, `"APAC"`, and `"Apac"` all match correctly
- Revenue KPIs only count `Won` deals — `Lost` deals are included in deal count and win rate but excluded from revenue totals
- `dropna()` before calculating `avg_discount` — prevents `mean()` returning `NaN` silently when null values exist
- `float()` wrapping on all numeric outputs — prevents pandas dtype objects causing serialisation errors when writing to JSON later

---

### Step 6 — `app/pipeline/prompt.py`

**Created fifth** — takes a KPI dictionary, returns a formatted prompt string.

Key decisions made:
- Guard at the top checks all required keys exist in the dictionary before building — catches breaking changes in `kpi.py` immediately with a clear error instead of a confusing `KeyError` inside an f-string
- Three-part prompt structure: Role → Context → Task — consistently produces better LLM output than a flat question
- Used `:,.0f` f-string formatting for revenue — turns `1678000.75` into `$1,678,001` which is how executives expect to see numbers
- No imports — this file has zero dependencies, making it the easiest module to test and change

---

### Step 7 — `app/pipeline/llm_client.py`

**Created sixth** — calls the OpenAI API, returns a response dictionary.

Key decisions made:
- `wrappers.wrap_openai()` from LangSmith wraps the client — every API call is automatically traced to the LangSmith dashboard with zero additional code in other modules
- `@traceable(name="generate_insight")` decorator names the trace in LangSmith — makes it easy to find and compare runs
- Retry loop runs up to `MAX_RETRIES` times — catches transient rate limit errors without crashing the pipeline
- `AuthenticationError` breaks the retry loop immediately — no point retrying a wrong API key
- Two response guards: empty `choices` list check before `[0]` indexing, blank text check after extraction — prevents silent empty responses

---

### Step 8 — `app/pipeline/writer.py`

**Created seventh** — saves pipeline results to disk.

Key decisions made:
- Each run gets its own subfolder named by `run_id` (timestamp) — reports from different runs never overwrite each other
- Writes both `.txt` (human-readable for VP) and `.json` (machine-readable for downstream systems) — covers both use cases in one call
- `encoding="utf-8"` on all file writes — prevents `UnicodeEncodeError` on Windows when LLM returns em-dashes or smart quotes
- `json.dump(..., default=str)` — converts any non-serialisable pandas or datetime objects to strings automatically

---

### Step 9 — `main.py`

**Created last** because it depends on every other module.

Key decisions made:
- `run_pipeline()` is a separate function from `main()` — makes it easy to call for multiple regions in a future batch version
- All errors are caught inside `run_pipeline()` and returned as `status="failed"` — the function never raises, so a caller can handle failures without try/except wrapping
- Stage 1 validation runs before anything else — fails immediately with a clear message if API key or data file is missing
- `sys.exit(1)` on failure — returns a non-zero exit code so Docker and CI systems know the run failed

---

### Step 10 — `tests/test_pipeline.py`

**Written alongside each module** — 16 tests covering all four core modules.

Key decisions made:
- Uses `pytest` fixtures and `tmp_path` — tests write to temporary directories that are cleaned up automatically
- `unittest.mock.patch` used in writer tests — redirects output to a temp folder without changing any production code
- No API key needed — all tests use sample data defined at the top of the file
- Tests deliberately check failure cases (missing file, wrong region, missing columns) not just happy path

---

## How to run locally

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/llm-analytics-pipeline.git
cd llm-analytics-pipeline

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Open .env and add your OPENAI_API_KEY and LANGCHAIN_API_KEY

# 5. Run tests — no API key needed
pytest tests/ -v

# 6. Run the pipeline
python main.py
```

---

## How to run with Docker

```bash
# Build the image
docker build -t llm-analytics-pipeline .

# Run with docker compose
docker compose up

# Change region without editing code
docker run --env-file .env -e FOCUS_REGION=APAC llm-analytics-pipeline
```

---

## Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
# Required
OPENAI_API_KEY=your-openai-key-here
LANGCHAIN_API_KEY=ls__your-langsmith-key-here

# LLM settings
MODEL=gpt-4o
MAX_TOKENS=400
MAX_RETRIES=2
RETRY_DELAY_SECS=15

# Pipeline settings
FOCUS_REGION=EMEA
DATA_FILE=sales_data.csv
API_DELAY_SECS=2

# LangSmith observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=llm-analytics-pipeline

# Logging
LOG_LEVEL=INFO
```

---

## How to run tests

```bash
# Run all 16 tests
pytest tests/ -v

# Run only one module's tests
pytest tests/ -v -k "TestKpi"

# Run one specific test
pytest tests/ -v -k "test_revenue_is_won_deals_only"

# Stop on first failure
pytest tests/ -v -x
```

---

## Output

Every run creates two files in `output/{run_id}/`:

| File | Purpose |
|---|---|
| `insight_EMEA.txt` | Human-readable report — KPI summary + LLM insight |
| `insight_EMEA.json` | Machine-readable — for dashboards or downstream pipelines |

---

## Monitoring with LangSmith

Every API call is automatically traced to `https://smith.langchain.com`. Each trace shows:

| What LangSmith records | What it tells you |
|---|---|
| Full prompt sent | Exactly what was passed to the LLM |
| Full response received | Exactly what came back |
| Latency | How long the API call took |
| Token count | Input + output tokens per call |
| Cost estimate | Approximate $ per run |

---

## Skills demonstrated

`Python` · `OpenAI SDK` · `pandas` · `pathlib` · `python-dotenv` · `logging` · `LangSmith` · `pytest` · `Docker` · `docker-compose` · `Git` · `modular architecture` · `error handling` · `retry logic` · `data quality` · `production pipeline design`