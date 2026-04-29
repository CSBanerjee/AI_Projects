# ============================================================
# tests/test_pipeline.py
# ============================================================
# PURPOSE:
#   Tests every module in the pipeline without making a
#   single real API call and without spending any tokens.
#   Uses sample data defined at the top of this file.
#
# HOW TO RUN:
#   pytest tests/ -v
#
# WHAT EACH CLASS TESTS:
#   TestLoader  → app/data/loader.py
#   TestKpi     → app/pipeline/kpi.py
#   TestPrompt  → app/pipeline/prompt.py
#   TestWriter  → app/pipeline/writer.py
# ============================================================

import json
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch

# ── Sample data used across all tests ────────────────────────
# This is a small version of your sales_data.csv
# defined here so tests never depend on an external file
SAMPLE_ROWS = [
    {
        "deal_id"     : "D001",
        "region"      : "APAC",
        "product"     : "Analytics Pro",
        "revenue"     : 45000,
        "discount_pct": 10,
        "rep_name"    : "Priya Sharma",
        "close_date"  : "2024-01-15",
        "status"      : "Won"
    },
    {
        "deal_id"     : "D002",
        "region"      : "APAC",
        "product"     : "CRM Suite",
        "revenue"     : 95000,
        "discount_pct": 8,
        "rep_name"    : "Wei Chen",
        "close_date"  : "2024-01-25",
        "status"      : "Won"
    },
    {
        "deal_id"     : "D003",
        "region"      : "APAC",
        "product"     : "Analytics Pro",
        "revenue"     : 30000,
        "discount_pct": 20,
        "rep_name"    : "Raj Patel",
        "close_date"  : "2024-02-10",
        "status"      : "Lost"
    },
    {
        "deal_id"     : "D004",
        "region"      : "EMEA",
        "product"     : "CRM Suite",
        "revenue"     : 120000,
        "discount_pct": 5,
        "rep_name"    : "Hans Mueller",
        "close_date"  : "2024-01-18",
        "status"      : "Won"
    },
    {
        "deal_id"     : "D005",
        "region"      : "EMEA",
        "product"     : "Analytics Pro",
        "revenue"     : 55000,
        "discount_pct": 12,
        "rep_name"    : "Sophie Martin",
        "close_date"  : "2024-02-01",
        "status"      : "Lost"
    },
]


@pytest.fixture
def sample_df():
    # Reusable clean DataFrame for tests
    # @pytest.fixture means pytest automatically passes this
    # into any test function that has "sample_df" as a parameter
    return pd.DataFrame(SAMPLE_ROWS)


# ── TestLoader ────────────────────────────────────────────────
# Tests app/data/loader.py
# Uses tmp_path — a pytest built-in that creates a temporary
# folder for each test and deletes it automatically after

class TestLoader:

    def test_raises_if_file_missing(self, tmp_path):
        # loader.load() must raise FileNotFoundError
        # when the CSV file does not exist
        from app.data.loader import load
        fake_path = tmp_path / "nonexistent.csv"
        with pytest.raises(FileNotFoundError):
            load(fake_path)

    def test_raises_if_required_column_missing(self, tmp_path):
        # loader.load() must raise ValueError
        # when a required column like "revenue" is absent
        from app.data.loader import load
        bad_csv = tmp_path / "bad.csv"
        # Write a CSV with only 2 columns — missing revenue and others
        bad_csv.write_text("deal_id,region\nD001,APAC\n")
        with pytest.raises(ValueError, match="missing required columns"):
            load(bad_csv)

    def test_raises_if_file_is_empty(self, tmp_path):
        # loader.load() must raise ValueError
        # when CSV has a header row but zero data rows
        from app.data.loader import load
        empty_csv = tmp_path / "empty.csv"
        # Write header only — no data rows below it
        empty_csv.write_text(
            "deal_id,region,product,revenue,discount_pct,"
            "rep_name,close_date,status\n"
        )
        with pytest.raises(ValueError):
            load(empty_csv)

    def test_normalises_column_names_to_lowercase(self, tmp_path):
        # loader.load() must convert "Revenue" → "revenue"
        # and strip spaces from " Region " → "region"
        from app.data.loader import load
        csv = tmp_path / "data.csv"
        csv.write_text(
            "Deal_ID,Region,Product,Revenue,Discount_Pct,"
            "Rep_Name,Close_Date,Status\n"
            "D001,APAC,Pro,45000,10,Priya,2024-01-15,Won\n"
        )
        df = load(csv)
        # After normalisation these columns must exist in lowercase
        assert "revenue"  in df.columns
        assert "deal_id"  in df.columns
        assert "region"   in df.columns

    def test_returns_dataframe_with_correct_row_count(self, tmp_path):
        # loader.load() must return exactly the number of rows
        # that exist in the CSV file
        from app.data.loader import load
        csv = tmp_path / "data.csv"
        csv.write_text(
            "deal_id,region,product,revenue,discount_pct,"
            "rep_name,close_date,status\n"
            "D001,APAC,Pro,45000,10,Priya,2024-01-15,Won\n"
            "D002,EMEA,Suite,95000,8,Hans,2024-01-18,Won\n"
        )
        df = load(csv)
        assert len(df) == 2


# ── TestKpi ───────────────────────────────────────────────────
# Tests app/pipeline/kpi.py

class TestKpi:

    def test_win_rate_calculated_correctly(self, sample_df):
        # APAC has 2 Won deals and 1 Lost deal
        # win rate = 2 / 3 * 100 = 66.7%
        from app.pipeline.kpi import compute
        result = compute(sample_df, "APAC")
        assert result["win_rate"] == 66.7

    def test_total_revenue_counts_won_deals_only(self, sample_df):
        # APAC Won deals: D001 (45000) + D002 (95000) = 140000
        # D003 is Lost — must NOT be included in revenue
        from app.pipeline.kpi import compute
        result = compute(sample_df, "APAC")
        assert result["total_revenue"] == 140000.0

    def test_total_deals_counts_won_and_lost(self, sample_df):
        # total_deals must count ALL deals including Lost
        # APAC has 3 deals total (2 Won + 1 Lost)
        from app.pipeline.kpi import compute
        result = compute(sample_df, "APAC")
        assert result["total_deals"] == 3

    def test_won_deals_counts_only_won(self, sample_df):
        # won_deals must count only Won deals
        # APAC has 2 Won deals
        from app.pipeline.kpi import compute
        result = compute(sample_df, "APAC")
        assert result["won_deals"] == 2

    def test_raises_for_unknown_region(self, sample_df):
        # kpi.compute() must raise ValueError
        # when the region does not exist in the data
        from app.pipeline.kpi import compute
        with pytest.raises(ValueError, match="not found in data"):
            compute(sample_df, "UNKNOWN_REGION")

    def test_region_match_is_case_insensitive(self, sample_df):
        # "apac", "APAC", "Apac" must all return the same result
        from app.pipeline.kpi import compute
        result_upper = compute(sample_df, "APAC")
        result_lower = compute(sample_df, "apac")
        result_mixed = compute(sample_df, "Apac")
        assert result_upper["total_revenue"] == result_lower["total_revenue"]
        assert result_upper["total_revenue"] == result_mixed["total_revenue"]

    def test_returns_all_required_keys(self, sample_df):
        # KPI dictionary must contain all keys that
        # prompt.build() and writer.save() expect
        from app.pipeline.kpi import compute
        result = compute(sample_df, "APAC")
        expected_keys = [
            "region",
            "total_deals",
            "won_deals",
            "win_rate",
            "total_revenue",
            "avg_deal_size",
            "avg_discount",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key in KPI result: {key}"

    def test_avg_deal_size_is_won_deals_only(self, sample_df):
        # avg_deal_size must be the average of Won deals only
        # APAC Won: 45000 + 95000 = 140000 / 2 = 70000
        from app.pipeline.kpi import compute
        result = compute(sample_df, "APAC")
        assert result["avg_deal_size"] == 70000.0


# ── TestPrompt ────────────────────────────────────────────────
# Tests app/pipeline/prompt.py

# Sample KPI dictionary used across all prompt tests
SAMPLE_KPIS = {
    "region"        : "APAC",
    "total_deals"   : 3,
    "won_deals"     : 2,
    "win_rate"      : 66.7,
    "total_revenue" : 140000.0,
    "avg_deal_size" : 70000.0,
    "avg_discount"  : 12.7,
}


class TestPrompt:

    def test_prompt_contains_region_name(self):
        # The region name must appear in the prompt
        # so the LLM knows which region to write about
        from app.pipeline.prompt import build
        result = build(SAMPLE_KPIS)
        assert "APAC" in result

    def test_prompt_contains_win_rate(self):
        # The win rate value must be injected into the prompt
        from app.pipeline.prompt import build
        result = build(SAMPLE_KPIS)
        assert "66.7" in result

    def test_prompt_contains_revenue(self):
        # The revenue value must appear in the prompt
        from app.pipeline.prompt import build
        result = build(SAMPLE_KPIS)
        # Revenue is formatted with commas: 140,000
        assert "140,000" in result

    def test_prompt_raises_on_missing_keys(self):
        # prompt.build() must raise ValueError
        # if the KPI dictionary is missing required keys
        from app.pipeline.prompt import build
        incomplete_kpis = {"region": "APAC"}  # missing all other keys
        with pytest.raises(ValueError, match="missing keys"):
            build(incomplete_kpis)

    def test_prompt_returns_non_empty_string(self):
        # prompt.build() must always return
        # a non-empty string — never None or ""
        from app.pipeline.prompt import build
        result = build(SAMPLE_KPIS)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_prompt_raises_on_empty_dict(self):
        # prompt.build() must raise ValueError
        # when given a completely empty dictionary
        from app.pipeline.prompt import build
        with pytest.raises(ValueError):
            build({})


# ── TestWriter ────────────────────────────────────────────────
# Tests app/pipeline/writer.py
# Uses tmp_path and patch to redirect output to a temp folder
# so tests never write to your real output/ folder

SAMPLE_INSIGHT = "APAC delivered strong results this quarter."

SAMPLE_KPIS_WRITER = {
    "region"        : "APAC",
    "total_deals"   : 3,
    "won_deals"     : 2,
    "win_rate"      : 66.7,
    "total_revenue" : 140000.0,
    "avg_deal_size" : 70000.0,
    "avg_discount"  : 12.7,
}


class TestWriter:

    def test_creates_txt_file(self, tmp_path):
        # writer.save() must create a .txt report file
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        assert Path(paths["txt_path"]).exists()

    def test_creates_json_file(self, tmp_path):
        # writer.save() must create a .json report file
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        assert Path(paths["json_path"]).exists()

    def test_json_contains_insight_text(self, tmp_path):
        # The JSON file must contain the exact insight string
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        with open(paths["json_path"]) as f:
            data = json.load(f)
        assert data["insight"] == SAMPLE_INSIGHT

    def test_json_contains_region(self, tmp_path):
        # The JSON file must contain the region name
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        with open(paths["json_path"]) as f:
            data = json.load(f)
        assert data["region"] == "APAC"

    def test_json_contains_token_count(self, tmp_path):
        # The JSON file must record how many tokens were used
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        with open(paths["json_path"]) as f:
            data = json.load(f)
        assert data["tokens_used"] == 120

    def test_txt_contains_region_name(self, tmp_path):
        # The text report must include the region name
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        content = Path(paths["txt_path"]).read_text()
        assert "APAC" in content

    def test_txt_contains_insight_text(self, tmp_path):
        # The text report must include the LLM insight
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        content = Path(paths["txt_path"]).read_text()
        assert SAMPLE_INSIGHT in content

    def test_save_returns_both_paths(self, tmp_path):
        # writer.save() must return a dictionary
        # containing both txt_path and json_path keys
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths = writer.save(
                SAMPLE_KPIS_WRITER,
                SAMPLE_INSIGHT,
                120,
                "test_run_001"
            )
        assert "txt_path"  in paths
        assert "json_path" in paths

    def test_different_run_ids_create_separate_folders(self, tmp_path):
        # Each run_id must create its own subfolder
        # so reports from different runs never overwrite each other
        from app.pipeline import writer
        with patch.object(writer.settings, "OUTPUT_DIR", tmp_path):
            paths_1 = writer.save(
                SAMPLE_KPIS_WRITER, SAMPLE_INSIGHT, 120, "run_001"
            )
            paths_2 = writer.save(
                SAMPLE_KPIS_WRITER, SAMPLE_INSIGHT, 120, "run_002"
            )
        # Both files must exist and be in different folders
        assert Path(paths_1["txt_path"]).exists()
        assert Path(paths_2["txt_path"]).exists()
        assert paths_1["txt_path"] != paths_2["txt_path"]