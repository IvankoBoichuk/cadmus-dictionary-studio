# Cadmus Dictionary Studio

Cadmus is an information system for transforming scans and PDFs of printed
dictionaries into reviewed, structured lexicographic data while preserving
source provenance.

The repository contains the initial FastAPI backend scaffold. Domain features,
the worker, persistence, and the web client are introduced by separate Jira
Stories.

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

Docker Compose is the standard way to run Cadmus locally. At this stage it
builds and starts the implemented FastAPI `api` service. PostgreSQL, Redis,
the worker, MinIO, and the frontend are not placeholders in this baseline;
their owning Stories add them when their implementations exist.

Prerequisites:

- Docker Engine or Docker Desktop with Docker Compose v2;
- ports used by the configured services must be available (`8000` by default
  for the API).

The checked-in defaults are safe for local use and require no `.env` file. To
customize them, copy the example and edit the untracked file:

~~~bash
cp .env.example .env
~~~

Validate, build, and start the environment from the repository root:

~~~bash
docker compose config
docker compose build
docker compose up
~~~

To start in the background and verify the API:

~~~bash
docker compose up --build -d
docker compose ps
curl --fail http://localhost:8000/health
~~~

The API container should report `healthy`, and the health endpoint returns a
JSON response whose `status` is `ok`. If `CADMUS_API_PORT` is changed, use that
port in the URL. View logs and stop the environment with:

~~~bash
docker compose logs --no-color
docker compose logs --follow
docker compose down
~~~

The current baseline has no persistent volumes, so no volume cleanup is
necessary. Future stateful services must document their named volumes and the
explicit, destructive cleanup command when they are introduced.

Convenience targets mirror the common workflow:

~~~bash
make compose-build
make compose-up
make compose-logs
make compose-down
~~~

Every future Story that introduces a Cadmus component or infrastructure
dependency must integrate it into Docker Compose and verify it through the
standard Compose commands in the same change set. Specifically, `BH-178` adds
the React frontend, `BH-179` adds PostgreSQL and Alembic migration execution,
`BH-180` adds Redis and the background worker, and `BH-181` adds MinIO and its
S3-compatible configuration. See `infrastructure/README.md` for the extension
rules.

## Root commands

~~~bash
make install
make api
make test
make lint
make format-check
make type-check
make verify
~~~

Python 3.12 and uv 0.12.x are required. `make install` creates the locked local
environment. `make api` starts the API on `http://127.0.0.1:8000`; OpenAPI is
available at `/openapi.json`, Swagger UI at `/docs`, and liveness at `/health`.

The API reads its metadata from environment variables. All are optional and
have safe local defaults:

| Variable | Default | Purpose |
|---|---|---|
| `CADMUS_NAME` | `cadmus-api` | service name and OpenAPI title |
| `CADMUS_ENVIRONMENT` | `development` | deployment environment |
| `CADMUS_VERSION` | `0.1.0` | service and OpenAPI version |

`make verify` checks lock consistency, whitespace, repository structure, lint,
formatting, types, and backend tests. It does not require PostgreSQL, Redis,
object storage, or Docker.

## Development workflow

- read AGENTS.md before making changes;
- use one Jira Story per branch and pull request;
- include the Jira key in branch names, commits, and PR titles;
- never commit source dictionaries, private scans, secrets, local volumes, or
  generated artifacts.

## License

No open-source license has been selected yet. See LICENSE.md.
