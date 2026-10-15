import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import audit_participant_coverage as a


def put(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class CoverageTests(unittest.TestCase):
    def fixture(self, root):
        project, source, excluded = root / "project", root / "source", root / "excluded"
        for p in (project / "bids", project / "derivatives", source, excluded):
            p.mkdir(parents=True)
        put(project / "bids/participants.tsv", "participant_id\tage\tsex\nsub-10001\t40\tM\n")
        put(project / "bids/.heudiconv/10001/ses-01/info/dicominfo_ses-01.tsv", "patient_age\tpatient_sex\n040Y\tM\n")
        put(source / "Smith-SRA-10002/inner/scans/1-localizer/a.dcm")
        put(excluded / "Smith-SRA-10003/inner/a.dcm")
        put(project / "bids/sub-10003/ses-01/func/old_bold.nii.gz")
        put(project / "bids/sub-10004/ses-01/anat/anat_T1w.nii.gz")
        put(project / "derivatives/fmriprep/sub-10005/ses-01/func/bold.nii.gz")
        put(source / "10006/Smith-SRA-10006/a.dcm")
        put(source / "Smith-SRA-10007-2-socialdoors/a.IMA")
        put(source / "Smith-SRA-10008/scan.zip")
        put(project / "bids/.heudiconv/10009/ses-01/info/dicominfo_ses-01.tsv", "patient_age\tpatient_sex\n050Y\tF\n051Y\tF\n")
        put(project / "derivatives/source_repairs/old/sub-10010/old.nii.gz")
        (source / "unmatched-folder").mkdir()
        return project, source, excluded

    def test_discovery_and_exclusion_priority(self):
        with tempfile.TemporaryDirectory() as d:
            project, source, excluded = self.fixture(Path(d))
            with patch.object(a, "REQUESTED", ["10003", "10011"]):
                report = a.collect(project, source, excluded)
            rows = {r["subject"]: r for r in report["subjects"]}
            expected = {"10001": "represented", "10002": "raw_present_conversion_review",
                        "10003": "intentional_source_exclusion", "10004": "bids_missing_participant_row",
                        "10005": "derivatives_without_bids_review", "10006": "raw_present_conversion_review",
                        "10007": "raw_present_conversion_review", "10008": "source_folder_without_recognized_dicoms",
                        "10009": "conversion_inventory_without_images", "10011": "no_local_imaging_evidence"}
            self.assertEqual({s: r["status"] for s, r in rows.items()}, expected)
            self.assertEqual(rows["10002"]["production_raw"]["localizer_path_files"], 1)
            self.assertEqual(rows["10009"]["baseline_source"], "invalid_or_conflicting")
            self.assertEqual(report["unmatched_source_directories"], 1)
            self.assertNotIn("patient_age", json.dumps(report))

    def test_missing_root_and_walk_error_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            project, source, excluded = self.fixture(Path(d))
            with self.assertRaises(ValueError):
                a.collect(project, source, excluded / "missing")
            with patch.object(a.os, "walk", side_effect=PermissionError), self.assertRaises(PermissionError):
                a.collect(project, source, excluded)

    def test_excluded_table_row_and_duplicates_are_not_represented(self):
        row = dict(source_excluded=True, table_rows=1)
        self.assertEqual(a.classify(row), "excluded_but_in_table")
        row.update(source_excluded=False, table_rows=2)
        self.assertEqual(a.classify(row), "duplicate_table_rows")

    def test_cli_private_output_and_public_aggregate_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            project, source, excluded = self.fixture(root)
            target = project / "work/coverage"
            args = ["audit", "--project-root", str(project), "--source-root", str(source),
                    "--exclusions-root", str(excluded), "--private-dir", str(target)]
            before = (project / "bids/participants.tsv").read_bytes()
            with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(a.main(), 0)
                self.assertNotIn("10003", output.getvalue())
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertEqual((project / "bids/participants.tsv").read_bytes(), before)
            self.assertTrue((target / "review.tsv").is_file())
            with patch.object(sys, "argv", args), self.assertRaises(ValueError):
                a.main()
            args[-1] = str(project / "qc/not-private")
            with patch.object(sys, "argv", args), self.assertRaises(ValueError):
                a.main()


if __name__ == "__main__":
    unittest.main()
