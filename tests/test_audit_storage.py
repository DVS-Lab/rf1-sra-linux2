import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import audit_storage as audit


class StorageInventoryTests(unittest.TestCase):
    def test_known_outputs_have_distinct_buckets(self):
        pairs = {
            "derivatives/tedana-audit/cohort-pca-v1/benchmark/x.nii.gz": "derivatives / TEDANA cohort PCA",
            "derivatives/smoothness-evaluation-6mm-v1/runs/x.nii.gz": "derivatives / smoothing variants",
            "derivatives/fsl-no-tedana-wave1/x.nii.gz": "derivatives / fsl-no-tedana-wave1",
            "derivatives/fsl/sub-00000/ses-01/x.feat/stats/cope4.nii.gz": "derivatives / fsl / first levels",
            "derivatives/fsl/L3-act/x.gfeat/stats/cope4.nii.gz": "derivatives / fsl / group analyses",
            "work/reviewed-install-archive-v1/originals/x": "work / repair archives",
            "work/reviewed-source-repairs-v3/x": "work / repair stages",
            "work/wave1-randomise.abc123/results/x": "work / paired/group analysis inputs",
            "work/stage1-linux2.abc123/audit/x": "work / batch plans and runtime",
        }
        for value, expected in pairs.items():
            with self.subTest(value=value):
                self.assertEqual(audit.project_bucket(Path(value)), expected)
        self.assertEqual(audit.artifact_kind(Path("x_desc-optcom_bold.nii.gz"), 10),
                         "optimally combined BOLD")
        self.assertEqual(audit.artifact_kind(Path("x_echo-2_desc-preproc_bold.nii.gz"), 10),
                         "preprocessed echoes")
        self.assertEqual(audit.artifact_kind(Path("x_desc-smoothToFWHM6_bold.nii.gz"), 10),
                         "target-smoothed BOLD")

    def test_bytes_links_protected_snapshots_and_no_input_changes(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            main = root / "rf1-sra-linux2"
            work = main / "work"
            work.mkdir(parents=True)
            raw = work / "sample_desc-optcom_bold.nii.gz"
            raw.write_bytes(b"data")
            other = root / "rf1-sra-socdoors"
            other.mkdir()
            os.link(raw, other / "hard.nii.gz")
            (other / "external").symlink_to(work, target_is_directory=True)
            (other / "broken").symlink_to(root / "absent")
            snapshot = other / ".zfs" / "snapshot"
            snapshot.mkdir(parents=True)
            (snapshot / "not-live.nii.gz").write_bytes(b"snapshot")
            before = {p: p.lstat().st_mtime_ns for p in root.rglob("*")}
            inv = audit.Inventory()
            inv.walk("main", main, audit.project_bucket)
            inv.walk("other", other, audit.project_bucket)
            inv.walk("absent", root / "absent", audit.project_bucket)
            self.assertEqual(inv.roots["main"].apparent, 4)
            self.assertEqual(inv.roots["main"].allocated, raw.stat().st_blocks * 512)
            self.assertEqual(inv.roots["other"].files, 0)
            self.assertEqual(inv.notes["other", "hard-link aliases not counted twice"], 1)
            self.assertEqual(inv.notes["other", "symlinks not followed"], 2)
            self.assertEqual(inv.notes["absent", "root not present"], 1)
            self.assertEqual(before, {p: p.lstat().st_mtime_ns for p in root.rglob("*")})
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                audit.rows("Project totals", inv.roots)
            self.assertIn("main", buf.getvalue())
            self.assertNotIn(raw.name, buf.getvalue())

    def test_cli_prints_aggregate_rows_only(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            project = root/"projects"/"rf1-sra-socdoors-psychosocial"
            project.mkdir(parents=True)
            (project/"test_subject_identifier.nii.gz").write_bytes(b"x")
            proc = subprocess.run([sys.executable, str(Path(audit.__file__)), "--data-root", str(root)],
                                  capture_output=True, text=True, check=True)
            self.assertIn("rf1-sra-socdoors-psychosocial", proc.stdout)
            self.assertIn("No study files modified.", proc.stdout)
            self.assertNotIn("test_subject_identifier", proc.stdout)


if __name__ == "__main__":
    unittest.main()
