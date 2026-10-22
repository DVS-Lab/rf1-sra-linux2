"""Inventory audit must find displaced matches without changing eligibility."""
from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import audit_duplicate_task_series as audit


def episode(first=23, label="SocialDoors_face", volumes=872, norm=False):
    protocol = f"task-{label}_TR1615"
    rows = []
    for offset, suffix, count in [(0, "_SBRef", 4), (1, "_SBRef_Pha", 4),
                                   (2, "", volumes), (3, "_Pha", volumes)]:
        description = protocol + suffix
        rows.append(SimpleNamespace(series_id=f"{first + offset}-{description}",
            protocol_name=protocol, series_description=description, dim3=51, dim4=count,
            image_type=("ORIGINAL", "NORM") if norm and offset == 2 else ("ORIGINAL",)))
    return rows


def selected(rows):
    return audit.normalize(audit.heuristics_XA30.infotodict(rows))


def save(root, rows, subject="11935", session="01", mapping=None):
    folder = root / f"bids/.heudiconv/{subject}/ses-{session}/info"
    folder.mkdir(parents=True)
    table = folder / f"dicominfo_ses-{session}.tsv"
    with table.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(vars(rows[0])), delimiter="\t")
        writer.writeheader()
        writer.writerows(vars(r) for r in rows)
    if mapping is None:
        mapping = audit.heuristics_XA30.infotodict(rows)
    (folder / "conversion.auto.txt").write_text(repr(mapping))
    (root / f"bids/sub-{subject}/ses-{session}").mkdir(parents=True)
    return table


class DuplicateSeriesTests(unittest.TestCase):
    def test_normal_single_run_and_two_ugr_runs_are_not_duplicates(self):
        for rows in [episode(), episode(label="UGR", volumes=960) +
                     episode(27, label="UGR", volumes=960)]:
            self.assertEqual(audit.inspect(rows, {"saved": selected(rows)}), [])

    def test_11935_like_overwrite_omission_and_extra_sbref(self):
        rows = episode() + episode(27)
        mapping = selected(rows)
        mapping[("socialdoors", "sbref")] = [rows[0].series_id, rows[4].series_id]
        findings = audit.inspect(rows, {"saved": mapping})
        types = {r["finding"] for r in findings}
        self.assertEqual(types, {"current_rule_overwrites_match",
            "candidate_omitted_from_saved_mapping", "saved_bold_sbref_count_mismatch"})
        displaced = next(r for r in findings if r["view"] == "current_XA30" and r["part"] == "mag")
        self.assertTrue(displaced["omitted"].startswith("25@"))
        self.assertTrue(displaced["selected"].startswith("29@"))

    def test_both_complete_runs_retained_still_exposes_current_rule_risk(self):
        rows = episode() + episode(27)
        mapping = selected(rows)
        for part, indices in [("mag", [2, 6]), ("phase", [3, 7]), ("sbref", [0, 4])]:
            mapping[("socialdoors", part)] = [rows[i].series_id for i in indices]
        findings = audit.inspect(rows, {"saved": mapping})
        self.assertEqual({r["finding"] for r in findings}, {"current_rule_overwrites_match"})

    def test_omission_detected_even_when_task_key_absent(self):
        findings = audit.inspect(episode() + episode(27), {"saved": {}})
        self.assertIn("candidate_omitted_from_saved_mapping", {r["finding"] for r in findings})

    def test_old_rf1_rules_are_checked_too(self):
        rows = episode(norm=True) + episode(27, norm=True)
        findings = audit.inspect(rows, {})
        self.assertTrue(any(r["view"] == "current_RF1" and r["part"] == "mag" for r in findings))

    def test_partial_series_not_misrepresented_as_full_match(self):
        rows = episode(volumes=680)
        self.assertEqual(audit.inspect(rows, {"saved": selected(rows)}), [])

    def test_repeated_cross_task_unknown_and_mismatched_mapping(self):
        rows = episode()
        mapping = selected(rows)
        mapping[("doors", "mag")] = [rows[2].series_id] * 2
        mapping[("doors", "phase")] = ["99-not-in-inventory"]
        types = {r["finding"] for r in audit.inspect(rows, {"saved": mapping})}
        self.assertTrue({"same_series_assigned_repeatedly", "same_bold_series_multiple_tasks",
            "mapped_series_not_in_inventory", "saved_mag_phase_count_mismatch"} <= types)

    def test_reference_preserves_distinct_identity_but_hides_header_labels(self):
        self.assertNotEqual(audit.ref("25-PRIVATE_A"), audit.ref("25-PRIVATE_B"))
        self.assertNotIn("PRIVATE", audit.ref("25-PRIVATE_A"))

    def test_build_check_all_sessions_without_roster_or_policy_edits(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            root = Path(tmp)
            save(root, episode())
            save(root, episode(), subject="11207", session="02")
            policy = root / "settled-exclusions.tsv"
            policy.write_text("11207\texcluded\n")
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            out = root / "reports"
            self.assertEqual(audit.build(root, out), 0)
            self.assertEqual(audit.check(root, out), 0)
            self.assertEqual(json.loads((out / "summary.json").read_text())["audited_sessions"], 2)
            for p, data in before.items():
                self.assertEqual(p.read_bytes(), data)
            with self.assertRaisesRegex(ValueError, "new output"):
                audit.build(root, out)

    def test_changed_source_or_output_invalidates_check(self):
        for target in ["source", "output", "new_inventory"]:
            with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
                root = Path(tmp)
                table = save(root, episode())
                out = root / "reports"
                audit.build(root, out)
                if target == "source":
                    table.write_text(table.read_text() + "\n")
                elif target == "output":
                    (out / "findings.tsv").write_text("changed")
                else:
                    save(root, episode(), session="02")
                with self.assertRaises(ValueError):
                    audit.check(root, out)

    def test_missing_inventory_is_not_a_clean_cohort(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            root = Path(tmp)
            save(root, episode())
            (root / "bids/sub-99999/ses-01").mkdir(parents=True)
            out = root / "reports"
            self.assertEqual(audit.build(root, out), 1)
            with self.assertRaisesRegex(ValueError, "incomplete"):
                audit.check(root, out)

    def test_malformed_mapping_is_not_executed_or_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            root = Path(tmp)
            table = save(root, episode())
            marker = root / "executed"
            (table.parent / "conversion.auto.txt").write_text(
                f"__import__('pathlib').Path({str(marker)!r}).touch()")
            self.assertEqual(audit.build(root, root / "reports"), 1)
            self.assertFalse(marker.exists())

    def test_duplicate_inventory_id_and_missing_mapping_fail_closed(self):
        for mode in ["duplicate_id", "no_mapping"]:
            with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
                root = Path(tmp)
                rows = episode()
                if mode == "duplicate_id":
                    rows[1].series_id = rows[0].series_id
                table = save(root, rows)
                if mode == "no_mapping":
                    (table.parent / "conversion.auto.txt").unlink()
                self.assertEqual(audit.build(root, root / "reports"), 1)


if __name__ == "__main__":
    unittest.main()
