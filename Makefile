.PHONY: help install api compose-build compose-up compose-down compose-logs test lint format-check type-check lock-check diff-check structure-check verify

UV ?= uv

help:
	@echo "Cadmus repository commands:"
	@echo "  make install       Install locked workspace dependencies"
	@echo "  make api           Run the FastAPI development server"
	@echo "  make compose-build Build the local Compose services"
	@echo "  make compose-up    Build and start the local environment"
	@echo "  make compose-down  Stop the local environment"
	@echo "  make compose-logs  Follow local environment logs"
	@echo "  make test          Run backend tests"
	@echo "  make lint          Run Ruff lint checks"
	@echo "  make format-check  Check Python formatting"
	@echo "  make type-check    Run mypy"
	@echo "  make verify        Run all repository checks"

install:
	$(UV) sync --all-packages --locked

api:
	$(UV) run --locked --package cadmus-api uvicorn cadmus_api.main:create_app --factory

compose-build:
	docker compose build

compose-up:
	docker compose up --build

compose-down:
	docker compose down

compose-logs:
	docker compose logs --follow

test:
	$(UV) run --locked pytest

lint:
	$(UV) run --locked ruff check .

format-check:
	$(UV) run --locked ruff format --check .

type-check:
	$(UV) run --locked mypy apps/api/src apps/api/tests packages/backend/src packages/backend/tests

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
	test -d apps/api
	test -d apps/worker
	test -d apps/web
	test -d packages/backend/src/cadmus
	test -d infrastructure
	test -d fixtures
	test -d tests

verify: lock-check diff-check structure-check lint format-check type-check test
