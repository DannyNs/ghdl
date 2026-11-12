<!-- GHDL_ITEM_BEGIN
{
  "id": "GHDL-20261112-21_52_36",
  "title": "Reduce ghdl.py working-tree diff to functional changes only",
  "type": "refactor",
  "priority": "P1",
  "status": "DONE",
  "parent": null,
  "depends_on": [],
  "owner": "agent",
  "worktree": "main",
  "blocked_reason": null,
  "resume_status": null,
  "cancel_reason": null,
  "created": "2026-11-12",
  "updated": "2026-11-12"
}
GHDL_ITEM_END -->

# Reduce ghdl.py working-tree diff to functional changes only

## Outcome

`git diff .ghdl/scripts/ghdl.py` contains only functional changes (timestamp-based item IDs with collision suffixes, `--id-suffix` argument, removal of the legacy-layout migration feature) instead of ~754 lines of unrelated line-wrapping reformatting noise.

## Context

An earlier session reformatted `ghdl.py` in black style while making functional changes, so the working-tree diff is 808 changed lines for what should be a small set of hunks. The user asked to clean this up so the diff is reviewable and commit-ready.

## Scope

### In scope

- Restore `.ghdl/scripts/ghdl.py` from `HEAD`, then re-apply only the functional hunks: timestamp-based ID allocation (`GHDL-YYYYMMDD-HH_mm_ss`) with same-second collision suffixes `-1`, `-2`, ...; explicit `--id-suffix N` (1-99) argument; updated `ID_RE`/`INDEX_LINE_RE`; updated validation message; removal of the legacy-layout migration feature (`LEGACY_RUNS_D`, legacy guard in `load_items()`, `migrate_legacy_layout()`, `command_migrate`, `migrate` subparser entry, init help text and "Migrated legacy flat work items" print); import cleanup (drop `time`, `uuid`; add `datetime`).

### Out of scope

- No changes to `AGENTS.md`, `README.md`, or `tests/test_ghdl.py` (their diffs are already purely functional).
- No reformatting of unrelated code; the restored file keeps its original line wrapping.

## Acceptance criteria

<!-- Use unique IDs. Each criterion must be objectively verifiable. -->

- [x] AC-1: `git diff --stat .ghdl/scripts/ghdl.py` shows a small change count (far below the 808-line noise level; expected on the order of ~60 changed lines).
- [x] AC-2: The three AGENTS.md §9 verification commands pass: compile check, `python -m unittest discover -s tests`, and `python .ghdl/scripts/ghdl.py validate`.
- [x] AC-3: A grep for `migrat|LEGACY_RUNS|legacy flat` in `.ghdl/scripts/ghdl.py` returns no matches (the "legacy numeric format" wording in the ID validation message is acceptable).
- [x] AC-4: Timestamp-based IDs still work end-to-end: creating two items in the same second yields `GHDL-YYYYMMDD-HH_mm_ss` and `GHDL-YYYYMMDD-HH_mm_ss-1`; `--id-suffix 7` produces an ID ending in `-7`.

## Constraints and assumptions

- Constraints: keep the original file's line wrapping (no reformatting); preserve `import shutil` (still used by archive/restore); do not touch other files' diffs.
- Assumptions: the Zed editor buffer for `ghdl.py` is closed or will not autosave over disk edits during this operation; the committed original at HEAD is the correct base to restore from.

## Dependencies and decisions

- Dependency rationale: none (no prerequisite items).
- Decisions: restore-from-HEAD + re-apply functional hunks is preferred over manually deleting ~754 lines of wrapping noise; the "legacy numeric format" wording in the ID validation message is kept because legacy numeric IDs are still accepted by `ID_RE`.
- Open questions: none.

## Risks and approvals

- Risk: low
- Rationale: the functional code is already proven correct by 16/16 passing tests; this work only re-applies identical hunks onto a clean base, then re-runs the full verification suite.
- Human approval required before: nothing (no destructive or external side effects).

## Delivery notes

<!-- Add concise discoveries and follow-up references. Do not use this section as a substitute for run evidence. -->
