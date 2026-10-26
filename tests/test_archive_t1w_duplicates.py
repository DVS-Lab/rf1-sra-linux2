import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))
SPEC = importlib.util.spec_from_file_location("archive_t1w_duplicates", CODE / "archive_t1w_duplicates.py")
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        expected = {}
        for subject in archive.EXPECTED:
            plain, compressed, _ = archive.paths(self.project, subject)
            plain.parent.mkdir(parents=True)
            payload = (f"synthetic header and data {subject}").encode() * 100
            plain.write_bytes(payload)
            compressed.write_bytes(gzip.compress(payload, mtime=0))
            expected[subject] = hashlib.sha256(payload).hexdigest()
        self.patch = patch.dict(archive.EXPECTED, expected, clear=True)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_preview_then_apply_check_and_repeat(self):
        sentinel = self.project / "settled-exclusions.tsv"
        sentinel.write_text("unchanged")
        gz_original = {s: archive.paths(self.project, s)[1].read_bytes() for s in archive.EXPECTED}
        archive.execute(self.project, "preview")
        self.assertFalse((self.project / archive.ARCHIVE).exists())
        archive.execute(self.project, "apply")
        archive.execute(self.project, "check")
        archive.execute(self.project, "apply")
        for subject in archive.EXPECTED:
            plain, compressed, saved = archive.paths(self.project, subject)
            self.assertFalse(plain.exists())
            self.assertEqual(saved.read_bytes(), gzip.decompress(compressed.read_bytes()))
            self.assertEqual(compressed.read_bytes(), gz_original[subject])
        self.assertEqual(sentinel.read_text(), "unchanged")

    def test_second_pair_mismatch_prevents_any_move(self):
        archive.paths(self.project, "12038")[0].write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "Content differs"):
            archive.execute(self.project, "apply")
        self.assertTrue(archive.paths(self.project, "11982")[0].exists())
        self.assertFalse((self.project / archive.ARCHIVE).exists())

    def test_resume_after_first_move(self):
        records = archive.inspect(self.project)
        folder = self.project / archive.ARCHIVE
        folder.mkdir(parents=True)
        archive.save_receipt(folder / "receipt.json", {
            "schema_version": 1, "project": str(self.project), "status": "prepared", "pairs": records,
        })
        plain, _, saved = archive.paths(self.project, "11982")
        saved.parent.mkdir(parents=True)
        plain.rename(saved)
        archive.execute(self.project, "apply")
        archive.execute(self.project, "check")
        self.assertEqual(json.loads((folder / "receipt.json").read_text())["status"], "complete")

    def test_check_detects_retained_gzip_change(self):
        archive.execute(self.project, "apply")
        compressed = archive.paths(self.project, "11982")[1]
        payload = gzip.decompress(compressed.read_bytes())
        compressed.write_bytes(gzip.compress(payload, mtime=42))
        with self.assertRaisesRegex(ValueError, "Retained compressed file changed"):
            archive.execute(self.project, "check")

    def test_existing_destination_never_overwritten(self):
        plain, _, saved = archive.paths(self.project, "11982")
        saved.parent.mkdir(parents=True)
        saved.write_bytes(b"do not overwrite")
        with self.assertRaisesRegex(ValueError, "Both source and archive"):
            archive.execute(self.project, "apply")
        self.assertTrue(plain.exists())
        self.assertEqual(saved.read_bytes(), b"do not overwrite")


if __name__ == "__main__":
    unittest.main()
