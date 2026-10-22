"""Local safety/unit tests. Actual ANTs/fMRIPrep integration runs on Linux2."""
import argparse
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))
import run_11935_initialization as experiment


class InitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "work/new-trial"
        raw = self.root / "bids/sub-11935/ses-01/func"
        func = self.root / "derivatives/fmriprep/sub-11935/ses-01/func"
        raw.mkdir(parents=True)
        func.mkdir(parents=True)
        for stem in (experiment.STEM, "sub-11935_ses-01_task-ugr_run-1"):
            for echo in range(1, 5):
                (raw / f"{stem}_echo-{echo}_sbref.nii.gz").write_bytes(b"synthetic input")
            for suffix in ("desc-hmc_boldref", "desc-coreg_boldref", "desc-brain_mask"):
                (func / f"{stem}_part-mag_{suffix}.nii.gz").write_bytes(b"synthetic derivative")
        anat = self.root / "derivatives/fmriprep/sub-11935/anat"
        anat.mkdir()
        for suffix in ("desc-preproc_T1w.nii.gz", "desc-brain_mask.nii.gz", "dseg.nii.gz",
                       "from-T1w_to-MNI152NLin6Asym_mode-image_xfm.h5",
                       "from-MNI152NLin6Asym_to-T1w_mode-image_xfm.h5"):
            (anat / ("sub-11935_" + suffix)).write_bytes(b"synthetic anatomy")
        (anat.parents[1] / "dataset_description.json").write_text("{}")
        fs = self.root / "derivatives/freesurfer/sub-11935/mri"
        fs.mkdir(parents=True)
        (fs / "T1.mgz").write_bytes(b"synthetic FreeSurfer")
        self.image = self.root / "image.simg"
        self.image.write_bytes(b"synthetic image")
        templates = self.root / "templates"
        templates.mkdir()
        licenses = self.root / "licenses"
        licenses.mkdir()
        (licenses / "fs_license.txt").write_text("synthetic license")
        self.args = argparse.Namespace(project=self.root, output=self.output, image=self.image,
                                       templateflow=templates, licenses=licenses, nprocs=8, dry_run=False)

    def test_patch_only_expected_workflow(self):
        source = "def other():\n    transform=('Affine', 0.1),\n\n" + \
                 "def init_enhance_and_skullstrip_bold_wf():\n    transform=('Affine', 0.1),\n    name='init_aff'\n\n" + \
                 "def last():\n    transform=('Affine', 0.1),\n"
        changed = experiment.patch_source(source)
        self.assertEqual(changed.count(experiment.NEW), 1)
        self.assertEqual(changed.replace(experiment.NEW, experiment.OLD), source)
        with self.assertRaises(ValueError):
            experiment.patch_source(changed)
        with self.assertRaises(ValueError):
            experiment.patch_source(source.replace("name='init_aff'", "name='unexpected'"))

    def test_bounded_filter_and_commands(self):
        filters = experiment.bids_filter()
        self.assertEqual(set(filters), {"bold", "sbref"})
        for row in filters.values():
            self.assertEqual((row["session"], row["task"], row["run"]), ("01", "socialdoors", 1))
            self.assertEqual(row["part"], [None, "mag"])
        original = experiment.full_command(self.args, self.output, "affine", "/env/util.py")
        patched = experiment.full_command(self.args, self.output, "rigid", "/env/util.py")
        self.assertIn(f"{self.root}:/project:ro", original)
        self.assertIn(f"{self.output}/patch/util.py:/env/util.py:ro", patched)
        self.assertNotIn(f"{self.output}/patch/util.py:/env/util.py:ro", original)
        for cmd in (original, patched):
            self.assertIn("anatomy=/out/anatomy", cmd)
            self.assertIn("--fs-no-resume", cmd)
            self.assertNotIn("--fs-no-reconall", cmd)
            self.assertNotIn("--sloppy", cmd)
            self.assertNotIn("--ignore", cmd)
            self.assertEqual(cmd[cmd.index("--random-seed") + 1], str(experiment.FULL_SEED))
            self.assertEqual(cmd[cmd.index("--omp-nthreads") + 1], "1")
            self.assertEqual(cmd[cmd.index("--nprocs") + 1], "8")

    def test_anatomy_collection_cannot_reuse_functional_outputs(self):
        paths = experiment.anat_files(self.root)
        self.assertTrue(paths)
        self.assertTrue(all("func" not in p.parts for p in paths))
        (self.root / "derivatives/fmriprep/sub-11935/anat/sub-11935_dseg.nii.gz").unlink()
        with self.assertRaisesRegex(ValueError, "Missing reusable"):
            experiment.anat_files(self.root)

    def test_existing_and_production_destinations_rejected(self):
        with self.assertRaises(ValueError):
            experiment.guard_output(self.root, self.root / "derivatives/unsafe")
        self.output.mkdir(parents=True)
        with self.assertRaises(ValueError):
            experiment.guard_output(self.root, self.output)

    def test_dry_run_writes_nothing(self):
        self.args.dry_run = True
        with patch.object(experiment.shutil, "which", return_value="apptainer"), \
                patch.object(experiment.subprocess, "run") as runner:
            self.assertEqual(experiment.host(self.args), 0)
            runner.assert_not_called()
        self.assertFalse(self.output.exists())

    def fake_run(self, cmd, cwd, env, check):
        self.assertEqual(cwd, self.output)
        self.assertIn(f"{self.root}:/project:ro", cmd)
        self.assertNotIn("APPTAINER_BINDPATH", env)
        if "pairs" in cmd:
            experiment.write_json(self.output / "patch/provenance.json", dict(installed_module="/env/util.py"))
            cache = self.output / "pair_cache"
            cache.mkdir()
            (cache / "cached-result.pklz").write_bytes(b"no archive")
        if "validate" in cmd:
            mode = cmd[cmd.index("--mode") + 1]
            experiment.write_json(self.output / ("full-" + mode + "-validation.json"),
                                  dict(canonical_coverage_pct=99.5))
        return types.SimpleNamespace(returncode=0)

    def test_host_copies_not_links_and_archives_only_evidence(self):
        inputs = {str(p): experiment.sha(p) for p in self.root.rglob("*") if p.is_file()}
        with patch.object(experiment.shutil, "which", return_value="apptainer"), \
                patch.object(experiment.subprocess, "run", side_effect=self.fake_run) as runner, \
                patch.dict(experiment.os.environ, {"APPTAINER_BINDPATH": "/unsafe:/rw"}):
            self.assertEqual(experiment.host(self.args), 0)
            self.assertEqual(runner.call_count, 5)
        self.assertEqual(inputs, {name: experiment.sha(name) for name in inputs})
        original = self.root / "derivatives/freesurfer/sub-11935/mri/T1.mgz"
        copied = self.output / "fs/affine/sub-11935/mri/T1.mgz"
        self.assertNotEqual(original.stat().st_ino, copied.stat().st_ino)
        self.assertFalse(copied.is_symlink())
        self.assertFalse(any("func" in p.parts for p in (self.output / "anatomy").rglob("*")))
        state = json.loads((self.output / "state.json").read_text())
        self.assertTrue(state["validated"])
        self.assertTrue(state["production_inputs_unchanged"])
        with tarfile.open(self.output.with_suffix(".tar.gz")) as archive:
            for name in archive.getnames():
                self.assertFalse(set(Path(name).parts) & {"pair_cache", "cache", "fs", "anatomy", "full"})

    def test_failure_stops_before_full_run_and_preserves_evidence(self):
        with patch.object(experiment.shutil, "which", return_value="apptainer"), \
                patch.object(experiment.subprocess, "run", return_value=types.SimpleNamespace(returncode=7)) as runner:
            with self.assertRaisesRegex(RuntimeError, "exited 7"):
                experiment.host(self.args)
            self.assertEqual(runner.call_count, 1)
        state = json.loads((self.output / "state.json").read_text())
        self.assertFalse(state["validated"])
        self.assertTrue(state["production_inputs_unchanged"])
        self.assertTrue(self.output.with_suffix(".tar.gz").is_file())

    def test_detects_external_source_change(self):
        def tamper(*args, **kwargs):
            completed = self.fake_run(*args, **kwargs)
            (self.root / "bids/sub-11935/ses-01/func" / (experiment.STEM + "_echo-1_sbref.nii.gz")).write_bytes(b"changed")
            return completed
        with patch.object(experiment.shutil, "which", return_value="apptainer"), \
                patch.object(experiment.subprocess, "run", side_effect=tamper):
            with self.assertRaisesRegex(ValueError, "preservation"):
                experiment.host(self.args)
        self.assertFalse(json.loads((self.output / "state.json").read_text())["validated"])

    def test_original_full_failure_does_not_prevent_patched_test(self):
        def original_fails(cmd, **kwargs):
            if "fmriprep" in cmd and "/out/full/affine/derivatives" in cmd:
                return types.SimpleNamespace(returncode=9)
            return self.fake_run(cmd, **kwargs)
        with patch.object(experiment.shutil, "which", return_value="apptainer"), \
                patch.object(experiment.subprocess, "run", side_effect=original_fails) as runner:
            with self.assertRaisesRegex(RuntimeError, "conditions failed"):
                experiment.host(self.args)
            self.assertEqual(runner.call_count, 4)
        self.assertTrue((self.output / "full-rigid-validation.json").is_file())
        self.assertFalse(json.loads((self.output / "state.json").read_text())["validated"])


class ImageIntegrityTests(unittest.TestCase):
    def test_full_validator_lineage_and_grid_gates(self):
        import numpy as np
        import nibabel as nib
        sys.path.insert(0, str(ROOT / "code"))
        import inspect_xa60_coverage
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "trial"
            project = Path(folder) / "project"
            func = root / "full/rigid/derivatives/sub-11935/ses-01/func"
            raw = project / "bids/sub-11935/ses-01/func"
            prod = project / "derivatives/fmriprep/sub-11935/ses-01/func"
            target = project / "qc/reference" / experiment.TARGET
            for path in (func, raw, prod, target.parent):
                path.mkdir(parents=True)
            affine = np.diag([2.7, 2.7, 2.97, 1])
            def save(path, temporal=False):
                shape = (3, 4, 5, 218) if temporal else (3, 4, 5)
                img = nib.Nifti1Image(np.ones(shape, dtype=np.float32), affine)
                img.set_qform(affine, 1)
                img.set_sform(affine, 1)
                nib.save(img, path)
            for echo in range(1, 5):
                save(raw / (experiment.STEM + f"_echo-{echo}_bold.nii.gz"), True)
                save(func / (experiment.STEM + f"_echo-{echo}_part-mag_desc-preproc_bold.nii.gz"), True)
            mni_name = experiment.STEM + "_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
            save(func / mni_name, True)
            save(prod / mni_name, True)
            save(func / (experiment.STEM + "_part-mag_space-T1w_desc-preproc_bold.nii.gz"), True)
            for suffix in ("_part-mag_desc-brain_mask.nii.gz", "_part-mag_desc-coreg_boldref.nii.gz",
                           "_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz",
                           "_part-mag_space-MNI152NLin6Asym_boldref.nii.gz"):
                save(func / (experiment.STEM + suffix))
            save(target)
            sources_path = func / (experiment.STEM + "_part-mag_desc-coreg_boldref.json")
            sources = ["bids:raw:" + experiment.STEM + "_echo-1_sbref.nii.gz",
                       "bids::sub-11935_ses-01_acq-socialdoors_run-1_fmapid-auto00000_desc-coeff_fieldmap.nii.gz"]
            sources_path.write_text(json.dumps(dict(Sources=sources)))
            conf = func / (experiment.STEM + "_part-mag_desc-confounds_timeseries.tsv")
            conf.write_text("trans_x\ttrans_y\ttrans_z\tframewise_displacement\n" + "0\t0\t0\t0\n" * 218)
            command = root / "full/rigid/cache/func/enhance_and_skullstrip_bold_wf/init_aff/command.txt"
            command.parent.mkdir(parents=True)
            command.write_text("antsAI -t Rigid[0.1]")
            with patch.object(inspect_xa60_coverage, "montage"):
                self.assertEqual(experiment.validate_full("rigid", root, project), 0)
                record = json.loads((root / "full-rigid-validation.json").read_text())
                self.assertEqual(record["confound_rows"], 218)
                self.assertEqual(record["canonical_coverage_pct"], 100.0)
                self.assertFalse(record["scientific_acceptance"])
                sources_path.write_text(json.dumps(dict(Sources=sources[:1])))
                with self.assertRaisesRegex(ValueError, "matched Social Doors"):
                    experiment.validate_full("rigid", root, project)
                sources_path.write_text(json.dumps(dict(Sources=sources)))
                conf.write_text("trans_x\ttrans_y\ttrans_z\tframewise_displacement\n0\t0\t0\t0\n")
                with self.assertRaisesRegex(ValueError, "Confound row count"):
                    experiment.validate_full("rigid", root, project)

    def test_full_image_data_validated(self):
        import numpy as np
        import nibabel as nib
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bold.nii.gz"
            array = np.ones((3, 4, 5, 6), dtype=np.float32)
            nib.save(nib.Nifti1Image(array, np.eye(4)), path)
            self.assertEqual(experiment.check_volume(path, 6).shape, array.shape)
            with self.assertRaisesRegex(ValueError, "count"):
                experiment.check_volume(path, 7)
            array[2, 3, 4, 5] = np.nan
            nib.save(nib.Nifti1Image(array, np.eye(4)), path)
            with self.assertRaisesRegex(ValueError, "Nonfinite"):
                experiment.check_volume(path, 6)


if __name__ == "__main__":
    unittest.main()
