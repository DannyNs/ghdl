# GHDL — Graph Harness Development Lifecycle

A tool-agnostic protocol for planning and executing software changes as a **verifiable dependency graph (DAG)**.

GHDL separates *the development method* from *the agent runtime*. It works with IDE assistants, terminal agents, API-based agents, or plain manual development — no specific model, editor, CLI, or orchestration framework is required. If the runtime cannot support a feature (parallel workers, persistent checkpoints, tool permissions), state the limitation and use the closest safe manual equivalent.

## When to use

Use GHDL for feature work, bug fixes, refactoring, architecture changes — anything where scope, dependencies, or verification matter. For truly trivial edits, apply the same rules in lightweight form without creating runtime artifacts.

## Adopting in another project

1. Copy `AGENTS.md` and the `.ghdl/` directory into your repository root.
2. Add project-specific conventions to `AGENTS.md` (keep it short) or a separate reference file under `.ghdl/references/`.
3. For each task, follow `AGENTS.md` → `.ghdl/README.md` → `.ghdl/references/lifecycle.md`, and use the templates in `.ghdl/templates/` when the task warrants artifacts.

## Directory layout

```text
AGENTS.md            # short repo-level entry point (rules + final report format)
.ghdl/
├── README.md        # protocol overview, lifecycle summary, runtime boundary
├── references/
│   ├── lifecycle.md     # detailed stage rules (intake → report)
│   └── graph-contract.md  # node fields, invariants, sizing guidance
└── templates/
    ├── task-contract.md   # goal, scope, acceptance criteria, risk/approvals
    ├── graph.md           # Mermaid DAG + node contract table
    └── run-state.md       # per-node status, attempts, evidence, final status
```

## Minimal lifecycle

`INTAKE → DISCOVER → PLAN → IMPLEMENT → VERIFY → REVIEW → REPORT`

| Stage | What happens |
|---|---|
| **Intake** | One-sentence goal; in/out of scope, checkable acceptance criteria, constraints, risk level (low/medium/high), human-approval operations. Record reversible assumptions instead of asking when safe to do so. |
| **Discover** | Inspect instructions, code/tests/build files, `git status --short`, and existing diffs. Never infer repository facts without inspection; never overwrite user changes. |
| **Plan** | Task contract + small DAG. Node types: `inspect`, `design`, `implement`, `verify`, `review`, `human_gate`. Do not over-fragment trivial work. |
| **Implement** | Execute only nodes whose dependencies are complete. If new facts invalidate the graph: stop downstream work, explain why, revise the plan (bump revision), get approval if scope/risk changed, resume from the earliest invalidated node. |
| **Verify** | Deterministic evidence in order: focused tests → broader tests → build/type-check/lint → diff review against acceptance criteria. Record each check as `PASS` / `FAIL` / `BLOCKED` / `N/A`. Retry policy: one initial attempt + at most two repair attempts, then stop and report. Never silently weaken a test or predicate. |
| **Review** | Scope creep, secrets, error handling/compatibility, migrations/rollback, whether tests actually prove the acceptance criteria, whether every claim has evidence. Human review required before consequential actions (production deploys, destructive ops, permission changes). |
| **Report** | Truthful status: `DONE` / `PARTIAL` / `BLOCKED`, with exact commands and results, unresolved items, risks, and artifact paths. Never claim an unrun command passed. |

## Non-negotiable rules

- Inspect the repository and existing user changes before editing.
- Define a task contract and checkable acceptance criteria before implementation.
- Represent work as a DAG with explicit dependencies.
- A node is complete only when its completion predicate has evidence.
- Use deterministic checks (tests, builds, linters, scripts) wherever possible.
- Bound retries: one initial attempt plus at most two repair attempts per failed node.
- Ask for human approval before destructive actions, production changes, external side effects, or materially expanded scope.
- Do not overwrite unrelated changes, weaken tests silently, or claim checks passed if they were not run.
- If new evidence invalidates the plan, revise the graph and record why.
- Report `DONE`, `PARTIAL`, or `BLOCKED` truthfully.

## Graph contract (node semantics)

Every node defines: stable `id`, observable `goal`, `depends_on`, `inputs`, `outputs`, `done_when`, `status` (`PENDING` / `READY` / `RUNNING` / `PASS` / `FAIL` / `BLOCKED` / `SKIPPED`), `attempts`, and `owner`.

Key invariants:

- Dependencies form a DAG; repair is bounded retry, not an unbounded cycle.
- A node is `READY` only when its dependencies are `PASS` (or a documented alternative supplies the required input).
- `SKIPPED` ≠ `PASS`; `PASS` requires evidence such as a command result, artifact, test output, or explicit human decision.
- A failed node does not satisfy downstream dependencies.
- Human approval is an explicit gate, never inferred.
- Re-plan and increment the graph revision when scope or facts change.
- Do not claim parallelism unless the runtime actually executes work concurrently.

Keep graphs small: one node per meaningful independent output, dependency, risk boundary, or verification predicate — not one node per shell command.

## Per-task artifacts

For tasks complex enough to benefit, create in the working tree:

- `ghdl/task-contract.md` — goal, scope, acceptance criteria, constraints/assumptions, risk and approvals
- `ghdl/graph.md` — Mermaid DAG + node contract table
- `ghdl/run-state.md` — per-node status/attempts/evidence, decisions, final status

These are transient run artifacts, not permanent repository files. Avoid committing them unless the project wants them versioned.

## Runtime boundary

This protocol describes a process; it does not execute graphs, spawn agents, persist state automatically, or guarantee parallelism. A compatible runtime may automate those functions later; otherwise, follow the protocol and update the artifacts manually.
