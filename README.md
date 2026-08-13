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
