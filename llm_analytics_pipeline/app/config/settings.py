# ============================================================
# app/config/settings.py
# ============================================================
# PURPOSE:
#   Single source of truth for ALL configuration.
#   Every value comes from environment variables (.env file).
#   No hardcoded values anywhere in the project.
#
# WHY THIS FILE EXISTS:
#   Instead of every module reading .env separately,
#   they all import from here. If a variable name changes,
#   you fix it in one place — not across 5 files.
#
# HOW IT WORKS:
#   os.getenv("KEY", "default") reads the variable from .env.
#   If the variable is not set, it uses the default value.
#   This means the app works locally without Docker too.
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file into memory
# After this line, os.getenv() can read your .env values
load_dotenv()

# ── Paths ─────────────────────────────────────────────────────
# __file__  = this file:     app/config/settings.py
# .parent   = config folder: app/config/
# .parent   = app folder:    app/
# .parent   = project root:  llm_analytics_pipeline/
BASE_DIR   = Path(__file__).resolve().parent.parent.parent

DATA_DIR   = BASE_DIR / "data"      # where sales_data.csv lives
OUTPUT_DIR = BASE_DIR / "output"    # where reports are saved
LOG_DIR    = BASE_DIR / "logs"      # where log files are saved

# ── Data ──────────────────────────────────────────────────────
DATA_FILE  = DATA_DIR / os.getenv("DATA_FILE", "sales_data.csv")

# ── LLM ───────────────────────────────────────────────────────
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
MODEL            = os.getenv("MODEL", "gpt-4o")
MAX_TOKENS       = int(os.getenv("MAX_TOKENS", "400"))
MAX_RETRIES      = int(os.getenv("MAX_RETRIES", "2"))
RETRY_DELAY_SECS = int(os.getenv("RETRY_DELAY_SECS", "15"))
# ── LangSmith Observability ───────────────────────────────────
LANGCHAIN_TRACING_V2  = os.getenv("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_ENDPOINT    = os.getenv("LANGCHAIN_ENDPOINT", "")
LANGCHAIN_API_KEY     = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT     = os.getenv("LANGCHAIN_PROJECT", "llm-analytics-pipeline")

# ── Pipeline ──────────────────────────────────────────────────
FOCUS_REGION   = os.getenv("FOCUS_REGION", "EMEA")
API_DELAY_SECS = int(os.getenv("API_DELAY_SECS", "2"))

# ── Logging ───────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE  = LOG_DIR / "pipeline.log"


def validate():
    # ── Called once at startup in main.py ─────────────────────
    # Checks everything is in place BEFORE the pipeline runs.
    # Fails immediately with a clear message instead of
    # crashing 50 lines later with a confusing error.

    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set.\n"
            "Add this line to your .env file:\n"
            "OPENAI_API_KEY=your-openai-key-here"
        )

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Data file not found: {DATA_FILE}\n"
            f"Place your CSV in the data/ folder."
        )

    # Create output and log directories if they don't exist yet
    # exist_ok=True means: don't crash if folder already exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)