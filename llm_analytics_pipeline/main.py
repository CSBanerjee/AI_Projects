# ============================================================
# main.py  —  Pipeline Entry Point
# ============================================================
# PURPOSE:
#   The orchestrator. Calls every module in order.
#   Contains NO business logic of its own — only coordinates.
#   This is the only file you run: python main.py
#
# PIPELINE STAGES:
#   1. Validate environment    (app/config/settings.py)
#   2. Load data               (app/data/loader.py)
#   3. Compute KPIs            (app/pipeline/kpi.py)
#   4. Build prompt            (app/pipeline/prompt.py)
#   5. Call LLM                (app/pipeline/llm_client.py)
#   6. Save output             (app/pipeline/writer.py)
# ============================================================

import sys
import time
from datetime import datetime

from app.config import settings
from app.utils.logger import get_logger, log_event
from app.data import loader
from app.pipeline import kpi, prompt, llm_client, writer

log = get_logger(__name__)


def run_pipeline(region: str) -> dict:
    # ── Runs the full pipeline for one region ─────────────────
    # Returns a result dictionary with status and outputs.
    # Never raises — all errors are caught and returned
    # as status="failed" so the caller can handle them cleanly.
    result = {"region": region, "status": "pending"}
    start  = time.time()

    try:
        # ── Stage 2: Load data ─────────────────────────────────
        log.info(f"[{region}] Stage 2: Loading data...")
        df = loader.load(settings.DATA_FILE)

        # ── Stage 3: Compute KPIs ──────────────────────────────
        log.info(f"[{region}] Stage 3: Computing KPIs...")
        kpis = kpi.compute(df, region)

        # ── Stage 4: Build prompt ──────────────────────────────
        log.info(f"[{region}] Stage 4: Building prompt...")
        llm_prompt = prompt.build(kpis)

        # ── Stage 5: Call LLM ──────────────────────────────────
        log.info(f"[{region}] Stage 5: Calling LLM...")
        client   = llm_client.build_client()
        response = llm_client.generate(client, llm_prompt)

        # ── Stage 6: Save output ───────────────────────────────
        log.info(f"[{region}] Stage 6: Saving output...")
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        paths  = writer.save(kpis, response["text"],
                             response["tokens"], run_id)

        result.update({
            "status"  : "success",
            "kpis"    : kpis,
            "insight" : response["text"],
            "tokens"  : response["tokens"],
            "paths"   : paths,
            "duration": round(time.time() - start, 1),
        })

        log_event(log, "info", "pipeline_success",
                  region=region,
                  tokens=response["tokens"],
                  duration=result["duration"])

    except (FileNotFoundError, ValueError) as e:
        log.error(f"[{region}] Data error: {e}")
        result.update({"status": "failed", "error": str(e)})

    except RuntimeError as e:
        log.error(f"[{region}] LLM error: {e}")
        result.update({"status": "failed", "error": str(e)})

    except Exception as e:
        log.exception(f"[{region}] Unexpected error: {e}")
        result.update({"status": "failed", "error": str(e)})

    return result


def main():
    start_time = time.time()
    run_id     = datetime.now().strftime("%Y%m%d_%H%M%S")

    log.info("=" * 55)
    log.info(f"PIPELINE START  run_id={run_id}")
    log.info(f"Region: {settings.FOCUS_REGION}")
    log.info("=" * 55)

    # ── Stage 1: Validate environment ─────────────────────────
    # Checks API key and data file exist before doing any work.
    # Fails immediately with a clear message if anything
    # is missing — instead of crashing mid-pipeline.
    log.info("Stage 1: Validating environment...")
    try:
        settings.validate()
    except (EnvironmentError, FileNotFoundError) as e:
        log.error(f"Environment validation failed: {e}")
        sys.exit(1)
    log.info("Environment OK.")

    # ── Run pipeline for the configured region ─────────────────
    result   = run_pipeline(settings.FOCUS_REGION)
    duration = round(time.time() - start_time, 1)

    # ── Print final summary ────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"PIPELINE COMPLETE")
    print(f"{'='*55}")
    print(f"  Region   : {result['region']}")
    print(f"  Status   : {result['status'].upper()}")
    print(f"  Duration : {duration}s")

    if result["status"] == "success":
        print(f"  Tokens   : {result['tokens']}")
        print(f"  Reports  : {result['paths']['txt_path']}")
        print(f"\nINSIGHT:")
        print("-" * 55)
        print(result["insight"])
        print("-" * 55)
    else:
        print(f"  Error    : {result.get('error')}")
        sys.exit(1)

    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()