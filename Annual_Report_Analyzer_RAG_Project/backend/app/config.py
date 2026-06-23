# ── Import the tools that read .env and map values to this class ──────────────
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Resolve .env path relative to this file, not the working directory ────────
# config.py is at backend/app/config.py
# parents[0] = backend/app/
# parents[1] = backend/
# parents[2] = project root  ← where .env lives
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


# ── Define all the config variables the app needs ────────────────────────────
class Settings(BaseSettings):

    # Tell pydantic-settings where to find the .env file
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,             # absolute path — always resolves correctly
        env_file_encoding="utf-8",     # how to read the file
        extra="ignore",                # ignore any extra keys not listed below
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    openrouter_api_key: str = ""       # OPENROUTER_API_KEY in .env
    openrouter_model: str = ""         # OPENROUTER_MODEL in .env

    # ── Tracing ──────────────────────────────────────────────────────────────
    langchain_api_key: str = ""        # LANGCHAIN_API_KEY in .env
    langchain_project: str = ""        # LANGCHAIN_PROJECT in .env

    # ── Jira ─────────────────────────────────────────────────────────────────
    jira_url: str = ""                 # JIRA_URL in .env
    jira_personal_token: str = ""      # JIRA_PERSONAL_TOKEN in .env
    jira_project_key: str = ""         # JIRA_PROJECT_KEY in .env
    jira_assignee_account_id: str = "" # JIRA_ASSIGNEE_ACCOUNT_ID in .env


# ── Create one shared settings object — imported by all other files ───────────
settings = Settings()