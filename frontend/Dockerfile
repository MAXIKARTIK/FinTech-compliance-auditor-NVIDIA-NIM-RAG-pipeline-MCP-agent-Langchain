# ---------- build stage ----------
FROM node:20-alpine AS build
WORKDIR /app

# Install deps first for better layer caching.
COPY package.json package-lock.json ./
RUN npm ci

# Build-time config. Vite inlines VITE_* vars into the static bundle, so these
# are baked at build time (pass --build-arg to override).
ARG VITE_API_BASE=/api
ARG VITE_API_KEY=change-me
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_API_KEY=$VITE_API_KEY

COPY . .
RUN npm run build

# ---------- serve stage ----------
FROM nginx:1.27-alpine AS serve

# envsubst (gettext) is used by the entrypoint to render the nginx template.
RUN apk add --no-cache gettext

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
