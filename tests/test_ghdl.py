"""Integration tests for the repository-local GHDL helper."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class GHDLHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(SOURCE_ROOT / ".ghdl", self.root / ".ghdl")
        shutil.copy2(SOURCE_ROOT / "AGENTS.md", self.root / "AGENTS.md")
        self.script = self.root / ".ghdl" / "scripts" / "ghdl.py"

    def tearDown(self):
        self.temp.cleanup()

    def run_ghdl(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(
            result.returncode,
            expected,
            msg="command={!r}\nstdout={}\nstderr={}".format(args, result.stdout, result.stderr),
        )
        return result

    def init(self):
        self.run_ghdl("init")

    def item_dir(self, item_id, area="items"):
        return self.root / "ghdl" / area / item_id

    def new_item(self, title, *extra):
        result = self.run_ghdl("new", "--title", title, *extra)
        item_id = result.stdout.split("Created ", 1)[1].split(":", 1)[0]
        item_path = self.item_dir(item_id) / "task.md"
        text = item_path.read_text(encoding="utf-8")
        text = text.replace(
            "- [ ] AC-1:",
            "- [ ] AC-1: The requested outcome is observable and testable.",
        )
        item_path.write_text(text, encoding="utf-8")
        self.run_ghdl("board")
        return item_id, item_path

    def read_metadata(self, task_path):
        content = task_path.read_text(encoding="utf-8")
        start = content.index("<!-- GHDL_ITEM_BEGIN") + len("<!-- GHDL_ITEM_BEGIN")
        end = content.index("GHDL_ITEM_END -->", start)
        return json.loads(content[start:end].strip()), content

    def write_metadata(self, task_path, metadata, content):
        start = content.index("<!-- GHDL_ITEM_BEGIN") + len("<!-- GHDL_ITEM_BEGIN")
        end = content.index("GHDL_ITEM_END -->", start)
        block = "\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
        content = content[:start] + block + content[end:]
        task_path.write_text(content, encoding="utf-8")

    def set_status(self, item_id, status):
        task_path = self.item_dir(item_id) / "task.md"
        metadata, content = self.read_metadata(task_path)
        metadata["status"] = status
        self.write_metadata(task_path, metadata, content)

    def test_init_creates_new_structure_and_preserves_product(self):
        product = self.root / "ghdl" / "PRODUCT.md"
        product.parent.mkdir(parents=True)
        product.write_text("user-owned product context\n", encoding="utf-8")
        self.init()
        self.assertEqual(product.read_text(encoding="utf-8"), "user-owned product context\n")
        self.assertTrue((self.root / "ghdl" / "BOARD.md").is_file())
        self.assertTrue((self.root / "ghdl" / "archive" / "INDEX.md").is_file())

    def test_adoption_copies_only_framework_assets_and_init_keeps_them_read_only(self):
        framework_before = {
            path.relative_to(self.root / ".ghdl").as_posix(): path.read_bytes()
            for path in (self.root / ".ghdl").rglob("*") if path.is_file()
        }
        agents_before = (self.root / "AGENTS.md").read_bytes()

        self.init()

        framework_after = {
            path.relative_to(self.root / ".ghdl").as_posix(): path.read_bytes()
            for path in (self.root / ".ghdl").rglob("*") if path.is_file()
        }
        self.assertEqual(framework_after, framework_before)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), agents_before)
        self.assertEqual(
            {path.name for path in self.root.iterdir()},
            {"AGENTS.md", ".ghdl", "ghdl"},
        )

    def test_new_item_is_a_directory_with_task_md(self):
        self.init()
        item_id, task_path = self.new_item("An item")
        self.assertTrue(task_path.is_file())
        self.assertTrue(self.item_dir(item_id).is_dir())
        self.assertFalse((self.root / "ghdl" / "items" / (item_id + ".md")).exists())
        self.assertIn("[{}](items/{}/task.md)".format(item_id, item_id),
                      (self.root / "ghdl" / "BOARD.md").read_text(encoding="utf-8"))

    def test_ready_requires_acceptance_criteria(self):
        self.init()
        result = self.run_ghdl("new", "--title", "An item without criteria")
        item_id = result.stdout.split("Created ", 1)[1].split(":", 1)[0]
        self.run_ghdl("transition", item_id, "READY", expected=2)

    def test_dependencies_must_be_done_before_ready(self):
        self.init()
        first, _ = self.new_item("Prerequisite")
        second, _ = self.new_item("Dependent", "--depends-on", first)
        self.run_ghdl("transition", first, "READY")
        self.run_ghdl("transition", second, "READY", expected=2)

    def test_run_artifacts_are_created_inside_item_directory(self):
        self.init()
        item_id, _ = self.new_item("Run artifacts")
        self.run_ghdl("transition", item_id, "READY")
        self.run_ghdl("transition", item_id, "IN_PROGRESS", "--worktree", "agent-a")
        self.assertTrue((self.item_dir(item_id) / "graph.md").is_file())
        self.assertTrue((self.item_dir(item_id) / "run-state.md").is_file())
        self.assertFalse((self.root / "ghdl" / "runs").exists())

    def test_wip_limit_is_per_worktree(self):
        self.init()
        first, _ = self.new_item("First item")
        second, _ = self.new_item("Second item")
        self.run_ghdl("transition", first, "READY")
        self.run_ghdl("transition", second, "READY")
        self.run_ghdl("transition", first, "IN_PROGRESS", "--worktree", "agent-a")
        self.run_ghdl("transition", second, "IN_PROGRESS", "--worktree", "agent-a", expected=2)
        self.run_ghdl("transition", second, "IN_PROGRESS", "--worktree", "agent-b")
        self.run_ghdl("validate")

    def test_node_cannot_pass_before_its_dependencies(self):
        self.init()
        item_id, _ = self.new_item("DAG dependency guard")
        self.run_ghdl("transition", item_id, "READY")
        self.run_ghdl("transition", item_id, "IN_PROGRESS")
        state_path = self.item_dir(item_id) / "run-state.md"
        state = state_path.read_text(encoding="utf-8")
        state = state.replace(
            "| IMPLEMENT | implement | PENDING | 0 | | |",
            "| IMPLEMENT | implement | PASS | 1 | premature evidence | |",
        )
        state_path.write_text(state, encoding="utf-8")
        self.run_ghdl("validate", expected=2)

    def test_archive_moves_all_eligible_directories_and_writes_plain_index(self):
        self.init()
        first, _ = self.new_item("A task with no dependencies")
        second, _ = self.new_item("Another independent task")
        # Candidate status is deliberately non-terminal: eligibility has no separate status gate.
        self.run_ghdl("archive")
        for item_id in (first, second):
            self.assertFalse(self.item_dir(item_id).exists())
            self.assertTrue(self.item_dir(item_id, "archive").is_dir())
            self.assertTrue((self.item_dir(item_id, "archive") / "task.md").is_file())
        index = (self.root / "ghdl" / "archive" / "INDEX.md").read_text(encoding="utf-8")
        self.assertEqual(
            index.splitlines(),
            sorted(["{} A task with no dependencies".format(first), "{} Another independent task".format(second)]),
        )
        self.assertNotIn("[", index)
        board = (self.root / "ghdl" / "BOARD.md").read_text(encoding="utf-8")
        self.assertNotIn(first, board)
        self.assertNotIn(second, board)

    def test_archive_checks_incoming_and_outgoing_dependency_relationships(self):
        self.init()
        prerequisite, _ = self.new_item("Prerequisite")
        dependent, _ = self.new_item("Dependent", "--depends-on", prerequisite)
        blocked_prerequisite, _ = self.new_item("Still required")
        active_dependent, _ = self.new_item("Active dependent", "--depends-on", blocked_prerequisite)

        # The dependency endpoints are terminal for the first pair, so both can move.
        self.set_status(prerequisite, "DONE")
        self.set_status(dependent, "CANCELLED")
        # The second pair remains connected to a non-terminal task and must stay active.
        self.set_status(active_dependent, "BACKLOG")
        self.run_ghdl("board")
        result = self.run_ghdl("archive")

        self.assertTrue(self.item_dir(prerequisite, "archive").is_dir())
        self.assertTrue(self.item_dir(dependent, "archive").is_dir())
        self.assertTrue(self.item_dir(blocked_prerequisite).is_dir())
        self.assertTrue(self.item_dir(active_dependent).is_dir())
        self.assertIn("SKIPPED {}".format(blocked_prerequisite), result.stdout)
        self.assertIn("SKIPPED {}".format(active_dependent), result.stdout)

    def test_archive_uses_cancelled_as_terminal_dependency_status(self):
        self.init()
        cancelled, _ = self.new_item("Cancelled prerequisite")
        dependent, _ = self.new_item("Item depending on cancelled", "--depends-on", cancelled)
        self.set_status(cancelled, "CANCELLED")
        # The dependent is BACKLOG; its link is terminal for archive eligibility.
        self.run_ghdl("board")
        self.run_ghdl("archive")
        # The dependent may be archived because its prerequisite is CANCELLED;
        # the prerequisite itself remains because a BACKLOG task still references it.
        self.assertTrue(self.item_dir(cancelled).is_dir())
        self.assertTrue(self.item_dir(dependent, "archive").is_dir())

    def test_archive_index_is_maintained_by_script_and_restore_removes_entry(self):
        self.init()
        item_id, _ = self.new_item("Restorable task")
        self.run_ghdl("archive")
        index_path = self.root / "ghdl" / "archive" / "INDEX.md"
        self.assertIn("{} Restorable task".format(item_id), index_path.read_text(encoding="utf-8"))
        self.run_ghdl("restore", item_id)
        self.assertTrue(self.item_dir(item_id).is_dir())
        self.assertFalse(self.item_dir(item_id, "archive").exists())
        self.assertNotIn(item_id, index_path.read_text(encoding="utf-8"))

    def test_archive_preserves_all_task_artifacts(self):
        self.init()
        item_id, _ = self.new_item("Full folder archive")
        self.run_ghdl("transition", item_id, "READY")
        self.run_ghdl("transition", item_id, "IN_PROGRESS")
        graph = self.item_dir(item_id) / "graph.md"
        state = self.item_dir(item_id) / "run-state.md"
        graph.write_text("graph evidence preserved\n", encoding="utf-8")
        state.write_text("run evidence preserved\n", encoding="utf-8")
        self.run_ghdl("archive")
        archived = self.item_dir(item_id, "archive")
        self.assertEqual((archived / "graph.md").read_text(encoding="utf-8"), "graph evidence preserved\n")
        self.assertEqual((archived / "run-state.md").read_text(encoding="utf-8"), "run evidence preserved\n")

    def test_migrate_legacy_flat_item_and_run_directory(self):
        self.init()
        item_id = "GHDL-20260101-ABCDEF12"
        legacy_items = self.root / "ghdl" / "items"
        legacy_runs = self.root / "ghdl" / "runs" / item_id
        legacy_runs.mkdir(parents=True)
        metadata = {
            "id": item_id, "title": "Legacy item", "type": "feature", "priority": "P2",
            "status": "BACKLOG", "parent": None, "depends_on": [], "owner": None,
            "worktree": None, "blocked_reason": None, "resume_status": None,
            "cancel_reason": None, "created": "2026-01-01", "updated": "2026-01-01",
        }
        task = "<!-- GHDL_ITEM_BEGIN\n{}\nGHDL_ITEM_END -->\n# Legacy item\n\n## Acceptance criteria\n- [ ] AC-1: Keep the record\n".format(json.dumps(metadata, indent=2))
        (legacy_items / (item_id + ".md")).write_text(task, encoding="utf-8")
        (legacy_runs / "graph.md").write_text("legacy graph\n", encoding="utf-8")
        (legacy_runs / "run-state.md").write_text("legacy state\n", encoding="utf-8")
        self.run_ghdl("migrate")
        destination = self.item_dir(item_id)
        self.assertTrue((destination / "task.md").is_file())
        self.assertEqual((destination / "graph.md").read_text(encoding="utf-8"), "legacy graph\n")
        self.assertEqual((destination / "run-state.md").read_text(encoding="utf-8"), "legacy state\n")
        self.assertFalse((legacy_items / (item_id + ".md")).exists())
        self.assertFalse((self.root / "ghdl" / "runs").exists())

    def test_archive_index_rejects_malformed_existing_lines_without_moving_tasks(self):
        self.init()
        item_id, _ = self.new_item("Index validation")
        index_path = self.root / "ghdl" / "archive" / "INDEX.md"
        index_path.write_text("this is not a valid index line\n", encoding="utf-8")
        self.run_ghdl("archive", expected=2)
        self.assertTrue(self.item_dir(item_id).is_dir())
        self.assertEqual(index_path.read_text(encoding="utf-8"), "this is not a valid index line\n")


if __name__ == "__main__":
    unittest.main()
