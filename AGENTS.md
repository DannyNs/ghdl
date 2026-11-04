# GHDL — Graph Harness Development Lifecycle

**GHDL Continuous Flow 2.3.0** is a lightweight, repository-first process for delivering software with AI agents and developers. It combines a persistent Kanban backlog with a small execution DAG for each selected work item. The process is model-, vendor-, editor-, and runtime-independent.

This file is the **single authoritative process instruction**. Agents MUST follow it. Files in `.ghdl/templates/` are copy-only templates, not additional instructions.

**Distribution boundary:** to adopt GHDL in another repository, copy only this `AGENTS.md` and the complete `.ghdl/` directory. They are generic, portable, read-only framework assets during normal project operation. Never store project-specific state, reports, backlog items, or run evidence in either location. All generated and mutable project state belongs under `ghdl/`.

## 1. Non-negotiable operating rules

1. **Do not skip lifecycle stages.** Follow the ordered procedure in this file for every non-trivial change.
2. **Inspect before editing.** Inspect repository instructions, relevant source/tests/configuration, `git status`, and existing diffs before creating or changing files.
3. **Preserve user work.** Never reset, clean, stash, checkout over, or overwrite unrelated user changes. Do not revert changes you did not make.
4. **Backlog before implementation.** Every non-trivial request MUST exist as a work item in `ghdl/items/` before implementation begins.
5. **One source of truth.** Work-item metadata in `task.md` is authoritative. `ghdl/BOARD.md` is a generated Kanban view; never edit it by hand.
6. **Just-in-time planning.** Refine only the next useful slice. Do not decompose an entire product or epic upfront unless the user explicitly requests it.
7. **One active item per worktree.** An item in `IN_PROGRESS` or `VERIFY` consumes the worktree's WIP slot. Do not start another item until it is `DONE` or `BLOCKED`. Parallel work requires separate Git worktrees/branches and non-overlapping file ownership.
8. **Every active item has an execution graph.** Before implementation, create and populate its `graph.md` and `run-state.md` in the same item directory as `task.md`.
9. **Dependencies are gates.** Never start an item while any declared dependency is not `DONE`. Never execute a graph node before all its dependencies are `PASS`.
10. **Evidence, not claims.** A task, node, check, or acceptance criterion is complete only when its evidence is recorded. Never claim an unrun check passed.
11. **Bound repair.** A failing node gets one initial attempt and at most two repair attempts. Then stop and report `BLOCKED` or `PARTIAL` with evidence.
12. **No silent scope changes.** If evidence materially changes scope, behavior, architecture, risk, or acceptance criteria, update the item and graph and obtain user approval when the change exceeds the request.
13. **No consequential action without approval.** Obtain explicit user approval before destructive data operations, production changes, permission/security changes, purchases, external communications, or other irreversible/external side effects.
14. **Update persistent state before finishing.** Update the work item, execution records, and generated board. Validate the project state before reporting.
15. **Report truthfully.** Use `DONE`, `PARTIAL`, or `BLOCKED`. Never convert an unverified or skipped step into success.

## 2. Repository layout and ownership

```text
AGENTS.md                         # the only mandatory process instruction
.ghdl/
  scripts/ghdl.py                 # standard-library helper for state and board
  templates/
    product.md                    # copied once to ghdl/PRODUCT.md
    work-item.md                  # copied as task.md for each new item
    graph.md                      # copied when an item is activated
    run-state.md                  # copied when an item is activated
ghdl/
  PRODUCT.md                      # durable product goal and project constraints
  BOARD.md                        # generated Kanban projection; do not edit manually
  items/                          # active work items only; source of truth
    GHDL-YYYYMMDD-XXXXXXXX/
      task.md                     # canonical metadata, scope, criteria, decisions
      graph.md                    # execution DAG (created on activation)
      run-state.md                # execution evidence (created on activation)
  archive/
    INDEX.md                      # ID + title only; maintained by the helper
    GHDL-YYYYMMDD-XXXXXXXX/       # complete archived item directory
      task.md
      graph.md                    # when it existed
      run-state.md                # when it existed
```

### Ownership rules

- `AGENTS.md` and `.ghdl/` are the portable GHDL installation and are read-only during project operation. Normal GHDL commands MUST NOT create, modify, or delete files there.
- `ghdl/` is the project-local writable state directory. All generated output, backlog items, run evidence, and archives MUST stay beneath it.
- `AGENTS.md` owns the process. Do not create extra process-instruction files.
- `.ghdl/templates/` contains pristine blueprints only. Never put project state, task content, or execution results in `.ghdl/templates/`.
- `ghdl/PRODUCT.md` describes durable product goals, users, boundaries, and constraints. Keep it concise and update it only when durable project direction changes.
- Each `ghdl/items/<ID>/task.md` is the canonical record for one active backlog item: metadata, outcome, scope, acceptance criteria, dependencies, assumptions, and decisions.
- `graph.md` and `run-state.md` live inside the same item directory as `task.md`. They are persistent execution evidence, not disposable temporary files.
- `ghdl/BOARD.md` is generated from active item metadata by the helper script. Do not edit it manually or treat it as a second source of truth.
- `ghdl/archive/INDEX.md` is a script-maintained inventory. Each non-empty line has exactly this form: `GHDL-YYYYMMDD-XXXXXXXX Task title`. Do not add brackets, statuses, summaries, or other fields.
- The task directory is the unit of movement. Archiving moves the entire `ghdl/items/<ID>/` directory to `ghdl/archive/<ID>/` without editing its contents.

## 3. Archive context boundary — mandatory

Archived work is historical context, not active backlog.

- During normal repository discovery and task execution, **NEVER scan, traverse, enumerate, search, glob, or read archived task directories** under `ghdl/archive/`.
- The only archive file permitted for routine awareness is `ghdl/archive/INDEX.md`. It may be read to know which historical task IDs and titles exist.
- Reading the index does not authorize opening any archived task directory.
- Read an archived task's files only when the user explicitly references that task, or when concrete historical details are necessary to investigate or implement the current request.
- When archive content is needed, use `INDEX.md` to identify the relevant ID, then inspect only that task directory and only the files necessary. Never load the entire archive.
- Do not use archive contents as part of normal active-task discovery, planning, or dependency resolution.
- **Never manually move task directories into or out of the archive.** Use the helper commands below.
- **Never manually create, edit, sort, or maintain `INDEX.md`.** The Python helper reads the title from the task metadata and updates the index during `archive` and `restore` operations.

### Archiving eligibility

The helper determines eligibility using one rule only:

> Every dependency relationship involving the candidate task must connect it to a task whose status is `DONE` or `CANCELLED`.

This checks both directions of `depends_on`: the candidate's prerequisites and active items that depend on the candidate. A task with no `depends_on` relationships is eligible. The candidate's own status is not an additional eligibility condition. Parent/grouping links are not dependency relationships for this check.

Run:

```bash
python .ghdl/scripts/ghdl.py archive
```

Do not pass an item ID. The helper checks all active items, archives every eligible item, leaves ineligible items in place with reasons, updates `archive/INDEX.md` from each task's metadata title, and regenerates `BOARD.md`. Index lines are `ID Title`, with no square brackets. No LLM-generated summary or manual index update is required.

To restore one item:

```bash
python .ghdl/scripts/ghdl.py restore <ITEM-ID>
```

The helper moves the complete item directory back to `items/` and removes its index entry.

## 4. Mandatory lifecycle — execute in this order

### Stage 0 — Discover current repository state

Before changing anything:

1. Read this `AGENTS.md` and any more specific `AGENTS.md` files governing the target paths.
2. Inspect the repository structure and relevant implementation, tests, build files, configuration, and project conventions.
3. Run `git status --short --branch` and inspect relevant staged, unstaged, and untracked changes. Preserve unrelated changes.
4. Read `ghdl/PRODUCT.md` and `ghdl/BOARD.md` when present. Read the relevant active `task.md`, `graph.md`, and `run-state.md` when continuing work.
5. You may read `ghdl/archive/INDEX.md` for historical awareness, but do not inspect archive task folders unless historical details are required.
6. Identify available deterministic verification commands. Do not guess command names; inspect build manifests and existing automation.
7. Record relevant findings and existing changes in the work item or run state before implementation.

If `ghdl/` does not exist, initialize it using Section 5. Never overwrite an existing project file during initialization.

### Stage 1 — Intake and backlog capture

Translate the user's request into one or more work items before implementation.

- Search active `ghdl/items/` for an existing item that already represents the requested outcome. Update that item instead of creating a duplicate.
- Otherwise create a new item with the helper command in Section 5.
- Record the desired observable outcome, scope, relevant context, constraints, and checkable acceptance criteria.
- Record assumptions as assumptions. Ask only when missing information materially affects safety, externally visible behavior, architecture, or scope. Otherwise choose a reversible assumption and record it.
- Do not turn every implementation step into a backlog item. Items represent independently valuable outcomes, not shell commands or individual edits.

### Stage 2 — Refine the next deliverable

Move an item from `BACKLOG` to `READY` only when:

1. The outcome is specific and observable.
2. Scope is bounded, with relevant exclusions recorded.
3. It is a deliverable vertical slice whenever practical.
4. It has uniquely identified, objectively checkable acceptance criteria (`AC-1`, `AC-2`, ...).
5. All dependencies are explicit and already `DONE`; the dependency graph is acyclic.
6. Required inputs and decisions are available; material uncertainty is not hidden in assumptions.
7. The item is small enough to implement, verify, and review in one focused agent run. Otherwise split it and keep a parent only as a grouping item.

Do not estimate story points, create artificial sprint boundaries, or require a complete product plan. Refine the next item only when it is likely to be pulled.

### Stage 3 — Select and claim work

1. Run `python .ghdl/scripts/ghdl.py validate`.
2. Run `python .ghdl/scripts/ghdl.py next` and inspect the `READY` candidates.
3. Select the highest-priority unblocked item (`P0`, then `P1`, `P2`, `P3`). Use user priority and project context to break ties.
4. Confirm every dependency is `DONE` and the WIP slot is free.
5. Claim exactly one item:

   `python .ghdl/scripts/ghdl.py transition <ITEM-ID> IN_PROGRESS`

   The helper creates `graph.md` and `run-state.md` directly inside `ghdl/items/<ITEM-ID>/` from pristine templates. It must not overwrite existing run records.

6. If no item is `READY`, refine the next useful backlog item. Do not start directly from an unrefined `BACKLOG` item.

### Stage 4 — Create the execution contract and DAG

Before editing implementation files, populate:

- `ghdl/items/<ITEM-ID>/graph.md`
- `ghdl/items/<ITEM-ID>/run-state.md`

The graph MUST:

- contain unique, stable node IDs;
- include `inspect`, `implement`, `verify`, and `review` node types (add `design` or `human_gate` when needed);
- state each node's observable goal, dependencies, inputs, outputs, and completion predicate;
- form a directed acyclic graph;
- remain small: one node per meaningful output, dependency, risk boundary, or verification predicate — never one node per shell command.

The run-state table MUST mirror every graph node exactly and record status, attempt count, and evidence. Initial node status is `PENDING`. The run record MUST capture repository findings, verification commands, acceptance evidence, decisions, and blockers.

### Stage 5 — Implement in dependency order

1. Start only nodes whose dependencies are all `PASS`.
2. Mark a node `RUNNING` before executing it. Record its attempt count.
3. Make only changes required by the work item. Keep file ownership disjoint when using multiple agents.
4. After each meaningful change, inspect the diff and update run state with outputs and evidence.
5. Mark a node `PASS` only after its completion predicate is evidenced. Mark failures `FAIL`; use `BLOCKED` only when progress cannot safely continue. `SKIPPED` never satisfies a dependency.
6. If new facts invalidate the plan, stop affected downstream nodes, explain the invalidated assumption, revise the item/graph, increment graph revision, and resume from the earliest invalidated node. Obtain approval before materially expanding scope.
7. For each failed node, allow at most two repair attempts after the initial attempt. If still failing, stop; do not weaken tests or predicates to force success.

### Stage 6 — Enter verification

Move `IN_PROGRESS` to `VERIFY` only after implementation is complete:

1. Every `inspect`, `design`, `implement`, and `human_gate` node is `PASS` with evidence.
2. The run-state `Implementation` gate is `PASS` with evidence.
3. The helper accepts the transition:

   `python .ghdl/scripts/ghdl.py transition <ITEM-ID> VERIFY`

If any condition is unmet, remain `IN_PROGRESS` or move to `BLOCKED`.

### Stage 7 — Verify and review

Run verification in this order, adapting only when a category is genuinely irrelevant:

1. Focused tests for changed behavior.
2. Relevant broader or regression tests.
3. Build, type-check, lint, static analysis, or equivalent checks.
4. Manual/integration checks required by acceptance criteria.
5. Final diff review against scope and acceptance criteria.

For every check, record the exact command, result, and useful output. Outcomes are `PASS`, `FAIL`, `BLOCKED`, or `N/A` (with a reason). Map every acceptance criterion to evidence; mark its checkbox `[x]` only when proven. Set Verification/Review gates to `PASS` only with evidence.

If verification fails, return the item to `IN_PROGRESS` using the helper, repair within the retry limit, and repeat verification. If it cannot be resolved safely, move it to `BLOCKED` and preserve evidence.

### Stage 8 — Complete and persist the result

An item may move from `VERIFY` to `DONE` only when:

1. Every acceptance criterion is checked and has corresponding `PASS` evidence.
2. `Implementation`, `Verification`, and `Review` gates are `PASS` with evidence.
3. Every graph node is `PASS` with evidence.
4. No required check is `FAIL` or `BLOCKED`; every `N/A` has a concrete reason.
5. The final diff contains no unrelated or unexplained changes.
6. Run-state final status is `DONE`.
7. `python .ghdl/scripts/ghdl.py validate` succeeds.

Then run:

`python .ghdl/scripts/ghdl.py transition <ITEM-ID> DONE`

The helper enforces the transition and regenerates `ghdl/BOARD.md`. It detects the current Git branch as the WIP key; pass `--worktree <KEY>` only when branch detection is unavailable or detached worktrees need distinct labels. Do not edit status metadata directly.

### Stage 9 — Reassess the backlog

After each completed or blocked item:

1. Review discoveries, decisions, and remaining work.
2. Add follow-up items for newly discovered requirements, defects, or necessary cleanup. Do not silently expand the completed item.
3. Update `ghdl/PRODUCT.md` only when durable product goals, constraints, or boundaries changed.
4. Reorder priorities only when evidence or user direction justifies it.
5. Regenerate the board and run validation.
6. Stop after the requested outcome is delivered. Do not automatically pull unrelated backlog work.

## 5. Project initialization and helper commands

The helpers use only the Python standard library. They do not call a model, access the network, or modify application source files. Run commands from the repository root; use `python`, `python3`, or `py -3` as appropriate.

### Adopt, initialize, or upgrade a project

Copy this `AGENTS.md` and the complete `.ghdl/` directory into the target project root. Do not copy this release's `ghdl/` project data into an adopting project. Then run:

```bash
python .ghdl/scripts/ghdl.py init
```

`init` creates missing `ghdl/` directories, creates `archive/INDEX.md` if missing, copies `PRODUCT.md` from the template only when absent, regenerates `BOARD.md`, and automatically migrates the legacy `items/<ID>.md` + `runs/<ID>/` structure when found. For an explicit migration, run `python .ghdl/scripts/ghdl.py migrate`. The migration refuses to overwrite conflicting destinations and preserves all task/run files.

### Create a backlog item

```bash
python .ghdl/scripts/ghdl.py new --title "Add user sign-in" --type feature --priority P1
```

Optional arguments: `--parent <ITEM-ID>` and `--depends-on <ID,ID,...>`. The command allocates `GHDL-YYYYMMDD-XXXXXXXX`, creates `ghdl/items/<ITEM-ID>/task.md`, writes metadata, and refreshes `BOARD.md`. Complete the item body and define measurable acceptance criteria before moving it to `READY`.

Allowed types: `feature`, `bug`, `refactor`, `chore`, `spike`. Priorities: `P0` (urgent), `P1` (high), `P2` (normal), `P3` (low).

### Move an item through the workflow

```bash
python .ghdl/scripts/ghdl.py transition <ITEM-ID> READY
python .ghdl/scripts/ghdl.py transition <ITEM-ID> IN_PROGRESS
python .ghdl/scripts/ghdl.py transition <ITEM-ID> VERIFY
python .ghdl/scripts/ghdl.py transition <ITEM-ID> DONE
```

`IN_PROGRESS` creates `graph.md` and `run-state.md` inside the item directory. Existing run files are never overwritten.

Use `BLOCKED` with a reason when progress cannot continue:

```bash
python .ghdl/scripts/ghdl.py transition <ITEM-ID> BLOCKED --reason "Waiting for API contract"
```

A blocked item can return only to its recorded previous state, with a reason explaining blocker resolution:

```bash
python .ghdl/scripts/ghdl.py transition <ITEM-ID> <PREVIOUS-STATE> --reason "Blocker resolved: ..."
```

Allowed transitions:

| Current state       | Allowed next state                               |
| ------------------- | ------------------------------------------------ |
| `BACKLOG`           | `READY`, `BLOCKED`, `CANCELLED`                  |
| `READY`             | `BACKLOG`, `IN_PROGRESS`, `BLOCKED`, `CANCELLED` |
| `IN_PROGRESS`       | `VERIFY`, `BLOCKED`                              |
| `VERIFY`            | `IN_PROGRESS`, `DONE`, `BLOCKED`                 |
| `BLOCKED`           | Recorded previous state, or `CANCELLED`          |
| `DONE`, `CANCELLED` | Terminal; create a new item for new work         |

### Inspect and validate

```bash
python .ghdl/scripts/ghdl.py next
python .ghdl/scripts/ghdl.py board
python .ghdl/scripts/ghdl.py validate
```

- `next` lists `READY` items in priority order whose dependencies are `DONE`.
- `board` regenerates the Kanban view from active item metadata, including per-worktree WIP.
- `validate` checks active metadata, IDs, dependency references/cycles, per-worktree WIP, run artifacts, state gates, and board consistency. It does not enumerate archived task folders.

## 6. Kanban and backlog rules

- `BACKLOG` — captured, but not sufficiently refined or not selected.
- `READY` — bounded, independently deliverable, acceptance criteria are checkable, and dependencies are complete.
- `IN_PROGRESS` — claimed and actively implemented; execution DAG and run state exist.
- `VERIFY` — implementation gate passed; verification and review are in progress.
- `BLOCKED` — cannot proceed; blocker and prior state are recorded.
- `DONE` — all acceptance criteria and gates have evidence.
- `CANCELLED` — explicitly abandoned; not equivalent to `DONE`.

Prefer vertical slices that deliver observable user value. Keep tasks small enough for one focused implementation/verification cycle. Use `parent` to group related items; use `depends_on` only for genuine prerequisites. Do not create sprint containers, story points, velocity tracking, mandatory ceremonies, artificial deadlines, or full upfront plans.

Default WIP limit is one item in `IN_PROGRESS` or `VERIFY` per worktree. Parallel work requires separate Git worktrees/branches, different READY items, and non-overlapping write ownership. Do not let multiple agents edit the same item, board, or shared files concurrently.

## 7. Graph contract and evidence rules

Every graph node MUST define ID, type, goal, dependencies, inputs, outputs, and completion predicate. Run state MUST define status, attempts, and evidence.

Node statuses:

- `PENDING` — not started.
- `READY` — all dependencies are `PASS`.
- `RUNNING` — currently executing.
- `PASS` — completion predicate met with recorded evidence.
- `FAIL` — attempted and failed.
- `BLOCKED` — cannot safely proceed.
- `SKIPPED` — intentionally not run; never satisfies a dependency.

A graph is valid only if dependencies form a DAG, every dependency references an existing node, IDs are unique, and every non-root node waits for its dependencies. Increment graph revision whenever the graph changes and record why. Evidence may be a command and exit code, test result, relevant log excerpt, changed artifact path, explicit human decision, or reproducible manual observation. "Implemented" or "looks good" is not evidence.

## 8. Safety and runtime limitations

- Never infer human approval from silence, prior approval, or tool availability.
- If the runtime cannot run a check, record `BLOCKED` with the exact limitation.
- Do not claim an agent, worker, tool, test, or command ran unless it actually did.
- Do not write secrets, credentials, or private user data into work items or run artifacts.
- Do not perform destructive cleanup to make validation pass. Preserve evidence and report the blocker.

## 9. Maintaining and testing GHDL itself

When changing the helper or templates, run:

```bash
python -c "from pathlib import Path; compile(Path('.ghdl/scripts/ghdl.py').read_text(encoding='utf-8'), 'ghdl.py', 'exec')"
python -m unittest discover -s tests -v
python .ghdl/scripts/ghdl.py validate
```

Do not report a helper change as verified unless these commands actually ran. If a command cannot run, state why.

## 10. Required final response

End every GHDL task with a concise report containing:

- **Status:** `DONE`, `PARTIAL`, or `BLOCKED`.
- **Delivered:** observable outcome and key paths changed.
- **Acceptance:** each criterion met/unmet with evidence.
- **Verification:** exact commands and actual results; list checks not run.
- **Backlog:** follow-up items or blockers.
- **Risks:** remaining risks, assumptions, or required human decisions.

The reported status MUST be no stronger than the evidence. `DONE` means every required acceptance criterion is proven. `PARTIAL` means useful work was completed but something remains unverified or unmet. `BLOCKED` means safe progress could not continue.
