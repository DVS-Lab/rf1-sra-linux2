import json
from pathlib import Path
import sys
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import build_socialdoors_randomise as bundle
from test_diagnose_socialdoors_difference import decision


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    pairs, paths = [], []
    for i, sub in enumerate(("10001", "10002", "10003", "10004")):
        for contrast in bundle.diag.LABELS:
            row = dict(subject=sub, session="01", contrast=contrast,
                       group="strict_pass" if i < 3 else "fd_tsnr_flagged",
                       flags="" if i < 3 else "doors:fd_mean:high_fd_mean")
            for task in bundle.diag.TASKS:
                row.update({task + "_coverage_pct": "95", task + "_fd_mean_fence": "0.5",
                            task + "_tsnr_fence": "10", task + "_qc_failure_reasons": "",
                            task + "_fd_mean": str(0.1 + (0.03 if task == "socialdoors" else 0.01) * i),
                            task + "_tsnr": str(20 + (4 if task == "socialdoors" else 1) * i)})
                for field in ("cope", "varcope", "mask"):
                    data = np.ones((3, 4, 5))
                    if field == "cope":
                        data *= ((i + 1) * int(contrast) if task == "socialdoors" else 2)
                    elif field == "mask" and sub == "10003":
                        data[0, 0, 0] = 0
                    path = tmp_path / f"{sub}_{task}_{contrast}_{field}.nii.gz"
                    nib.save(nib.Nifti1Image(data, np.diag([2., 2., 2., 1.])), path)
                    row[task + "_" + field] = str(path)
                    paths.append(path)
            pairs.append(row)
    diagnostic = tmp_path / "diagnostic"
    runs = bundle.diag.diagnostic_runs([decision(subject=s, task=t)
                                       for s in ("10001", "10002", "10003", "10004") for t in bundle.diag.TASKS])
    plan = dict(policy=bundle.diag.POLICY, previous=str(tmp_path / "previous"), pairs=pairs,
                runs=runs, sources=[bundle.diag.fingerprint(p) for p in paths])
    monkeypatch.setattr(bundle.diag, "prepare", lambda _: plan)
    monkeypatch.setattr(bundle.diag, "plot", lambda *_: None)
    bundle.diag.build(SimpleNamespace(output=diagnostic, previous=tmp_path / "previous", jobs=2))
    manifest = tmp_path / "strict.tsv"
    manifest.write_text(bundle.table([r for r in pairs if r["group"] == "strict_pass"]))
    return SimpleNamespace(manifest=manifest, diagnostic=diagnostic, cohort=None, output=tmp_path / "bundle"), plan


def test_complete_bundle_and_unchanged_resume(prepared):
    args, original = prepared
    bundle.build(args)
    bundle.check(args)
    plan = bundle.load_plan(args.output)
    assert plan["subjects"] == ["10001", "10002", "10003"]
    assert plan["scope"] == "imaging_pool_not_final_paper_cohort"
    for contrast in bundle.diag.LABELS:
        img = nib.load(args.output / f"cope-{contrast}/difference_4d.nii.gz")
        assert img.shape == (3, 4, 5, 3)
        assert img.get_data_dtype() == np.dtype("float32")
        assert img.header.get_xyzt_units()[1] == "unknown"
        a = img.get_fdata()
        assert (a[0, 0, 0] == 0).all()
        np.testing.assert_array_equal(a[1, 1, 1], np.arange(1, 4) * int(contrast) - 2)
        assert np.isfinite(a).all()
    times = {p: p.stat().st_mtime_ns for p in args.output.rglob("*") if p.is_file()}
    bundle.build(args)
    assert {p: p.stat().st_mtime_ns for p in times} == times
    assert not list(args.output.rglob("design.*"))
    bundle.diag.verify_fingerprints(original["sources"])


def test_final_cohort_order_centering_and_mask(prepared, tmp_path):
    args, _ = prepared
    args.cohort = tmp_path / "final.tsv"
    args.cohort.write_text("subject\nsub-10002\n10001\n")
    bundle.build(args)
    bundle.check(args)
    plan = bundle.load_plan(args.output)
    assert plan["scope"] == "provided_final_cohort"
    _, order = bundle.read_rows(args.output / "subjects.tsv")
    assert [r["subject"] for r in order] == ["10002", "10001"]
    assert [r["volume_index"] for r in order] == ["0", "1"]
    a = nib.load(args.output / "cope-4/difference_4d.nii.gz").get_fdata()
    np.testing.assert_array_equal(a[0, 0, 0], [6, 2])  # Dropped subject's mask no longer restricts support.
    _, centered = bundle.read_rows(args.output / "qc_covariates_centered.tsv")
    np.testing.assert_allclose([float(r["delta_fd"]) for r in centered], [0.01, -0.01])
    for name in bundle.DERIVED:
        assert sum(float(r[name]) for r in centered) == pytest.approx(0)
    info = json.loads((args.output / "covariate_centering.json").read_text())
    assert info["means"]["delta_tsnr"] == 1.5
    assert info["automatically_selected_for_design"] is False


@pytest.mark.parametrize("text,match", [
    ("subject\n10001\n10001\n", "duplicate"),
    ("subject\n10001\n10004\n", "outside settled"),
    ("subject\n10001\n99999\n", "outside settled"),
    ("subject\n10001\n", "At least two"),
    ("subject\n10001\nabc\n", "Invalid"),
    ("participant_id\n10001\n10002\n", "header"),
])
def test_cohort_refuses_silent_selection(prepared, tmp_path, text, match):
    args, plan = prepared
    cohort = tmp_path / "cohort.tsv"
    cohort.write_text(text)
    with pytest.raises(ValueError, match=match):
        bundle.choose_subjects(bundle.strict_rows(args.manifest, plan), cohort)


def test_manifest_cannot_reintroduce_flagged_or_drop_subject(prepared):
    args, plan = prepared
    args.manifest.write_text(bundle.table(plan["pairs"]))
    with pytest.raises(ValueError, match="entire verified strict pool"):
        bundle.strict_rows(args.manifest, plan)
    args.manifest.write_text(bundle.table([r for r in plan["pairs"] if r["subject"] == "10001"]))
    with pytest.raises(ValueError, match="entire verified strict pool"):
        bundle.strict_rows(args.manifest, plan)


@pytest.mark.parametrize("field,value", [("doors_coverage_pct", "94.9"), ("doors_fd_mean", "0.51"),
                                        ("doors_tsnr", "9"), ("doors_tsnr", "nan")])
def test_numeric_qc_guard(prepared, field, value):
    args, plan = prepared
    for row in plan["pairs"]:
        if row["subject"] == "10001":
            row[field] = value
    args.manifest.write_text(bundle.table([r for r in plan["pairs"] if r["group"] == "strict_pass"]))
    with pytest.raises(ValueError, match="settled run QC"):
        bundle.strict_rows(args.manifest, plan)


def test_corrupted_complete_image_not_overwritten(prepared):
    args, _ = prepared
    bundle.build(args)
    path = args.output / "cope-1/difference_4d.nii.gz"
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="artifact inventory/hash"):
        bundle.build(args)
    assert path.read_bytes() == b"corrupt"


def test_partial_resume_preserves_receipted_outputs(prepared, monkeypatch):
    args, _ = prepared
    original = bundle.contrast_arrays

    def interrupt(plan, contrast):
        if contrast == "2":
            raise RuntimeError("interrupted")
        return original(plan, contrast)

    monkeypatch.setattr(bundle, "contrast_arrays", interrupt)
    with pytest.raises(RuntimeError, match="interrupted"):
        bundle.build(args)
    path = args.output / "cope-1/difference_4d.nii.gz"
    timestamp = path.stat().st_mtime_ns
    monkeypatch.setattr(bundle, "contrast_arrays", original)
    bundle.build(args)
    bundle.check(args)
    assert path.stat().st_mtime_ns == timestamp


def test_source_mutation_stops_verification(prepared):
    args, original = prepared
    bundle.build(args)
    path = Path(original["pairs"][0]["doors_cope"])
    img = nib.load(path)
    nib.save(nib.Nifti1Image(img.get_fdata() + 1, img.affine), path)
    with pytest.raises(ValueError, match="input changed"):
        bundle.check(args)


def test_changed_cohort_requires_new_directory(prepared, tmp_path):
    args, _ = prepared
    bundle.build(args)
    args.cohort = tmp_path / "cohort.tsv"
    args.cohort.write_text("subject\n10001\n10002\n")
    with pytest.raises(ValueError, match="Different cohort"):
        bundle.build(args)


def test_empty_intersection_and_grid_mismatch(prepared, monkeypatch):
    args, _ = prepared
    plan = bundle.prepare(args)
    # Isolate the mask/grid guard; normal execution also rejects changed receipts.
    monkeypatch.setattr(bundle.diag, "verify_pair", lambda *_: None)
    row = plan["pairs"][0]
    path = bundle.diag.directory(args.diagnostic, row) / "valid_mask.nii.gz"
    img = nib.load(path)
    nib.save(nib.Nifti1Image(np.zeros(img.shape), img.affine), path)
    with pytest.raises(ValueError, match="Empty group intersection"):
        bundle.contrast_arrays(plan, "1")
    affine = img.affine.copy()
    affine[0, 3] += 1
    nib.save(nib.Nifti1Image(np.ones(img.shape), affine), path)
    with pytest.raises(ValueError, match="grids differ"):
        bundle.contrast_arrays(plan, "1")


def test_canonical_snapshot_matches_saved_json_value_types():
    root = bundle.ROOT / "qc/paired_difference/socialdoors-v1"
    _, rows = bundle.read_rows(root / "diagnostic_pairs.tsv")
    for row in rows:
        for task in bundle.diag.TASKS:
            row[task + "_dof_value"] = float(row[task + "_dof_value"])
    selected = bundle.strict_rows(root / "strict_pairs.tsv", dict(pairs=rows))
    assert len(selected) == 484
    assert len(bundle.choose_subjects(selected, None)) == 121


def test_output_cannot_modify_diagnostic_tree(prepared):
    args, _ = prepared
    args.output = args.diagnostic / "new-bundle"
    with pytest.raises(ValueError, match="must not overlap"):
        bundle.build(args)
    assert not args.output.exists()
