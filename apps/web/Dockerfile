FROM oven/bun:1.3.14-alpine AS build

WORKDIR /app

COPY apps/web/package.json apps/web/bun.lock ./
RUN bun install --frozen-lockfile

COPY apps/web/ ./

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN bun run build

FROM nginx:1.29.4-alpine AS runtime

ENV CADMUS_API_UPSTREAM=api:8000 \
    CADMUS_MAX_UPLOAD_SIZE_MB=100 \
    NGINX_ENVSUBST_FILTER=CADMUS_

COPY apps/web/nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
