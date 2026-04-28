# ============================================================
# app/pipeline/writer.py
# ============================================================
# PURPOSE:
#   One responsibility: save pipeline results to disk.
#   Writes a human-readable .txt report and a
#   machine-readable .json file for every pipeline run.
#
# WHY THIS FILE EXISTS:
#   Output format changes independently of pipeline logic.
#   If you need to add PDF output, email delivery, or a
#   database write later, you add it here without touching
#   the KPI or LLM code.
#
# HOW OTHER MODULES USE IT:
#   from app.pipeline import writer
#   paths = writer.save(kpis, insight, tokens, run_id)
# ============================================================

import json
from pathlib import Path
from datetime import datetime
from app.config import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


def save(kpis: dict, insight: str, tokens: int, run_id: str) -> dict:
    # ── Set up output directory ────────────────────────────────
    # Each run gets its own folder named by run_id
    # so reports from different runs never overwrite each other
    region  = kpis["region"].upper()
    out_dir = settings.OUTPUT_DIR / run_id

    # exist_ok=True means: don't crash if folder already exists
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Write human-readable text report ──────────────────────
    # This is what you would send to a regional VP
    txt_path = out_dir / f"insight_{region}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"REGIONAL INSIGHT REPORT\n")
        f.write(f"Region    : {region}\n")
        f.write(f"Run ID    : {run_id}\n")
        f.write(f"Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 55 + "\n\n")
        f.write("KPI SUMMARY:\n")
        f.write(f"  Win Rate       : {kpis['win_rate']:.1f}%\n")
        f.write(f"  Total Revenue  : ${kpis['total_revenue']:,.0f}\n")
        f.write(f"  Avg Deal Size  : ${kpis['avg_deal_size']:,.0f}\n")
        f.write(f"  Avg Discount   : {kpis['avg_discount']:.1f}%\n")
        f.write(f"  Total Deals    : {kpis['total_deals']}\n")
        f.write(f"  Won Deals      : {kpis['won_deals']}\n")
        f.write(f"\nEXECUTIVE INSIGHT ({len(insight.split())} words):\n")
        f.write("-" * 55 + "\n")
        f.write(insight + "\n")
        f.write("-" * 55 + "\n")
        f.write(f"\nTokens used: {tokens}\n")

    # ── Write machine-readable JSON report ────────────────────
    # This can be consumed by other systems, dashboards,
    # or a future database ingestion pipeline
    json_path = out_dir / f"insight_{region}.json"
    payload = {
        "run_id"     : run_id,
        "region"     : region,
        "timestamp"  : datetime.now().isoformat(),
        "kpis"       : kpis,
        "insight"    : insight,
        "word_count" : len(insight.split()),
        "tokens_used": tokens,
    }
    with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
    
    log.info(f"Reports saved → {txt_path.name}, {json_path.name}")

    # Return both paths so main.py can print them
    return {
        "txt_path" : str(txt_path),
        "json_path": str(json_path),
    }