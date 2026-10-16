import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import plan_source_intake as plan


def put(path, value=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


class IntakeTests(unittest.TestCase):
    def setup_tree(self, root):
        project, source, excluded = root / "project", root / "source", root / "excluded"
        for p in (project / "bids", source, excluded):
            p.mkdir(parents=True)
        manifest = root / "manifest.tsv"
        manifest.write_text("subject\tsession\tstatus\tsource_relative\trequired_runs\treason\n")
        return project, source, excluded, manifest

    def dicom(self, source, sub, ses="01"):
        put(plan.source_scan_dir(source, sub if ses == "01" else sub + "-2") / "1-scan/x/DICOM/files/a.dcm")

    def test_new_sessions_existing_and_baseline_guard(self):
        with tempfile.TemporaryDirectory() as d:
            project, source, excluded, manifest = self.setup_tree(Path(d))
            for sub, ses in (("10001", "01"), ("10001", "02"), ("10002", "02"), ("10003", "01")):
                self.dicom(source, sub, ses)
            (project / "bids/sub-10001/ses-01").mkdir(parents=True)
            put(project / "bids/.heudiconv/10001/ses-01/info/dicominfo_ses-01.tsv")
            (excluded / "Smith-SRA-10003").mkdir()
            report = plan.collect(project, source, excluded, manifest)
            actual = {(r["subject"], r["session"]): r["status"] for r in report["sessions"]}
            self.assertEqual(actual, {("10001", "01"): "existing_bids_not_revalidated",
                                      ("10001", "02"): "new_session_candidate",
                                      ("10002", "02"): "baseline_metadata_needed_first"})
            self.assertEqual(report["excluded_production_subjects"], 1)

    def test_special_layouts_unknown_names_and_empty_download(self):
        with tempfile.TemporaryDirectory() as d:
            project, source, excluded, manifest = self.setup_tree(Path(d))
            for sub in ("11891", "12018"):
                self.dicom(source, sub)
            (source / "Smith-SRA-12080").mkdir()
            (source / "Smith-SRA-12081-3").mkdir()
            (excluded / "private-unmatched").mkdir()
            report = plan.collect(project, source, excluded, manifest)
            self.assertEqual([r["status"] for r in report["sessions"]].count("new_session_candidate"), 2)
            self.assertEqual(report["sessions"][-1]["status"], "source_layout_or_download_review")
            self.assertEqual(len(report["unmatched_source_folders"]), 1)
            self.assertEqual(len(report["unmatched_exclusion_folders"]), 1)

    def test_supplemental_not_assigned_new_session(self):
        with tempfile.TemporaryDirectory() as d:
            project, source, excluded, manifest = self.setup_tree(Path(d))
            manifest.write_text(manifest.read_text() + "11116\t02\tactive\tSmith-SRA-11116-2-socialdoors/inner\tdoors:1\treviewed\n")
            put(source / "Smith-SRA-11116-2-socialdoors/inner/scans/a.dcm")
            report = plan.collect(project, source, excluded, manifest)
            self.assertEqual(len(report["supplemental_without_base"]), 1)
            self.assertEqual(report["sessions"], [])
            self.dicom(source, "11116", "02")
            report = plan.collect(project, source, excluded, manifest)
            self.assertEqual(report["supplemental_without_base"], [])
            self.assertEqual(report["sessions"][0]["session"], "02")
            manifest.write_text(manifest.read_text().replace("active", "paused"))
            self.assertEqual(plan.collect(project, source, excluded, manifest)["sessions"][0]["status"], "supplemental_review")

    def test_missing_root_fails(self):
        with tempfile.TemporaryDirectory() as d:
            project, source, excluded, manifest = self.setup_tree(Path(d))
            with self.assertRaises(ValueError):
                plan.collect(project, source, excluded / "missing", manifest)

    def test_cli_no_input_writes_and_private_paths_not_logged(self):
        with tempfile.TemporaryDirectory() as d:
            project, source, excluded, manifest = self.setup_tree(Path(d))
            self.dicom(source, "10001")
            (source / "private-unknown").mkdir()
            out = project / "work/intake"
            args = ["plan", "--project-root", str(project), "--source-root", str(source),
                    "--exclusions-root", str(excluded), "--manifest", str(manifest), "--private-dir", str(out)]
            with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(plan.main(), 0)
            self.assertNotIn("private-unknown", printed.getvalue())
            self.assertIn("10001 | 01 | new_session_candidate", printed.getvalue())
            self.assertEqual(list((project / "bids").iterdir()), [])
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            with patch.object(sys, "argv", args), self.assertRaises(ValueError):
                plan.main()


if __name__ == "__main__":
    unittest.main()
