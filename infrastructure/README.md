# Infrastructure

Local and deployment infrastructure belongs here. The root `compose.yaml` is
the standard local entrypoint. Never commit secrets or persistent local volume
data.

Every Story that introduces a Cadmus component or infrastructure dependency
must add it to Docker Compose and verify it through the standard Compose
commands in the same change set. Extend the existing `cadmus` network and add
health-based dependency ordering where one service requires another. Stateful
services own clearly named persistent volumes; stateless services do not.

Implemented stateful infrastructure:

- `BH-179` adds pinned PostgreSQL, the `postgres-data` named volume, health
  ordering, a configurable local host port, Alembic execution, and an isolated
  test profile.
- `BH-180` adds pinned Redis 7.2 from its BSD-3-Clause release line, the
  `redis-data` named volume, a health check, and readiness ordering for the API
  and Celery worker.
- `BH-181` builds the pinned MinIO security release from source, adds the
  `minio-data` named volume and health check, and initializes the configured
  bucket before the API starts. The server is AGPL-3.0 and its archived
  upstream requires a new maintenance/licensing review before production use.

Implemented stateless services:

- `BH-178` builds the React frontend with Bun, serves its production assets
  through Nginx, publishes the configurable host port, and proxies same-origin
  `/api` requests to the Compose API service.

Future extension points are added only by their owning Stories; there are no
placeholder services in the Compose file.
