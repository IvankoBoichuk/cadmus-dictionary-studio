.PHONY: help install api worker postgres-up redis-up db-upgrade db-revision db-current db-history db-downgrade test-integration compose-build compose-up compose-down compose-logs compose-reset test lint format-check type-check lock-check diff-check structure-check verify

UV ?= uv

help:
	@echo "Cadmus repository commands:"
	@echo "  make install       Install locked workspace dependencies"
	@echo "  make api           Run the FastAPI development server"
	@echo "  make worker        Run the Celery worker"
	@echo "  make postgres-up   Start PostgreSQL and wait for its health check"
	@echo "  make redis-up      Start Redis and wait for its health check"
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

api:
	$(UV) run --locked --package cadmus-api uvicorn cadmus_api.main:create_app --factory

worker:
	$(UV) run --locked --package cadmus-worker celery --app cadmus_worker.celery_app:celery_app worker --loglevel INFO

postgres-up:
	docker compose up -d --wait postgres

redis-up:
	docker compose up -d --wait redis

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
		docker compose --profile test rm --stop --force postgres-test; \
	}; \
	status=0; \
	trap cleanup EXIT HUP INT TERM; \
	docker compose --profile test run --rm integration-test || status=$$?; \
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

lint:
	$(UV) run --locked ruff check .

format-check:
	$(UV) run --locked ruff format --check .

type-check:
	$(UV) run --locked mypy apps/api/src apps/api/tests apps/worker/src apps/worker/tests packages/backend/src packages/backend/tests tests/integration

lock-check:
	$(UV) lock --check

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

verify: lock-check diff-check structure-check lint format-check type-check test
