# Cadmus Dictionary Studio

Cadmus is an information system for transforming scans and PDFs of printed
dictionaries into reviewed, structured lexicographic data while preserving
source provenance.

The project is currently in its architecture and repository-bootstrap phase.
Application code is introduced by separate Jira Stories.

## Repository structure

| Path | Purpose |
|---|---|
| apps/api | FastAPI HTTP entrypoint and transport adapters |
| apps/worker | background-job entrypoints |
| apps/web | React and TypeScript web client |
| packages/backend | shared domain and application modules for API and worker |
| infrastructure | local and deployment infrastructure |
| docs | architecture and Architecture Decision Records |
| fixtures | small, redistributable, non-sensitive test inputs |
| tests | cross-module integration and end-to-end tests |

The API and worker are separate processes built from one modular-monolith
backend. They are not independent microservices. See docs/architecture.md.

## Root commands

~~~bash
make help
make verify
~~~

make verify performs the checks available during the bootstrap phase. Backend,
frontend, worker, and quality-tooling Stories will extend the root commands
when their real toolchains are introduced.

## Development workflow

- read AGENTS.md before making changes;
- use one Jira Story per branch and pull request;
- include the Jira key in branch names, commits, and PR titles;
- never commit source dictionaries, private scans, secrets, local volumes, or
  generated artifacts.

## License

No open-source license has been selected yet. See LICENSE.md.

