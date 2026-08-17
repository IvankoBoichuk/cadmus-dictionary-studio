# Compact AI prompt for a Jira Story

Use this prompt after the Story contains an unambiguous description and Acceptance Criteria.

~~~text
Implement Jira Story [JIRA_KEY] in cadmus-dictionary-studio.

Follow the applicable AGENTS.md instructions.

Work only within the Acceptance Criteria. Start with the Story, targeted symbol
search, relevant implementation files, and adjacent tests. Do not perform a full
repository review. Read architecture documentation or ADRs only when the change
affects their boundary.

Run targeted checks while implementing. Run make verify once before handoff when
the environment supports it. Create agent/[JIRA_KEY]-<short-description>, commit
the scoped changes, push it, and open a Draft PR.

Report the PR, changed files, checks, Acceptance Criteria evidence, and actual
limitations concisely. Do not merge the PR or mark the Story Done.
~~~

Add task-specific constraints only when they are absent from the Story or repository instructions. Do not paste the repository rules into every prompt.
