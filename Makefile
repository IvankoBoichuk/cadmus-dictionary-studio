.PHONY: help verify

help:
	@echo "Cadmus repository commands:"
	@echo "  make verify  Validate bootstrap structure and tracked documentation"

verify:
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then git diff --check; fi
	@test -s README.md
	@test -s AGENTS.md
	@test -s LICENSE.md
	@test -s .gitignore
	@test -s docs/architecture.md
	@test -s docs/decisions/0001-modular-monolith-with-worker.md
	@test -s docs/decisions/0002-postgresql-and-object-storage.md
	@test -s docs/decisions/0003-provider-neutral-processing-pipeline.md
	@test -s docs/decisions/0004-provenance-first-data-model.md
	@test -d apps/api
	@test -d apps/worker
	@test -d apps/web
	@test -d packages/backend/src/cadmus
	@test -d infrastructure
	@test -d fixtures
	@test -d tests
	@echo "Bootstrap verification passed."
