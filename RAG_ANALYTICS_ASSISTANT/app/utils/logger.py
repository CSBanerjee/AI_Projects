import logging                              # Python's built-in logging library — no install needed
from logging.handlers import RotatingFileHandler  # a special file handler that automatically
                                                   # creates a new file when the current one gets too big
from app.config import settings        # import our settings so we can read LOG_LEVEL, LOG_DIR, LOG_FILE

# This module-level variable acts as a guard.
# Once setup_logging() runs once, _configured becomes True.
# Every subsequent call sees True and returns immediately — preventing
# duplicate handlers being added each time a module imports get_logger().
_configured = False


def setup_logging() -> None:
    # global tells Python we want to modify the module-level _configured variable,
    # not create a new local variable with the same name inside this function.
    global _configured

    # If logging is already configured, do nothing and return early.
    # Without this guard, every module that calls get_logger() would add
    # another console handler, and you would see each log line printed
    # once per module that imported it.
    if _configured:
        return

    # logging.getLogger() with no arguments returns the ROOT logger.
    # All other loggers in the app are children of the root logger.
    # Setting the level here to DEBUG means the root logger accepts
    # every message — individual handlers then decide what to actually show.
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)   # DEBUG is the lowest level — accept everything

    # The formatter defines how each log line looks.
    # %(asctime)s     → timestamp e.g. 2024-01-15T14:32:01
    # %(levelname)-8s → level name padded to 8 chars e.g. "INFO    " or "WARNING "
    # %(name)s        → the logger's name, which we set to __name__ in each module
    #                   so you can see exactly which file produced the log line
    # %(message)s     → the actual message text
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",   # ISO 8601 format — unambiguous, sortable
    )

    # ── Handler 1: Console ────────────────────────────────────────────────────
    # StreamHandler sends log lines to the terminal (stdout/stderr).
    console = logging.StreamHandler()

    # getattr(logging, "INFO", logging.INFO) converts the string "INFO" from
    # settings.LOG_LEVEL into the integer constant logging.INFO (which equals 20).
    # The third argument logging.INFO is the fallback if the string in .env is
    # misspelled — e.g. if someone writes LOG_LEVEL=INFOR it falls back to INFO
    # instead of crashing.
    console.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

    console.setFormatter(formatter)    # apply the format we defined above
    root.addHandler(console)           # attach this handler to the root logger

    # ── Handler 2: Rotating file ──────────────────────────────────────────────
    # Make sure the logs/ directory exists before we try to write into it.
    # If it already exists, exist_ok=True means do nothing (no error).
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    # RotatingFileHandler writes to a file and automatically rotates it when
    # it reaches maxBytes. Old files are renamed to .log.1, .log.2, .log.3
    # and then deleted once backupCount is exceeded.
    # This prevents the log file from growing forever and filling your disk.
    file_handler = RotatingFileHandler(
        settings.LOG_FILE,      # full path to rag_pipeline.log
        maxBytes=1_000_000,     # rotate when the file reaches 1 MB (1,000,000 bytes)
        backupCount=3,          # keep at most 3 old rotated files (.log.1, .log.2, .log.3)
        encoding="utf-8",       # use UTF-8 so non-ASCII characters (e.g. in questions) don't crash
    )

    # The file handler always captures DEBUG and above — everything.
    # This means the file gets more detail than the console, which is useful
    # when debugging issues that only appear in production.
    file_handler.setLevel(logging.DEBUG)

    file_handler.setFormatter(formatter)   # same format as the console
    root.addHandler(file_handler)          # attach this handler to the root logger

    # Mark logging as configured so this function becomes a no-op on all future calls.
    _configured = True


def get_logger(name: str) -> logging.Logger:
    # Every module in the project calls this function at the top:
    #   log = get_logger(__name__)
    # __name__ is a Python built-in that equals the module's dotted path,
    # e.g. "app.retrieval.retriever" or "app.generation.llm_client".
    # This gives every log line a precise source so you know exactly
    # which file it came from.

    setup_logging()                    # ensure handlers are configured before returning a logger
    return logging.getLogger(name)     # return a logger named after the calling module


def log_event(logger: logging.Logger, level: str, event: str, **kwargs) -> None:
    # This helper produces structured log lines in a consistent key=value format.
    # Every module uses this instead of logger.info("some random text")
    # so that logs are machine-parseable and easy to search.
    #
    # Example call:
    #   log_event(log, "info", "retrieval_done", chunks=3, latency_ms=42)
    #
    # Produces this log line:
    #   2024-01-15T14:32:01 | INFO     | app.retrieval.retriever | event=retrieval_done chunks=3 latency_ms=42

    # **kwargs captures any number of keyword arguments passed to log_event.
    # We turn them into a string of "key=value" pairs separated by spaces.
    # e.g. {"chunks": 3, "latency_ms": 42} → "chunks=3 latency_ms=42"
    details = " ".join(f"{k}={v}" for k, v in kwargs.items())

    # Combine the event name with the key=value details into one message string.
    # .strip() removes any trailing space if kwargs was empty.
    message = f"event={event} {details}".strip()

    # getattr(logger, "info") returns logger.info — the method for that log level.
    # This lets us call any log level (info, warning, debug, error) dynamically
    # from a single function instead of writing a separate if/elif chain.
    # .lower() ensures "INFO" and "info" both work.
    getattr(logger, level.lower())(message)


# ── Smoke test ────────────────────────────────────────────────────────────────
# This block only runs when you execute this file directly:
#   python app/utils/logger.py
# It does NOT run when other modules import logger.py.
# Use it to verify the logger is working: check the terminal output and
# confirm that logs/rag_pipeline.log was created.
if __name__ == "__main__":
    log = get_logger(__name__)                          # get a logger named "__main__"
    log_event(log, "info",    "logger_smoke_test", status="ok")
    log_event(log, "warning", "logger_smoke_test", status="warning_check")
    log_event(log, "debug",   "logger_smoke_test", status="debug_visible_in_file_only")
    print(f"Log file written to: {settings.LOG_FILE}")  # confirm the path to the log file