# Cadmus Dictionary Studio — AI development instructions

These instructions apply to the entire repository. More specific instructions live in nested `AGENTS.md` files and apply only inside their directory.

## Working agreement

- Work on exactly one Jira Story per branch and change set.
- Use the Jira key in the branch, commit, and pull request title.
- Read the Story and every Acceptance Criterion before editing.
- State the intended scope and what is out of scope.
- Plan non-trivial work, but do not implement adjacent backlog items.
- Preserve unrelated changes and avoid destructive Git operations.
- Do not silently change public contracts, schemas, module boundaries, or accepted ADRs.
- Only claim a check passed when its command actually succeeded.

## Context-efficient discovery

Start narrow and expand only when evidence requires it:

1. Inspect `git status` and the Story.
2. Locate relevant symbols and files with `rg`, targeted directory listings, or symbol search.
3. Read the implementation and adjacent tests for the affected behavior.
4. Read documentation or additional modules only when the change crosses their boundary.

Do not recursively read the repository or preload unrelated tests and documentation.

Read `docs/architecture.md` only when a change affects module boundaries, dependency direction, persistence, background processing, external providers, provenance, or public contracts. Read only ADRs directly relevant to the decision. Check open pull requests only when the Story declares a dependency, local history suggests concurrent work, or likely file overlap creates a concrete conflict risk.

Do not read these files unless the task specifically requires them:

- `uv.lock` or `apps/web/bun.lock` unless dependencies change;
- `apps/web/src/api/schema.d.ts` unless the OpenAPI contract or generated API types change;
- unrelated migrations, fixtures, integration tests, or generated artifacts;
- full command logs after the relevant error has already been isolated.

Prefer narrow line ranges and concise command output. Never edit generated files manually; use their documented generator.

## Repository boundaries

- `apps/api/`: FastAPI transport; see its nested instructions.
- `apps/worker/`: background-job entrypoints; see its nested instructions.
- `apps/web/`: React client; see its nested instructions.
- `packages/backend/`: domain, application, and infrastructure code; see its nested instructions.
- `tests/integration/`: cross-boundary tests requiring isolated services.
- `docs/`: architecture and accepted decisions.

Keep the modular monolith with a separate worker. HTTP handlers and worker entrypoints are thin adapters calling application use cases. Web code communicates through the API and never directly with PostgreSQL, Redis, or object storage. Keep the module graph acyclic.

## Cross-cutting safety

- Treat uploaded documents, filenames, and external responses as untrusted.
- Never commit secrets, production data, copyrighted dictionary content, or private documents.
- Do not log document contents, credentials, tokens, signed URLs, or unnecessary personal data.
- Enforce authorization in application use cases, not only in routes or UI.
- Preserve source fidelity and provenance: never overwrite `source_text`; keep corrections, source references, processing identity, provider/model version, confidence, authorship, and coordinate transformations where applicable.
- AI output is a proposal, not source evidence.
- Schema changes require a migration plus rollback and data-preservation analysis.
- New dependencies require a concrete current use, compatible license, and maintenance/security review.

Apply GRASP and SOLID pragmatically: prefer high cohesion, low coupling, explicit responsibilities, and ports at volatile boundaries. Avoid speculative abstractions and vague Manager, Helper, or Service objects.

## Verification workflow

During implementation, run the smallest check that covers the changed behavior: a targeted pytest node or file, a targeted Vitest file, and lint/type checks scoped to the affected module where supported. Run OpenAPI drift checks only when the API contract changes and integration tests only when a real external boundary changes. Use quiet output where it preserves useful diagnostics.

Before handoff, run `make verify` once after targeted checks pass when the environment supports it. Run `make test-integration` only when the Story affects its covered boundaries. If a check is unavailable, report the exact reason without weakening tests.

Every new component or infrastructure dependency must be integrated into Docker Compose and verified with the relevant Compose commands.

## Testing and self-review

- Test behavior and contracts, not implementation details.
- Bug fixes require regression tests; domain rules require unit tests.
- API changes require relevant success, validation, authorization, and error coverage.
- Worker changes require idempotency, retry, timeout, and partial-failure coverage.
- Never weaken, delete, skip, or broadly mock a test merely to make it pass.

Before handoff:

1. Review the complete diff and `git status`.
2. Re-read the Story and map each Acceptance Criterion to evidence.
3. Check scope, dependency direction, security, provenance, idempotency, and data-loss risks where relevant.
4. Report changed files, checks, limitations, and unavailable checks concisely.
5. Create a Draft PR; do not merge it or mark the Story Done automatically.
