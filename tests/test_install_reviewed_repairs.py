"""Synthetic byte-level tests; scientific validation comes from staged receipts."""
import fcntl
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import install_reviewed_repairs as install
import promote_11935 as common
from test_promote_11935 import PromotionTests


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.fixture = PromotionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.project, self.socdoors, self.cohort, self.stage = f.project, f.socdoors, f.cohort, f.stage
        self.ugr = f.root / "ugr"
        self.ugr.mkdir()
        self.archive = self.project / "work/install-v1"
        self.wave2 = self.project / "work/reviewed-source-repairs-v3/sub-10964-project"
        self.stages = {"10964": self.wave2, "11935": self.stage}
        self.write = f.write
        self.write(self.project / "bids/participants.tsv", b"participant_id\tage\nsub-10964\t60\n")
        self.write(self.project / "bids/sub-10964/ses-01/anat/baseline.nii.gz", b"baseline")
        self.write(self.wave2 / "bids/sub-10964/ses-01/anat/baseline.nii.gz", b"do not replace baseline")
        self.write(self.wave2 / "bids/participants.tsv", b"do not install this")
        hashes = []
        for task, run in sorted(install.SPECS["10964"][1]):
            base = "sub-10964/ses-02"
            stem = f"sub-10964_ses-02_task-{task}_run-{run}"
            acq = f"sub-10964_ses-02_acq-{task}_run-{run}"
            names = [f"bids/{base}/func/{stem}_echo-1_part-mag_bold.nii.gz",
                     f"bids/{base}/func/{stem}_events.tsv", f"bids/{base}/fmap/{acq}_fieldmap.json",
                     f"derivatives/warpkit/{base}/{stem}.warpkit_done",
                     f"derivatives/fmriprep/{base}/func/{stem}_desc-preproc_bold.nii.gz",
                     f"derivatives/tedana/{base}/{stem}_desc-ICA_mixing.tsv",
                     f"derivatives/fsl/confounds_tedana/sub-10964/{stem}_desc-TedanaPlusConfounds.tsv",
                     f"derivatives/mriqc/{base}/func/{stem}_bold.json"]
            for n in names:
                self.write(self.wave2 / n, b"new wave2:" + n.encode())
                self.write(self.project / n, b"old wave2:" + n.encode())
                hashes.append(n)
        content = "filename\tacq_time\n" + "".join("func/" + Path(n).name + "\t2026\n" for n in hashes if n.startswith("bids/") and n.endswith(".nii.gz"))
        self.write(self.wave2 / install.scans_name("10964"), content.encode())
        self.write(self.project / install.scans_name("10964"), content.encode())
        self.write(self.wave2 / "repair.json", json.dumps({"production": str(self.project), "state": "ready",
                                                         "protected": {str(self.project / "bids/participants.tsv"): install.stamp(self.project / "bids/participants.tsv")}}).encode())
        self.refresh_ready()
        manifest = install.read(self.cohort / "manifest.json")
        manifest["rows"] = [manifest["rows"][0], {"run_key": "sub-10964_ses-02_task-ugr_run-1", "inputs": {hashes[0]: {}}}]
        for row in manifest["rows"]:
            for n in row["inputs"]:
                size, mtime = install.stamp(self.project / n)
                row["inputs"][n] = {"size": size, "mtime_ns": mtime, "sha256": common.sha256(self.project / n)}
        self.write(self.cohort / "manifest.json", json.dumps(manifest).encode())
        self.write(self.cohort / "validation.json", json.dumps({"validated": True, "failures": 0,
                   "summary_rows": 6, "expected_jobs": 6, "manifest_sha256": common.sha256(self.cohort / "manifest.json")}).encode())
        self.write(self.cohort / "old-results/success.json", b"preserve all completed outputs")
        self.write(self.ugr / "derivatives/fsl/sub-10964/ses-02/L2_task-ugr_ses-02_model-1_type-act.gfeat/cope.nii.gz", b"old L2")

    def refresh_ready(self):
        self.write(self.wave2 / "validated.json", json.dumps({"validated": True, "subject": "10964", "session": "02",
                   "outputs": install.validated_stage_tree(self.wave2)}).encode())

    def plan(self):
        return install.plan(self.project, self.stages, self.archive, self.socdoors, self.ugr, self.cohort)

    def test_install_both_preserves_cohort_baseline_decisions_and_originals(self):
        before = install.tree(self.cohort)
        p = self.plan()
        receipt = install.install(p)
        install.check(receipt)
        self.assertEqual(install.tree(self.cohort), before)
        self.assertEqual((self.project / "bids/sub-10964/ses-01/anat/baseline.nii.gz").read_bytes(), b"baseline")
        self.assertIn(b"sub-10964", (self.project / "bids/participants.tsv").read_bytes())
        self.assertEqual(receipt["state"], "installed")
        for n, item in p["installs"].items():
            self.assertEqual(common.sha256(self.project / n), item["sha256"])
            self.assertEqual((self.project / n).stat().st_mode & 0o777, 0o666)
        for item in p["originals"].values():
            self.assertEqual(common.sha256(self.archive / item["archive"]), item["sha256"])
        for n in self.fixture.affected_external:
            self.assertFalse((self.socdoors / n).exists(), n)
        for n in self.fixture.unrelated_external:
            self.assertTrue((self.socdoors / n).exists(), n)

    def test_plan_readonly(self):
        before = install.tree(self.project)
        self.plan()
        self.assertEqual(before, install.tree(self.project))
        self.assertFalse(self.archive.exists())

    def test_stage_tampering_rejected(self):
        (self.wave2 / "bids/participants.tsv").write_text("changed since validated")
        with self.assertRaisesRegex(ValueError, "staged outputs differ"):
            self.plan()

    def test_missing_family_rejected(self):
        p = next((self.wave2 / "derivatives/warpkit").rglob("*warpkit_done"))
        p.unlink()
        self.refresh_ready()
        with self.assertRaisesRegex(ValueError, "missing staged product family"):
            self.plan()

    def test_protected_production_change_rejected(self):
        (self.project / "bids/participants.tsv").write_text("changed")
        with self.assertRaisesRegex(ValueError, "production input changed"):
            self.plan()

    def test_unvalidated_cohort_rejected(self):
        (self.cohort / "validation.json").write_text('{"validated":false}')
        with self.assertRaisesRegex(ValueError, "completed cohort validation"):
            self.plan()

    def test_changed_cohort_input_rejected(self):
        n = next(iter(install.read(self.cohort / "manifest.json")["rows"][0]["inputs"]))
        (self.project / n).write_text("tampered")
        with self.assertRaisesRegex(ValueError, "cohort input already changed"):
            self.plan()

    def test_existing_archive_rejected(self):
        self.archive.mkdir()
        with self.assertRaisesRegex(ValueError, "archive already exists"):
            self.plan()

    def test_scans_mismatch_rejected(self):
        (self.wave2 / install.scans_name("10964")).write_text("filename\n")
        self.refresh_ready()
        with self.assertRaisesRegex(ValueError, "scans rows"):
            self.plan()

    def test_copy_failure_before_live_mutation(self):
        p = self.plan()
        before = {n: Path(n).read_bytes() for n in p["remove"]}
        with patch.object(install, "copy_shared", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(RuntimeError, "Installation incomplete"):
                install.install(p)
        self.assertEqual(before, {n: Path(n).read_bytes() for n in p["remove"]})
        self.assertEqual(install.read(self.archive / "installation.json")["state"], "preparing")

    def test_failed_partial_install_cannot_be_called_complete(self):
        p = self.plan()
        with patch.object(install.os, "link", side_effect=OSError("interrupted")):
            with self.assertRaises(RuntimeError):
                install.install(p)
        with self.assertRaisesRegex(ValueError, "partial installation"):
            install.check(install.read(self.archive / "installation.json"))
        for item in p["originals"].values():
            self.assertTrue((self.archive / item["archive"]).exists())

    def test_busy_cohort_lock_rejected(self):
        with (self.cohort / ".cohort.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                with install.guards(self.project, self.stages, self.socdoors, self.ugr, self.cohort):
                    self.fail("must not enter")

    def test_busy_stage_lock_rejected(self):
        with (self.stage.parent / ".stage.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                with install.guards(self.project, self.stages, self.socdoors, self.ugr, self.cohort):
                    self.fail("must not enter")

    def test_existing_subject_lock_never_deleted(self):
        lock = self.project / "logs/locks/fmriprep-sub-10964.lock"
        lock.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            with install.guards(self.project, self.stages, self.socdoors, self.ugr, self.cohort):
                self.fail("must not enter")
        self.assertTrue(lock.is_dir())

    def test_ses01_and_other_runs_not_selected(self):
        for name in ("bids/sub-10964/ses-01/func/sub-10964_ses-01_task-doors_run-1_bold.nii.gz",
                     "bids/sub-11935/ses-01/func/sub-11935_ses-01_task-doors_run-10_bold.nii.gz",
                     "bids/participants.tsv"):
            self.assertIsNone(install.product(name, "10964"))
            self.assertIsNone(install.product(name, "11935"))

    def test_symlink_payload_rejected(self):
        target = next((self.wave2 / "derivatives/tedana").rglob("*.tsv"))
        target.unlink()
        target.symlink_to(self.project / "bids/participants.tsv")
        with self.assertRaisesRegex(ValueError, "symlink forbidden"):
            self.plan()

    def test_completed_cohort_mutation_detected(self):
        receipt = install.install(self.plan())
        (self.cohort / "old-results/success.json").write_text("bad")
        with self.assertRaisesRegex(ValueError, "cohort experiment changed"):
            install.check(receipt)

    def test_new_stale_product_detected(self):
        receipt = install.install(self.plan())
        p = self.project / "bids/sub-10964/ses-02/func/sub-10964_ses-02_task-ugr_run-1_obsolete.json"
        self.write(p, b"stale")
        with self.assertRaisesRegex(ValueError, "unexpected/stale"):
            install.check(receipt)

    def test_decision_mutation_detected(self):
        receipt = install.install(self.plan())
        (self.project / "qc/run_disposition.tsv").write_text("bad change")
        with self.assertRaisesRegex(ValueError, "protected file changed"):
            install.check(receipt)

    def test_guarded_install_and_check_leave_experiment_unchanged(self):
        with install.guards(self.project, self.stages, self.socdoors, self.ugr, self.cohort):
            receipt = install.install(self.plan())
        with install.guards(self.project, self.stages, self.socdoors, self.ugr, self.cohort):
            install.check(receipt)
        self.assertFalse((self.project / "logs/locks/fmriprep-sub-10964.lock").exists())
        self.assertFalse((self.project / "logs/locks/fmriprep-sub-11935.lock").exists())

    def add_surface_link(self, root, subject):
        folder = root / f"derivatives/freesurfer/sub-{subject}_ses-01/surf"
        self.write(folder / "lh.white", b"completed surface")
        link = folder / "lh.white.K"
        link.symlink_to("lh.white")
        return link

    def test_freesurfer_links_not_payload_and_preserved_through_install(self):
        stage_link = self.add_surface_link(self.wave2, "10964")
        prod_link = self.add_surface_link(self.project, "10964")
        self.refresh_ready()
        metadata = install.read(self.wave2 / "repair.json")
        s = prod_link.stat()
        metadata["protected"][str(prod_link)] = [s.st_size, s.st_mtime_ns]
        (self.wave2 / "repair.json").write_text(json.dumps(metadata))
        # The 11935 ready receipt also observes production FreeSurfer links.
        other = self.add_surface_link(self.project, "11935")
        ready = install.read(self.stage / common.READY)
        s = other.stat()
        ready["inputs"] = {str(other): [s.st_size, s.st_mtime_ns]}
        (self.stage / common.READY).write_text(json.dumps(ready))
        before = install.freesurfer_snapshot(self.project)
        p = self.plan()
        self.assertFalse(any("freesurfer" in n for n in p["installs"]))
        receipt = install.install(p)
        install.check(receipt)
        self.assertEqual(before, install.freesurfer_snapshot(self.project))
        self.assertTrue(stage_link.is_symlink())
        self.assertEqual(os.readlink(prod_link), "lh.white")

    def test_changed_surface_target_still_rejected(self):
        link = self.add_surface_link(self.wave2, "10964")
        self.refresh_ready()
        link.resolve().write_text("changed since final validation")
        with self.assertRaisesRegex(ValueError, "staged outputs differ"):
            self.plan()

    def test_surface_link_topology_change_detected_after_install(self):
        link = self.add_surface_link(self.project, "10964")
        receipt = install.install(self.plan())
        link.unlink()
        link.symlink_to("different-target")
        with self.assertRaisesRegex(ValueError, "FreeSurfer anatomy or links changed"):
            install.check(receipt)

    def feat_folder(self):
        return self.socdoors / "derivatives/fsl/sub-11935/ses-01/L1_task-socialdoors_ses-01_model-1_type-act_run-1_sm-5.feat"

    def test_feat_file_directory_and_dangling_links_archived_without_following(self):
        feat = self.feat_folder()
        target = self.fixture.root / "external-FSL-template"
        self.write(target / "standard.nii.gz", b"external template must not change")
        reg = feat / "reg"
        reg.mkdir()
        links = {reg / "standard.nii.gz": str(target / "standard.nii.gz"),
                 reg / "external-dir": str(target),
                 reg / "missing.nii.gz": "no-such-file.nii.gz",
                 reg / "relative.nii.gz": "standard.nii.gz"}
        for path, text in links.items():
            path.symlink_to(text)
        before = install.tree(target)
        p = self.plan()
        for path, text in links.items():
            self.assertEqual(p["originals"][str(path)]["symlink"], text)
        self.assertFalse(any("external-dir/standard" in n for n in p["originals"]))
        receipt = install.install(p)
        install.check(receipt)
        for path, text in links.items():
            archived = self.archive / p["originals"][str(path)]["archive"]
            self.assertTrue(archived.is_symlink())
            self.assertEqual(os.readlink(archived), text)
            self.assertFalse(os.path.lexists(path))
        self.assertEqual(before, install.tree(target))
        self.assertEqual((target / "standard.nii.gz").read_bytes(), b"external template must not change")

    def test_archive_link_tampering_detected(self):
        link = self.feat_folder() / "linked-template"
        link.symlink_to("missing-template")
        p = self.plan()
        receipt = install.install(p)
        archived = self.archive / p["originals"][str(link)]["archive"]
        archived.unlink()
        archived.symlink_to("changed-target")
        with self.assertRaisesRegex(ValueError, "original file/link mismatch"):
            install.check(receipt)

    def test_archive_does_not_traverse_symlink_parent(self):
        folder = self.fixture.root / "unsafe-parent"
        folder.symlink_to(self.project, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink forbidden"):
            install.original_signature(folder / "bids/participants.tsv")

    def test_special_feat_file_rejected_before_install(self):
        os.mkfifo(self.feat_folder() / "named-pipe")
        with self.assertRaisesRegex(ValueError, "special file"):
            self.plan()
        self.assertFalse(self.archive.exists())


if __name__ == "__main__":
    unittest.main()
