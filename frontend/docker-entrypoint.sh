#!/bin/sh
set -eu

# Defaults let the same image run under docker-compose (service name "api")
# or on a hosting platform that injects PORT and a public backend URL.
export API_UPSTREAM="${API_UPSTREAM:-http://api:8000}"
export PORT="${PORT:-80}"

# Substitute ONLY these two vars so nginx's own $uri/$host/etc. are preserved.
envsubst '${API_UPSTREAM} ${PORT}' \
    < /etc/nginx/templates/nginx.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "[frontend] serving on :${PORT}, proxying /api -> ${API_UPSTREAM}"
exec nginx -g 'daemon off;'
