# Backend package instructions

These rules apply under `packages/backend/` in addition to the repository instructions.

## Boundaries and design

- Domain code must not import FastAPI, Celery, SQLAlchemy, Redis, S3/OCR SDKs, or React concerns.
- Application use cases are controllers for external operations and own authorization and transaction boundaries.
- Infrastructure implements ports owned by the application/domain side.
- Place behavior with the information expert; use focused factories where creation belongs to an aggregate.
- Use contracts for genuine variation or a meaningful test seam, especially storage, queues, OCR, and exports.
- Do not add one-implementation interfaces or vague Manager, Helper, or Service objects without a precise responsibility.

## Data and provenance

- ORM models are persistence mappings; invariants belong in domain/application code.
- Never overwrite or implicitly normalize `source_text`.
- Store corrections separately and preserve source references, geometry, processing identity, confidence, authorship, and provider/model version.
- Exports use an explicit reviewed revision and never silently combine incompatible processing runs.
- Schema changes require a new migration and rollback/data-preservation analysis; never edit an applied shared migration.

## Targeted verification

Read the affected module and adjacent tests, not the entire backend suite. Prefer:

~~~bash
uv run --locked pytest packages/backend/tests/path_to_test.py -q
uv run --locked ruff check packages/backend/src/cadmus/affected_module packages/backend/tests/path_to_test.py
uv run --locked mypy packages/backend/src/cadmus/affected_module
~~~

Use integration tests only for behavior that crosses a real persistence, queue, storage, SMTP, or external-provider boundary.
