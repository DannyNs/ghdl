#!/usr/bin/env python3
"""GHDL project-state helper. Python standard library only."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# The installed .ghdl/ tree is read-only during project operation.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
GH_D = ROOT / "ghdl"
ITEMS_D = GH_D / "items"
ARCHIVE_D = GH_D / "archive"
ARCHIVE_INDEX = ARCHIVE_D / "INDEX.md"
LEGACY_RUNS_D = GH_D / "runs"
TEMPLATES_D = ROOT / ".ghdl" / "templates"
BOARD_FILE = GH_D / "BOARD.md"

STATUSES = ("BACKLOG", "READY", "IN_PROGRESS", "VERIFY", "BLOCKED", "DONE", "CANCELLED")
TERMINAL_STATUSES = ("DONE", "CANCELLED")
PRIORITIES = ("P0", "P1", "P2", "P3")
ITEM_TYPES = ("feature", "bug", "refactor", "chore", "spike")
NODE_STATUSES = ("PENDING", "READY", "RUNNING", "PASS", "FAIL", "BLOCKED", "SKIPPED")
NODE_TYPES = ("inspect", "design", "implement", "verify", "review", "human_gate")
ACTIVE_STATUSES = ("IN_PROGRESS", "VERIFY")
WIP_LIMIT = 1
META_RE = re.compile(r"<!-- GHDL_ITEM_BEGIN\s*(.*?)\s*GHDL_ITEM_END -->", re.DOTALL)
ID_RE = re.compile(r"^GHDL-(?:\d{4,}|\d{8}-[0-9A-F]{8})$")
INDEX_LINE_RE = re.compile(r"^(GHDL-(?:\d{4,}|\d{8}-[0-9A-F]{8}))\s+(.+?)\s*$")
ALLOWED_TRANSITIONS = {
    "BACKLOG": {"READY", "BLOCKED", "CANCELLED"},
    "READY": {"BACKLOG", "IN_PROGRESS", "BLOCKED", "CANCELLED"},
    "IN_PROGRESS": {"VERIFY", "BLOCKED"},
    "VERIFY": {"IN_PROGRESS", "DONE", "BLOCKED"},
    "BLOCKED": {"BACKLOG", "READY", "IN_PROGRESS", "VERIFY", "CANCELLED"},
    "DONE": set(),
    "CANCELLED": set(),
}


class GHDLError(Exception):
    """Expected, user-correctable GHDL error."""


def today() -> str:
    return date.today().isoformat()


def current_worktree_key(override: Optional[str] = None) -> str:
    if override and override.strip():
        return override.strip()
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=str(ROOT), check=False,
            capture_output=True, text=True, timeout=5,
        )
        branch = (result.stdout or "").strip()
        if result.returncode == 0 and branch:
            return branch
    except (OSError, subprocess.SubprocessError):
        pass
    return ROOT.name


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def atomic_write_text(path: Path, content: str) -> None:
    """Replace a text file atomically, keeping its parent on the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def require_file(path: Path, label: str) -> str:
    if not path.is_file():
        raise GHDLError("Missing {}: {}".format(label, relative(path)))
    return path.read_text(encoding="utf-8")


def read_metadata(path: Path) -> Tuple[Dict[str, Any], str]:
    content = require_file(path, "work item")
    match = META_RE.search(content)
    if not match:
        raise GHDLError("{} has no GHDL metadata block".format(relative(path)))
    try:
        data = json.loads(match.group(1).strip())
    except json.JSONDecodeError as exc:
        raise GHDLError("Invalid JSON metadata in {}: {}".format(relative(path), exc))
    if not isinstance(data, dict):
        raise GHDLError("Metadata in {} must be a JSON object".format(relative(path)))
    return data, content


def write_metadata(path: Path, metadata: Dict[str, Any], content: Optional[str] = None) -> None:
    if content is None:
        _, content = read_metadata(path)
    block = "<!-- GHDL_ITEM_BEGIN\n{}\nGHDL_ITEM_END -->".format(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )
    updated, count = META_RE.subn(lambda _match: block, content, count=1)
    if count != 1:
        raise GHDLError("Could not safely update metadata in {}".format(relative(path)))
    atomic_write_text(path, updated)


def task_file(item_id: str, base: Path = ITEMS_D) -> Path:
    return base / item_id / "task.md"


def load_archived_metadata(item_id: str) -> Optional[Dict[str, Any]]:
    """Read one explicitly referenced archive record; never enumerate the archive."""
    path = task_file(item_id, ARCHIVE_D)
    if not path.is_file():
        return None
    metadata, _content = read_metadata(path)
    return metadata


def dependency_status(item_id: str, items: Dict[str, Tuple[Dict[str, Any], Path, str]]) -> Optional[str]:
    if item_id in items:
        return str(items[item_id][0].get("status") or "")
    archived = load_archived_metadata(item_id)
    if archived is not None:
        return str(archived.get("status") or "")
    return None


def load_items() -> Dict[str, Tuple[Dict[str, Any], Path, str]]:
    ITEMS_D.mkdir(parents=True, exist_ok=True)
    legacy_files = sorted(ITEMS_D.glob("*.md"))
    if legacy_files:
        raise GHDLError(
            "Legacy flat work-item files were found. Run 'python .ghdl/scripts/ghdl.py migrate' first."
        )
    found: Dict[str, Tuple[Dict[str, Any], Path, str]] = {}
    for item_dir in sorted(path for path in ITEMS_D.iterdir() if path.is_dir()):
        path = item_dir / "task.md"
        if not path.is_file():
            raise GHDLError("{} is missing task.md".format(relative(item_dir)))
        metadata, content = read_metadata(path)
        item_id = metadata.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise GHDLError("{} has no valid 'id' metadata".format(relative(path)))
        if item_dir.name != item_id:
            raise GHDLError("Item directory {} must match metadata ID {}".format(item_dir.name, item_id))
        if item_id in found:
            raise GHDLError("Duplicate work-item ID: {}".format(item_id))
        found[item_id] = (metadata, path, content)
    return found


def parse_table(text: str, required_header: Sequence[str]) -> List[List[str]]:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        normalized = [cell.lower() for cell in cells]
        if all(any(req.lower() in cell for cell in normalized) for req in required_header):
            start = index + 2
            break
    if start is None:
        return []
    rows: List[List[str]] = []
    for line in lines[start:]:
        if not line.strip().startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    return rows


def parse_acceptance(content: str) -> List[Tuple[str, bool, str]]:
    rows: List[Tuple[str, bool, str]] = []
    in_section = False
    for line in content.splitlines():
        if line.strip().lower() == "## acceptance criteria":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = re.match(r"^\s*-\s*\[([ xX])\]\s*(AC-\d+)\s*:\s*(.*?)\s*$", line)
        if match:
            text = match.group(3).strip()
            if text and text not in ("<...>", "..."):
                rows.append((match.group(2), match.group(1).lower() == "x", text))
    return rows


def item_dependencies(metadata: Dict[str, Any]) -> List[str]:
    deps = metadata.get("depends_on", [])
    if not isinstance(deps, list) or any(not isinstance(value, str) for value in deps):
        raise GHDLError("{}: depends_on must be an array of item IDs".format(metadata.get("id", "?")))
    return deps


def validate_dependency_graph(items: Dict[str, Tuple[Dict[str, Any], Path, str]]) -> None:
    graph: Dict[str, List[str]] = {}
    parent_graph: Dict[str, List[str]] = {}
    for item_id, (meta, _path, _content) in items.items():
        deps = item_dependencies(meta)
        if item_id in deps:
            raise GHDLError("{} cannot depend on itself".format(item_id))
        if len(deps) != len(set(deps)):
            raise GHDLError("{} contains duplicate dependencies".format(item_id))
        for dep in deps:
            if dep not in items and not (ARCHIVE_D / dep / "task.md").is_file():
                raise GHDLError("{} depends on unknown item {}".format(item_id, dep))
        parent = meta.get("parent")
        if parent is not None:
            if not isinstance(parent, str) or (parent not in items and not (ARCHIVE_D / parent / "task.md").is_file()):
                raise GHDLError("{} has unknown parent {!r}".format(item_id, parent))
            if parent == item_id:
                raise GHDLError("{} cannot be its own parent".format(item_id))
            parent_graph[item_id] = [parent] if parent in items else []
        else:
            parent_graph[item_id] = []
        graph[item_id] = [dep for dep in deps if dep in items]

    def validate_acyclic(source: Dict[str, List[str]], label: str) -> None:
        visiting = set()
        visited = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise GHDLError("{} contains a cycle at {}".format(label, node))
            if node in visited:
                return
            visiting.add(node)
            for neighbour in source.get(node, []):
                visit(neighbour)
            visiting.remove(node)
            visited.add(node)

        for node in source:
            visit(node)

    validate_acyclic(graph, "Dependency graph")
    validate_acyclic(parent_graph, "Parent hierarchy")


def board_text(items: Dict[str, Tuple[Dict[str, Any], Path, str]]) -> str:
    active_by_worktree: Dict[str, int] = {}
    for meta, _path, _content in items.values():
        if meta.get("status") in ACTIVE_STATUSES:
            key = str(meta.get("worktree") or "(missing)")
            active_by_worktree[key] = active_by_worktree.get(key, 0) + 1
    lines = [
        "# GHDL Kanban board", "",
        "> Generated from `ghdl/items/<ID>/task.md` metadata by `.ghdl/scripts/ghdl.py`. Do not edit manually.",
        "> Work-item directories are the source of truth.", "",
        "## Work in progress by worktree", "",
        "| Worktree / branch | Active items | WIP limit |", "|---|---:|---:|",
    ]
    if active_by_worktree:
        for key, count in sorted(active_by_worktree.items()):
            lines.append("| {} | {} | {} |".format(key, count, WIP_LIMIT))
    else:
        lines.append("| — | 0 | {} |".format(WIP_LIMIT))
    lines.append("")
    order = ("BACKLOG", "READY", "IN_PROGRESS", "VERIFY", "BLOCKED", "DONE", "CANCELLED")
    for status in order:
        lines.extend(["## {}".format(status), ""])
        selected = [(meta, path) for meta, path, _content in items.values() if meta.get("status") == status]
        selected.sort(key=lambda pair: (
            PRIORITIES.index(pair[0].get("priority", "P2")) if pair[0].get("priority") in PRIORITIES else 99,
            pair[0].get("id", ""),
        ))
        if not selected:
            lines.extend(["_No items._", ""])
            continue
        lines.extend([
            "| ID | Item | Priority | Type | Parent | Depends on | Owner | Worktree |",
            "|---|---|---:|---|---|---|---|---|",
        ])
        for meta, _path in selected:
            item_id = str(meta.get("id", ""))
            title = str(meta.get("title", "(untitled)")).replace("|", "\\|")
            parent = str(meta.get("parent") or "—").replace("|", "\\|")
            deps = ", ".join(item_dependencies(meta)) or "—"
            owner = str(meta.get("owner") or "—").replace("|", "\\|")
            worktree = str(meta.get("worktree") or "—").replace("|", "\\|")
            lines.append("| [{}](items/{}/task.md) | {} | {} | {} | {} | {} | {} | {} |".format(
                item_id, item_id, title, meta.get("priority", "—"), meta.get("type", "—"),
                parent, deps, owner, worktree,
            ))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def refresh_board(items: Optional[Dict[str, Tuple[Dict[str, Any], Path, str]]] = None) -> None:
    GH_D.mkdir(parents=True, exist_ok=True)
    if items is None:
        items = load_items()
    atomic_write_text(BOARD_FILE, board_text(items))


def get_run_files(item_id: str) -> Tuple[Path, Path]:
    item_dir = ITEMS_D / item_id
    return item_dir / "graph.md", item_dir / "run-state.md"


def parse_node_rows(run_state: str) -> List[Tuple[str, str, str, str, str]]:
    raw = parse_table(run_state, ("Node ID", "Type", "Status", "Attempts", "Evidence"))
    parsed = []
    for row in raw:
        if len(row) < 6:
            continue
        parsed.append((row[0], row[1], row[2].upper(), row[3], row[4]))
    return parsed


def parse_graph_rows(graph: str) -> List[Tuple[str, str, List[str]]]:
    raw = parse_table(graph, ("Node ID", "Type", "Depends on", "Goal"))
    parsed = []
    for row in raw:
        if len(row) < 7:
            raise GHDLError("Graph node rows must define ID, type, dependencies, goal, inputs, outputs, and completion predicate")
        node_id, node_type, deps_text = row[0], row[1], row[2]
        if any(not cell.strip() for cell in (node_id, node_type, row[3], row[4], row[5], row[6])):
            raise GHDLError("Graph node rows must not leave required contract fields blank")
        deps = [] if deps_text in ("—", "-", "", "None") else [value.strip() for value in deps_text.split(",") if value.strip()]
        parsed.append((node_id, node_type, deps))
    return parsed


def parse_gate(run_state: str, gate: str) -> Tuple[str, str]:
    pattern = re.compile(
        r"^-\s*{}:\s*([A-Z_]+)\s*(?:[—-]\s*evidence:\s*(.*))?$".format(re.escape(gate)),
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(run_state)
    if not match:
        return "MISSING", ""
    return match.group(1).upper(), (match.group(2) or "").strip()


def validate_graph_and_state(
    item_id: str, item_meta: Dict[str, Any], item_content: str,
    require_implementation: bool = False, require_done: bool = False,
) -> None:
    graph_path, state_path = get_run_files(item_id)
    graph = require_file(graph_path, "execution graph")
    state = require_file(state_path, "run state")
    graph_rows = parse_graph_rows(graph)
    state_rows = parse_node_rows(state)
    if not graph_rows:
        raise GHDLError("{}: graph.md must contain a populated Node contracts table".format(item_id))
    if not state_rows:
        raise GHDLError("{}: run-state.md must contain a populated Node status table".format(item_id))
    graph_ids = [row[0] for row in graph_rows]
    state_ids = [row[0] for row in state_rows]
    if len(graph_ids) != len(set(graph_ids)):
        raise GHDLError("{}: graph node IDs are not unique".format(item_id))
    if set(graph_ids) != set(state_ids):
        raise GHDLError("{}: graph node table and run-state node table do not match".format(item_id))
    types_by_id = {node_id: node_type for node_id, node_type, _deps in graph_rows}
    for node_id, node_type, deps in graph_rows:
        if node_type not in NODE_TYPES:
            raise GHDLError("{}: node {} has unknown type {!r}".format(item_id, node_id, node_type))
        unknown = [dep for dep in deps if dep not in types_by_id]
        if unknown:
            raise GHDLError("{}: node {} has unknown dependencies {}".format(item_id, node_id, ", ".join(unknown)))
    node_deps = {node_id: deps for node_id, _node_type, deps in graph_rows}
    visiting, visited = set(), set()

    def visit_node(node: str) -> None:
        if node in visiting:
            raise GHDLError("{}: execution graph contains a cycle at {}".format(item_id, node))
        if node in visited:
            return
        visiting.add(node)
        for dep in node_deps[node]:
            visit_node(dep)
        visiting.remove(node)
        visited.add(node)

    for node_id in node_deps:
        visit_node(node_id)
    required_types = {"inspect", "implement", "verify", "review"}
    missing_types = required_types - set(types_by_id.values())
    if missing_types:
        raise GHDLError("{}: graph is missing required node types: {}".format(item_id, ", ".join(sorted(missing_types))))
    state_by_id = {row[0]: row for row in state_rows}
    for node_id, _node_type, deps in graph_rows:
        row = state_by_id[node_id]
        graph_type = types_by_id[node_id]
        if row[1] != graph_type:
            raise GHDLError("{}: node type mismatch for {} (graph={}, state={})".format(item_id, node_id, graph_type, row[1]))
        if row[2] not in NODE_STATUSES:
            raise GHDLError("{}: invalid status {!r} for node {}".format(item_id, row[2], node_id))
        try:
            attempts = int(row[3])
        except ValueError:
            raise GHDLError("{}: attempts for node {} must be an integer".format(item_id, node_id))
        if attempts < 0 or attempts > 3:
            raise GHDLError("{}: node {} has invalid attempts {}; maximum is 3".format(item_id, node_id, attempts))
        if row[2] in ("RUNNING", "PASS") and attempts < 1:
            raise GHDLError("{}: node {} must record an attempt before RUNNING/PASS".format(item_id, node_id))
        if row[2] == "PASS" and not row[4]:
            raise GHDLError("{}: node {} cannot be PASS without evidence".format(item_id, node_id))
        if row[2] in ("READY", "RUNNING", "PASS"):
            unmet = [dep for dep in deps if state_by_id[dep][2] != "PASS"]
            if unmet:
                raise GHDLError("{}: node {} is {} before dependencies PASS: {}".format(
                    item_id, node_id, row[2], ", ".join(unmet),
                ))
    if require_implementation:
        gate_status, gate_evidence = parse_gate(state, "Implementation")
        if gate_status != "PASS" or not gate_evidence:
            raise GHDLError("{}: Implementation gate must be PASS with evidence before entering VERIFY".format(item_id))
        for node_id, node_type, _deps in graph_rows:
            if node_type not in ("verify", "review"):
                row = state_by_id[node_id]
                if row[2] != "PASS" or not row[4]:
                    raise GHDLError("{}: pre-verification node {} must be PASS with evidence".format(item_id, node_id))
    if require_done:
        for gate in ("Implementation", "Verification", "Review"):
            gate_status, evidence = parse_gate(state, gate)
            if gate_status != "PASS" or not evidence:
                raise GHDLError("{}: {} gate must be PASS with evidence before DONE".format(item_id, gate))
        final_match = re.search(r"^-\s*Final status:\s*(\w+)\s*$", state, re.MULTILINE | re.IGNORECASE)
        if not final_match or final_match.group(1).upper() != "DONE":
            raise GHDLError("{}: run-state Final status must be DONE".format(item_id))
        for node_id, _node_type, _deps in graph_rows:
            row = state_by_id[node_id]
            if row[2] != "PASS" or not row[4]:
                raise GHDLError("{}: node {} must be PASS with evidence before DONE".format(item_id, node_id))
        criteria = parse_acceptance(item_content)
        if not criteria:
            raise GHDLError("{}: work item has no non-empty acceptance criteria".format(item_id))
        unchecked = [ac_id for ac_id, checked, _text in criteria if not checked]
        if unchecked:
            raise GHDLError("{}: acceptance criteria are not checked: {}".format(item_id, ", ".join(unchecked)))
        evidence_rows = parse_table(state, ("Criterion ID", "Result", "Evidence"))
        evidence_by_id = {}
        for row in evidence_rows:
            if len(row) >= 3:
                evidence_by_id[row[0]] = (row[1].upper(), row[2])
        for ac_id, _checked, _text in criteria:
            result, evidence = evidence_by_id.get(ac_id, ("MISSING", ""))
            if result != "PASS" or not evidence:
                raise GHDLError("{}: {} needs PASS acceptance evidence in run-state.md".format(item_id, ac_id))
        check_rows = parse_table(state, ("Check", "Required?", "Exact command", "Result", "Evidence"))
        if not check_rows:
            raise GHDLError("{}: run-state has no verification checks".format(item_id))
        for row in check_rows:
            if len(row) < 5:
                continue
            name, required, command, result, evidence = row[0], row[1].lower(), row[2], row[3].upper(), row[4]
            if required == "yes" and result != "PASS":
                raise GHDLError("{}: required check '{}' must be PASS".format(item_id, name))
            if result not in ("PASS", "N/A"):
                raise GHDLError("{}: check '{}' is {} instead of PASS/N/A".format(item_id, name, result))
            if not command or not evidence:
                raise GHDLError("{}: check '{}' needs an exact procedure/command and evidence or N/A reason".format(item_id, name))


def validate_items(items: Dict[str, Tuple[Dict[str, Any], Path, str]], check_board: bool = True) -> List[str]:
    errors: List[str] = []
    try:
        validate_dependency_graph(items)
    except GHDLError as exc:
        errors.append(str(exc))
    active_by_worktree: Dict[str, int] = {}
    for item_id, (meta, path, content) in items.items():
        if path.parent.name != item_id:
            errors.append("{}: directory must match metadata ID {}".format(relative(path), item_id))
        if not ID_RE.fullmatch(item_id):
            errors.append("{}: ID must use GHDL-YYYYMMDD-XXXXXXXX format (legacy numeric IDs are also accepted)".format(item_id))
        for field in ("title", "type", "priority", "status", "created", "updated", "depends_on"):
            if field not in meta:
                errors.append("{}: missing metadata field '{}'".format(item_id, field))
        if not isinstance(meta.get("title"), str) or not meta.get("title", "").strip():
            errors.append("{}: title must be a non-empty string".format(item_id))
        else:
            first_heading = next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), None)
            if first_heading != meta.get("title"):
                errors.append("{}: first Markdown heading must match metadata title".format(item_id))
        if meta.get("type") not in ITEM_TYPES:
            errors.append("{}: invalid type {!r}".format(item_id, meta.get("type")))
        if meta.get("priority") not in PRIORITIES:
            errors.append("{}: invalid priority {!r}".format(item_id, meta.get("priority")))
        status = meta.get("status")
        if status not in STATUSES:
            errors.append("{}: invalid status {!r}".format(item_id, status))
        if status in ACTIVE_STATUSES:
            worktree = meta.get("worktree")
            if not isinstance(worktree, str) or not worktree.strip():
                errors.append("{}: active items must record their worktree/branch".format(item_id))
            else:
                active_by_worktree[worktree] = active_by_worktree.get(worktree, 0) + 1
        if status in ("READY", "IN_PROGRESS", "VERIFY", "DONE"):
            criteria = parse_acceptance(content)
            if not criteria:
                errors.append("{}: READY-or-later items need at least one non-empty AC-N acceptance criterion".format(item_id))
            elif len({ac_id for ac_id, _checked, _text in criteria}) != len(criteria):
                errors.append("{}: acceptance criterion IDs must be unique".format(item_id))
            for dep in item_dependencies(meta):
                dep_status = dependency_status(dep, items)
                if dep_status != "DONE":
                    errors.append("{}: dependency {} is not DONE (status: {})".format(item_id, dep, dep_status or "UNKNOWN"))
        if status == "DONE":
            criteria = parse_acceptance(content)
            if any(not checked for _ac_id, checked, _text in criteria):
                errors.append("{}: DONE item has unchecked acceptance criteria".format(item_id))
        if status in ("IN_PROGRESS", "VERIFY", "DONE"):
            try:
                validate_graph_and_state(
                    item_id, meta, content,
                    require_implementation=(status in ("VERIFY", "DONE")),
                    require_done=(status == "DONE"),
                )
            except GHDLError as exc:
                errors.append(str(exc))
    for worktree, active_count in active_by_worktree.items():
        if active_count > WIP_LIMIT:
            errors.append("WIP limit exceeded in worktree '{}': {} active items; limit is {}".format(worktree, active_count, WIP_LIMIT))
    if check_board:
        expected = board_text(items)
        if not BOARD_FILE.is_file():
            errors.append("ghdl/BOARD.md is missing; run 'python .ghdl/scripts/ghdl.py board'")
        elif BOARD_FILE.read_text(encoding="utf-8") != expected:
            errors.append("ghdl/BOARD.md is stale; run 'python .ghdl/scripts/ghdl.py board'")
    if not ARCHIVE_INDEX.is_file():
        errors.append("ghdl/archive/INDEX.md is missing; run 'python .ghdl/scripts/ghdl.py init'")
    return errors


def copy_template(template_name: str, destination: Path, replacements: Optional[Dict[str, str]] = None) -> bool:
    source = TEMPLATES_D / template_name
    if not source.is_file():
        raise GHDLError("Missing template: {}".format(relative(source)))
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = source.read_text(encoding="utf-8")
    for key, value in (replacements or {}).items():
        content = content.replace("{{" + key + "}}", value)
    atomic_write_text(destination, content)
    return True


def parse_archive_index(content: str) -> Dict[str, str]:
    entries: Dict[str, str] = {}
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        match = INDEX_LINE_RE.fullmatch(line.strip())
        if not match:
            raise GHDLError("Invalid archive INDEX.md entry on line {}: {!r}".format(line_number, line))
        item_id, title = match.group(1), match.group(2).strip()
        if item_id in entries and entries[item_id] != title:
            raise GHDLError("Duplicate archive INDEX.md entry for {}".format(item_id))
        entries[item_id] = title
    return entries


def archive_index_text(entries: Dict[str, str]) -> str:
    return "".join("{} {}\n".format(item_id, entries[item_id]) for item_id in sorted(entries))


def update_archive_index(additions: Optional[Dict[str, str]] = None, removals: Optional[Sequence[str]] = None) -> str:
    ARCHIVE_D.mkdir(parents=True, exist_ok=True)
    original = ARCHIVE_INDEX.read_text(encoding="utf-8") if ARCHIVE_INDEX.is_file() else ""
    entries = parse_archive_index(original)
    for item_id in removals or []:
        entries.pop(item_id, None)
    for item_id, title in (additions or {}).items():
        clean_title = " ".join(str(title).split())
        if not clean_title:
            raise GHDLError("Cannot add {} to archive INDEX.md without a title".format(item_id))
        entries[item_id] = clean_title
    atomic_write_text(ARCHIVE_INDEX, archive_index_text(entries))
    return original


def migrate_legacy_layout() -> int:
    """Move legacy items/*.md and runs/<ID> into items/<ID>/ without overwriting."""
    ITEMS_D.mkdir(parents=True, exist_ok=True)
    legacy_item_files = sorted(ITEMS_D.glob("*.md"))
    legacy_run_dirs = [path for path in LEGACY_RUNS_D.iterdir() if path.is_dir()] if LEGACY_RUNS_D.is_dir() else []
    operations: List[Tuple[Path, Path]] = []
    item_ids_seen = set()

    for legacy_file in legacy_item_files:
        metadata, _content = read_metadata(legacy_file)
        item_id = metadata.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise GHDLError("{} has no valid item ID; migration stopped without moving files".format(relative(legacy_file)))
        if legacy_file.stem != item_id:
            raise GHDLError("Legacy filename {} does not match metadata ID {}".format(legacy_file.name, item_id))
        if item_id in item_ids_seen:
            raise GHDLError("Duplicate legacy work-item ID: {}".format(item_id))
        item_ids_seen.add(item_id)
        target_dir = ITEMS_D / item_id
        if target_dir.exists():
            raise GHDLError("Migration conflict: {} already exists".format(relative(target_dir)))
        operations.append((legacy_file, target_dir / "task.md"))
        run_dir = LEGACY_RUNS_D / item_id
        if run_dir.is_dir():
            for source in sorted(run_dir.rglob("*")):
                if source.is_file():
                    rel = source.relative_to(run_dir)
                    operations.append((source, target_dir / rel))

    for run_dir in legacy_run_dirs:
        if run_dir.name not in item_ids_seen and not (ITEMS_D / run_dir.name / "task.md").is_file():
            raise GHDLError("Orphan legacy run directory {}; no matching work item exists".format(relative(run_dir)))
        if run_dir.name not in item_ids_seen:
            target_dir = ITEMS_D / run_dir.name
            for source in sorted(run_dir.rglob("*")):
                if source.is_file():
                    rel = source.relative_to(run_dir)
                    operations.append((source, target_dir / rel))

    planned_destinations = set()
    for source, destination in operations:
        if destination in planned_destinations or destination.exists():
            raise GHDLError("Migration conflict: destination {} already exists".format(relative(destination)))
        planned_destinations.add(destination)

    moved: List[Tuple[Path, Path]] = []
    try:
        for source, destination in operations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append((source, destination))
    except Exception:
        for source, destination in reversed(moved):
            source.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                shutil.move(str(destination), str(source))
        raise

    if LEGACY_RUNS_D.is_dir():
        for directory in sorted((p for p in LEGACY_RUNS_D.rglob("*") if p.is_dir()), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            LEGACY_RUNS_D.rmdir()
        except OSError:
            pass
    old_board = GH_D / "board.md"
    if old_board.is_file() and not BOARD_FILE.exists():
        old_board.rename(BOARD_FILE)
    return len(legacy_item_files)


def command_init(_args: argparse.Namespace) -> None:
    GH_D.mkdir(parents=True, exist_ok=True)
    ITEMS_D.mkdir(parents=True, exist_ok=True)
    ARCHIVE_D.mkdir(parents=True, exist_ok=True)
    migrated = migrate_legacy_layout()
    created = copy_template("product.md", GH_D / "PRODUCT.md")
    if not ARCHIVE_INDEX.exists():
        atomic_write_text(ARCHIVE_INDEX, "")
    items = load_items()
    refresh_board(items)
    print("GHDL project structure ready at ghdl/.")
    print("Product context: {}".format("created from template" if created else "preserved"))
    print("Work items found: {}".format(len(items)))
    if migrated:
        print("Migrated legacy flat work items: {}".format(migrated))


def command_migrate(_args: argparse.Namespace) -> None:
    GH_D.mkdir(parents=True, exist_ok=True)
    ITEMS_D.mkdir(parents=True, exist_ok=True)
    ARCHIVE_D.mkdir(parents=True, exist_ok=True)
    migrated = migrate_legacy_layout()
    if not ARCHIVE_INDEX.exists():
        atomic_write_text(ARCHIVE_INDEX, "")
    if not (GH_D / "PRODUCT.md").exists():
        copy_template("product.md", GH_D / "PRODUCT.md")
    items = load_items()
    refresh_board(items)
    print("Migration complete. Converted {} legacy item(s).".format(migrated))
    print("Active work items: {}".format(len(items)))


def command_new(args: argparse.Namespace) -> None:
    if not args.title.strip() or "\n" in args.title or "\r" in args.title:
        raise GHDLError("--title must be a non-empty single line")
    if not GH_D.exists():
        raise GHDLError("ghdl/ does not exist; run 'python .ghdl/scripts/ghdl.py init' first")
    items = load_items()
    parent = args.parent
    deps = [value.strip() for value in args.depends_on.split(",") if value.strip()] if args.depends_on else []
    for ref in ([parent] if parent else []) + deps:
        if ref not in items:
            raise GHDLError("Unknown active parent/dependency item: {}".format(ref))
    def allocate_id() -> str:
        # Avoid blocking on OS entropy: the timestamp + process ID + repository path
        # provide a collision-resistant seed across concurrent helper processes.
        seed = "{}:{}:{}".format(ROOT.resolve(), os.getpid(), time.time_ns())
        suffix = uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:8].upper()
        return "GHDL-{}-{}".format(today().replace("-", ""), suffix)

    item_id = allocate_id()
    while item_id in items or (ITEMS_D / item_id).exists() or (ARCHIVE_D / item_id).exists():
        item_id = allocate_id()
    destination_dir = ITEMS_D / item_id
    destination = destination_dir / "task.md"
    metadata = {
        "id": item_id,
        "title": args.title.strip(),
        "type": args.type,
        "priority": args.priority,
        "status": "BACKLOG",
        "parent": parent,
        "depends_on": deps,
        "owner": None,
        "worktree": None,
        "blocked_reason": None,
        "resume_status": None,
        "cancel_reason": None,
        "created": today(),
        "updated": today(),
    }
    template = require_file(TEMPLATES_D / "work-item.md", "work-item template")
    if "{{METADATA}}" not in template:
        raise GHDLError("work-item.md template must contain {{METADATA}}")
    content = template.replace("{{METADATA}}", json.dumps(metadata, ensure_ascii=False, indent=2)).replace("{{TITLE}}", args.title.strip())
    destination_dir.mkdir(parents=True, exist_ok=False)
    atomic_write_text(destination, content)
    refresh_board()
    print("Created {}: {}".format(item_id, args.title.strip()))
    print("Edit {} and define measurable acceptance criteria before moving it to READY.".format(relative(destination)))


def ensure_dependencies_done(metadata: Dict[str, Any], items: Dict[str, Tuple[Dict[str, Any], Path, str]]) -> None:
    pending = [dep for dep in item_dependencies(metadata) if dependency_status(dep, items) != "DONE"]
    if pending:
        raise GHDLError("Dependencies must be DONE first: {}".format(", ".join(pending)))


def ensure_ready_content(content: str) -> None:
    if not parse_acceptance(content):
        raise GHDLError("Add at least one non-empty acceptance criterion (for example '- [ ] AC-1: ...') before READY")


def create_run_artifacts(item_id: str) -> None:
    item_dir = ITEMS_D / item_id
    graph_path, state_path = get_run_files(item_id)
    if item_dir.exists() and graph_path.exists() != state_path.exists():
        raise GHDLError("{} has incomplete existing run artifacts; inspect them manually. Nothing was overwritten.".format(relative(item_dir)))
    if graph_path.exists() and state_path.exists():
        print("Preserved existing run artifacts for {}".format(item_id))
        return
    item_dir.mkdir(parents=True, exist_ok=True)
    replacements = {"ITEM_ID": item_id, "DATE": today()}
    copy_template("graph.md", graph_path, replacements)
    copy_template("run-state.md", state_path, replacements)
    print("Created execution artifacts in {}".format(relative(item_dir)))


def command_transition(args: argparse.Namespace) -> None:
    items = load_items()
    if args.item_id not in items:
        raise GHDLError("Unknown item ID: {}".format(args.item_id))
    metadata, path, content = items[args.item_id]
    current, target = metadata.get("status"), args.status
    if current not in ALLOWED_TRANSITIONS:
        raise GHDLError("{} has invalid current status {!r}".format(args.item_id, current))
    if target not in ALLOWED_TRANSITIONS[current]:
        raise GHDLError("Illegal transition {} -> {} for {}".format(current, target, args.item_id))
    original_metadata = dict(metadata)
    reason = (args.reason or "").strip()
    if target in ("BLOCKED", "CANCELLED") and not reason:
        raise GHDLError("A non-empty --reason is required when moving an item to {}".format(target))
    if current == "BLOCKED" and target != "CANCELLED" and not reason:
        raise GHDLError("A non-empty --reason explaining blocker resolution is required")
    if target == "READY":
        ensure_ready_content(content)
        ensure_dependencies_done(metadata, items)
        if current == "BLOCKED" and metadata.get("resume_status") not in (None, "BACKLOG", "READY"):
            raise GHDLError("This blocked item must resume to its recorded state: {}".format(metadata.get("resume_status")))
    if target == "IN_PROGRESS":
        ensure_ready_content(content)
        ensure_dependencies_done(metadata, items)
        worktree_key = current_worktree_key(args.worktree)
        active_others = [
            item_id for item_id, (other_meta, _other_path, _other_content) in items.items()
            if item_id != args.item_id and other_meta.get("status") in ACTIVE_STATUSES
            and other_meta.get("worktree") == worktree_key
        ]
        if active_others:
            raise GHDLError("WIP limit is {} in worktree '{}'. Active item(s): {}".format(WIP_LIMIT, worktree_key, ", ".join(active_others)))
        if current == "BLOCKED" and metadata.get("resume_status") != "IN_PROGRESS":
            raise GHDLError("Blocked item must resume to its recorded state: {}".format(metadata.get("resume_status")))
        create_run_artifacts(args.item_id)
    if target == "VERIFY":
        validate_graph_and_state(args.item_id, metadata, content, require_implementation=True)
    if target == "DONE":
        validate_graph_and_state(args.item_id, metadata, content, require_implementation=True, require_done=True)
    if current == "BLOCKED" and target != "CANCELLED":
        expected = metadata.get("resume_status")
        if target != expected:
            raise GHDLError("Blocked item must return to its recorded previous state: {}".format(expected))
        metadata["blocked_reason"] = None
        metadata["resume_status"] = None
    elif target == "BLOCKED":
        metadata["resume_status"] = current
        metadata["blocked_reason"] = reason
    elif target == "CANCELLED":
        metadata["cancel_reason"] = reason
    metadata["status"] = target
    metadata["updated"] = today()
    if target in ACTIVE_STATUSES:
        metadata["worktree"] = current_worktree_key(args.worktree)
    if target == "IN_PROGRESS" and not metadata.get("owner"):
        metadata["owner"] = "agent"
    write_metadata(path, metadata, content)
    refresh_board()
    updated_items = load_items()
    errors = validate_items(updated_items, check_board=True)
    if errors:
        metadata.clear()
        metadata.update(original_metadata)
        write_metadata(path, metadata, content)
        refresh_board()
        raise GHDLError("Transition validation failed; item status was restored.\n- " + "\n- ".join(errors))
    print("{}: {} -> {}".format(args.item_id, current, target))
    if reason:
        print("Reason: {}".format(reason))


def archive_blockers(item_id: str, metadata: Dict[str, Any], items: Dict[str, Tuple[Dict[str, Any], Path, str]]) -> List[str]:
    """A task is eligible iff every task connected by depends_on is terminal."""
    blockers: List[str] = []
    for dependency_id in item_dependencies(metadata):
        status = dependency_status(dependency_id, items)
        if status not in TERMINAL_STATUSES:
            blockers.append("depends on {} (status: {})".format(dependency_id, status or "UNKNOWN"))
    for other_id, (other_meta, _other_path, _other_content) in items.items():
        if other_id == item_id:
            continue
        if item_id in item_dependencies(other_meta) and other_meta.get("status") not in TERMINAL_STATUSES:
            blockers.append("required by {} (status: {})".format(other_id, other_meta.get("status", "UNKNOWN")))
    return blockers


def command_archive(_args: argparse.Namespace) -> None:
    items = load_items()
    eligible: Dict[str, Tuple[Dict[str, Any], Path, str]] = {}
    skipped: Dict[str, List[str]] = {}
    for item_id, record in sorted(items.items()):
        blockers = archive_blockers(item_id, record[0], items)
        if blockers:
            skipped[item_id] = blockers
        else:
            eligible[item_id] = record
    if not eligible:
        print("No tasks eligible for archiving.")
    moves: List[Tuple[Path, Path]] = []
    for item_id in eligible:
        source = ITEMS_D / item_id
        destination = ARCHIVE_D / item_id
        if destination.exists():
            raise GHDLError("Archive destination already exists: {}".format(relative(destination)))
        moves.append((source, destination))

    original_index = ARCHIVE_INDEX.read_text(encoding="utf-8") if ARCHIVE_INDEX.is_file() else ""
    index_entries = parse_archive_index(original_index)
    additions: Dict[str, str] = {}
    for item_id, record in eligible.items():
        title = record[0].get("title")
        if not isinstance(title, str) or not title.strip():
            raise GHDLError("{} has no valid title; cannot update archive INDEX.md".format(item_id))
        additions[item_id] = title
    index_entries.update(additions)
    moved: List[Tuple[Path, Path]] = []
    try:
        ARCHIVE_D.mkdir(parents=True, exist_ok=True)
        for source, destination in moves:
            shutil.move(str(source), str(destination))
            moved.append((source, destination))
        atomic_write_text(ARCHIVE_INDEX, archive_index_text(index_entries))
        active_items = load_items()
        refresh_board(active_items)
    except Exception:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        atomic_write_text(ARCHIVE_INDEX, original_index)
        try:
            refresh_board(load_items())
        except Exception:
            pass
        raise

    for item_id, record in sorted(eligible.items()):
        print("ARCHIVED {} — {}".format(item_id, record[0].get("title", "(untitled)")))
    for item_id, reasons in sorted(skipped.items()):
        print("SKIPPED {} — {}".format(item_id, "; ".join(reasons)))
    print("Archived: {} | Skipped: {}".format(len(eligible), len(skipped)))


def command_restore(args: argparse.Namespace) -> None:
    item_id = args.item_id
    source = ARCHIVE_D / item_id
    destination = ITEMS_D / item_id
    if not (source / "task.md").is_file():
        raise GHDLError("Archived task not found: {}".format(item_id))
    if destination.exists():
        raise GHDLError("Active task already exists: {}".format(item_id))
    metadata, _content = read_metadata(source / "task.md")
    if metadata.get("id") != item_id:
        raise GHDLError("Archived task directory and metadata ID do not match for {}".format(item_id))
    original_index = ARCHIVE_INDEX.read_text(encoding="utf-8") if ARCHIVE_INDEX.is_file() else ""
    entries = parse_archive_index(original_index)
    entries.pop(item_id, None)
    moved = False
    try:
        ITEMS_D.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        moved = True
        atomic_write_text(ARCHIVE_INDEX, archive_index_text(entries))
        refresh_board()
    except Exception:
        if moved and destination.exists() and not source.exists():
            shutil.move(str(destination), str(source))
        atomic_write_text(ARCHIVE_INDEX, original_index)
        raise
    print("RESTORED {} — {}".format(item_id, metadata.get("title", "(untitled)")))


def command_board(_args: argparse.Namespace) -> None:
    items = load_items()
    refresh_board(items)
    print("Regenerated ghdl/BOARD.md ({} work items).".format(len(items)))


def command_validate(_args: argparse.Namespace) -> None:
    items = load_items()
    errors = validate_items(items, check_board=True)
    if errors:
        print("GHDL validation FAILED:", file=sys.stderr)
        for error in errors:
            print("- " + error, file=sys.stderr)
        raise GHDLError("{} validation error(s)".format(len(errors)))
    print("GHDL validation PASS")
    active: Dict[str, int] = {}
    for metadata, _path, _content in items.values():
        if metadata.get("status") in ACTIVE_STATUSES:
            key = metadata.get("worktree") or "(missing)"
            active[key] = active.get(key, 0) + 1
    print("Work items: {} | Active worktrees: {}".format(len(items), len(active)))
    for key, count in sorted(active.items()):
        print("- {}: {} / {}".format(key, count, WIP_LIMIT))


def command_next(_args: argparse.Namespace) -> None:
    items = load_items()
    errors = validate_items(items, check_board=True)
    if errors:
        raise GHDLError("Project state is invalid; run validate and fix errors before pulling work:\n- " + "\n- ".join(errors))
    candidates = []
    for metadata, path, _content in items.values():
        if metadata.get("status") == "READY" and all(dependency_status(dep, items) == "DONE" for dep in item_dependencies(metadata)):
            candidates.append((metadata, path))
    candidates.sort(key=lambda pair: (PRIORITIES.index(pair[0]["priority"]), pair[0]["id"]))
    current_key = current_worktree_key()
    active_here = [
        item_id for item_id, (metadata, _path, _content) in items.items()
        if metadata.get("status") in ACTIVE_STATUSES and metadata.get("worktree") == current_key
    ]
    if active_here:
        print("WIP slot in worktree '{}' is occupied by {}.".format(current_key, ", ".join(active_here)))
        return
    if not candidates:
        print("No READY items available. Refine the next useful BACKLOG item or resolve blockers.")
        return
    print("READY items (priority order):")
    for metadata, path in candidates:
        print("- {} [{}] {} ({})".format(metadata["id"], metadata["priority"], metadata["title"], relative(path)))



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GHDL Continuous Flow project-state helper")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="initialize project files and migrate the legacy layout if found")
    init_parser.set_defaults(func=command_init)

    migrate_parser = sub.add_parser("migrate", help="move legacy items/*.md and runs/<ID>/ into items/<ID>/")
    migrate_parser.set_defaults(func=command_migrate)

    new_parser = sub.add_parser("new", help="create a BACKLOG work item from the template")
    new_parser.add_argument("--title", required=True)
    new_parser.add_argument("--type", choices=ITEM_TYPES, default="feature")
    new_parser.add_argument("--priority", choices=PRIORITIES, default="P2")
    new_parser.add_argument("--parent")
    new_parser.add_argument("--depends-on", help="comma-separated prerequisite item IDs")
    new_parser.set_defaults(func=command_new)

    transition_parser = sub.add_parser("transition", help="perform a guarded work-item state transition")
    transition_parser.add_argument("item_id")
    transition_parser.add_argument("status", choices=STATUSES)
    transition_parser.add_argument("--reason")
    transition_parser.add_argument("--worktree", help="override detected Git branch/worktree key")
    transition_parser.set_defaults(func=command_transition)

    archive_parser = sub.add_parser("archive", help="archive every item whose dependency relationships are terminal")
    archive_parser.set_defaults(func=command_archive)

    restore_parser = sub.add_parser("restore", help="restore one archived item by ID")
    restore_parser.add_argument("item_id")
    restore_parser.set_defaults(func=command_restore)

    board_parser = sub.add_parser("board", help="regenerate the Kanban board from active item metadata")
    board_parser.set_defaults(func=command_board)

    validate_parser = sub.add_parser("validate", help="validate active items, dependencies, WIP, run gates, and board")
    validate_parser.set_defaults(func=command_validate)

    next_parser = sub.add_parser("next", help="list READY items whose dependencies are DONE")
    next_parser.set_defaults(func=command_next)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except GHDLError as exc:
        print("GHDL ERROR: {}".format(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print("GHDL I/O ERROR: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
