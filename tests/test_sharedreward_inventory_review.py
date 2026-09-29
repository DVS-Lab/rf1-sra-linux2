"""Offline linkage never turns an unproven candidate into a source decision."""
import copy
import csv
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import review_sharedreward_inventory as review


def series(uid="PRIVATE-UID", folder="11913"):
    return {"series_uid": uid, "folders": [folder], "image_types": ["M"],
            "fields": {"SeriesNumber": ["25"], "ProtocolName": ["PRIVATE-PROTOCOL"],
                       "StudyInstanceUID": ["PRIVATE-STUDY"]}}


class InventoryReviewTests(unittest.TestCase):
    def conversion_fixture(self, root):
        info = root / ".heudiconv/11913/ses-01/info"
        info.mkdir(parents=True)
        template = ("sub-{subject}/{session}/func/sub-{subject}_{session}_"
                    "task-sharedreward_run-{item:d}_part-mag_bold")
        table = {(template, ("nii.gz",), None): ["25-shared", "29-shared"]}
        edit = info / "11913_ses-01.edit.txt"
        edit.write_text(repr(table))
        seqfile = info / "dicominfo_ses-01.tsv"
        with seqfile.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, delimiter="\t", fieldnames=["series_id", "series_uid", "series_files"])
            writer.writeheader()
            writer.writerows([{"series_id": "25-shared", "series_uid": "PRIVATE-UID", "series_files": 2},
                              {"series_id": "29-shared", "series_uid": "PRIVATE-RUN2", "series_files": 1}])
        filegroup = info / "filegroup_ses-01.json"
        filegroup.write_text(json.dumps({"25-shared": ["PRIVATE-PATH/a", "PRIVATE-PATH/b"],
                                        "29-shared": ["PRIVATE-PATH/c"]}))
        return edit, seqfile, filegroup

    def test_conversion_provenance_disambiguates_same_series_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.conversion_fixture(root)
            sources = [series(), series("OTHER-UID", "11923"), series("PRIVATE-RUN2")]
            status, matches, bad, hashes = review.conversion_match(root, "11913", "1", {"SeriesNumber": 25}, sources)
            self.assertEqual(status, "PROVENANCE_UID_LINKED")
            self.assertEqual(matches[0]["series_uid"], "PRIVATE-UID")
            self.assertFalse(bad)
            self.assertEqual(len(hashes), 3)
            self.assertEqual(review.conversion_match(root, "11913", "2", {}, sources)[1][0]["series_uid"], "PRIVATE-RUN2")

    def test_provenance_never_falls_back_to_auto_or_executes_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edit, _, _ = self.conversion_fixture(root)
            edit.rename(edit.with_name("11913_ses-01.auto.txt"))
            self.assertEqual(review.conversion_match(root, "11913", "1", {}, [series()])[0], "PROVENANCE_MISSING")
            marker = root / "should-not-exist"
            edit.write_text(f"__import__('pathlib').Path({str(marker)!r}).touch()")
            self.assertEqual(review.conversion_match(root, "11913", "1", {}, [series()])[0], "PROVENANCE_INVALID")
            self.assertFalse(marker.exists())

    def test_provenance_conflicts_and_duplicate_output_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            edit, _, filegroup = self.conversion_fixture(root)
            self.assertEqual(review.conversion_match(root, "11913", "1", {"SeriesInstanceUID": "OTHER"}, [series()])[0],
                             "PROVENANCE_SIDECAR_UID_CONFLICT")
            filegroup.write_text('{"25-shared": ["PRIVATE-PATH/a"]}')
            self.assertEqual(review.conversion_match(root, "11913", "1", {}, [series()])[0], "PROVENANCE_FILECOUNT_CONFLICT")
            edit.write_text(repr({("sub-{subject}/{session}/func/sub-{subject}_{session}_task-sharedreward_run-1_part-mag_bold",
                                  ("nii.gz",), None): ["25-shared", "29-shared"]}))
            self.assertEqual(review.conversion_match(root, "11913", "1", {}, [series()])[0], "PROVENANCE_OUTPUT_NOT_UNIQUE")

    def test_integrated_provenance_report_is_private_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.conversion_fixture(root)
            name = review.stem("11913", "1")
            func = root / "sub-11913/ses-01/func"
            func.mkdir(parents=True)
            path = func / (name + ".json")
            meta = {"SeriesNumber": 25}
            path.write_text(json.dumps(meta))
            (func / (name + ".nii.gz")).write_bytes(b"unchanged-test-image")
            inventory = {"series": [series(), series("OTHER-UID", "11923")],
                         "header_errors": [], "missing": [],
                         "bids_sidecars": [{"path": str(path), "metadata": meta}]}
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch.object(review, "EXPECTED", (("11913", "1"),)):
                report, result = review.review(inventory, root, True)
            self.assertEqual(result, 0)
            self.assertIn("PROVENANCE_UID_LINKED", report)
            self.assertIn("Exact UID links: 1/1", report)
            self.assertNotIn("PRIVATE", report)
            self.assertNotIn(str(root), report)
            for p, data in before.items():
                self.assertEqual(p.read_bytes(), data)

    def test_unique_metadata_candidate_is_not_proof(self):
        status, matches, _ = review.source_match({"SeriesNumber": 25}, [series()])
        self.assertEqual(status, "CANDIDATE_ONLY")
        self.assertEqual(len(matches), 1)

    def test_search_does_not_restrict_subject_folder(self):
        status, matches, _ = review.source_match({"SeriesNumber": 25},
            [series(), series("OTHER-UID", "11923")])
        self.assertEqual(status, "AMBIGUOUS_CANDIDATES")
        self.assertEqual(len(matches), 2)

    def test_uid_conflict_and_missing_uid_do_not_fall_back(self):
        for metadata, expected in [
            ({"SeriesInstanceUID": "PRIVATE-UID"}, "UID_LINKED"),
            ({"SeriesInstanceUID": "PRIVATE-UID", "SeriesNumber": 26}, "METADATA_CONFLICT"),
            ({"SeriesInstanceUID": "PRIVATE-UID", "ImageType": ["P"]}, "METADATA_CONFLICT"),
            ({"SeriesInstanceUID": "UNKNOWN", "SeriesNumber": 25}, "UID_NOT_FOUND"),
            ({}, "NO_SOURCE_KEYS")]:
            self.assertEqual(review.source_match(metadata, [series()])[0], expected)

    def test_duplicate_uid_is_ambiguous(self):
        self.assertEqual(review.source_match({"SeriesInstanceUID": "PRIVATE-UID"},
                         [series(), series()])[0], "AMBIGUOUS_UID")

    def test_live_snapshot_missing_drift_and_redaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = {"series": [], "header_errors": [], "missing": [],
                         "bids_sidecars": []}
            paths = []
            for subject, run in review.EXPECTED:
                name = review.stem(subject, run)
                func = root / f"sub-{subject}" / "ses-01" / "func"
                func.mkdir(parents=True, exist_ok=True)
                path = func / (name + ".json")
                uid = f"PRIVATE-UID-{subject}-{run}"
                inventory["series"].append(series(uid, subject))
                meta = {"SeriesInstanceUID": uid, "ProtocolName": "PRIVATE-PROTOCOL"}
                path.write_text(json.dumps(meta))
                (func / (name + ".nii.gz")).write_bytes(b"unchanged-test-image")
                inventory["bids_sidecars"].append({"path": str(path), "metadata": meta})
                paths.append(path)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            report, result = review.review(inventory, root)
            self.assertEqual(result, 0)
            self.assertIn("Exact UID links: 5/5", report)
            self.assertNotIn("PRIVATE", report)
            self.assertNotIn(str(root), report)
            for p, content in before.items():
                self.assertEqual(p.read_bytes(), content)
            reused = copy.deepcopy(inventory)
            reused["bids_sidecars"][1]["metadata"] = reused["bids_sidecars"][0]["metadata"]
            paths[1].write_text(json.dumps(reused["bids_sidecars"][1]["metadata"]))
            reuse_report, reuse_result = review.review(reused, root)
            self.assertEqual(reuse_result, 1)
            self.assertEqual(reuse_report.count("SOURCE_REUSED"), 2)
            paths[0].write_text('{}')
            paths[1].unlink()
            report, result = review.review(inventory, root)
            self.assertEqual(result, 1)
            self.assertIn("SIDECAR_CHANGED", report)
            self.assertIn("LIVE_INPUT_MISSING", report)
            incomplete = copy.deepcopy(inventory)
            incomplete["missing"] = ["PRIVATE-MISSING"]
            self.assertIn("Saved inventory incomplete: yes", review.review(incomplete, root)[0])

    def test_cli_errors_are_redacted(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = review.main(["--inventory", "/PRIVATE-MISSING/inventory.json"])
        self.assertEqual(result, 2)
        self.assertNotIn("PRIVATE-MISSING", err.getvalue())


if __name__ == "__main__":
    unittest.main()
