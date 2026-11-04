import csv
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest


SPEC = importlib.util.spec_from_file_location(
    "inventory_lifespan_measures", Path(__file__).resolve().parents[1] / "code/inventory_lifespan_measures.py")
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def write_table(path, fields, rows, delimiter=","):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.fields = ["sub_id_rf1_data", "redcap_event_name", *inventory.SCORES.values()]

    def row(self, sub="12345", event="baseline", **changes):
        row = dict(zip(self.fields, (sub, event, "5", "31", "0", "25")))
        row.update(changes)
        return row

    def profile(self, rows):
        path = self.root / "scores.csv"
        write_table(path, self.fields, rows)
        return inventory.survey_inventory(path)[0]

    def test_zero_and_young_adults_are_preserved(self):
        result = self.profile([self.row()])["whole_file"]
        self.assertEqual(result["n_all_four_finite_adult_records"], 1)
        self.assertEqual(result["measures"]["depressive_symptoms"]["minimum_as_exported"], 0)
        self.assertEqual(result["age_strata_descriptive_only"]["18-34"]["loneliness"], 1)

    def test_duplicates_are_not_silently_chosen_or_pooled(self):
        profile = self.profile([self.row(), self.row(event="followup", sub_age="27")])
        self.assertEqual(profile["whole_file"]["n_repeated_rf1_ids"], 1)
        self.assertEqual(profile["whole_file"]["n_unique_id_records"], 0)
        self.assertEqual(profile["by_redcap_event"]["baseline"]["n_unique_id_records"], 1)
        self.assertEqual(profile["by_redcap_event"]["followup"]["n_unique_id_records"], 1)

    def test_alias_and_decimal_ids_need_review(self):
        result = self.profile([self.row(sub="12345_duplicate"), self.row(sub="12345.0"), self.row(sub="sub-23456")])["whole_file"]
        self.assertEqual(result["n_invalid_or_missing_id_rows"], 2)
        self.assertEqual(result["n_unresolved_duplicate_suffix_rows"], 1)
        self.assertEqual(result["n_unique_id_records"], 1)

    def test_missing_nonnumeric_and_infinite_scores_are_distinct(self):
        result = self.profile([self.row(uclal_score="NA"), self.row(sub="23456", uclal_score="unknown"),
                               self.row(sub="34567", uclal_score="inf")])["whole_file"]
        measure = result["measures"]["loneliness"]
        self.assertEqual(measure["n_blank_or_missing_token"], 1)
        self.assertEqual(measure["n_other_nonnumeric_or_nonfinite"], 2)
        self.assertEqual(result["n_all_four_finite_unique_id_records"], 0)

    def test_finite_scores_are_explicitly_not_validated(self):
        result = self.profile([self.row(uclal_score="999", sub_age="15")])["whole_file"]
        self.assertEqual(result["measures"]["loneliness"]["status"], "exported_not_scoring_verified")
        self.assertEqual(result["n_all_four_finite_unique_id_records"], 1)
        self.assertEqual(result["n_all_four_finite_adult_records"], 0)

    def test_multiple_identity_fields_not_guessed(self):
        path = self.root / "ambiguous.csv"
        write_table(path, ["rf1_id", "subject", "uclal_score"],
                    [{"rf1_id": "12345", "subject": "23456", "uclal_score": "5"}])
        profile, _ = inventory.survey_inventory(path)
        self.assertEqual(profile["status"], "review_identity_columns")
        self.assertNotIn("whole_file", profile)

    def test_ragged_and_duplicate_columns_fail(self):
        for text in ("subject,uclal_score\n12345,5,extra\n", "subject,subject\n12345,12345\n"):
            path = self.root / "bad.csv"
            path.write_text(text)
            with self.assertRaises(ValueError):
                inventory.table(path)

    def test_discovery_is_bounded_and_does_not_enter_processing_or_symlinks(self):
        for folder in ("data", "work", "bids", "derivatives", "stimuli", "data/a/b/c/d"):
            write_table(self.root / folder / "scores.csv", ["rf1_id", "uclal_score"], [])
        (self.root / "linked").symlink_to(self.root / "data", target_is_directory=True)
        result = inventory.discover([self.root, self.root])
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(Path(result["candidates"][0]["path"]).parent.name, "data")

    def test_build_is_aggregate_only_and_preserves_inputs_and_previous_outputs(self):
        path = self.root / "scores.csv"
        write_table(path, self.fields, [self.row()])
        original = path.read_bytes()
        output = self.root / "output"
        args = SimpleNamespace(output=output, survey=[path], discover_root=[], project=None)
        inventory.build(args)
        data = (output / "inventory-private.json").read_text()
        self.assertNotIn("12345", data)
        self.assertFalse(json.loads(data)["final_cohort_assigned"])
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            inventory.build(args)


class QCTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.fields = ["subject", "session", "task", "run", "brain_coverage_pct", "fd_mean_outlier", "tsnr_outlier"]

    def row(self, task, session="01", **changes):
        row = dict(zip(self.fields, ("12345", session, task, "1", "95", "FALSE", "FALSE")))
        row.update(changes)
        return row

    def profile(self, rows):
        write_table(self.root / "qc/run_qc.tsv", self.fields, rows, "\t")
        return inventory.qc_inventory(self.root)[0]["by_session"]

    def test_session2_failure_cannot_change_session1_and_exact95_passes(self):
        result = self.profile([self.row("doors"), self.row("socialdoors"),
                               self.row("doors", "02", fd_mean_outlier="TRUE"), self.row("socialdoors", "02")])
        self.assertEqual(result["01"]["n_both_recorded_fd_tsnr_clear_coverage95"], 1)
        self.assertEqual(result["02"]["n_both_recorded_fd_tsnr_clear_coverage95"], 0)

    def test_missing_data_not_treated_as_pass(self):
        result = self.profile([self.row("doors", brain_coverage_pct="NA"), self.row("socialdoors")])
        self.assertEqual(result["01"]["n_pairs_with_missing_or_invalid_qc"], 1)
        self.assertEqual(result["01"]["n_both_recorded_fd_tsnr_clear_coverage95"], 0)

    def test_impossible_coverage_not_treated_as_pass(self):
        result = self.profile([self.row("doors", brain_coverage_pct="101"), self.row("socialdoors")])
        self.assertEqual(result["01"]["n_pairs_with_missing_or_invalid_qc"], 1)

    def test_duplicate_key_fails(self):
        with self.assertRaises(ValueError):
            self.profile([self.row("doors"), self.row("doors")])


class LauncherTests(unittest.TestCase):
    def test_frozen_launcher_publishes_on_success_and_failure_without_checkout_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            code = project / "code"
            code.mkdir()
            source = Path(__file__).resolve().parents[1] / "code"
            shutil.copyfile(source / "inventory_lifespan_measures.py", code / "inventory_lifespan_measures.py")
            (code / "run_logged.sh").write_text(
                '#!/usr/bin/env bash\nset -eu\nwhile [[ "$1" != "--" ]]; do shift; done\nshift\nexec "$@"\n')
            (code / "publish_run_logs.py").write_text(
                'from pathlib import Path\nimport os\n'
                'assert os.environ["GIT_CONFIG_VALUE_0"].startswith("https://")\n'
                'Path("work/published.txt").write_text("published")\n')
            (project / ".gitignore").write_text("work/\n")
            fields = ["subject", "session", "task", "run", "brain_coverage_pct", "fd_mean_outlier", "tsnr_outlier"]
            write_table(project / "qc/run_qc.tsv", fields, [], "\t")
            def git(*args):
                return subprocess.run(["git", "-C", str(project), *args], check=True,
                                      text=True, capture_output=True).stdout
            git("init", "-b", "main")
            git("config", "user.name", "Inventory Test")
            git("config", "user.email", "inventory@example.invalid")
            git("add", ".")
            git("commit", "-m", "Synthetic launcher fixture")
            git("fetch", ".", "main")
            before = git("status", "--porcelain")
            env = dict(os.environ, LIFESPAN_PROJECT=str(project))
            result = subprocess.run(["bash", str(source / "run_lifespan_inventory.sh")],
                                    cwd=project, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((project / "work/published.txt").is_file())
            self.assertEqual(git("status", "--porcelain"), before)
            (project / "work/published.txt").unlink()
            result = subprocess.run(["bash", str(source / "run_lifespan_inventory.sh"),
                                     "--survey", str(project / "absent.csv")],
                                    cwd=project, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertTrue((project / "work/published.txt").is_file())
            self.assertEqual(git("status", "--porcelain"), before)


if __name__ == "__main__":
    unittest.main()
