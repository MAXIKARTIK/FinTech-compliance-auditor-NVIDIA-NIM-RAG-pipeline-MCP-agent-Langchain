---
title: FinTech Compliance Auditor
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# FinTech Compliance Auditor — Hugging Face Space (all-in-one)

This Space runs the **entire stack in one free container** (no credit card):
FastAPI + Celery worker + PostgreSQL + Redis + ChromaDB + WeasyPrint + a
LangGraph agent, with the React dashboard served by Nginx on port `7860`.
All processes are supervised by `supervisord`; only `7860` is public and Nginx
reverse-proxies `/api` to the backend.

> The application code is cloned from GitHub at build time, so this Space repo
> only needs four files: `Dockerfile`, `supervisord.conf`, `nginx.conf`, `README.md`.

## Deploy (≈5 minutes)
1. Create a new Space → **SDK: Docker** → **CPU basic (free)**.
2. Add these four files to the Space repo (this folder's contents):
   `Dockerfile`, `supervisord.conf`, `nginx.conf`, `README.md`.
3. Space → **Settings → Variables and secrets** → add a **Secret**:
   - `NVIDIA_API_KEY` = your NVIDIA NIM key (from build.nvidia.com).
   - *(optional)* `SLACK_MCP_TOKEN`, `SLACK_CHANNEL`, `SEC_EDGAR_USER_AGENT`.
4. The Space builds automatically. When it's "Running", open the Space URL —
   the dashboard loads and every feature works.

## Notes
- **Storage is ephemeral on the free tier**: Postgres/Chroma data resets when
  the Space restarts. Migrations + demo seed run automatically on every boot,
  so it self-heals. (Attach paid persistent storage if you need durability.)
- **API key**: the dashboard's write key defaults to `demo-public-key` (baked
  into the frontend and matched by the runtime `API_KEY`). To change it, set the
  build **Variable** `APP_API_KEY` and a **Secret** `API_KEY` to the same value.
- **EDGAR is US-listings only** — use PayPal / Coinbase / SoFi / Robinhood.
- To update to the latest code, click **Factory rebuild** (re-clones GitHub).

## Verify
- Dashboard: open the Space URL, upload a fintech 10-K (PDF/URL) → "indexed" →
  Run Audit → score + findings + PDF report.
- Agent: `POST /api/agent/audit` with header `X-API-Key: demo-public-key` and
  body `{"ticker":"PYPL"}`.
- Health: `GET /api/health` → `postgres`, `redis`, `chroma` all `ok`.
