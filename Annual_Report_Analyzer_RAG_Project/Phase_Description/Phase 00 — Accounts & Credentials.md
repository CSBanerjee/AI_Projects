# Phase 00 — Accounts & Credentials

**Type:** Checklist — no code written in this phase
**Deliverable:** All accounts are created and all secret values are in hand
before Phase 01 begins

---

## Purpose

All external service accounts and credentials are established before any
code is written. Nothing in Phase 01 onward should be blocked by a missing
account or key.

---

## Accounts to be created

| # | Service | Purpose | What is obtained |
|---|---------|---------|-----------------|
| 1 | [OpenRouter](https://openrouter.ai) | LLM API — free tier access to multiple models | `OPENROUTER_API_KEY` |
| 2 | [LangSmith](https://smith.langchain.com) | Agent tracing and evaluation | `LANGCHAIN_API_KEY`, project name |
| 3 | Atlassian / Jira | Escalation ticket creation via MCP | PAT, project key, assignee `accountId` — see below |
| 4 | [GitHub](https://github.com) | Repo hosting, source for Render and Streamlit Cloud | Empty repo named `Annual_Report_Analyzer_RAG_Project` |
| 5 | [Render](https://render.com) | Backend hosting — free tier with persistent disk | Account only; repo connected in Phase 08 |
| 6 | [Streamlit Community Cloud](https://streamlit.io/cloud) | Frontend hosting — free tier | Account only; repo connected in Phase 08 |

---

## OpenRouter setup

Sign up at [openrouter.ai](https://openrouter.ai) and go to **Keys** to generate an API key.
The free tier gives access to several models (e.g. `mistralai/mistral-7b-instruct`, `google/gemma-3-27b-it`) with no credit card required.
The key is shown only once — store it securely.

---

## Jira setup

A Jira project is created using the Software or Business template. The
**project key** is noted — visible in any issue URL:
`yoursite.atlassian.net/browse/SUPPORT-123` → key is `SUPPORT`.

The **"Story"** issue type is confirmed as available in the project.
Some Business-template projects only include Task and Bug by default.

A **Personal Access Token** is generated at:
`id.atlassian.com/manage-profile/security/api-tokens`
The token is shown only once and stored securely.

The **assignee accountId** is retrieved via:
```bash
curl -u your-email@example.com:YOUR_API_TOKEN \
  "https://yoursite.atlassian.net/rest/api/3/user/search?query=your-email@example.com"
```
The `"accountId"` value is copied from the JSON response.

---

## Credentials to be stored privately

The following values are stored in private notes only.
**These are never committed to the repository.**

```
OPENROUTER_API_KEY=
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=annual-report-analyzer
JIRA_URL=https://yoursite.atlassian.net
JIRA_PERSONAL_TOKEN=
JIRA_PROJECT_KEY=
JIRA_ASSIGNEE_ACCOUNT_ID=
```

---

## Done when

- [ ] All 6 accounts exist
- [ ] All 7 credential values above are noted privately
- [ ] Jira "Story" issue type is confirmed as available
- [ ] GitHub repo `Annual_Report_Analyzer_RAG_Project` is created (empty)