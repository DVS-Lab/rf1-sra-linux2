from argparse import Namespace
import json
from pathlib import Path
import sys

import nibabel as nib
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import benchmark_tedana_cohort as cohort
from build_run_qc import RunKey


def image(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    obj = nib.Nifti1Image(np.asarray(data, dtype=np.float32), np.eye(4))
    if obj.ndim == 4:
        obj.header.set_zooms((1, 1, 1, 1.615))
    nib.save(obj, path)


@pytest.fixture
def experiment(tmp_path):
    project = tmp_path / "project"
    excluded = tmp_path / "excluded"
    excluded.mkdir()
    key = RunKey("10001", "01", "ugr", "1")
    func = project / "bids/sub-10001/ses-01/func"
    preproc = project / "derivatives/fmriprep/sub-10001/ses-01/func"
    for echo in range(1, 5):
        image(func / f"{key.prefix}_echo-{echo}_part-mag_bold.nii.gz", np.ones((2, 2, 2, 8)))
        (func / f"{key.prefix}_echo-{echo}_part-mag_bold.json").write_text(json.dumps({"EchoTime": echo * .015, "SoftwareVersions": "XA60"}))
        image(preproc / f"{key.prefix}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz", np.ones((2, 2, 2, 8)))
    image(preproc / f"{key.prefix}_part-mag_desc-brain_mask.nii.gz", np.ones((2, 2, 2)))
    pd.DataFrame({"trans_x": np.arange(8), "non_steady_state_outlier00": [1] + [0]*7}).to_csv(
        preproc / f"{key.prefix}_part-mag_desc-confounds_timeseries.tsv", sep="\t", index=False)
    root = project / "derivatives/tedana-audit/cohort-pca-v1"
    root.mkdir(parents=True)
    args = Namespace(excluded_source_root=excluded, tedana_command=tmp_path / "tedana", jobs=2,
                     retry_failed=False, min_free_gib=0)
    assert cohort.prepare(args, project, root) == 0
    manifest = cohort.load_manifest(args, project, root)
    return args, project, root, manifest


def products(job, offset=0):
    prefix = job.run_key
    components = ["ica_0", "ica_1"]
    job.output_dir.mkdir(parents=True, exist_ok=True)
    image(job.output_dir / f"{prefix}_desc-optcom_bold.nii.gz", np.ones((2, 2, 2, 7)) + offset)
    image(job.output_dir / f"{prefix}_desc-denoised_bold.nii.gz", np.ones((2, 2, 2, 7)))
    pd.DataFrame(np.arange(14).reshape(7, 2), columns=components).to_csv(job.output_dir / f"{prefix}_desc-ICA_mixing.tsv", sep="\t", index=False)
    pd.DataFrame({"Component": components, "classification": ["accepted", "rejected"],
                  "normalized variance explained": [60., 40.]}).to_csv(job.output_dir / f"{prefix}_desc-tedana_metrics.tsv", sep="\t", index=False)
    pd.DataFrame({"Component": components}).to_csv(job.output_dir / f"{prefix}_desc-PCA_metrics.tsv", sep="\t", index=False)
    (job.output_dir / f"{prefix}_desc-PCACrossComponent_metrics.json").write_text(json.dumps({
        name: {"n_components": 2} for name in ("aic", "kic", "mdl", "varex_90", "varex_95")}))


def fake_execution(monkeypatch, args, project, root, manifest, offset_config=None):
    def execute(command, **kwargs):
        assert kwargs["env"]["OPENBLAS_NUM_THREADS"] == "1"
        assert kwargs["pass_fds"]
        config = {"aic": "nss-fastica", "kic": "nss-kic-fastica", "mdl": "nss-mdl-fastica"}[command[command.index("--tedpca") + 1]]
        job = cohort.job_for(project, root, args.tedana_command, manifest["rows"][0], config)
        products(job, int(config == offset_config))
        return Namespace(returncode=0)
    monkeypatch.setattr(cohort.subprocess, "run", execute)


def test_all_runs_not_qc_filtered_and_plan_frozen(experiment):
    args, project, root, manifest = experiment
    assert len(manifest["rows"]) == 1
    assert manifest["rows"][0]["nss_count"] == 1
    assert cohort.prepare(args, project, root) == 0
    row = manifest["rows"][0]
    (project / row["fmriprep_confounds"]).write_text("changed")
    with pytest.raises(ValueError, match="inputs changed"):
        cohort.load_manifest(args, project, root)
    with pytest.raises(ValueError, match="frozen manifest differs"):
        cohort.prepare(args, project, root)


def test_end_to_end_and_resume(experiment, monkeypatch):
    args, project, root, manifest = experiment
    fake_execution(monkeypatch, *experiment)
    with cohort.exclusive(root) as lock:
        assert cohort.run_jobs(args, project, root, manifest, "26.0.3", lock.fileno()) == 0
    assert json.loads((root / "validation.json").read_text())["validated"]
    summary = pd.read_csv(root / "component_summary.tsv", sep="\t")
    assert len(summary) == 3
    assert (summary.rejected_components == 1).all()
    assert np.allclose(summary.rejected_normalized_variance, .4)
    def forbidden(*args, **kwargs):
        raise AssertionError("completed runs must not execute again")
    monkeypatch.setattr(cohort.subprocess, "run", forbidden)
    with cohort.exclusive(root) as lock:
        assert cohort.run_jobs(args, project, root, manifest, "26.0.3", lock.fileno()) == 0
    statuses = pd.read_csv(root / "status.tsv", sep="\t")
    assert set(statuses.status) == {"SKIPPED_COMPLETE"}


def test_matched_optcom_validation(experiment, monkeypatch):
    args, project, root, manifest = experiment
    fake_execution(monkeypatch, *experiment, offset_config="nss-mdl-fastica")
    with cohort.exclusive(root) as lock:
        assert cohort.run_jobs(args, project, root, manifest, "26.0.3", lock.fileno()) == 1
    assert "optcom inputs differ" in (root / "check_failures.tsv").read_text()


def test_partial_outputs_archive_only_on_explicit_retry(experiment, monkeypatch):
    args, project, root, manifest = experiment
    job = cohort.job_for(project, root, args.tedana_command, manifest["rows"][0], cohort.CONFIGS[0])
    job.output_dir.mkdir(parents=True)
    (job.output_dir / "important.log").write_text("preserve me")
    fake_execution(monkeypatch, *experiment)
    with cohort.exclusive(root) as lock:
        result = cohort.run_one(job, "26.0.3", False, 0, lock.fileno())
        assert result["status"] == "FAILED"
        assert (job.output_dir / "important.log").read_text() == "preserve me"
        assert cohort.run_one(job, "26.0.3", True, 0, lock.fileno())["status"] == "COMPLETED"
    assert next((root / "failed-attempts").rglob("important.log")).read_text() == "preserve me"


def test_bad_completed_products_never_overwritten(experiment, monkeypatch):
    args, project, root, manifest = experiment
    fake_execution(monkeypatch, *experiment)
    job = cohort.job_for(project, root, args.tedana_command, manifest["rows"][0], cohort.CONFIGS[0])
    with cohort.exclusive(root) as lock:
        assert cohort.run_one(job, "26.0.3", False, 0, lock.fileno())["status"] == "COMPLETED"
        path = job.output_dir / f"{job.run_key}_desc-ICA_mixing.tsv"
        path.write_text("changed")
        assert cohort.run_one(job, "26.0.3", True, 0, lock.fileno())["status"] == "FAILED"
        assert path.read_text() == "changed"


def test_lock(experiment):
    root = experiment[2]
    with cohort.exclusive(root):
        with pytest.raises(ValueError, match="another cohort command"):
            with cohort.exclusive(root):
                pass


def test_missing_inputs_reported_not_silently_omitted(experiment):
    args, project, root, manifest = experiment
    (root / "manifest.json").unlink()
    (project / manifest["rows"][0]["fmriprep_mask"]).unlink()
    assert cohort.prepare(args, project, root) == 1
    assert len(json.loads((root / "manifest.json").read_text())["blocked"]) == 1
    assert "missing input" in (root / "blocked.tsv").read_text()


def test_source_exclusion_roster_changes_stop_resume(experiment):
    args, project, root, manifest = experiment
    (args.excluded_source_root / "Smith-SRA-10002").mkdir()
    with pytest.raises(ValueError, match="roster/source exclusions differ"):
        cohort.load_manifest(args, project, root)


def test_noncontiguous_nss_blocks_prepare(experiment):
    args, project, root, manifest = experiment
    (root / "manifest.json").unlink()
    path = project / manifest["rows"][0]["fmriprep_confounds"]
    frame = pd.read_csv(path, sep="\t")
    frame["non_steady_state_outlier00"] = [0, 1] + [0]*6
    frame.to_csv(path, sep="\t", index=False)
    assert cohort.prepare(args, project, root) == 1
    assert "NSS mismatch" in (root / "blocked.tsv").read_text()


def test_low_disk_does_not_start_job(experiment, monkeypatch):
    args, project, root, manifest = experiment
    job = cohort.job_for(project, root, args.tedana_command, manifest["rows"][0], cohort.CONFIGS[0])
    monkeypatch.setattr(cohort.shutil, "disk_usage", lambda _: Namespace(free=0))
    with cohort.exclusive(root) as lock:
        result = cohort.run_one(job, "26.0.3", False, 1, lock.fileno())
    assert result["status"] == "FAILED"
    assert not job.output_dir.exists()


def test_wrong_metric_component_labels_rejected(experiment):
    args, project, root, manifest = experiment
    job = cohort.job_for(project, root, args.tedana_command, manifest["rows"][0], cohort.CONFIGS[0])
    products(job)
    path = job.output_dir / f"{job.run_key}_desc-tedana_metrics.tsv"
    frame = pd.read_csv(path, sep="\t")
    frame.loc[0, "Component"] = "wrong"
    frame.to_csv(path, sep="\t", index=False)
    with pytest.raises(ValueError, match="component labels/count"):
        cohort.validate_products(job)


def test_output_wrong_length_rejected(experiment):
    args, project, root, manifest = experiment
    job = cohort.job_for(project, root, args.tedana_command, manifest["rows"][0], cohort.CONFIGS[0])
    products(job)
    image(job.output_dir / f"{job.run_key}_desc-denoised_bold.nii.gz", np.ones((2, 2, 2, 8)))
    with pytest.raises(ValueError, match="geometry/length"):
        cohort.validate_products(job)


def test_changed_source_invalidates_prior_pass(experiment, monkeypatch):
    args, project, root, manifest = experiment
    fake_execution(monkeypatch, *experiment)
    with cohort.exclusive(root) as lock:
        assert cohort.run_jobs(args, project, root, manifest, "26.0.3", lock.fileno()) == 0
    (project / manifest["rows"][0]["fmriprep_confounds"]).write_text("changed")
    with pytest.raises(ValueError, match="inputs changed"):
        cohort.check(args, project, root, manifest, "26.0.3")
    assert not json.loads((root / "validation.json").read_text())["validated"]
