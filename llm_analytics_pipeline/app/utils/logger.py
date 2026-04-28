# ============================================================
# app/utils/logger.py
# ============================================================
# PURPOSE:
#   Centralised logging for the entire project.
#   Every module calls get_logger(__name__) from here.
#   All logs go to the same file with the same format.
#
# WHY THIS FILE EXISTS:
#   Without this, every module sets up its own logging
#   separately — you get duplicate log lines, inconsistent
#   formats, and logs scattered across multiple files.
#   One logger setup here = consistent logs everywhere.
#
# HOW OTHER MODULES USE IT:
#   from app.utils.logger import get_logger
#   log = get_logger(__name__)
#   log.info("something happened")
# ============================================================

import logging
from logging.handlers import RotatingFileHandler
from app.config import settings

# Guard: prevents duplicate handler setup if this module
# is imported multiple times across different files
_configured = False


def setup_logging():
    global _configured
    if _configured:
        return  # already set up — skip

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # capture everything at root

    # Standard format for every log line:
    # 2024-01-15T09:30:00 | INFO     | app.pipeline.kpi | message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # ── Console handler ───────────────────────────────────────
    # Shows INFO and above in your terminal
    # DEBUG messages are too detailed for the console
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    console.setFormatter(formatter)
    root.addHandler(console)

    # ── File handler ──────────────────────────────────────────
    # Writes DEBUG and above to logs/pipeline.log
    # RotatingFileHandler: creates a new file after 1MB
    # backupCount=3: keeps last 3 old log files, deletes older
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    # Call this at the top of every module:
    #   log = get_logger(__name__)
    #
    # __name__ is automatically the module's file path
    # e.g. "app.pipeline.kpi" or "app.data.loader"
    # This tells you exactly which file produced each log line
    setup_logging()
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: str, event: str, **kwargs):
    # Structured logging helper — produces key=value log lines
    # that are easy to search and parse later.
    #
    # Usage:
    #   log_event(log, "info", "api_call", region="APAC", tokens=120)
    #
    # Produces this log line:
    #   event=api_call region=APAC tokens=120
    details = " ".join(f"{k}={v}" for k, v in kwargs.items())
    message = f"event={event} {details}".strip()
    getattr(logger, level.lower())(message)