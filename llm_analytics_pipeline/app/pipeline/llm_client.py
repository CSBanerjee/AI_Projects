# ============================================================
# app/pipeline/llm_client.py
# ============================================================
# PURPOSE:
#   One responsibility: talk to the OpenAI API.
#   LangSmith wraps the client automatically — every call
#   is traced and visible in the LangSmith dashboard.
#   No manual trace code needed anywhere in the project.
# ============================================================

import os
import time
from openai import OpenAI, RateLimitError, AuthenticationError
from langsmith import wrappers, traceable
from app.config import settings
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)


def build_client() -> OpenAI:
    # Sets LangSmith environment variables so the SDK
    # knows where to send traces
    os.environ["LANGCHAIN_TRACING_V2"]  = settings.LANGCHAIN_TRACING_V2
    os.environ["LANGCHAIN_ENDPOINT"]    = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"]     = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"]     = settings.LANGCHAIN_PROJECT

    # wrappers.wrap_openai() wraps the standard OpenAI client
    # Every call made through this client is automatically
    # traced and sent to LangSmith — no extra code needed
    client = wrappers.wrap_openai(
        OpenAI(api_key=settings.OPENAI_API_KEY)
    )
    log.info("OpenAI client built with LangSmith tracing enabled.")
    return client


@traceable(name="generate_insight")
def generate(client, prompt: str) -> dict:
    # @traceable decorator tells LangSmith to treat this
    # function as a named trace — you will see it as
    # "generate_insight" in the LangSmith dashboard with
    # its own input, output, latency, and token count
    for attempt in range(1, settings.MAX_RETRIES + 1):
        try:
            log_event(log, "info", "api_call_start",
                      attempt=attempt,
                      max=settings.MAX_RETRIES,
                      model=settings.MODEL)

            response = client.chat.completions.create(
                model=settings.MODEL,
                max_tokens=settings.MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}]
            )

            # Guard 1: is the choices list empty?
            if not response.choices:
                raise ValueError("API returned empty choices list.")

            text = response.choices[0].message.content.strip()

            # Guard 2: is the text blank?
            if not text:
                raise ValueError("API returned blank text response.")

            log_event(log, "info", "api_call_success",
                      tokens_in=response.usage.prompt_tokens,
                      tokens_out=response.usage.completion_tokens,
                      chars=len(text))

            return {
                "text"  : text,
                "tokens": response.usage.completion_tokens
            }

        except RateLimitError:
            log.warning(
                f"Rate limit hit on attempt {attempt}. "
                f"Waiting {settings.RETRY_DELAY_SECS}s..."
            )
            if attempt < settings.MAX_RETRIES:
                time.sleep(settings.RETRY_DELAY_SECS)

        except AuthenticationError:
            raise RuntimeError(
                "OpenAI API authentication failed.\n"
                "Check OPENAI_API_KEY in your .env file."
            )

        except ValueError as e:
            log.warning(f"Bad response on attempt {attempt}: {e}")
            if attempt == settings.MAX_RETRIES:
                raise RuntimeError(
                    f"API returned invalid response after "
                    f"{settings.MAX_RETRIES} attempts: {e}"
                )

        except Exception as e:
            log.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt == settings.MAX_RETRIES:
                raise RuntimeError(
                    f"API call failed after {settings.MAX_RETRIES} "
                    f"attempts. Last error: {e}"
                )

    raise RuntimeError("generate() exited retry loop without a result.")