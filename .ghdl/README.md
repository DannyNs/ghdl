# GHDL

Graph Harness Development Lifecycle — a tool-agnostic development protocol.

GHDL separates **the development method** from **the agent runtime**. `AGENTS.md` is the short repository-level entry point; this directory contains the detailed process, graph rules, and reusable templates.

## Directory layout

```text
AGENTS.md
.ghdl/
├── README.md
├── references/
│   ├── lifecycle.md
│   └── graph-contract.md
└── templates/
    ├── task-contract.md
    ├── graph.md
    └── run-state.md
```

## Minimal lifecycle

`INTAKE → DISCOVER → PLAN → IMPLEMENT → VERIFY → REVIEW → REPORT`

### 1. Intake

Clarify the goal, scope, constraints, acceptance criteria, risk, and required human approvals.

### 2. Discover

Read repository guidance, inspect relevant code/tests/build files, and check existing changes. Do not infer repository facts without inspection.

### 3. Plan

Create a task contract and a small DAG. Each node must have dependencies, inputs, outputs, and an observable completion predicate. Mark human gates.

### 4. Implement

Execute only ready nodes. Keep changes in scope. Avoid overlapping write ownership when using multiple agents.

### 5. Verify

Run relevant deterministic checks. Record exact commands and results. Retry a failed node no more than twice after the first attempt.

### 6. Review

Inspect the diff, scope, security implications, test coverage, compatibility, and acceptance criteria.

### 7. Report

Return a truthful status: `DONE`, `PARTIAL`, or `BLOCKED`, with evidence and unresolved items.

## Per-task artifacts

Create `ghdl/task-contract.md`, `ghdl/graph.md`, and `ghdl/run-state.md` in the working tree when the task is complex enough to benefit from them. These are run artifacts, not required permanent repository files. Avoid committing transient artifacts unless the project wants them versioned.

## Runtime boundary

This directory describes a protocol. By itself, it does not execute a graph, spawn agents, persist state automatically, or guarantee parallelism. A compatible runtime may automate those functions later; otherwise, the assistant/developer follows the protocol and updates the artifacts manually.

## Customization

- Keep `AGENTS.md` short and stable.
- Put detailed process rules under `.ghdl/references/`.
- Add project-specific conventions in `AGENTS.md` or a separate reference file.
- Avoid model-specific syntax and provider-specific assumptions in core rules.
