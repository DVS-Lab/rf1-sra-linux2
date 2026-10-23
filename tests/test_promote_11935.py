"""Byte-level transaction tests; image approval remains a separate human gate."""

import csv
import fcntl
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import promote_11935 as promotion


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "production"
        self.stage = self.project / "work/11935-production-repair-v1/sub11935-project"
        self.socdoors = self.root / "socdoors"
        self.cohort = self.project / "derivatives/cohort-experiment"
        self.archive = self.project / "derivatives/source_repairs/new-promotion"
        for path in (self.stage, self.socdoors, self.cohort):
            path.mkdir(parents=True)
        self.hashes = {}
        for task in promotion.TASKS:
            stem = f"{promotion.BASE}task-{task}_run-1"
            acq = f"{promotion.BASE}acq-{task}_run-1"
            paths = [f"bids/{promotion.SESSION}/func/{stem}_echo-1_part-mag_bold.nii.gz",
                     f"bids/{promotion.SESSION}/func/{stem}_events.tsv",
                     f"bids/{promotion.SESSION}/fmap/{acq}_fieldmap.json",
                     f"derivatives/warpkit/{promotion.SESSION}/{stem}.warpkit_done",
                     f"derivatives/fmriprep/{promotion.SESSION}/func/{stem}_desc-preproc_bold.nii.gz",
                     f"derivatives/fmriprep/{promotion.SESSION}/func/{stem}_desc-preproc_bold.json",
                     f"derivatives/fmriprep/{promotion.SESSION}/fmap/{acq}_desc-coeff_fieldmap.nii.gz",
                     f"derivatives/fmriprep/sub-11935/figures/{acq}_desc-fieldmap.svg",
                     f"derivatives/fmriprep/sub-11935/figures/{stem}_desc-coreg.svg",
                     f"derivatives/tedana/{promotion.SESSION}/{stem}_desc-ICA_mixing.tsv",
                     f"derivatives/tedana/{promotion.SESSION}/figures/{stem}_comp_000.svg",
                     f"derivatives/fsl/confounds_tedana/sub-11935/{stem}_desc-TedanaPlusConfounds.tsv",
                     f"derivatives/mriqc/{promotion.SESSION}/func/{stem}_bold.json",
                     f"derivatives/mriqc/{stem}_bold.html"]
            for name in paths:
                self.write(self.stage / name, b"new:" + name.encode())
                self.hashes[name] = promotion.sha256(self.stage / name)
                # Old production had no Doors at all.
                if task == "socialdoors":
                    self.write(self.project / name, b"old:" + name.encode())
        self.stale = f"derivatives/fmriprep/{promotion.SESSION}/func/{promotion.BASE}task-socialdoors_run-1_desc-obsolete_bold.nii.gz"
        self.write(self.project / self.stale, b"stale old filename")
        self.external_input = f"bids/{promotion.SESSION}/anat/sub-11935_ses-01_T1w.nii.gz"
        self.write(self.project / self.external_input, b"preserved anatomy input")
        self.other = [self.external_input,
                      f"bids/{promotion.SESSION}/func/{promotion.BASE}task-ugr_run-1_bold.nii.gz",
                      f"bids/{promotion.SESSION}/func/{promotion.BASE}task-socialdoors_run-2_bold.nii.gz",
                      f"derivatives/fmriprep/{promotion.SESSION}/fmap/sub-11935_ses-01_fmapid-auto00000_fieldmap.nii.gz",
                      "derivatives/fmriprep/sub-11935.html",
                      "derivatives/fmriprep/sub-11935/anat/sub-11935_T1w.nii.gz",
                      "derivatives/freesurfer/sub-11935/mri/T1.mgz",
                      "derivatives/tedana/sub-99999/ses-01/other.tsv",
                      "bids/dataset_description.json", "qc/run_disposition.tsv",
                      "code/task_holds.tsv", "code/exclusions.tsv",
                      "derivatives/source_repairs/old-archive/promotion.json"]
        for name in self.other:
            if not (self.project / name).exists():
                self.write(self.project / name, b"untouched:" + name.encode())
        self.old_scans = ("filename\tacq_time\told_column\n"
                          "func/sub-11935_ses-01_task-ugr_run-1_bold.nii.gz\tunchanged\tkeep\n"
                          "func/sub-11935_ses-01_task-socialdoors_run-2_bold.nii.gz\trun2\tkeep2\n"
                          "func/sub-11935_ses-01_task-socialdoors_run-1_echo-1_part-mag_bold.nii.gz\twrong\told\n")
        self.write(self.project / promotion.SCANS, self.old_scans.encode())
        self.stage_scans = "filename\tacq_time\n" + "".join(
            f"func/{promotion.BASE}task-{task}_run-1_echo-1_part-mag_bold.nii.gz\tnew-{task}\n"
            for task in promotion.TASKS)
        self.write(self.stage / promotion.SCANS, self.stage_scans.encode())
        self.affected_external = []
        self.unrelated_external = []
        for variant in ("fsl", "fsl-no-tedana-age55"):
            base = f"derivatives/{variant}/{promotion.SESSION}"
            for task in ("socialdoors", "doors"):
                for kind in ("act", "ppi_seed-mPFC", "nppi-dmn"):
                    for name in (f"L1_task-{task}_ses-01_model-1_type-{kind}_run-1_sm-5.feat/stats/cope1.nii.gz",
                                 f"L1_sub-11935_task-{task}_ses-01_model-1_type-{kind}_run-1.fsf"):
                        self.affected_external.append(f"{base}/{name}")
                self.affected_external.extend([
                    f"derivatives/{variant}/EVfiles/{promotion.SESSION}/{task}/run-1_win.txt",
                    f"{base}/ts_task-{task}_ses-01_net0000_nppi-dmn_run-1.txt"])
            self.affected_external.append(f"{base}/L2_task-socialdoors_ses-01_model-1_type-act_sm-5.gfeat/cope1.feat/stats/cope1.nii.gz")
            self.unrelated_external.extend([
                f"{base}/L1_task-ugr_ses-01_model-3_type-act_run-1_sm-5.feat/keep",
                f"{base}/L1_task-socialdoors_ses-01_model-1_type-act_run-10_sm-5.feat/keep",
                f"{base}/ts_task-socialdoors_ses-01_net0000_nppi-dmn_run-2.txt",
                f"derivatives/{variant}/EVfiles/{promotion.SESSION}/socialdoors/run-2_win.txt",
                f"derivatives/{variant}/sub-11935/ses-02/L1_task-socialdoors_ses-02_type-act_run-1.feat/keep",
                f"derivatives/{variant}/sub-11936/ses-01/L1_task-socialdoors_ses-01_type-act_run-1.feat/keep",
                f"derivatives/{variant}/L3_task-socialdoors.gfeat/cope1.feat/stats/zstat1.nii.gz"])
        for name in self.affected_external + self.unrelated_external:
            self.write(self.socdoors / name, b"external:" + name.encode())
        manifest = {"schema": 1, "project_root": str(self.project), "rows": [
            {"run_key": promotion.BASE + "task-socialdoors_run-1", "inputs": {
                self.external_input: {}, self.stale: {}}},
            {"run_key": promotion.BASE + "task-ugr_run-1", "inputs": {"ignore": {}}}]}
        self.write(self.cohort / "manifest.json", json.dumps(manifest).encode())
        self.write(self.cohort / "validation.json", b'{"validated":true}')
        # Realistic workspace contains files that are NOT publication payload.
        for name in ("code/tool.py", "converted-not-promoted/old.txt", "cache/private.log",
                     "derivatives/freesurfer/sub-11935/mri/T1.mgz",
                     "derivatives/fmriprep/sub-11935.html", "bids/dataset_description.json",
                     "derivatives/tedana/sub-11935/ses-01/figures/unrelated_report.svg",
                     "derivatives/fmriprep/sub-11935/ses-01/fmap/sub-11935_fmapid-auto00000_fieldmap.nii.gz"):
            self.write(self.stage / name, b"workspace only")
        self.write(self.stage / "repair.json", json.dumps({"state": "ready", "production": str(self.project)}).encode())
        self.ready()

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def ready(self, **changes):
        data = {"validated": True, "subject": "11935", "session": "01",
                "tasks": list(promotion.TASKS), "files": self.hashes}
        data.update(changes)
        (self.stage / promotion.READY).write_text(json.dumps(data))

    def plan(self, cohort=True):
        return promotion.plan(self.project, self.stage, self.archive, self.socdoors,
                              self.cohort if cohort else None)

    def snapshot(self, paths):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}

    def test_plan_is_read_only_and_json_and_has_new_doors_key(self):
        before = self.snapshot([self.project / promotion.SCANS, self.cohort / "manifest.json"])
        p = self.plan()
        self.assertEqual(json.loads(json.dumps(p)), p)
        self.assertEqual(self.snapshot(map(Path, before)), before)
        self.assertFalse(self.archive.exists())
        self.assertFalse((self.project / "logs").exists())
        self.assertEqual(p["changed_keys"], [promotion.BASE + "task-doors_run-1", promotion.BASE + "task-socialdoors_run-1"])
        self.assertEqual(p["scans_merge"]["staged_sha256"], promotion.sha256(self.stage / promotion.SCANS))
        self.assertEqual(p["scans_merge"]["old_sha256"], promotion.sha256(self.project / promotion.SCANS))
        self.assertTrue(any("_type-ppi_" in x for x in p["other_analysis_requires_rebuild"]))
        self.assertTrue(all("_type-act_" in x for x in p["activation_rebuild"]))
        self.assertTrue(p["stale_l3_report"]["paths"])

    def test_promotion_preserves_archives_inputs_unrelated_files_and_mtimes(self):
        untouched = [self.project / name for name in self.other] + [self.socdoors / name for name in self.unrelated_external]
        before = self.snapshot(untouched + [self.cohort / "manifest.json"])
        p = self.plan()
        result = promotion.apply_plan(p)
        self.assertEqual(result["state"], "installed")
        self.assertTrue(promotion.check(p)["verified"])
        self.assertEqual(self.snapshot(map(Path, before)), before)
        for name, digest in self.hashes.items():
            self.assertEqual(promotion.sha256(self.project / name), digest)
        for item in p["moves"]:
            self.assertEqual(promotion.sha256(item["archive_path"]), item["sha256"])
        self.assertFalse((self.project / self.stale).exists())
        for name in self.affected_external:
            self.assertFalse((self.socdoors / name).exists())
        original = result["source_original_inputs"][self.external_input]
        self.assertEqual(Path(original["archive_path"]).read_bytes(), b"preserved anatomy input")
        self.assertEqual((self.archive / "project" / promotion.SCANS).read_text(), self.old_scans)
        self.assertFalse(json.loads((self.cohort / "validation.json").read_text())["validated"])
        self.assertEqual(promotion.check(self.archive / "promotion.json")["state"], "installed")
        self.assertFalse((self.project / "logs/locks/fmriprep-sub-11935.lock").exists())

    def test_scans_merge_preserves_unrelated_rows_and_adds_doors(self):
        p = self.plan()
        rows = list(csv.DictReader(io.StringIO(p["scans_merge"]["content"]), delimiter="\t"))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0], {"filename": "func/sub-11935_ses-01_task-ugr_run-1_bold.nii.gz", "acq_time": "unchanged", "old_column": "keep"})
        self.assertEqual(rows[1]["acq_time"], "run2")
        self.assertEqual({r["acq_time"] for r in rows[2:]}, {"new-doors", "new-socialdoors"})
        self.assertEqual(promotion.sha256(self.project / promotion.SCANS), p["scans_merge"]["old_sha256"])

    def test_later_check_allows_rebuilt_outputs_but_strict_gate_rejects_them(self):
        receipt = promotion.apply_plan(self.plan())
        self.write(self.socdoors / self.affected_external[0], b"rebuilt output")
        self.assertTrue(promotion.check(receipt)["verified"])
        with self.assertRaisesRegex(ValueError, "stale"):
            promotion.check(receipt, allow_rebuilt=False)

    def test_missing_or_unvalidated_ready_fails(self):
        (self.stage / promotion.READY).unlink()
        with self.assertRaisesRegex(ValueError, "missing required ready"):
            self.plan()
        self.ready(validated=False)
        with self.assertRaisesRegex(ValueError, "invalid ready"):
            self.plan()

    def test_exact_tasks_required(self):
        self.ready(tasks=["socialdoors"])
        with self.assertRaises(ValueError):
            self.plan()

    def test_extra_manifest_path_escape_global_html_and_metadata_rejected(self):
        for bad in ("../escape", "/tmp/escape", "bids/dataset_description.json",
                    "derivatives/fmriprep/sub-11935.html",
                    "derivatives/fmriprep/sub-11935/ses-01/fmap/sub-11935_fmapid-auto00000_fieldmap.nii.gz",
                    f"bids/{promotion.SESSION}/func/{promotion.BASE}task-doors_run-10_bold.nii.gz"):
            with self.subTest(bad=bad):
                self.ready(files=dict(self.hashes, **{bad: "0" * 64}))
                with self.assertRaises(ValueError):
                    self.plan()
        self.ready()

    def test_unlisted_target_extra_and_hash_mismatch_rejected(self):
        name = f"bids/{promotion.SESSION}/func/{promotion.BASE}task-doors_run-1_extra.json"
        self.write(self.stage / name, b"unlisted")
        with self.assertRaisesRegex(ValueError, "unlisted extra"):
            self.plan()
        (self.stage / name).unlink()
        self.write(self.stage / next(iter(self.hashes)), b"wrong")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.plan()

    def test_symlink_file_parent_live_archive_and_scans_rejected(self):
        name = next(iter(self.hashes))
        path = self.stage / name
        original = path.read_bytes()
        path.unlink()
        path.symlink_to(self.project / self.external_input)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()
        path.unlink()
        path.write_bytes(original)
        live = self.project / self.stale
        live.unlink()
        live.symlink_to(self.project / self.external_input)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()
        live.unlink()
        live.write_bytes(b"stale")
        scans = self.stage / promotion.SCANS
        scans.unlink()
        scans.symlink_to(self.project / promotion.SCANS)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()

    def test_scans_mutation_invalidates_plan(self):
        for root in (self.stage, self.project):
            with self.subTest(root=root):
                p = self.plan()
                path = root / promotion.SCANS
                content = path.read_bytes()
                path.write_bytes(content.replace(b"acq_time", b"scanner_time"))
                with self.assertRaisesRegex(ValueError, "plan changed"):
                    promotion.apply_plan(p)
                path.write_bytes(content)
                self.assertFalse(self.archive.exists())

    def test_live_or_stage_mutation_invalidates_plan(self):
        p = self.plan()
        self.write(self.project / self.stale, b"changed old")
        with self.assertRaisesRegex(ValueError, "plan changed"):
            promotion.apply_plan(p)
        self.assertFalse(self.archive.exists())

    def test_existing_archive_never_overwritten_even_installed(self):
        p = self.plan()
        promotion.apply_plan(p)
        before = (self.archive / "promotion.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "Manual recovery"):
            promotion.apply_plan(p)
        self.assertEqual((self.archive / "promotion.json").read_bytes(), before)

    def test_failed_copy_prepared_receipt_no_canonical_changes(self):
        p = self.plan()
        before = self.snapshot([Path(item["source"]) for item in p["moves"]])
        with patch.object(promotion, "copy_verified", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(RuntimeError, "NOT installed.*Manual recovery"):
                promotion.apply_plan(p)
        receipt = json.loads((self.archive / "promotion.json").read_text())
        self.assertEqual(receipt["state"], "prepared")
        self.assertEqual(before, self.snapshot(map(Path, before)))
        with self.assertRaisesRegex(ValueError, "Manual recovery"):
            promotion.check(receipt)
        with self.assertRaisesRegex(ValueError, "Manual recovery"):
            promotion.apply_plan(p)

    def test_interrupted_install_leaves_applying_and_validation_false(self):
        p = self.plan()
        with patch.object(promotion.os, "link", side_effect=KeyboardInterrupt("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "NOT installed"):
                promotion.apply_plan(p)
        receipt = json.loads((self.archive / "promotion.json").read_text())
        self.assertEqual(receipt["state"], "applying")
        self.assertTrue(all(Path(item["archive_path"]).exists() for item in p["moves"]))
        self.assertFalse(json.loads((self.cohort / "validation.json").read_text())["validated"])
        with self.assertRaisesRegex(ValueError, "Manual recovery"):
            promotion.check(self.archive / "promotion.json")

    def test_check_detects_installed_and_archive_tampering(self):
        receipt = promotion.apply_plan(self.plan())
        name = next(iter(self.hashes))
        original = (self.project / name).read_bytes()
        self.write(self.project / name, b"changed installed")
        with self.assertRaisesRegex(ValueError, "installed hash"):
            promotion.check(receipt)
        self.write(self.project / name, original)
        self.write(Path(receipt["moves"][0]["archive_path"]), b"changed archive")
        with self.assertRaisesRegex(ValueError, "archive hash"):
            promotion.check(receipt)

    def test_fmriprep_lock_never_stale_guessed(self):
        p = self.plan()
        lock = self.project / "logs/locks/fmriprep-sub-11935.lock"
        self.write(lock / "host", b"unknown-host")
        self.write(lock / "pid", b"99999999")
        with self.assertRaisesRegex(ValueError, "subject lock exists"):
            promotion.apply_plan(p)
        self.assertEqual((lock / "pid").read_bytes(), b"99999999")
        self.assertFalse(self.archive.exists())

    def test_borrowed_cohort_lock_and_nested_guard(self):
        p = self.plan()
        lock = self.cohort / ".cohort.lock"
        with lock.open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with promotion.production_guard(p, lock_fds=(handle.fileno(),)) as fds:
                self.assertTrue((self.project / "logs/locks/fmriprep-sub-11935.lock").exists())
                result = promotion.apply_plan(p, lock_fds=fds)
            self.assertEqual(result["state"], "installed")
            with lock.open("a+") as probe:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_lock_contention_and_unlocked_borrowed_fd_fail(self):
        p = self.plan()
        lock = self.cohort / ".cohort.lock"
        with lock.open("a+") as handle:
            with self.assertRaisesRegex(ValueError, "not locked"):
                promotion.apply_plan(p, lock_fds=(handle.fileno(),))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, "lock busy"):
                promotion.apply_plan(p)
        self.assertFalse(self.archive.exists())

    def test_cli_approval_gate_and_read_only_plan(self):
        args = ["--project-root", str(self.project), "--staged-project", str(self.stage),
                "--archive-root", str(self.archive), "--socdoors-root", str(self.socdoors),
                "--cohort-root", str(self.cohort)]
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertEqual(promotion.main(["plan", *args]), 0)
            self.assertEqual(json.loads(output.getvalue())["project"], str(self.project))
        with patch("sys.stderr", new_callable=io.StringIO) as output:
            self.assertEqual(promotion.main(["promote", *args]), 1)
            self.assertIn("--approve-images", output.getvalue())
        self.assertFalse(self.archive.exists())

    def test_scans_missing_replacement_rows_and_manifest_escape_fail(self):
        self.write(self.stage / promotion.SCANS, b"filename\tacq_time\n")
        with self.assertRaisesRegex(ValueError, "replacement rows"):
            self.plan()
        self.write(self.stage / promotion.SCANS, self.stage_scans.encode())
        path = self.cohort / "manifest.json"
        data = json.loads(path.read_text())
        data["rows"][0]["inputs"] = {"../outside": {}}
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "escape"):
            self.plan()

    def test_plan_without_cohort_and_no_scans_available(self):
        (self.stage / promotion.SCANS).unlink()
        (self.project / promotion.SCANS).unlink()
        p = self.plan(cohort=False)
        self.assertIsNone(p["scans_merge"])
        self.assertIsNone(p["cohort_manifest"])
        self.assertTrue(promotion.check(promotion.apply_plan(p))["verified"])

    def test_stage_only_under_work_and_no_live_archive_overlap(self):
        for stage in (self.project / "bids/staging", self.cohort / "staging", self.socdoors / "work/staging"):
            stage.mkdir(parents=True, exist_ok=True)
            with self.assertRaisesRegex(ValueError, "nested staging"):
                promotion.plan(self.project, stage, self.archive, self.socdoors, self.cohort)
        for archive in (self.project / "bids/new", self.project / "derivatives/fmriprep/new",
                        self.cohort / "archive"):
            with self.assertRaisesRegex(ValueError, "archive"):
                promotion.plan(self.project, self.stage, archive, self.socdoors, self.cohort)

    def test_parent_and_archive_symlinks_rejected(self):
        folder = self.project / f"bids/{promotion.SESSION}/func"
        moved = folder.with_name("func-original")
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()
        folder.unlink()
        moved.rename(folder)
        alias = self.root / "archive-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            promotion.plan(self.project, self.stage, alias / "new", self.socdoors, self.cohort)

    def test_copy_hash_mismatch_aborts_before_canonical_unlink(self):
        p = self.plan()
        before = self.snapshot([Path(item["source"]) for item in p["moves"]])
        def corrupt(src, dst, length):
            dst.write(b"corrupt copy")
        with patch.object(promotion.shutil, "copyfileobj", side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, "copy hash mismatch"):
                promotion.apply_plan(p)
        self.assertEqual(before, self.snapshot(map(Path, before)))
        self.assertEqual(json.loads((self.archive / "promotion.json").read_text())["state"], "prepared")

    def test_shared_legacy_and_preferred_repair_locks_are_both_held(self):
        p = self.plan()
        with promotion.production_guard(p):
            for name in (".11935-repair.lock", "logs/locks/.11935-repair.lock"):
                with (self.project / name).open("a+") as probe:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_protected_ready_signatures_are_checked(self):
        path = self.project / self.external_input
        info = path.stat()
        self.ready(inputs={str(path): [info.st_size, info.st_mtime_ns]})
        self.plan()
        path.write_bytes(b"modified anatomy")
        with self.assertRaisesRegex(ValueError, "protected input changed"):
            self.plan()


if __name__ == "__main__":
    unittest.main()
