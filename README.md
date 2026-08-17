# Cadmus Dictionary Studio

Cadmus is an information system for transforming scans and PDFs of printed
dictionaries into reviewed, structured lexicographic data while preserving
source provenance.

The repository contains a React / TypeScript / Vite web client, the FastAPI
backend scaffold, its PostgreSQL 17 / SQLAlchemy 2 / Alembic persistence
foundation, a Redis-backed Celery worker, and local S3-compatible object storage
backed by MinIO. The identity module supports email/password registration and
one-time email verification; local messages are captured by Mailpit.

## Repository structure

| Path | Purpose |
|---|---|
| apps/api | FastAPI HTTP entrypoint and transport adapters |
| apps/worker | background-job entrypoints |
| apps/web | React and TypeScript web client |
| packages/backend | shared domain and application modules for API and worker |
| infrastructure | local and deployment infrastructure |
| docs | architecture and Architecture Decision Records |
| fixtures | small, redistributable, non-sensitive test inputs |
| tests | cross-module integration and end-to-end tests |

The API and worker are separate processes built from one modular-monolith
backend. They are not independent microservices. See docs/architecture.md.

## Local environment with Docker Compose

Docker Compose is the standard way to run Cadmus locally. It starts PostgreSQL,
Redis, MinIO, and Mailpit, initializes the configured object-storage bucket,
applies all Alembic migrations, then starts the API, Celery worker, and
production-built web client after their dependencies are ready.

Prerequisites:

- Docker Engine or Docker Desktop with Docker Compose v2;
- Python 3.12, uv 0.12.x, and Bun 1.3.x for host-side development commands;
- port `8000` (or `CADMUS_API_PORT`) must be available for the API;
- port `5173` (or `CADMUS_WEB_PORT`) must be available for the frontend;
- port `6379` (or `CADMUS_REDIS_PORT`) must be available for host-side Redis
  access;
- PostgreSQL is published on `CADMUS_POSTGRES_PORT` (`5432` by default) for
  local tools such as DBeaver.
- ports `9000` and `9001` (or `CADMUS_MINIO_API_PORT` and
  `CADMUS_MINIO_CONSOLE_PORT`) must be available for the MinIO API and console.
- port `8025` (or `CADMUS_MAILPIT_UI_PORT`) must be available for the local
  email inbox.

The checked-in defaults are safe for local use and require no `.env` file. To
customize them, copy the example and edit the untracked file:

~~~bash
cp .env.example .env
~~~

Validate, build, and start the full environment from the repository root:

~~~bash
docker compose config
docker compose build
docker compose up --build
~~~

To start in the background and verify the API and frontend:

~~~bash
docker compose up --build -d
docker compose ps
curl --fail http://localhost:8000/health
curl --fail http://localhost:5173/
curl --fail http://localhost:5173/api/health
~~~

The `postgres`, `redis`, `minio`, `mailpit`, `api`, `worker`, and `web`
containers should report `healthy`; `migrate` and `object-storage-init` should
exit with status 0.
The frontend is served from its published port and proxies `/api/health` over
the internal Compose network. Both API health endpoints return JSON whose
`status` is `ok`. If a published port is changed, use its configured value in
the corresponding host URL.

Submit the deterministic infrastructure task and poll its result:

~~~bash
curl --fail --request POST http://localhost:8000/tasks/test \
  --header 'Content-Type: application/json' \
  --data '{"value":"hello"}'
curl --fail http://localhost:8000/tasks/test/<task_id>
~~~

The first call returns `202 Accepted` with a `task_id`; the polling endpoint
eventually returns `status: "succeeded"` and `result: {"echo": "hello"}`.
Worker logs contain structured JSON events with the task ID; task inputs and
results are excluded from info-level logs. View logs and stop the environment with:

~~~bash
docker compose logs --no-color
docker compose logs --follow
docker compose down
~~~

`docker compose down` preserves the `postgres-data`, `redis-data`, and
`minio-data` named volumes. The following command permanently deletes the local
PostgreSQL database, queued Redis data, and MinIO objects and must only be used
when all three can be discarded:

~~~bash
make compose-reset DESTRUCTIVE=1
~~~

This runs `docker compose down --volumes`. The explicit flag is a guard against
accidental data loss.

## Registration and local email

Open `http://localhost:5173/register` to create an account. New accounts use
the `pending_verification` status. Compose routes verification messages to
Mailpit; open `http://localhost:8025` and follow the one-time link in the latest
message. The link expires after 24 hours by default. Passwords are stored as
salted scrypt hashes and verification token plaintext is never persisted.

Start only the local inbox with `make mailpit-up`. Production deployments must
override the SMTP settings and public web URL; Mailpit is a development and test
dependency, not a production mail delivery service.

## Google sign-in (BH-188)

"Продовжити з Google" on `/login` is optional: the API only mounts the
`/auth/google/*` routes when `CADMUS_GOOGLE_OAUTH_CLIENT_ID`,
`CADMUS_GOOGLE_OAUTH_CLIENT_SECRET`, and `CADMUS_GOOGLE_OAUTH_REDIRECT_URL` are
all set, so `docker compose up` works out of the box without Google
credentials.

To enable it locally:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials),
   create an OAuth 2.0 Client ID of type "Web application".
2. Add `http://localhost:5173/api/auth/google/callback` as an authorized
   redirect URI (adjust the host/port if you override `CADMUS_WEB_PORT`). This
   is the browser-facing address — Compose's `web` nginx proxies `/api/*` to
   the `api` service, so Google must redirect here, not directly to the API
   container.
3. Copy `.env.example` to `.env` and set `CADMUS_GOOGLE_OAUTH_CLIENT_ID`,
   `CADMUS_GOOGLE_OAUTH_CLIENT_SECRET`, and `CADMUS_GOOGLE_OAUTH_REDIRECT_URL`
   from the client you just created.
4. Restart the API: `docker compose up -d api`.

A first-time Google sign-in creates an `active` account with no password (the
email is already verified by Google). If a password account with the same
verified email already exists, the Google identity is linked to it instead of
creating a duplicate.

## MinIO and S3-compatible object storage

The local S3 API is published at `http://localhost:9000`; the administration
console is at `http://localhost:9001`. Start MinIO alone and run the idempotent
bucket initializer with:

~~~bash
make minio-up
docker compose ps minio object-storage-init
~~~

Host-side API processes use `localhost:9000`. Compose injects the internal
endpoint `minio:9000`, so application code contains no MinIO URL. The API
composition root creates the `ObjectStorage` adapter from typed environment
settings; upload HTTP endpoints remain outside BH-181.

The checked-in access values are explicitly disposable local/test defaults,
not deployable credentials. Set unique secrets through the environment or an
untracked `.env` outside local development. Do not commit real access keys.
`object-storage-init` safely creates `CADMUS_OBJECT_STORAGE_BUCKET` only when it
does not already exist.

The Python client is the Apache-2.0 MinIO SDK and speaks the S3-compatible API.
The local MinIO server is AGPL-3.0 and built from the pinned upstream security
release `RELEASE.2025-10-15T17-29-55Z`; it is a local infrastructure process,
not linked into application code. The upstream community repository is archived,
so production adoption requires a fresh maintenance and licensing review.

Convenience targets mirror the common workflow:

~~~bash
make compose-build
make compose-up
make compose-logs
make compose-down
~~~

## PostgreSQL and migrations

The development database uses the pinned image `postgres:17.6-bookworm`.
Containers connect to the Compose service name `postgres`, while host tools
connect to `localhost:${CADMUS_POSTGRES_PORT:-5432}`. Start only PostgreSQL and
apply migrations:

~~~bash
docker compose up -d --wait postgres
docker compose run --rm migrate
~~~

For a fresh volume, `docker compose up -d` performs the same migration before
starting the API. A migration error exits nonzero and prevents the API from
starting. Standard Alembic workflows run without host-side Python:

~~~bash
# Create an autogenerated revision after adding models to application metadata.
docker compose run --rm migrate alembic revision --autogenerate -m "describe change"

# Inspect and move the schema revision.
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic history
docker compose run --rm migrate alembic downgrade -1
docker compose run --rm migrate
~~~

Equivalent convenience targets are `make postgres-up`, `make db-upgrade`,
`make db-revision MESSAGE="describe change"`, `make db-current`,
`make db-history`, and `make db-downgrade`.

The initial revision `bh179_0001` creates the PostgreSQL schema `cadmus`.
Revision `bh5_0002` adds `users` and `email_verification_tokens`; downgrading it
deletes identity records and therefore requires a backup outside disposable
environments. Alembic owns `public.alembic_version`; SQLAlchemy persistence
models register tables on `cadmus.infrastructure.database.metadata` and
therefore live in `cadmus`.

To run the backend on the host while PostgreSQL remains in Compose:

~~~bash
docker compose up -d --wait postgres
docker compose run --rm migrate
make api
~~~

`CADMUS_POSTGRES_PORT` selects the published port. Keep
`CADMUS_DATABASE_HOST=localhost` and set `CADMUS_DATABASE_PORT` to the same
value for the host process. Normal Compose services override the host to
`postgres` and port to `5432`.

## Redis and background worker

The worker uses Celery 5.6 with Redis as both broker and short-lived result
backend. API and worker share the `cadmus-backend` package, but Celery entrypoints
remain thin adapters. Redis 7.2 is deliberately selected from its maintained
BSD-3-Clause line; the Compose image is pinned to `redis:7.2.15-bookworm`.

Start only Redis, or run the worker on the host against published Redis:

~~~bash
make redis-up
make worker
~~~

Redis database 0 is the broker and database 1 stores task results for one hour.
Compose overrides `CADMUS_REDIS_HOST` to the internal service name `redis`.
If Redis becomes unavailable after startup, task submission and polling return
HTTP 503 with a stable `Task queue is unavailable` detail instead of leaking a
transport exception.

Run real migration, object-storage, registration, and SMTP contract tests
against isolated PostgreSQL, MinIO, and Mailpit services with ephemeral data:

~~~bash
make test-integration
~~~

These tests refuse to run unless the database name ends in `_test`. They check
database connectivity and reversible migrations, then upload, read, and delete
a redistributable fixture through the application-owned storage contract. The
target always removes its isolated PostgreSQL, MinIO, and Mailpit services, including on
failure or interruption.

Every future Story that introduces a Cadmus component or infrastructure
dependency must integrate it into Docker Compose and verify it through the
standard Compose commands in the same change set. The current foundation was
added by `BH-178` (React frontend), `BH-179` (PostgreSQL and Alembic), `BH-180`
(Redis and worker), and `BH-181` (MinIO). See `infrastructure/README.md` for the
extension rules.

## Dictionary drafts: PDF upload and metadata (BH-26 / BH-27)

`POST /dictionaries/upload` accepts one PDF, validates it, stores the
original unchanged in object storage, and creates a `draft` dictionary. Only
cheap checks (extension, declared content-type, the `%PDF-` signature bytes,
a streamed size cap, and a streamed SHA-256 checksum) run inside the API
process; structural PDF parsing (page count) is never done there and instead
happens asynchronously in the worker, so the response's
`source.inspection_status` starts as `pending` and later becomes `verified`
(with `page_count`) or `failed`. Poll `GET /dictionaries/{id}` to observe
that transition.

The maximum upload size is `CADMUS_MAX_UPLOAD_SIZE_BYTES` (bytes, default
100 MiB). In Compose, the `web` container's nginx also enforces
`client_max_body_size`, configured separately via `CADMUS_MAX_UPLOAD_SIZE_MB`
(MiB, default `100`) since it fronts `/api` and would otherwise reject large
uploads with `413` before the API ever sees them — keep the two in sync when
changing the limit. A second upload with the same SHA-256 checksum among the
caller's own dictionaries is rejected as a duplicate (`409`) rather than
silently creating a copy; a different owner uploading identical content is
not considered a duplicate.

`PATCH /dictionaries/{id}` saves bibliographic, language, and legal
metadata for an existing draft without touching its stored PDF — required
fields (title, at least one language, legal status) may be left empty; the
response's `missing_required_fields` lists what is still absent. Legal
status is one of `public_domain`, `licensed`, `permission_granted`,
`restricted`, or `unknown`; `licensed` requires `license_type` and
`permission_granted` requires `permission_reference`. Publication year must
be between 1450 and next year; ISBN-10/13 checksums are validated after
stripping hyphens/spaces.

`draft` is the only status this pair of Stories ever sets. The transition to
`configured` (readiness for pipeline processing) belongs to BH-31 and is not
implemented here.

## Root commands

~~~bash
make install
make api
make worker
make web
make web-build
make web-test
make web-lint
make web-type-check
make test
make lint
make format-check
make type-check
make verify
~~~

Python 3.12, uv 0.12.x, and Bun 1.3.x are required. `make install` creates the
locked Python and frontend environments. `make api` starts the API on
`http://127.0.0.1:8000`; OpenAPI is available at `/openapi.json`, Swagger UI at
`/docs`, and liveness at `/health`. `make web` starts Vite on
`http://localhost:5173` and proxies `/api` to the local API.

The API reads its metadata from environment variables. All are optional and
have safe local defaults:

| Variable | Default | Purpose |
|---|---|---|
| `CADMUS_API_PORT` | `8000` | API port published to the local host |
| `CADMUS_WEB_PORT` | `5173` | production frontend port published to the local host |
| `CADMUS_NAME` | `cadmus-api` | service name and OpenAPI title |
| `CADMUS_ENVIRONMENT` | `development` | deployment environment |
| `CADMUS_VERSION` | `0.1.0` | service and OpenAPI version |
| `CADMUS_PUBLIC_WEB_URL` | `http://localhost:5173` | origin used to build verification links |
| `CADMUS_VERIFICATION_TOKEN_LIFETIME_HOURS` | `24` | verification link lifetime, from 1 to 168 hours |
| `CADMUS_SMTP_HOST` | `localhost` | SMTP host; Compose injects `mailpit` |
| `CADMUS_SMTP_PORT` | `1025` | SMTP port |
| `CADMUS_SMTP_USE_TLS` | `false` | enable SMTP STARTTLS |
| `CADMUS_EMAIL_FROM` | `Cadmus <noreply@cadmus.local>` | verification message sender |
| `CADMUS_MAILPIT_UI_PORT` | `8025` | local Mailpit inbox port |
| `CADMUS_GOOGLE_OAUTH_CLIENT_ID` | unset | Google OAuth 2.0 client ID; leave unset to disable Google sign-in |
| `CADMUS_GOOGLE_OAUTH_CLIENT_SECRET` | unset | Google OAuth 2.0 client secret |
| `CADMUS_GOOGLE_OAUTH_REDIRECT_URL` | unset | browser-facing callback URL registered with Google, e.g. `http://localhost:5173/api/auth/google/callback` |
| `CADMUS_DATABASE_NAME` | `cadmus` | PostgreSQL database name |
| `CADMUS_DATABASE_USER` | `cadmus` | PostgreSQL user |
| `CADMUS_DATABASE_PASSWORD` | `cadmus-local` | local-only password; override outside local development |
| `CADMUS_DATABASE_HOST` | `localhost` | host processes use this; Compose injects `postgres` |
| `CADMUS_DATABASE_PORT` | `5432` | PostgreSQL port seen by the current process |
| `CADMUS_DATABASE_URL` | unset | optional complete SQLAlchemy URL overriding the fields above |
| `CADMUS_POSTGRES_PORT` | `5432` | PostgreSQL port published to the local host |
| `CADMUS_REDIS_HOST` | `localhost` | host processes use this; Compose injects `redis` |
| `CADMUS_REDIS_PORT` | `6379` | Redis port seen by the process and published locally |
| `CADMUS_REDIS_BROKER_DATABASE` | `0` | Redis database used by the Celery broker |
| `CADMUS_REDIS_RESULT_DATABASE` | `1` | Redis database used for Celery task results |
| `CADMUS_REDIS_BROKER_URL` | unset | optional complete broker URL override |
| `CADMUS_REDIS_RESULT_BACKEND_URL` | unset | optional complete result backend URL override |
| `CADMUS_OBJECT_STORAGE_ENDPOINT` | `localhost:9000` | S3-compatible endpoint without a URL scheme; Compose injects `minio:9000` |
| `CADMUS_OBJECT_STORAGE_ACCESS_KEY` | local-only value | S3 access key; override outside local development |
| `CADMUS_OBJECT_STORAGE_SECRET_KEY` | local-only value | S3 secret key; override outside local development |
| `CADMUS_OBJECT_STORAGE_BUCKET` | `cadmus` | bucket initialized and used by the adapter |
| `CADMUS_OBJECT_STORAGE_SECURE` | `false` | enable TLS for the S3 connection |
| `CADMUS_MINIO_API_PORT` | `9000` | MinIO S3 API port published to the host |
| `CADMUS_MINIO_CONSOLE_PORT` | `9001` | MinIO console port published to the host |
| `CADMUS_MAX_UPLOAD_SIZE_BYTES` | `104857600` (100 MiB) | maximum accepted dictionary PDF upload size, in bytes |
| `CADMUS_MAX_UPLOAD_SIZE_MB` | `100` | nginx `client_max_body_size` for the `web` container; keep in sync with `CADMUS_MAX_UPLOAD_SIZE_BYTES` |

The application constructs the effective SQLAlchemy URL in one typed settings
method. Password fields and the full URL are secret-valued and must not be
logged. `.env` remains ignored; `.env.example` contains local-only defaults,
not production credentials.

`make verify` checks lock consistency, whitespace, repository structure, lint,
formatting, Python and TypeScript types, backend and frontend unit tests, and the
production frontend build. It also rejects drift between FastAPI's OpenAPI
contract and the generated frontend API types. It does not require PostgreSQL,
Redis, object storage, SMTP, or Docker; PostgreSQL, MinIO, and Mailpit contract
tests run separately with `make test-integration`.

## Development workflow

- read AGENTS.md before making changes;
- use one Jira Story per branch and pull request;
- include the Jira key in branch names, commits, and PR titles;
- never commit source dictionaries, private scans, secrets, local volumes, or
  generated artifacts.

## License

No open-source license has been selected yet. See LICENSE.md.
