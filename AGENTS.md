# Cadmus Dictionary Studio — AI development instructions

These instructions apply to the entire repository. Read docs/architecture.md and the relevant ADRs in docs/decisions/ before planning architecture-sensitive changes.

## Project and working agreement

Cadmus transforms scans and PDFs of printed dictionaries into reviewed structured lexicographic data. Scientific traceability is a core requirement.

- Work on exactly one Jira Story per branch and change set.
- Use the Jira key in the branch, commit, and pull request title.
- Before editing, read the Story, Acceptance Criteria, relevant code, tests, architecture, and ADRs.
- State the intended scope and what is out of scope.
- Plan non-trivial work before coding.
- Do not implement adjacent backlog items “while here”.
- Do not silently change public contracts, module boundaries, schemas, or accepted ADRs.
- Preserve unrelated user changes and avoid destructive Git operations.

## Repository layout

Target layout:

~~~text
apps/
  api/          FastAPI HTTP transport
  worker/       background-job entrypoints
  web/          React + TypeScript client
packages/
  backend/
    src/cadmus/ domain and application modules
infrastructure/ deployment and local infrastructure
docs/           architecture and decisions
fixtures/       non-sensitive test inputs
tests/          cross-module and end-to-end tests
~~~

Backend modules are identity, projects, sources, processing, document, lexicography, review, exports, and quality. Ownership and dependency directions are defined in docs/architecture.md.

## Commands

Only claim a check passed when its command actually ran successfully.

Run development and verification commands from the repository root:

~~~bash
make install
make api
make worker
make web
make web-build
make web-test
make web-lint
make web-type-check
make redis-up
make minio-up
make test
make lint
make format-check
make type-check
make verify
docker compose config
docker compose build
docker compose up
docker compose down
~~~

The commands require Python 3.12, uv 0.12.x, and Bun 1.3.x. `make install`
synchronizes all Python workspace packages from `uv.lock` and frontend packages
from `apps/web/bun.lock`. `make api` starts the FastAPI application factory
locally; `make web` starts the Vite frontend. `make verify` checks both lockfiles,
whitespace, lint, repository structure, formatting, Python and TypeScript types,
backend and frontend tests, and the production frontend build. Docker Compose v2
is required for the Compose commands; `make minio-up` starts MinIO and its
idempotent bucket initializer, and the root `compose.yaml` is the standard local
runtime entrypoint.

Worker build, test, lint, and type-check commands beyond the shared backend
checks are not available yet. Stories introducing that toolchain must update
this section with exact commands that work from a clean checkout. Once a command
is documented here, keeping it executable is part of every subsequent change.

Every Story that adds a component or infrastructure dependency must integrate
it into Docker Compose and verify it with the standard Compose commands in the
same change set.

## Architecture rules

- Keep a modular monolith with a separate worker process.
- HTTP handlers and worker entrypoints are thin adapters calling application use cases.
- Domain code must not import FastAPI, Celery/RQ, SQLAlchemy, Redis, S3 SDKs, OCR SDKs, or React concerns.
- Infrastructure implements ports owned by the application/domain side.
- Web code communicates through the API, never directly with PostgreSQL, Redis, or object storage.
- Long work executes in a worker and returns a processing-run identifier.
- Jobs must be idempotent; retries with identical input and configuration must not duplicate domain results.
- Keep the module graph in docs/architecture.md acyclic.
- Store stable relationships relationally; JSONB is for variable provider output/configuration.

## GRASP and design guidance

Apply GRASP pragmatically:

- Information Expert: place behavior with the module or object owning the required information.
- Creator: let an aggregate or focused factory create objects it closely owns or composes.
- Controller: route external operations through application use cases; keep routes and jobs thin.
- Low Coupling: depend on contracts and ports, not concrete infrastructure.
- High Cohesion: give each function, class, and module one focused responsibility.
- Polymorphism: use contracts where behavior genuinely varies, especially OCR, storage, queues, and exports.
- Pure Fabrication: introduce repositories, mappers, adapters, or application services when this preserves domain cohesion.
- Indirection: isolate volatile external systems behind ports/adapters.
- Protected Variations: shield the domain from changes in OCR providers, queues, storage SDKs, databases, models, and export formats.

GRASP is guidance, not an abstraction quota. Apply SOLID where it improves the current design. Prefer simple explicit code over speculative patterns.

Do not:

- create vague Manager, Helper, or Service objects without a precise responsibility;
- add a one-implementation interface unless it protects a known volatile boundary or meaningful test seam;
- put domain decisions in routes, React components, ORM mappings, worker functions, or provider adapters;
- introduce a pattern solely to demonstrate it.

## Source fidelity and provenance

These are hard constraints:

- Never overwrite or implicitly normalize source_text.
- Store corrected content separately as normalized_text or a revision/annotation.
- Never drop page, geometry/token references, processing-run identity, provider/model version, confidence, or authorship required by provenance.
- Treat automatic extraction as a proposal until it reaches an allowed review status.
- AI/LLM/VLM output is not source evidence; link it to observable source tokens or mark it as a generated recommendation.
- Exports must use an explicit reviewed revision and never silently combine incompatible processing runs.
- Preserve coordinate transformations so results map back to the original scan.

## Security and data

- Treat uploaded documents and filenames as untrusted.
- Validate content-derived file type, size, checksum, and allowed format; never rely only on extensions.
- Do not process untrusted PDFs inside the API process.
- Enforce authorization in application use cases, not only in UI.
- Do not log document contents, credentials, tokens, signed URLs, secrets, or unnecessary personal data.
- Never commit secrets, production data, copyrighted dictionary content, or private documents as fixtures.
- Publication/export must respect the recorded legal status.
- New dependencies need a concrete use, compatible license, and security/maintenance check.

## Database and migrations

- Schema changes require a migration and rollback/data-preservation analysis.
- Never edit an already-applied shared migration.
- Destructive or lossy migrations require explicit approval and a backup or staged strategy.
- ORM models are persistence mappings; domain invariants belong in domain/application code.
- Make transaction boundaries explicit in application use cases.

## Testing expectations

- Test behavior and contracts, not implementation details.
- Bug fixes require regression tests; domain rules require unit tests.
- Adapters require contract/integration tests against realistic boundaries.
- API changes require authorization, validation, success, and error-path tests.
- Worker changes require idempotency, retry, timeout, and partial-failure tests.
- Provenance changes require proof that source_text and source references survive edits and reruns.
- Frontend changes require accessible interaction tests; critical flows require end-to-end coverage.
- Never weaken, delete, skip, or broadly mock a test merely to make it pass.

## Definition of Done

A Story is done only when:

- every Acceptance Criterion maps to code, a test, or documented manual verification;
- the implementation stays inside Story scope;
- relevant documented build, test, lint, format, and type-check commands pass, or unavailable checks are reported honestly;
- migrations, API/OpenAPI contracts, and docs are updated when applicable;
- new behavior has appropriate positive, negative, authorization, and failure coverage;
- the diff contains no secrets, generated artifacts, source documents, or unrelated files;
- the complete diff has been self-reviewed;
- known limitations and follow-up work are reported without being silently implemented.

## Required self-review

Before handoff:

1. Read the complete diff.
2. Re-read the Jira Story and every Acceptance Criterion.
3. Map each criterion to evidence.
4. Check module boundaries, dependency direction, GRASP/cohesion, security, idempotency, provenance, and data-loss risks.
5. Run every relevant documented command.
6. Check Git status for unrelated or generated files.
7. Report changed files, checks, Acceptance Criteria evidence, limitations, and unavailable checks.

Never mark a Jira Story Done or claim full completion while a criterion lacks evidence.
