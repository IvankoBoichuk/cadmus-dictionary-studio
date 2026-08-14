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

Remaining extension points are deliberately not placeholders:

- `BH-178` adds the React frontend service;
- `BH-181` adds MinIO, its named volume, health check, and bucket initialization.
