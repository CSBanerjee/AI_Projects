# Knowledge Base Documentation

| File | Format | Topics | Last updated | Owner |
|------|--------|--------|--------------|-------|
| sales_playbook.txt | txt | Sales methodology, qualification, deal stages, closing techniques | 2024-01 | Sales Ops |
| kpi_definitions.txt | txt | ASP, win rate, pipeline coverage, quota attainment | 2024-01 | Analytics |
| discount_policy.txt | txt | Discount tiers by region and deal size, approval process | 2024-01 | Finance |
| regional_strategy_apac.txt | txt | APAC market priorities, key accounts, growth targets | 2024-01 | APAC VP |
| regional_strategy_emea.txt | txt | EMEA market priorities, key accounts, growth targets | 2024-01 | EMEA VP |

## Format

All source documents are plain text files. The ingestion pipeline
(`app/ingestion/loader.py`) is configured to load `.txt` only — any other
file extension in this folder is skipped silently.

## Updating the knowledge base

1. Add or replace a `.txt` file in this folder.
2. Run `python ingest.py --reset` to rebuild the vector store from scratch.
3. Verify with `python eval/retrieval_test.py` — precision must remain above 0.70.
4. Update the "Last updated" column in the table above.

## Switching to PDF sources later

If you swap these `.txt` files for real PDF documents, you must also update
`app/ingestion/loader.py`:
- Change the suffix filter from `.txt` to `.pdf`
- Replace `TextLoader` with a PDF loader (`pypdf` and `pdfplumber` are
  already in `requirements.txt` for this purpose)
- Re-run `python ingest.py --reset` and re-verify retrieval precision —
  PDF text extraction can change chunk boundaries and may require
  re-tuning `CHUNK_SIZE` / `CHUNK_OVERLAP`