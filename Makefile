.PHONY: help install api worker web web-build web-test web-lint web-type-check postgres-up redis-up minio-up mailpit-up db-upgrade db-revision db-current db-history db-downgrade test-integration compose-build compose-up compose-down compose-logs compose-reset test lint format-check type-check lock-check diff-check structure-check verify

UV ?= uv

help:
	@echo "Cadmus repository commands:"
	@echo "  make install       Install locked workspace dependencies"
	@echo "  make api           Run the FastAPI development server"
	@echo "  make worker        Run the Celery worker"
	@echo "  make web           Run the Vite frontend development server"
	@echo "  make web-build     Build the production frontend"
	@echo "  make web-test      Run frontend tests"
	@echo "  make web-lint      Run frontend lint checks"
	@echo "  make web-type-check  Run the frontend TypeScript check"
	@echo "  make postgres-up   Start PostgreSQL and wait for its health check"
	@echo "  make redis-up      Start Redis and wait for its health check"
	@echo "  make minio-up      Start MinIO and initialize its bucket"
	@echo "  make mailpit-up    Start the local email inbox"
	@echo "  make db-upgrade    Apply all migrations through Compose"
	@echo "  make db-revision MESSAGE='...'  Create an Alembic revision"
	@echo "  make db-current    Show the current database revision"
	@echo "  make db-history    Show migration history"
	@echo "  make db-downgrade  Revert one revision"
	@echo "  make test-integration  Run isolated PostgreSQL integration tests"
	@echo "  make compose-build Build the local Compose services"
	@echo "  make compose-up    Build and start the local environment"
	@echo "  make compose-down  Stop the local environment"
	@echo "  make compose-logs  Follow local environment logs"
	@echo "  make compose-reset DESTRUCTIVE=1  Delete the local database volume"
	@echo "  make test          Run backend tests"
	@echo "  make lint          Run Ruff lint checks"
	@echo "  make format-check  Check Python formatting"
	@echo "  make type-check    Run mypy"
	@echo "  make verify        Run all repository checks"

install:
	$(UV) sync --all-packages --locked
	cd apps/web && bun install --frozen-lockfile

api:
	$(UV) run --locked --package cadmus-api uvicorn cadmus_api.main:create_app --factory

worker:
	$(UV) run --locked --package cadmus-worker celery --app cadmus_worker.celery_app:celery_app worker --loglevel INFO

web:
	cd apps/web && bun run dev

web-build:
	cd apps/web && bun run build

web-test:
	cd apps/web && bun run test

web-lint:
	cd apps/web && bun run lint

web-type-check:
	cd apps/web && bun run type-check

postgres-up:
	docker compose up -d --wait postgres

redis-up:
	docker compose up -d --wait redis

minio-up:
	docker compose up -d --wait minio object-storage-init

mailpit-up:
	docker compose up -d --wait mailpit

db-upgrade:
	docker compose run --rm migrate

db-revision:
	test -n "$(MESSAGE)"
	docker compose run --rm migrate alembic revision --autogenerate -m "$(MESSAGE)"

db-current:
	docker compose run --rm migrate alembic current

db-history:
	docker compose run --rm migrate alembic history

db-downgrade:
	docker compose run --rm migrate alembic downgrade -1

test-integration:
	@cleanup() { \
		docker compose --profile test rm --stop --force \
			postgres-test minio-test object-storage-test-init mailpit-test; \
	}; \
	status=0; \
	trap cleanup EXIT HUP INT TERM; \
	docker compose --profile test run --build --rm integration-test || status=$$?; \
	exit $$status

compose-build:
	docker compose build

compose-up:
	docker compose up --build

compose-down:
	docker compose down

compose-logs:
	docker compose logs --follow

compose-reset:
	test "$(DESTRUCTIVE)" = "1"
	docker compose down --volumes

test:
	$(UV) run --locked pytest
	cd apps/web && bun run test

lint:
	$(UV) run --locked ruff check .
	cd apps/web && bun run lint

format-check:
	$(UV) run --locked ruff format --check .

type-check:
	$(UV) run --locked mypy apps/api/src apps/api/tests apps/worker/src apps/worker/tests packages/backend/src packages/backend/tests tests/integration
	cd apps/web && bun run type-check

lock-check:
	$(UV) lock --check
	cd apps/web && bun install --frozen-lockfile --lockfile-only

diff-check:
	git diff --check

structure-check:
	test -s README.md
	test -s AGENTS.md
	test -s LICENSE.md
	test -s .gitignore
	test -s .dockerignore
	test -s .env.example
	test -s compose.yaml
	test -s docs/architecture.md
	test -s docs/decisions/0001-modular-monolith-with-worker.md
	test -s docs/decisions/0002-postgresql-and-object-storage.md
	test -s docs/decisions/0003-provider-neutral-processing-pipeline.md
	test -s docs/decisions/0004-provenance-first-data-model.md
	test -s docs/decisions/0005-cadmus-database-schema-and-migrations.md
	test -d apps/api
	test -d apps/worker
	test -d apps/web
	test -d packages/backend/src/cadmus
	test -d infrastructure
	test -d fixtures
	test -d tests

verify: lock-check diff-check structure-check lint format-check type-check test web-build
