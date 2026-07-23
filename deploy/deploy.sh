#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build + launch the full stack (api, worker, postgres, redis, chromadb,
# frontend) in production mode and seed the demo data.
#
# Run from the repo root:  ./deploy/deploy.sh
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
# Set TUNNEL=1 to also start a free Cloudflare Quick Tunnel (public HTTPS URL,
# no domain / no open ports needed).  e.g.  TUNNEL=1 ./deploy/deploy.sh
if [ "${TUNNEL:-0}" = "1" ]; then
    COMPOSE="$COMPOSE -f docker-compose.tunnel.yml"
fi
# Set DUCKDNS=1 (with DUCKDNS_SUBDOMAIN + DUCKDNS_TOKEN in .env) for a free,
# stable hostname that survives EC2 Stop/Start without a paid Elastic IP.
if [ "${DUCKDNS:-0}" = "1" ]; then
    COMPOSE="$COMPOSE -f docker-compose.duckdns.yml"
fi

# --- 1. Ensure .env exists ------------------------------------------------
if [ ! -f .env ]; then
    echo "==> No .env found; creating from .env.example"
    cp .env.example .env
    echo "!!  Edit .env now and set NVIDIA_API_KEY, a strong API_KEY, and"
    echo "!!  CORS_ORIGINS, then re-run this script."
    exit 1
fi

# --- 2. Sanity-check critical secrets -------------------------------------
# Read values WITHOUT sourcing (a docker-style .env may contain unquoted spaces,
# e.g. SEC_EDGAR_USER_AGENT, which bash `source` would choke on).
get_env() { grep -E "^$1=" .env | head -n1 | cut -d= -f2-; }
NVIDIA_API_KEY="$(get_env NVIDIA_API_KEY || true)"
API_KEY="$(get_env API_KEY || true)"
missing=0
case "${NVIDIA_API_KEY}" in
    ""|"nvapi-your-new-key-here"|"nvapi-xxxxxxxx")
        echo "!!  NVIDIA_API_KEY is unset or still the placeholder in .env"; missing=1 ;;
esac
case "${API_KEY}" in
    ""|"change-me"|"change-me-strong-api-key")
        echo "!!  API_KEY is unset or still the placeholder — set a long random value."; missing=1 ;;
esac
if [ "$missing" -ne 0 ]; then
    echo "Aborting: fix the above in .env and re-run."
    exit 1
fi

# --- 3. Build + start ------------------------------------------------------
echo "==> Building and starting the stack (this pulls images + builds on first run)"
$COMPOSE up -d --build

# --- 4. Wait for the API to become healthy --------------------------------
echo "==> Waiting for the API to come up (migrations run on api startup)..."
for i in $(seq 1 60); do
    if $COMPOSE exec -T api python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health'); " >/dev/null 2>&1; then
        echo "    API is healthy."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "!!  API did not become healthy in time. Check: $COMPOSE logs api"
        exit 1
    fi
    sleep 3
done

# --- 5. Seed rules + demo company -----------------------------------------
echo "==> Seeding compliance rules + demo company"
$COMPOSE exec -T api python scripts/seed.py

# --- 6. Report -------------------------------------------------------------
PUBLIC_IP="$(curl -fsSL https://api.ipify.org 2>/dev/null || echo '<vm-public-ip>')"
echo ""
echo "=========================================================================="
echo " Deployment complete. All features are running:"
echo "   api, worker (Celery), postgres, redis, chromadb, frontend (Nginx)"
echo ""
echo "   Dashboard:  http://${PUBLIC_IP}/"
echo "   API docs :  ssh -L 8000:localhost:8000 <user>@${PUBLIC_IP}  ->  http://localhost:8000/docs"
echo ""
echo " Manage:  $COMPOSE ps   |   logs:  $COMPOSE logs -f api worker"
echo "=========================================================================="

# --- 7. If a Cloudflare Quick Tunnel was requested, surface its public URL ---
if [ "${TUNNEL:-0}" = "1" ]; then
    echo "==> Waiting for the Cloudflare tunnel URL..."
    url=""
    for i in $(seq 1 20); do
        url="$($COMPOSE logs cloudflared 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -n1 || true)"
        [ -n "$url" ] && break
        sleep 2
    done
    if [ -n "$url" ]; then
        echo "   Public HTTPS dashboard:  $url"
    else
        echo "   Tunnel URL not found yet — check:  $COMPOSE logs cloudflared"
    fi
    echo "=========================================================================="
fi
