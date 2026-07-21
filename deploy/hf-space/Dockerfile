# =============================================================================
# All-in-one image for Hugging Face Spaces (free CPU tier, no credit card).
# Runs the ENTIRE stack in one container via supervisord:
#   postgres + redis + chromadb (server) + celery worker + fastapi + nginx
# Exposes only port 7860 (HF standard); the frontend Nginx proxies /api -> API.
#
# Build context = this directory (deploy/hf-space). App code is cloned from
# GitHub at build time, so the Space repo only needs these 4 files.
# =============================================================================
FROM python:3.12-slim-bookworm

# ---- system packages ------------------------------------------------------
# WeasyPrint (pango/cairo/gdk-pixbuf), Postgres 15, Redis, Nginx, supervisor,
# Node+npm (to build the React frontend), git/curl.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 shared-mime-info \
      postgresql postgresql-contrib \
      redis-server \
      nginx \
      supervisor \
      nodejs npm \
      git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/usr/lib/postgresql/15/bin:$PATH

# ---- non-root user (HF Spaces runs the container as UID 1000) --------------
RUN useradd -m -u 1000 appuser
ENV HOME=/home/appuser

# ---- clone the application code -------------------------------------------
ARG REPO=https://github.com/MAXIKARTIK/FinTech-compliance-auditor-NVIDIA-NIM-RAG-pipeline-MCP-agent-Langchain.git
ARG CACHEBUST=0
RUN git clone --depth 1 "$REPO" /home/appuser/app_src

# ---- build the React frontend (served statically by nginx) ----------------
# VITE_API_BASE=/api  -> SPA calls same-origin; nginx proxies to the API.
# VITE_API_KEY is baked at build time (Vite inlines it). For a public demo the
# dashboard must carry the write key, so it defaults to a known value that the
# runtime API_KEY also defaults to (override both together if you want).
ARG VITE_API_BASE=/api
ARG APP_API_KEY=demo-public-key
RUN cd /home/appuser/app_src/frontend \
    && npm ci \
    && VITE_API_BASE="$VITE_API_BASE" VITE_API_KEY="$APP_API_KEY" npm run build \
    && mkdir -p /home/appuser/web \
    && cp -r dist/* /home/appuser/web/

# ---- install the backend; swap thin chroma client for the full server ------
RUN cd /home/appuser/app_src/backend \
    && pip install --no-cache-dir -e . \
    && pip uninstall -y chromadb-client \
    && pip install --no-cache-dir "chromadb>=0.5,<0.6" || pip install --no-cache-dir chromadb

# ---- runtime config files --------------------------------------------------
COPY nginx.conf /home/appuser/nginx.conf
COPY supervisord.conf /home/appuser/supervisord.conf

# ---- writable dirs + ownership --------------------------------------------
RUN mkdir -p /home/appuser/uploads /home/appuser/chroma \
    && chown -R appuser:appuser /home/appuser

# ---- initialise the Postgres cluster as appuser (baked into the image) -----
USER appuser
ENV PGDATA=/home/appuser/pgdata
RUN initdb -D "$PGDATA" -U compliance --auth-local=trust --auth-host=trust \
    && echo "listen_addresses='127.0.0.1'" >> "$PGDATA/postgresql.conf" \
    && echo "unix_socket_directories='/tmp'" >> "$PGDATA/postgresql.conf" \
    && echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf" \
    && pg_ctl -D "$PGDATA" -w start \
    && createdb -h /tmp -U compliance compliance \
    && pg_ctl -D "$PGDATA" -w stop

# ---- application environment (HF secrets can override NVIDIA_API_KEY etc.) --
ENV DATABASE_URL=postgresql+asyncpg://compliance:compliance@127.0.0.1:5432/compliance \
    SYNC_DATABASE_URL=postgresql+psycopg2://compliance:compliance@127.0.0.1:5432/compliance \
    REDIS_URL=redis://127.0.0.1:6379/0 \
    CHROMA_HOST=127.0.0.1 \
    CHROMA_PORT=8001 \
    LLM_PROVIDER=nvidia \
    API_KEY=demo-public-key \
    CORS_ORIGINS=* \
    UPLOAD_DIR=/home/appuser/uploads \
    PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["supervisord", "-c", "/home/appuser/supervisord.conf"]
