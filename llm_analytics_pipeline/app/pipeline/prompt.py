# ============================================================
# app/pipeline/prompt.py
# ============================================================
# PURPOSE:
#   One responsibility: build the LLM prompt from KPI data.
#   Takes a KPI dictionary and returns a prompt string.
#   No API calls, no file I/O, no DataFrame logic here.
#
# WHY THIS FILE EXISTS:
#   Prompt wording changes frequently — you tweak the tone,
#   add new KPIs, change output length, try different personas.
#   Keeping prompts here means you iterate on wording without
#   touching API call code or risking breaking anything else.
#
# HOW OTHER MODULES USE IT:
#   from app.pipeline import prompt
#   llm_prompt = prompt.build(kpis)
# ============================================================


def build(kpis: dict) -> str:
    # ── Guard: verify all required keys exist ──────────────────
    # prompt.build() needs specific keys from the KPI dict.
    # If kpi.compute() changes and removes a key, this catches
    # it immediately with a clear message instead of a confusing
    # KeyError buried inside an f-string
    required_keys = [
        "region",
        "total_deals",
        "won_deals",
        "win_rate",
        "total_revenue",
        "avg_deal_size",
        "avg_discount"
    ]
    missing = [k for k in required_keys if k not in kpis]
    if missing:
        raise ValueError(
            f"KPI dictionary is missing keys needed to build prompt: {missing}"
        )

    # ── Build the prompt ───────────────────────────────────────
    # Three part structure that produces better LLM output
    # than a single flat question:
    #   1. Role    — who Claude is speaking as
    #   2. Context — the data it should reason over
    #   3. Task    — exactly what output is expected
    #
    # f-string reminder:
    #   {kpis['win_rate']:.1f}   → 1 decimal place e.g. 66.7
    #   {kpis['total_revenue']:,.0f} → commas, no decimals e.g. 1,250,000
    prompt = f"""
You are a senior commercial analytics advisor preparing a briefing
for the {kpis['region']} Regional Vice President.

Here are the latest sales performance metrics for {kpis['region']}:

- Total Deals Tracked : {kpis['total_deals']}
- Won Deals           : {kpis['won_deals']}
- Win Rate            : {kpis['win_rate']:.1f}%
- Total Won Revenue   : ${kpis['total_revenue']:,.0f}
- Average Deal Size   : ${kpis['avg_deal_size']:,.0f}
- Average Discount    : {kpis['avg_discount']:.1f}%

Write a concise 4-sentence executive insight that:
1. States the headline performance in one sentence
2. Identifies the single strongest result to leverage
3. Flags the most important risk or concern in the numbers
4. Recommends one specific action for the VP to take this week

Use confident, direct language. No bullet points. Plain paragraphs only.
""".strip()

    return prompt