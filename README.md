# Automated FinTech Corporate Compliance Auditor

Backend + minimal dashboard that ingests financial-sector filings (10-K/10-Q PDFs or SEC URLs), isolates data per company/period in ChromaDB, audits statements against API-managed compliance rules (SOX/AML/KYC) using **metadata-filtered RAG + structured LLM reasoning on NVIDIA NIM (Nemotron)**, produces risk-scored audit reports (JSON + PDF), and runs a LangGraph agent that fetches filings from SEC EDGAR, queries audit history, and sends Slack alerts on critical findings.

> **Scope:** built for **financial-sector** filings (banks, payments, fintechs) where AML/KYC/SOX disclosures apply (e.g. PayPal, Coinbase, SoFi, Robinhood).

## Stack
- **LLM (NVIDIA NIM)**: `nvidia/nemotron-3-ultra-550b-a55b` for compliance reasoning (controllable reasoning budget); provider-switchable to Anthropic/OpenAI via `LLM_PROVIDER`
- **Embeddings (NVIDIA NIM)**: `nvidia/nemotron-3-embed-1b` (2048-dim), passage/query aware
- **API**: FastAPI (async), Pydantic v2
- **Async jobs**: Celery + Redis
- **DBs**: PostgreSQL (rules, filings, audits, findings), ChromaDB (vectors + metadata)
- **RAG**: LangChain + ChromaDB, metadata-filtered retrieval, structured JSON findings
- **Agent**: LangGraph (SEC EDGAR fetch → ingest → audit → history → alert); `mcp.json` provided to expose the tools to MCP clients
- **Reports**: WeasyPrint (PDF) + JSON
- **Frontend**: React + Vite + TypeScript

## Quick start
```bash
cp .env.example .env          # fill in NVIDIA_API_KEY and API_KEY
docker compose up -d --build  # api, worker, postgres, redis, chromadb
docker compose exec api python scripts/seed.py   # seed rules + demo company
# API docs: http://localhost:8000/docs   |   health: http://localhost:8000/health
```
Dashboard (separate terminal):
```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Architecture
```mermaid
flowchart TB
    UI[Dashboard React/Vite] --> API

    subgraph API[FastAPI]
      E1[POST /filings/ingest]
      E6[POST /filings/ingest-url]
      E2[CRUD /rules]
      E3[POST /audit/run]
      E4[GET /audit/report/:id]
      E5[POST /agent/audit]
    end

    E1 --> RD[(Redis)]
    E6 --> RD
    RD --> CW[Celery Worker]
    CW --> PARSE[pdfplumber / BeautifulSoup] --> CHUNK[chunk + metadata tag]
    CHUNK --> EMB[NVIDIA Embeddings] --> CHROMA[(ChromaDB)]

    E2 --> PG[(PostgreSQL)]
    E3 --> RET[metadata-filtered retrieval] --> CHROMA
    RET --> LLM[Nemotron 3 Ultra - NVIDIA NIM] --> PG

    E5 --> AGENT[LangGraph Agent]
    AGENT --> EDGAR[SEC EDGAR fetch + ingest]
    AGENT --> HIST[audit history - PostgreSQL]
    AGENT --> SLACK[Slack alert]
    AGENT --> RET
```

## Data model
```mermaid
erDiagram
    COMPANY ||--o{ FILING : has
    FILING ||--o{ AUDIT_RUN : audited_by
    RULE ||--o{ FINDING : evaluated_in
    AUDIT_RUN ||--o{ FINDING : contains

    COMPANY {
        string ticker PK
    }
    FILING {
        uuid id PK
        string ticker FK
        string filing_type
        int fiscal_year
        string fiscal_quarter
        string status
    }
    RULE {
        string rule_id PK
        int version
        string regulation
        text check_prompt
        int severity_weight
        bool is_active
    }
    AUDIT_RUN {
        uuid id PK
        uuid filing_id FK
        int compliance_score
        string model_name
        json rule_versions
    }
    FINDING {
        uuid id PK
        uuid audit_run_id FK
        string rule_id FK
        string status
        json evidence
        string severity
        float confidence
    }
```

## Key design guarantees
- **Multi-tenant isolation (R2)**: retrieval applies a ChromaDB `where` filter on `ticker + filing_type + fiscal_year + fiscal_quarter` **before** vector similarity, so one company's query can never surface another's chunks. See `backend/tests/test_isolation.py`.
- **Idempotent ingestion (R1)**: deterministic chunk IDs + a unique `(ticker, filing_type, fiscal_year, fiscal_quarter)` constraint mean re-ingest upserts, never duplicates. PDF **and** HTML (SEC .htm) inputs supported.
- **Rule reproducibility (R3/R6)**: rule updates create a new immutable version; each audit snapshots `rule_versions` + `model_name` + model params.
- **Robust LLM output (R4)**: malformed output is retried once, then downgraded to `needs_review` (never silently dropped).
- **Best-effort alerting (R7)**: Critical findings trigger a Slack alert; failures are logged and never fail the audit. Side effects are triggered by orchestrator code, never directly by the LLM.

## Agent layer
A **LangGraph** state machine drives the autonomous flow: `fetch (SEC EDGAR) → ingest → audit → history → alert`. The three tools are implemented as direct integrations (SEC EDGAR via HTTP, audit history via SQL, Slack via the Web API); an **`mcp.json`** is included so the same tools can be exposed to MCP clients (e.g. Claude Desktop).

## One-command demo
```bash
docker compose up -d --build
docker compose exec api python scripts/seed.py       # seed rules + demo company
cd frontend && npm install && npm run dev            # http://localhost:5173
# In the dashboard: upload a fintech 10-K (PayPal / Coinbase PDF or SEC URL),
# wait for "indexed", then Run Audit -> score + findings + PDF report.
```
Agentic path (fetch straight from EDGAR):
```bash
curl -X POST http://localhost:8000/agent/audit \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"ticker":"PYPL"}'
```

## Tests
```bash
cd backend && pip install -e '.[dev]' && pytest       # all LLM/embedding/EDGAR/Slack calls mocked
cd frontend && npm ci && npm run test -- --run
```

## Environment
Copy `.env.example` to `.env` and set:
- `NVIDIA_API_KEY` — from build.nvidia.com (used for both chat + embeddings)
- `LLM_PROVIDER=nvidia`, `CHAT_MODEL`, `REASONING_BUDGET`, `ENABLE_THINKING`, `CHAT_TEMPERATURE`, `CHAT_TOP_P`
- `EMBEDDING_MODEL`, `EMBED_DIM`, `RETRIEVAL_TOP_K`
- `API_KEY` — protects write endpoints (`X-API-Key`); set the same value as the dashboard's `VITE_API_KEY`
- `SLACK_MCP_TOKEN`, `SLACK_CHANNEL` — optional alerting
- `SEC_EDGAR_USER_AGENT` — required by SEC EDGAR (descriptive contact)

Secrets live only in `.env` (gitignored); `.env.example` holds placeholders.

## Deploy online (free)

The whole system ships as one Docker Compose stack (`api`, `worker`, `postgres`,
`redis`, `chromadb`, `frontend`), so the simplest deployment is to run that stack
on a single host. The frontend container serves the built React app with **Nginx**
and reverse-proxies `/api` to the backend, so only one public port is needed.

**Production hardening already baked in:** Postgres/Redis/Chroma ports are bound to
`127.0.0.1` (never exposed publicly on the host), every service has
`restart: unless-stopped`, Alembic migrations run on `api` startup, and write
endpoints require `X-API-Key`.

### Recommended free path — Oracle Cloud Always Free VM + Compose
A single **Oracle Cloud Always Free** VM (Ampere A1 Arm — up to 4 OCPU / 24 GB RAM,
non-expiring) runs *every* feature — the Celery worker, ChromaDB, Postgres and
Redis included — at no cost. Two helper scripts in [`deploy/`](deploy/) automate it.

**Step 1 — create the VM (Oracle console):** launch an *Ampere A1* instance
(Ubuntu 22.04+ recommended; allocate the full free shape for comfortable builds).

**Step 2 — open the network (two layers — this is the #1 Oracle gotcha):**
1. *Cloud layer:* in the VCN **Security List / NSG**, add an **Ingress rule**:
   Source `0.0.0.0/0`, IP Protocol TCP, destination port **80** (and **443** for TLS).
2. *Host layer:* handled automatically by `oracle-setup.sh` below.

**Step 3 — bootstrap + deploy (on the VM):**
```bash
git clone <your-repo> && cd fintech
chmod +x deploy/*.sh

./deploy/oracle-setup.sh      # installs Docker + Compose, opens host firewall 80/443
#   log out and back in once so the 'docker' group applies

cp .env.example .env          # set NVIDIA_API_KEY, a strong API_KEY, CORS_ORIGINS
./deploy/deploy.sh            # builds + starts the prod stack, waits for health, seeds
```

`deploy.sh` uses the production overlay
[`docker-compose.prod.yml`](docker-compose.prod.yml): the dashboard is published
on port **80** (the only public entrypoint) and the API is **not** exposed to the
open internet — the frontend's Nginx reaches it over the internal compose network,
so `/docs` is reachable only via an SSH tunnel
(`ssh -L 8000:localhost:8000 <user>@<vm-ip>`). When it finishes, open
`http://<vm-public-ip>/`.

**HTTPS (optional):** put a free **Cloudflare Tunnel** in front (no extra open
ports needed), or run Caddy/Traefik as a reverse proxy pointed at the `frontend`
container. Set `CORS_ORIGINS` to your final `https://…` dashboard URL.

### Managed PaaS alternatives (mind the free-tier limits)
These are convenient but each has a catch for a stack with an always-on worker:

| Platform | Fits this stack? | Free-tier catch (verify before relying on it) |
|----------|------------------|-----------------------------------------------|
| [Render](https://render.com/docs/free) | Partially | Web services sleep after ~15 min idle; free Postgres is deleted ~30 days after creation; background workers (needed for Celery) are a paid plan. |
| [Railway](https://railway.app) | Yes | Only a small monthly trial credit — not free once the credit is used. |
| [Fly.io](https://fly.io) | Yes | Credit card required; free machines are small (~256 MB RAM), tight for Chroma + WeasyPrint. |
| Oracle Cloud Always Free | Yes | Card required at signup; genuinely free and non-expiring afterward. |

If you prefer the fully-managed split (no worker on a paid plan), the pieces also
run on free managed services: **Neon** (Postgres, persistent), **Upstash** (Redis),
**Chroma Cloud** (vectors), a static-site host for the frontend, plus a container
host that supports an always-on process for the worker. This needs a few connection
strings in `.env` but no code changes. *(Free-tier terms change often — the linked
docs are the source of truth. Content summarized for licensing compliance.)*

### Pre-flight checklist
- `API_KEY` set to a long random value (and matched by the dashboard's build arg).
- `CORS_ORIGINS` set to your real dashboard URL (only needed if the browser calls
  the API cross-origin; the bundled Nginx proxy keeps it same-origin).
- `NVIDIA_API_KEY` set; Slack/EDGAR values set if you use those features.
- Never commit `.env` (already gitignored). Rotate any key that has been shared.

output example 
<img width="1277" height="766" alt="outputexample" src="https://github.com/user-attachments/assets/b7977d39-f3a0-49a2-b4cb-fe41e75cd0f0" />
