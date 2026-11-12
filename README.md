# GHDL — Graph Harness Development Lifecycle

GHDL 2.3.0 is a lightweight, tool-agnostic workflow for planning and delivering software changes as verifiable tasks with explicit dependencies and execution evidence.

## Adopt GHDL in a project

1. Copy **only** `AGENTS.md` and the complete `.ghdl/` directory into the target repository root.
2. Treat both as generic, read-only framework distribution files. Do not add project-specific state to them or edit them during normal use.
3. Run `python .ghdl/scripts/ghdl.py init`.
4. GHDL creates all writable project state under `ghdl/`; no other release files are required. `AGENTS.md` remains the single authoritative process instruction.

The helpers use only the Python standard library. They do not call a model or access the network. The distribution files `AGENTS.md` and `.ghdl/` are portable framework assets and are read-only during project operation; helper commands write only under `ghdl/`.

## Project data layout

```text
ghdl/
├── PRODUCT.md
├── BOARD.md
├── items/
│   └── GHDL-YYYYMMDD-HH_mm_ss/
│       ├── task.md
│       ├── graph.md
│       └── run-state.md
└── archive/
    ├── INDEX.md
    └── GHDL-YYYYMMDD-HH_mm_ss/
        ├── task.md
        ├── graph.md
        └── run-state.md
```

An item is a self-contained directory. `task.md` is its source of truth; `graph.md` and `run-state.md` are created when the item is activated. Archiving moves the whole directory unchanged.

## Helper commands

```bash
python .ghdl/scripts/ghdl.py init
python .ghdl/scripts/ghdl.py new --title "Add user sign-in" --type feature --priority P1
python .ghdl/scripts/ghdl.py transition <ITEM-ID> READY
python .ghdl/scripts/ghdl.py transition <ITEM-ID> IN_PROGRESS
python .ghdl/scripts/ghdl.py transition <ITEM-ID> VERIFY
python .ghdl/scripts/ghdl.py transition <ITEM-ID> DONE
python .ghdl/scripts/ghdl.py archive
python .ghdl/scripts/ghdl.py restore <ITEM-ID>
python .ghdl/scripts/ghdl.py board
python .ghdl/scripts/ghdl.py validate
python .ghdl/scripts/ghdl.py next
```

`archive` requires no ID. It checks every active task and moves all tasks whose incoming and outgoing `depends_on` relationships connect only to `DONE` or `CANCELLED` tasks. A task with no dependency relationships is eligible. The candidate's own status is not a separate condition.

The helper updates `ghdl/archive/INDEX.md` automatically. Its simple format is one line per archived task:

```text
GHDL-YYYYMMDD-HH_mm_ss Task title
```

Item IDs are `GHDL-<creation date>-<HH_mm_ss>`, so they sort chronologically. If two items are created in the same second, the helper appends `-1`, then `-2`, ... until the ID is unique.

The archive index is the only archive file permitted for routine LLM context discovery. Archived task directories must not be scanned unless historical details are necessary.

## Verification when maintaining GHDL

```bash
python -c "from pathlib import Path; compile(Path('.ghdl/scripts/ghdl.py').read_text(encoding='utf-8'), 'ghdl.py', 'exec')"
python -m unittest discover -s tests -v
python .ghdl/scripts/ghdl.py validate
```

See `AGENTS.md` for the complete lifecycle, constraints, and archive access restrictions.
