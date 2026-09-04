# dicom-kb

An open-source DICOM-standard knowledge-base builder.


## Working guide

Read `docs/development.md` for the code map, invariants, and extension workflow.
Run `make install` and `make check`; use targeted tests while iterating. Official
cache integration checks are separate from the offline development suite.

- Keep public resolver, repository, and importer exports stable when reorganizing.
- Keep domain logic out of CLI/MCP adapters and preserve citation/edition contracts.
- Use shared CLI options and explicit invocation contexts rather than global state.
- Keep generated artifacts outside the repository and prefer synthetic fixtures.
- Public guides and API reference belong in `dicom-standard-kb-docs`, which pins
  its documented source state. Local docs serve agents and developers working in
  this checkout. Keep completed plans and progress logs in Git history, not new
  root-level tracking documents.
- Follow `docs/release_checklist.md` for distribution and release verification.

## Git Commit Policy

Every completed task must be tracked in a descriptive, granular git commit.
This requirement is critical and must be followed under all
circumstances - no exceptions.

**Rules:**

- Commit after every distinct logical unit of work, not at the end of a session.
- Each commit covers exactly one coherent change (one module, one component, one
  test suite, one docs section). Do not batch unrelated changes into a single
  commit.
- Commit messages must be informative: use `type(scope): subject` format,
  include a blank line, then a body describing *what* changed and *why*.
  - Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
  - Scope: the module, file, or subsystem affected, such as `backend`,
    `frontend`, `pixels`, `server`, `types`, or `tests`
  - Subject: imperative mood, 72 characters or fewer
  - Body: explain the design decision, the invariant being established, or the
    behavior being changed, not a restatement of the diff
- Stage files selectively (`git add <file>`) rather than `git add -A`. Only
  commit files that belong to the current logical unit.
- Never amend or force-push commits that have been logged here.

**Verification:** After each task, run `git log --oneline -3` to confirm the
commit was recorded before moving to the next task.
