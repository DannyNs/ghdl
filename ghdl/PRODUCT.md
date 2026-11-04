# Product context — GHDL

## Product outcome

Provide a lightweight, tool-agnostic development process that lets humans and AI agents continuously turn software goals into small, independently verifiable deliveries while preserving project context and execution history in Git.

## Users and primary workflows

- Developers collaborating with one or more AI coding agents.
- Teams that need persistent project-level progress across models, tools, sessions, and contributors.
- Agents that need a deterministic next action, explicit dependencies, and objective completion evidence.

## Product boundaries

### In scope

- Repository-local Kanban backlog and persistent work-item history.
- Self-contained work-item directories and whole-directory archiving.
- Just-in-time refinement of the next deliverable slice.
- A small dependency DAG for each active item.
- Explicit verification, review, and evidence gates.
- Tool- and model-independent instructions and state files.

### Out of scope

- Sprint ceremonies, story points, velocity, or time-based planning.
- Full upfront decomposition of an entire product.
- A hosted task tracker or mandatory external service.
- A model-specific agent runtime, orchestration engine, or claim of automatic parallelism.

## Constraints

- Technical: Python standard library only for helper tooling; Markdown and JSON metadata remain inspectable in Git. The portable distribution is only `AGENTS.md` + `.ghdl/`; both are read-only during project operation, while mutable state is confined to `ghdl/`.
- Operational: one active item per worktree by default; project state must survive model/session changes.
- Security/privacy: no secrets or private user data in project artifacts; consequential actions require explicit approval.
- Compatibility: usable by different LLM providers, IDE assistants, terminal agents, and humans.

## Quality bar

- One authoritative process instruction file: `AGENTS.md`.
- The work-item record is the source of truth; the Kanban board is generated.
- Status transitions, dependency gates, WIP limits, and archive moves are validated by the helper.
- A task is DONE only when all acceptance criteria and execution gates have evidence.
- Archive contents remain intact and are excluded from default LLM context loading.

## Current direction

Continuous Flow: refine the next useful item, pull one ready slice, execute its DAG, prove its acceptance criteria, update the backlog, and repeat.
