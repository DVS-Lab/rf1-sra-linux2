import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import report_tedana_cohort_eras as eras


class CohortReportTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        roster, self.rows = [], []
        for i, (aic, mdl) in enumerate([(1, 1), (10, 2), (20, 19)]):
            r = dict(run_key=str(i), subject=str(i), session="01", task="doors",
                     run="1", software_versions="syngo MR XA60")
            roster.append(r)
            for cfg, rejected in zip(eras.METHODS, (aic, aic, mdl)):
                total = max(10, rejected)
                self.rows.append(dict(**r, config=cfg, total_components=total,
                                      rejected_components=rejected, rejected_fraction=rejected/total))
        raw = json.dumps({"rows": roster}).encode()
        (self.root / "manifest.json").write_bytes(raw)
        (self.root / "validation.json").write_text(json.dumps(dict(
            validated=True, failures=0, expected_jobs=9, summary_rows=9,
            expected_runs=3, manifest_sha256=hashlib.sha256(raw).hexdigest())))

    def load(self):
        with (self.root / "component_summary.tsv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(self.rows[0]), delimiter="\t")
            w.writeheader()
            w.writerows(self.rows)
        return eras.read_paired(self.root)

    def test_paired_delta_is_not_difference_of_medians(self):
        out = io.StringIO()
        eras.report(self.load(), out)
        row, = csv.DictReader(out.getvalue().splitlines(), delimiter="\t")
        self.assertEqual(row["median_within_run_MDL_minus_AIC_rejected"], "-1")
        self.assertEqual(row["MDL_rejected_pct"], "20.0")
        self.assertEqual(row["runs"], "3")

    def test_incomplete_and_duplicate(self):
        removed = self.rows.pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.load()
        self.rows.extend([removed, removed])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.load()

    def test_changed_manifest(self):
        with (self.root / "manifest.json").open("a") as f:
            f.write("\n")
        with self.assertRaisesRegex(ValueError, "validation"):
            self.load()
