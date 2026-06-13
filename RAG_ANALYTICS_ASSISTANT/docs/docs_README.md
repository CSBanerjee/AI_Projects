# Knowledge Base Documentation

| File | Topics | Pages | Last updated | Owner |
|------|--------|-------|-------------|-------|
| sales_playbook.pdf | MEDDPICC, qualification, deal stages, closing techniques, competitive intelligence, escalation policy | 4 | Jan 2024 | Sales Ops |
| kpi_definitions.pdf | ASP, ARR, NRR, GRR, win rate, pipeline coverage, quota attainment, CAC, LTV, churn, NPS | 5 | Jan 2024 | Analytics |
| discount_policy.pdf | Discount tiers by deal size, regional adjustments, approval tiers, stacking rules, PS discounts | 3 | Jan 2024 | Finance |
| regional_strategy_apac.pdf | APAC targets, key accounts, growth verticals, Japan/India expansion, competitive landscape, headcount | 4 | Jan 2024 | APAC VP |
| regional_strategy_emea.pdf | EMEA targets, key accounts, DACH/Middle East expansion, competitive landscape, risk register | 4 | Jan 2024 | EMEA VP |

## Format

All source documents are PDF files. Do not add `.txt` files — the ingestion
pipeline is configured to load `.pdf` only.

## Updating the knowledge base

1. Replace or add a `.pdf` file in this folder.
2. Run `python ingest.py --reset` to rebuild the vector store from scratch.
3. Verify with `python eval/retrieval_test.py` — precision must remain above 0.70.
4. Update the "Last updated" column in the table above.
