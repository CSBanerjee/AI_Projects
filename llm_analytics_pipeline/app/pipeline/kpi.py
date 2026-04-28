# ============================================================
# app/pipeline/kpi.py
# ============================================================
# PURPOSE:
#   One responsibility: calculate KPIs from a DataFrame.
#   Takes a clean DataFrame and a region name.
#   Returns a dictionary of KPI values.
#
# WHY THIS FILE EXISTS:
#   KPI logic changes often — new metrics get added, formulas
#   get revised. Keeping it isolated means you update only
#   this file without touching the LLM or loader code.
#   It is also independently testable without API calls.
#
# HOW OTHER MODULES USE IT:
#   from app.pipeline import kpi
#   kpis = kpi.compute(df, "EMEA")
# ============================================================

import pandas as pd
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)


def compute(df: pd.DataFrame, region: str) -> dict:
    # ── Filter to the target region ────────────────────────────
    # .str.upper() on both sides makes the match case-insensitive
    # "apac", "APAC", "Apac" all match correctly
    region_df = df[df["region"].str.upper() == region.upper()]

    # ── Guard: does this region exist in the data? ─────────────
    if region_df.empty:
        available = df["region"].unique().tolist()
        raise ValueError(
            f"Region '{region}' not found in data.\n"
            f"Available regions: {available}"
        )

    # ── Filter to Won deals only ───────────────────────────────
    # Revenue KPIs should only count deals that closed as Won
    # Lost deals are tracked for win rate but not revenue
    won = region_df[region_df["status"].str.lower() == "won"]

    # ── KPI 1: Total deals and Won deals ───────────────────────
    total_deals = len(region_df)
    won_count   = len(won)

    # ── KPI 2: Win rate ────────────────────────────────────────
    # Guard: avoid division by zero if total_deals is 0
    win_rate = (won_count / total_deals * 100) if total_deals > 0 else 0.0

    # ── KPI 3: Total revenue (Won deals only) ──────────────────
    total_revenue = float(won["revenue"].sum())

    # ── KPI 4: Average deal size (Won deals only) ──────────────
    # Guard: avoid mean() on empty DataFrame if no Won deals
    avg_deal_size = float(won["revenue"].mean()) if not won.empty else 0.0

    # ── KPI 5: Average discount ────────────────────────────────
    # dropna() excludes rows where discount_pct is null
    # before calculating the average — null rows would make
    # mean() return NaN silently without this guard
    discount_col  = region_df["discount_pct"].dropna()
    avg_discount  = float(discount_col.mean()) if not discount_col.empty else 0.0

    # Warn if any discount rows were excluded
    null_discounts = len(region_df) - len(discount_col)
    if null_discounts > 0:
        log.warning(
            f"{null_discounts} rows had null discount_pct "
            f"and were excluded from avg_discount calculation."
        )

    # ── Build and return the KPI dictionary ────────────────────
    # round() keeps numbers clean for the prompt and reports
    kpis = {
        "region"        : region,
        "total_deals"   : total_deals,
        "won_deals"     : won_count,
        "win_rate"      : round(win_rate, 1),
        "total_revenue" : total_revenue,
        "avg_deal_size" : round(avg_deal_size, 0),
        "avg_discount"  : round(avg_discount, 1),
    }

    log_event(log, "info", "kpis_computed",
              region=region,
              win_rate=kpis["win_rate"],
              revenue=kpis["total_revenue"],
              deals=total_deals)

    return kpis