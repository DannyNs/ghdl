# GHDL lifecycle

## Intake

Write a one-sentence goal and identify:
- in-scope and out-of-scope work
- acceptance criteria that can be checked
- constraints and assumptions
- risk level: low / medium / high
- operations requiring human approval

Ask only for missing information that materially changes safety, behavior, architecture, or scope. Otherwise record a reversible assumption.

## Discover

Inspect:
- `AGENTS.md`, README, contributor guides, and any nested instruction files
- relevant source code, tests, build manifests, and configuration
- `git status --short` and the existing diff
- available verification commands

Record relevant paths, conventions, existing user changes, and unknowns. Do not overwrite existing changes.

## Plan

Create a small directed acyclic graph. Use node types such as `inspect`, `design`, `implement`, `verify`, `review`, and `human_gate`.

Every node defines:
- stable `id`
- observable `goal`
- `depends_on`
- `inputs` and `outputs`
- `done_when`
- `owner`
- `failure_policy`

Do not over-fragment trivial work. Parallel work is appropriate only when dependencies and file ownership are clear and the runtime supports safe parallel execution.

## Implement

Execute only nodes whose dependencies are complete. Keep edits focused and inspect diffs after meaningful changes.

If new facts invalidate the graph:
1. stop affected downstream work;
2. explain the invalidated assumption/dependency;
3. revise the task contract and graph;
4. request approval if scope, risk, or acceptance criteria change;
5. resume from the earliest invalidated node.

## Verify

Prefer deterministic evidence in this order:
1. focused tests for changed behavior;
2. relevant broader tests;
3. build, type-check, lint, or static analysis;
4. diff review against acceptance criteria.

Record each check as:
- `PASS`: ran and met its predicate
- `FAIL`: ran and did not meet its predicate
- `BLOCKED`: could not run, with reason
- `N/A`: irrelevant, with reason

Retry policy: initial attempt plus at most two repair attempts for a failing node. If still failing, stop and report the evidence. Never silently weaken a test or completion predicate.

## Review

Inspect:
- scope creep and unrelated file changes
- accidental secrets or private data
- error handling and compatibility
- migrations and rollback where relevant
- whether tests prove acceptance criteria
- whether every reported claim is supported by actual evidence

Require human review before consequential actions such as production deployment, destructive data operations, permission changes, or externally visible side effects.

## Report

- `DONE`: all required acceptance criteria have evidence of success
- `PARTIAL`: useful work is done, but at least one criterion is unmet or unverified
- `BLOCKED`: safe progress cannot continue

Report changes, exact checks and results, unresolved issues, risks, and artifact paths. Never claim that an unrun command passed.
