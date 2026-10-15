# GHDL — Graph Harness Development Lifecycle

This repository uses GHDL, a tool-agnostic protocol for planning and executing software changes as a verifiable dependency graph.

## When to use

Use GHDL for feature work, bug fixes, refactoring, architecture changes, and other tasks where scope, dependencies, or verification matter. For a truly trivial edit, use the same rules in lightweight form without creating runtime artifacts.

## Start here

1. Read this file and the applicable repository instructions.
2. Read `.ghdl/README.md`.
3. Follow `.ghdl/references/lifecycle.md`.
4. Use `.ghdl/templates/` to create per-task artifacts when warranted.

## Non-negotiable rules

- Inspect the repository and existing user changes before editing.
- Define a task contract and checkable acceptance criteria before implementation.
- Represent work as a directed acyclic graph (DAG) with explicit dependencies.
- A node is complete only when its completion predicate has evidence.
- Use deterministic checks (tests, builds, linters, scripts) wherever possible.
- Bound retries: one initial attempt plus at most two repair attempts per failed node.
- Ask for human approval before destructive actions, production changes, external side effects, or materially expanded scope.
- Do not overwrite unrelated changes, weaken tests silently, or claim checks passed if they were not run.
- If new evidence invalidates the plan, revise the graph and record why.
- Report `DONE`, `PARTIAL`, or `BLOCKED` truthfully.

## Tool independence

GHDL is a process specification, not an instruction to use a particular model, editor, agent, CLI, or orchestration framework. Follow it whether working through an IDE assistant, terminal agent, API-based agent, or manually with a developer. If the runtime cannot support a feature (parallel workers, persistent checkpoints, tool permissions), state the limitation and use the closest safe manual equivalent.

## Required final report

- Status: `DONE` / `PARTIAL` / `BLOCKED`
- Outcome: what changed
- Verification: exact commands and results
- Acceptance criteria: met/unmet with evidence
- Risks/follow-up
- Artifact paths, if created

See `.ghdl/README.md` for the layout and `.ghdl/references/graph-contract.md` for node semantics.
