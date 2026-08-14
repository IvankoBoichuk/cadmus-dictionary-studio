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

Remaining extension points are deliberately not placeholders:

- `BH-178` adds the React frontend service;
- `BH-180` adds Redis and the background worker, including readiness ordering;
- `BH-181` adds MinIO, its named volume, health check, and bucket initialization.
