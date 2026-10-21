import argparse
import json
from pathlib import Path
import sys

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import inspect_xa60_coverage as inspect


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def record(subject, flagged=False, task="doors", session="01", run="1", fd=.1, era="XA60"):
    return dict(subject=subject, session=session, task=task, run=run, fd_mean=str(fd),
                brain_coverage_pct="98" if flagged else "99.9", brain_coverage_outlier=str(flagged),
                tedana_rejected_components="20", qc_complete="TRUE", software_era=era)


def tables(project, rows):
    (project / "qc/scanner_era").mkdir(parents=True, exist_ok=True)
    inspect.write_table(project / "qc/run_qc.tsv", rows)
    inspect.write_table(project / "qc/scanner_era/run_metrics.tsv", rows)


def test_selection_exact_task_session_run_era_and_fd(tmp_path):
    rows = [record("10001", True, fd=.2), record("10002", fd=.19), record("10003", fd=.25),
            record("10004", fd=.2, era="E11"), record("10005", fd=.2, task="socialdoors"),
            record("10006", fd=.2, session="02"), record("10007", fd=.2, run="2")]
    tables(tmp_path, rows)
    cases, pairs, units = inspect.select_pairs(tmp_path, ["doors"], ["01"], 2)
    assert len(cases) == 1 and len(units) == 3
    assert [p["control"] for p in pairs] == [inspect.name(rows[1]), inspect.name(rows[2])]
    assert pairs[0]["fd_difference"] == pytest.approx(.01)
    rows[1]["tedana_rejected_components"] = "500"
    tables(tmp_path, rows)
    assert inspect.select_pairs(tmp_path, ["doors"], ["01"], 2)[1] == pairs


def test_duplicate_stale_and_no_control_are_explicit(tmp_path):
    a = record("10001", True)
    tables(tmp_path, [a, a])
    with pytest.raises(ValueError, match="Duplicate"):
        inspect.select_pairs(tmp_path, ["doors"], ["01"], 2)
    tables(tmp_path, [a])
    _, pairs, _ = inspect.select_pairs(tmp_path, ["doors"], ["01"], 2)
    assert pairs[0]["control"] == ""
    inspect.write_table(tmp_path / "qc/scanner_era/run_metrics.tsv", [dict(a, brain_coverage_pct="99")])
    with pytest.raises(ValueError, match="differ"):
        inspect.select_pairs(tmp_path, ["doors"], ["01"], 2)


def image(data, affine=None):
    return nib.Nifti1Image(np.asarray(data, dtype=np.float32), np.eye(4) if affine is None else affine)


def test_mask_loss_with_retained_signal_is_not_acquisition_verdict():
    target = image(np.ones((10, 10, 10)))
    mask = np.ones((10, 10, 10))
    mask[:2] = 0
    metrics, _, missing, _ = inspect.spatial_metrics(target, image(mask), image(np.ones(mask.shape)*100))
    assert metrics["fixed_reference_coverage_pct"] == 80
    assert metrics["mask_grid_contains_target_pct"] == 100
    assert metrics["missing_voxels_above_5pct_retained_median_pct"] == 100
    assert missing.sum() == 200
    metrics, _, _, _ = inspect.spatial_metrics(target, image(mask), image(mask*100))
    assert metrics["missing_voxels_above_5pct_retained_median_pct"] == 0
    assert not any("exclude" in k or "diagnosis" in k for k in metrics)


def test_grid_clipping_is_visible_on_fixed_reference(tmp_path):
    target = image(np.ones((10, 10, 10)))
    mask = image(np.ones((8, 10, 10)))
    metrics, _, _, _ = inspect.spatial_metrics(target, mask, mask)
    assert metrics["fixed_reference_coverage_pct"] == 80
    assert metrics["mask_grid_contains_target_pct"] == 80
    nib.save(target, tmp_path / "target.nii.gz")
    nib.save(mask, tmp_path / "mask.nii.gz")
    assert inspect.qc.compute_coverage(tmp_path / "target.nii.gz", tmp_path / "mask.nii.gz") == 100


def fixture(project):
    shape = (41, 51, 41)
    affine = np.diag([4., 4., 4., 1.])
    affine[:3, 3] = (-80, -100, -60)
    x, y, z = np.indices(shape)
    target = ((x-20)/16)**2 + ((y-25)/20)**2 + ((z-20)/16)**2 < 1
    target_path = project / "qc/reference" / inspect.qc.TARGET_MASK_NAME
    target_path.parent.mkdir(parents=True)
    nib.save(image(target, affine), target_path)
    put(project / "qc/provenance.json", json.dumps({"coverage": {"target_mask_sha256": inspect.sha(target_path)}}))
    rows = []
    for sub, flagged in (("10001", True), ("10002", False)):
        row = record(sub, flagged)
        stem = inspect.name(row)
        folder = project / f"derivatives/fmriprep/sub-{sub}/ses-01/func"
        folder.mkdir(parents=True)
        m = target & (x < (32 if flagged else 41))
        mask = folder / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"
        nib.save(image(m, affine), mask)
        data = target * (100 + x + y*.2)
        series = image(np.repeat(data[..., None], 8, axis=3), affine)
        bold = folder / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
        nib.save(series, bold)
        raw = project / f"bids/sub-{sub}/ses-01/func/{stem}_echo-2_part-mag_bold.nii.gz"
        raw.parent.mkdir(parents=True)
        nib.save(series, raw)
        put(raw.with_name(raw.name.replace(".nii.gz", ".json")), json.dumps({"RepetitionTime": 2,
            "EchoTime": .03, "PatientName": "DO NOT COPY", "AcquisitionDateTime": "DO NOT COPY"}))
        nib.save(image(data, affine), folder / f"{stem}_part-mag_boldref.nii.gz")
        nib.save(image(m, affine), folder / f"{stem}_part-mag_desc-brain_mask.nii.gz")
        anat = project / f"derivatives/fmriprep/sub-{sub}/anat/sub-{sub}_space-MNI152NLin6Asym_desc-preproc_T1w.nii.gz"
        anat.parent.mkdir(parents=True)
        nib.save(image(data*2, affine), anat)
        row.update(fmriprep_brain_mask=str(mask.relative_to(project)), bids_bold=str(raw.relative_to(project)),
                   brain_coverage_pct=str(inspect.qc.compute_coverage(target_path, mask)))
        rows.append(row)
    tables(project, rows)
    return rows


def args(project):
    return argparse.Namespace(project_root=project, private_dir=project / "work/inspection", tasks="doors",
                              sessions="01", controls=1, jobs=1, max_cases=None, dry_run=False)


def test_sampled_mean_and_optional_discovery(tmp_path):
    rows = fixture(tmp_path)
    paths, states = inspect.resolve(tmp_path, rows[0])
    assert states["mni_t1"] == "available" and states["native_ref"] == "available"
    mean, indices = inspect.sampled_mean(paths["raw"])
    assert indices == [2, 4, 6] and len(mean.shape) == 3
    assert inspect.optional_one([paths["raw"], paths["mask"]])[1] == "ambiguous"


def test_build_preserves_inputs_and_checks_package(tmp_path):
    rows = fixture(tmp_path)
    before = {p: inspect.sha(p) for p in tmp_path.rglob("*") if p.is_file()}
    a = args(tmp_path)
    inspect.build(a)
    inspect.check(a)
    assert all(inspect.sha(p) == value for p, value in before.items())
    assert (a.private_dir / "index.html").is_file()
    assert (a.private_dir / "runs" / inspect.name(rows[0]) / "missing_focus.png").is_file()
    evidence = json.loads((a.private_dir / "runs" / inspect.name(rows[0]) / "evidence.json").read_text())
    assert evidence["acquisition_parameters"] == {"EchoTime": .03, "RepetitionTime": 2}
    assert "DO NOT COPY" not in (a.private_dir / "runs" / inspect.name(rows[0]) / "evidence.json").read_text()
    assert evidence["metrics"]["missing_voxels_above_5pct_retained_median_pct"] == 100
    with pytest.raises(ValueError, match="existing"):
        inspect.build(a)
    (a.private_dir / "runs" / inspect.name(rows[0]) / "mni_bold.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="output changed"):
        inspect.check(a)


def test_dry_run_writes_nothing(tmp_path):
    tables(tmp_path, [record("10001", True), record("10002")])
    a = args(tmp_path)
    a.dry_run = True
    inspect.build(a)
    assert not a.private_dir.exists()


def test_missing_required_image_does_not_pass(tmp_path):
    rows = fixture(tmp_path)
    paths, _ = inspect.resolve(tmp_path, rows[0])
    paths["raw"].unlink()
    private = tmp_path / "work/test"
    private.mkdir(parents=True)
    result = inspect.process_one(tmp_path, private, rows[0])
    assert result["status"] == "inspection_failed"
    assert not (private / "runs" / inspect.name(rows[0]) / "evidence.json").exists()


def test_live_coverage_disagreement_stops_run(tmp_path):
    rows = fixture(tmp_path)
    rows[0]["brain_coverage_pct"] = "1"
    private = tmp_path / "work/test"
    private.mkdir(parents=True)
    result = inspect.process_one(tmp_path, private, rows[0])
    assert result["status"] == "inspection_failed"
    assert "differs from canonical QC" in result["reason"]


def test_target_provenance_is_required(tmp_path):
    fixture(tmp_path)
    put(tmp_path / "qc/provenance.json", json.dumps({"coverage": {"target_mask_sha256": "wrong"}}))
    a = args(tmp_path)
    with pytest.raises(ValueError, match="target mask"):
        inspect.build(a)
    assert not a.private_dir.exists()
