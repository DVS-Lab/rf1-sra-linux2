import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import sync_published_checkout as syncer

LOG = "logs/records/20261025-094314_reviewed-install-v3.md"


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.writer, self.linux = self.root / "writer", self.root / "linux"
        self.git(self.root, "init", "--initial-branch=main", str(self.writer))
        self.git(self.writer, "config", "user.name", "Test")
        self.git(self.writer, "config", "user.email", "test@example.invalid")
        self.commit("code.py", "old code\n")
        self.commit(".gitignore", "work/\n")
        self.git(self.root, "clone", str(self.writer), str(self.linux))
        self.git(self.linux, "config", "user.name", "Test")
        self.git(self.linux, "config", "user.email", "test@example.invalid")
        self.commit("code.py", "new code\n")
        self.commit(".gitignore", "work/\n/.11935-repair.lock\n/.reviewed-install.lock\n")
        self.commit(LOG, "published log\n")
        self.write(self.linux / LOG, "published log\n")
        self.write(self.linux / ".11935-repair.lock", "")
        self.write(self.linux / ".reviewed-install.lock", "")
        self.git(self.linux, "fetch", "origin")

    @staticmethod
    def git(root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()

    @staticmethod
    def write(path, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    def commit(self, name, contents):
        self.write(self.writer / name, contents)
        self.git(self.writer, "add", name)
        self.git(self.writer, "commit", "-m", "update")

    def run_sync(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return syncer.sync(self.linux, apply=True, processing_stopped=True)

    def test_sync_preserves_logs_locks_and_backup_and_clean_status(self):
        locks = {p: p.stat().st_ino for p in self.linux.glob(".*.lock")}
        archive = self.run_sync()
        self.assertEqual((archive / LOG).read_bytes(), (self.linux / LOG).read_bytes())
        self.assertEqual(self.git(self.linux, "status", "--short"), "")
        self.assertEqual(self.git(self.linux, "rev-parse", "HEAD"), self.git(self.linux, "rev-parse", "origin/main"))
        self.assertEqual((self.linux / "code.py").read_text(), "new code\n")
        for p, inode in locks.items():
            self.assertEqual(p.stat().st_ino, inode)
        self.assertIsNone(self.run_sync())

    def test_preview_preserves_head_and_untracked_log(self):
        head = self.git(self.linux, "rev-parse", "HEAD")
        with contextlib.redirect_stdout(io.StringIO()):
            syncer.sync(self.linux)
        self.assertEqual(self.git(self.linux, "rev-parse", "HEAD"), head)
        self.assertTrue((self.linux / LOG).exists())
        self.assertFalse((self.linux / "work").exists())

    def test_mismatched_record_refused_without_removal(self):
        (self.linux / LOG).write_text("unpublished change")
        with self.assertRaisesRegex(ValueError, "differs from origin"):
            self.run_sync()
        self.assertEqual((self.linux / LOG).read_text(), "unpublished change")

    def test_tracked_and_staged_edits_refused(self):
        (self.linux / "code.py").write_text("user edit")
        with self.assertRaisesRegex(ValueError, "tracked/staged edits"):
            self.run_sync()
        self.git(self.linux, "add", "code.py")
        with self.assertRaisesRegex(ValueError, "tracked/staged edits"):
            self.run_sync()

    def test_divergence_refused(self):
        self.write(self.linux / "local.txt", "local commit")
        self.git(self.linux, "add", "local.txt")
        self.git(self.linux, "commit", "-m", "local")
        with self.assertRaisesRegex(ValueError, "divergent"):
            self.run_sync()

    def test_nonlog_collision_refused(self):
        self.commit("new-code.py", "remote\n")
        self.write(self.linux / "new-code.py", "remote\n")
        self.git(self.linux, "fetch", "origin")
        with self.assertRaisesRegex(ValueError, "not a run record"):
            self.run_sync()

    def test_merge_failure_restores_logs_and_keeps_backup(self):
        original = syncer.git
        def fail(root, *args, **kwargs):
            if args[0] == "merge":
                raise RuntimeError("simulated merge failure")
            return original(root, *args, **kwargs)
        with patch.object(syncer, "git", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "simulated merge"):
                self.run_sync()
        self.assertEqual((self.linux / LOG).read_text(), "published log\n")
        backups = list((self.linux / "work/checkout-sync").glob("*/" + LOG))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), "published log\n")

    def test_processing_confirmation_required(self):
        with self.assertRaisesRegex(ValueError, "processing-stopped"):
            syncer.sync(self.linux, apply=True)
        self.assertTrue((self.linux / LOG).exists())

    def test_unrelated_untracked_files_retained(self):
        self.write(self.linux / "keep.txt", "unrelated")
        self.run_sync()
        self.assertEqual((self.linux / "keep.txt").read_text(), "unrelated")


if __name__ == "__main__":
    unittest.main()
