# Automated FinTech Corporate Compliance Auditor

Backend + dashboard for ingesting 10-K/10-Q filings, running metadata-isolated RAG compliance audits, scoring risk, generating JSON/PDF reports, and orchestrating EDGAR-to-alert automation.

## R1-R9 Scope

- **R1 Ingestion**: Upload PDF or ingest by URL (PDF/HTML), async parse/index, idempotent per `(ticker, filing_type, fiscal_year, fiscal_quarter)`.
- **R2 Multi-tenant isolation**: ChromaDB `where` filter on ticker + fiscal period before similarity search.
- **R3 Rule management**: API-managed, versioned compliance rules in PostgreSQL.
- **R4 RAG engine**: retrieve -> structured finding (`status`, `evidence`, `explanation`, `confidence`); malformed output retries once then becomes `needs_review`.
- **R5 Scoring**: weighted compliance score `100 - failed_weight/total_weight * 100`.
- **R6 Reports**: persisted audit runs, JSON + PDF output, model/rule-version snapshot for reproducibility.
- **R7 Agent**: LangGraph flow `EDGAR fetch -> ingest -> audit -> history -> best-effort Slack alert on Critical`.
- **R8 Dashboard**: filing upload (PDF/URL), live status polling, run-audit control, findings + PDF popup.
- **R9 Non-functional**: Dockerized, async APIs/jobs, tests, `.env` secrets, API-key auth for write endpoints.

## Architecture Flow

`Upload/URL/EDGAR -> Celery parse (PDF/HTML) -> chunk + metadata -> NVIDIA embeddings -> ChromaDB -> metadata-filtered retrieval -> Nemotron reasoning -> structured findings -> weighted score -> PostgreSQL -> JSON/PDF report + optional Slack alert -> React dashboard`

## Stack

- **API**: FastAPI (async), Pydantic v2
- **Jobs**: Celery + Redis
- **Datastores**: PostgreSQL + ChromaDB
- **LLM**: NVIDIA NIM (`nemotron-3-ultra-550b-a55b`)
- **Embeddings**: NVIDIA NIM (`nemotron-3-embed-1b`)
- **Agent**: LangGraph + tool integrations (EDGAR/history/Slack)
- **Reports**: Jinja2 + WeasyPrint
- **Frontend**: React + Vite + TypeScript

## Quick Start

```bash
cp .env.example .env
docker compose up --build
# API docs: http://localhost:8000/docs
```

## Tests

```bash
cd backend && pip install -e ".[dev]" && python -m pytest
cd frontend && npm ci && npm run test -- --run
```

## Key Design Guarantees

- **Strict filing identity**: ingestion and chunk IDs are keyed by ticker + type + fiscal period; re-ingest upserts and does not duplicate.
- **Isolation first**: retrieval enforces metadata filter before similarity to prevent cross-company leakage.
- **Reproducible audits**: each run snapshots model config and exact rule versions.
- **Robust parsing of LLM output**: malformed model output never silently drops a rule.
- **Best-effort alerting**: Slack failures are logged and never fail audit completion.

## Notes on Domain Fit

Rules are tuned for fintech/financial filings (AML/KYC/SOX). Results on non-financial issuers may produce conservative false negatives for AML/KYC-specific checks.
