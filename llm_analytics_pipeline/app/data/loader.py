# ============================================================
# app/data/loader.py
# ============================================================
# PURPOSE:
#   One responsibility: load the CSV and validate it.
#   Returns a clean DataFrame to whoever calls it.
#   No KPI logic, no LLM calls, no prompt building here.
#
# WHY THIS FILE EXISTS:
#   If the data source changes later (CSV → database → API)
#   you change only this file. Every other module just
#   receives a clean DataFrame and doesn't care where
#   it came from.
#
# HOW OTHER MODULES USE IT:
#   from app.data import loader
#   df = loader.load(settings.DATA_FILE)
# ============================================================

import pandas as pd
from pathlib import Path
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)

# These columns must exist in the CSV before
# the pipeline is allowed to continue
REQUIRED_COLUMNS = [
    "deal_id",
    "region",
    "product",
    "revenue",
    "discount_pct",
    "rep_name",
    "close_date",
    "status"
]


def load(filepath: Path) -> pd.DataFrame:
    # ── Guard 1: does the file exist? ─────────────────────────
    # Check before trying to open it — gives a clear message
    # instead of a confusing Python FileNotFoundError traceback
    if not filepath.exists():
        raise FileNotFoundError(
            f"Data file not found: {filepath}\n"
            f"Make sure sales_data.csv is inside your data/ folder."
        )

    log.info(f"Loading data from: {filepath.name}")

    # Read the CSV into a pandas DataFrame
    # A DataFrame is a table — rows and columns, like Excel
    df = pd.read_csv(filepath)

    # ── Normalise column names ─────────────────────────────────
    # Converts "Revenue" → "revenue", " Region " → "region"
    # Prevents KeyError when column names have
    # accidental capital letters or spaces
    df.columns = df.columns.str.lower().str.strip()

    # ── Guard 2: are all required columns present? ─────────────
    # Build a list of columns that are missing
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {missing}\n"
            f"Columns found in file: {list(df.columns)}"
        )

    # ── Guard 3: does the file have actual data rows? ──────────
    # A CSV with only a header row and no data is useless
    if df.empty:
        raise ValueError(
            f"CSV file loaded but contains zero rows: {filepath.name}\n"
            f"Check that the file has data below the header row."
        )

    log_event(log, "info", "data_loaded",
              file=filepath.name,
              rows=len(df),
              columns=len(df.columns))

    return df