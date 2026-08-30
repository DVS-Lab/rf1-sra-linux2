from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
import pytest


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


qc = load("audit_tedana_nuisance_qc", CODE / "audit_tedana_nuisance_qc.py")


def save_image(path: Path, data: np.ndarray) -> None:
    affine = np.diag([2.7, 2.7, 2.97, 1.0])
    image = nib.Nifti1Image(data.astype(np.float32), affine)
    image.set_qform(affine, 1); image.set_sform(affine, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(image, str(path))


def make_inputs(project: Path) -> dict[str, str]:
    subject = "10001"; key = f"sub-{subject}_ses-01_task-trust_run-1"
    ffunc = project / "derivatives" / "fmriprep" / f"sub-{subject}" / "ses-01" / "func"
    bold = ffunc / f"{key}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
    mask = ffunc / f"{key}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"
    time = np.arange(12, dtype=float)
    data = np.ones((2, 2, 2, 12), dtype=float) * 100
    data += time[None, None, None, :] * np.linspace(0.1, 0.8, 8).reshape(2, 2, 2, 1)
    data[..., 5:] += 2 * np.sin(time[5:])[None, None, None, :]
    save_image(bold, data); save_image(mask, np.ones((2, 2, 2)))
    confounds: dict[str, np.ndarray] = {}
    for index, name in enumerate(("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"), start=1):
        values = np.sin(time / index)
        derivative = np.r_[np.nan, np.diff(values)]
        confounds[name] = values
        confounds[f"{name}_derivative1"] = derivative
        confounds[f"{name}_power2"] = values**2
        confounds[f"{name}_derivative1_power2"] = derivative**2
    confounds["framewise_displacement"] = np.r_[np.nan, np.abs(np.diff(np.sin(time)))]
    confounds["a_comp_cor_00"] = np.cos(time)
    confounds["cosine00"] = np.cos(np.pi * time / len(time))
    confounds_path = ffunc / f"{key}_part-mag_desc-confounds_timeseries.tsv"
    pd.DataFrame(confounds).to_csv(confounds_path, sep="\t", index=False)
    audit = project / "derivatives" / "tedana-audit" / "benchmark"
    mixing = pd.DataFrame({"ICA_00": np.sin(time), "ICA_01": np.cos(time / 2)})
    metrics = pd.DataFrame({"Component": ["ICA_00", "ICA_01"], "classification": ["accepted", "rejected"]})
    for config in ("full-fastica", "nss-fastica"):
        directory = audit / config / key; directory.mkdir(parents=True)
        mixing.to_csv(directory / f"{key}_desc-ICA_mixing.tsv", sep="\t", index=False)
        if config == "nss-fastica":
            mixing.to_csv(directory / f"{key}_desc-ICA_mixingFullGrid.tsv", sep="\t", index=False)
        metrics.to_csv(directory / f"{key}_desc-tedana_metrics.tsv", sep="\t", index=False)
    return {
        "subject": subject, "session": "01", "task": "trust", "run": "1",
        "run_key": key, "software_versions": "syngo MR XA60", "nss_count": "0",
        "number_of_original_volumes": "12",
        "fmriprep_mask": mask.relative_to(project).as_posix(),
        "fmriprep_confounds": confounds_path.relative_to(project).as_posix(),
    }


def test_nuisance_adjust_preserves_temporal_mean() -> None:
    data = np.column_stack((np.arange(8, dtype=float) + 10, np.arange(8, dtype=float) ** 2 + 20))
    nuisance = np.arange(8, dtype=float)[:, None]
    adjusted, rank = qc.nuisance_adjust(data, nuisance)
    assert rank == 1
    assert np.allclose(np.mean(adjusted, axis=0), np.mean(data, axis=0))


def test_n0_identity_uses_numerical_not_bitwise_equality() -> None:
    full = np.arange(24, dtype=float).reshape(6, 4) + 100
    numerically_same = full + 1e-7

    qc.assert_n0_numerical_identity(
        "sub-10001_ses-01_task-trust_run-1", full, numerically_same
    )


def test_n0_identity_rejects_meaningful_difference() -> None:
    full = np.arange(24, dtype=float).reshape(6, 4) + 100

    with pytest.raises(ValueError, match="max_abs_diff"):
        qc.assert_n0_numerical_identity(
            "sub-10001_ses-01_task-trust_run-1", full, full + 0.1
        )


def test_end_to_end_nuisance_qc(tmp_path: Path) -> None:
    project = tmp_path / "project"; row = make_inputs(project)
    sentinel = project / "qc" / "tedana_audit" / "sentinel_runs.tsv"
    sentinel.parent.mkdir(parents=True)
    pd.DataFrame([row]).to_csv(sentinel, sep="\t", index=False)
    output = project / "qc" / "tedana_audit" / "nuisance_qc"
    args = Namespace(
        project_root=project, sentinel_tsv=sentinel,
        audit_root=project / "derivatives" / "tedana-audit", output_dir=output,
        overwrite=False, dry_run=False,
    )
    assert qc.build(args) == 0
    assert qc.check(args) == 0
    runs = qc.read_tsv(output / "run_metrics.tsv")
    pairs = qc.read_tsv(output / "paired_conditions.tsv")
    assert len(runs) == 3; assert len(pairs) == 2
    nss_pair = next(row for row in pairs if row["comparison"] == "tedana_full_vs_tedana_nss")
    assert float(nss_pair["normalized_rmse"]) == 0
    assert float(nss_pair["median_voxelwise_temporal_correlation"]) == 1
    assert "simultaneously in FEAT" in (output / "report.md").read_text()
