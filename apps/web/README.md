# Web application

React 19, TypeScript, and Vite client for Cadmus Dictionary Studio. It contains
the application shell and the BH-5 registration and email-verification screens.
Login, OCR overlays, review, and other business screens remain outside BH-5.

## Local development

Bun 1.3.x is required. From the repository root:

~~~bash
make install
make api
make web
~~~

The frontend is available at `http://localhost:5173`; registration is at
`/register`. Vite sends same-origin
requests under `/api` to `http://127.0.0.1:8000` by default. Override the host
development proxy when necessary:

~~~bash
CADMUS_API_PROXY_TARGET=http://127.0.0.1:9000 make web
~~~

The browser-facing base path defaults to `/api`. A build for a different
deployment can set `VITE_API_BASE_URL`; this value is public and must never
contain credentials or secrets.

## Frontend checks

Run the exact frontend commands from the repository root:

~~~bash
make web-build
make web-test
make web-lint
make web-type-check
~~~

`make verify` includes all four checks along with the repository's backend
verification.

## Docker Compose

`docker compose up --build` builds static production assets with Bun, serves
them from the `web` Nginx container, and publishes
`http://localhost:${CADMUS_WEB_PORT:-5173}`. The application calls `/api/health`;
Nginx proxies it through the internal Compose network to `api:8000`. Override
only the host port in `.env`; the internal API service name is intentionally
fixed by the Compose configuration.
