from __future__ import annotations

import importlib.util
import json
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


summary = load(
    "summarize_tedana_pca_methods", CODE / "summarize_tedana_pca_methods.py"
)


def save_image(path: Path, data: np.ndarray) -> None:
    affine = np.diag([2.7, 2.7, 2.97, 1.0])
    image = nib.Nifti1Image(data.astype(np.float32), affine)
    image.header.set_zooms(
        (2.7, 2.7, 2.97, 1.615) if data.ndim == 4 else (2.7, 2.7, 2.97)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(image, str(path))


def make_inputs(project: Path, target: Path) -> None:
    key = "sub-10001_ses-01_task-trust_run-1"
    mask = Path(
        "derivatives/fmriprep/sub-10001/ses-01/func/"
        f"{key}_part-mag_desc-brain_mask.nii.gz"
    )
    confounds = Path(
        "derivatives/fmriprep/sub-10001/ses-01/func/"
        f"{key}_part-mag_desc-confounds_timeseries.tsv"
    )
    row = {
        "subject": "10001",
        "session": "01",
        "task": "trust",
        "run": "1",
        "run_key": key,
        "software_versions": "synthetic",
        "nss_count": "1",
        "number_of_original_volumes": "6",
        "number_of_steady_state_volumes": "5",
        "selection_reason": "synthetic",
        "fmriprep_mask": mask.as_posix(),
        "fmriprep_confounds": confounds.as_posix(),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(target, sep="\t", index=False)
    save_image(project / mask, np.ones((2, 2, 2)))
    motion: dict[str, np.ndarray] = {}
    for index, name in enumerate(
        ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"), start=1
    ):
        values = np.arange(6, dtype=float) / index
        derivative = np.r_[np.nan, np.diff(values)]
        motion[name] = values
        motion[f"{name}_derivative1"] = derivative
        motion[f"{name}_power2"] = values**2
        motion[f"{name}_derivative1_power2"] = derivative**2
    motion["framewise_displacement"] = np.r_[np.nan, np.linspace(0.1, 0.5, 5)]
    motion["a_comp_cor_00"] = np.linspace(-1, 1, 6)
    confound_path = project / confounds
    confound_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(motion).to_csv(confound_path, sep="\t", index=False)
    grid = np.arange(1, 9, dtype=np.float32).reshape((2, 2, 2, 1))
    optcom = grid + np.arange(5, dtype=np.float32)
    counts = {"aic": 3, "kic": 2, "mdl": 1}
    scales = {"aic": 0.70, "kic": 0.80, "mdl": 0.90}
    cross = {
        name: {"n_components": count, "explained_variance_total": 0.8 + count / 100}
        for name, count in counts.items()
    }
    cross.update(
        {
            "varex_90": {"n_components": 4, "explained_variance_total": 0.90},
            "varex_95": {"n_components": 5, "explained_variance_total": 0.95},
        }
    )
    for criterion, config in summary.METHODS.items():
        directory = project / "derivatives" / "tedana-audit" / "benchmark" / config / key
        count = counts[criterion]
        components = [f"ICA_{index:02d}" for index in range(count)]
        classifications = ["accepted"] * max(0, count - 1) + ["rejected"]
        metrics = pd.DataFrame(
            {
                "Component": components,
                "classification": classifications,
                "normalized variance explained": np.arange(count, 0, -1),
                "kappa": np.linspace(10, 2, count),
                "rho": np.linspace(2, 10, count),
            }
        )
        directory.mkdir(parents=True, exist_ok=True)
        metrics.to_csv(directory / f"{key}_desc-tedana_metrics.tsv", sep="\t", index=False)
        pd.DataFrame(
            np.column_stack([np.arange(6, dtype=float) ** (index + 1) for index in range(count)]),
            columns=components,
        ).to_csv(directory / f"{key}_desc-ICA_mixingFullGrid.tsv", sep="\t", index=False)
        pd.DataFrame({"Component": components}).to_csv(
            directory / f"{key}_desc-PCA_metrics.tsv", sep="\t", index=False
        )
        (directory / f"{key}_desc-PCACrossComponent_metrics.json").write_text(
            json.dumps(cross)
        )
        temporal_mean = np.mean(optcom, axis=3, keepdims=True)
        denoised = temporal_mean + scales[criterion] * (optcom - temporal_mean)
        save_image(directory / f"{key}_desc-optcom_bold.nii.gz", optcom)
        save_image(directory / f"{key}_desc-denoised_bold.nii.gz", denoised)


def test_build_and_check_matched_pca_methods(tmp_path: Path) -> None:
    project = tmp_path / "project"
    target = project / "qc" / "tedana_audit" / "design" / "pca_method_benchmark.tsv"
    output = project / "qc" / "tedana_audit" / "pca_methods"
    make_inputs(project, target)
    args = Namespace(
        project_root=project,
        target_tsv=target,
        audit_root=project / "derivatives" / "tedana-audit",
        output_dir=output,
        overwrite=False,
        dry_run=False,
    )

    assert summary.run_build(args) == 0
    assert summary.run_check(args) == 0
    methods = summary.read_tsv(output / "method_runs.tsv")
    pairs = summary.read_tsv(output / "paired_methods.tsv")
    assert len(methods) == 3
    assert len(pairs) == 2
    assert {row["criterion"] for row in methods} == {"aic", "kic", "mdl"}
    mdl = next(row for row in pairs if row["candidate_criterion"] == "mdl")
    assert float(mdl["candidate_minus_aic_pca_components"]) == -2
    assert float(mdl["candidate_minus_aic_residual_df_before_task"]) >= 0
    assert float(mdl["aic_candidate_median_voxelwise_temporal_correlation"]) == pytest.approx(1.0)
    assert "no gold-standard clean fMRI" in (output / "report.md").read_text()

    with (output / "paired_methods.tsv").open("a") as handle:
        handle.write("tampered\n")
    assert summary.run_check(args) == 1


def test_optcom_must_match_across_criteria(tmp_path: Path) -> None:
    project = tmp_path / "project"
    target = project / "qc" / "tedana_audit" / "design" / "pca_method_benchmark.tsv"
    make_inputs(project, target)
    key = "sub-10001_ses-01_task-trust_run-1"
    path = (
        project
        / "derivatives"
        / "tedana-audit"
        / "benchmark"
        / "nss-mdl-fastica"
        / key
        / f"{key}_desc-optcom_bold.nii.gz"
    )
    image = nib.load(path)
    save_image(path, np.asarray(image.dataobj) + 1)
    row = summary.read_tsv(target)[0]

    with pytest.raises(ValueError, match="optcom differs"):
        summary.summarize_run(project, project / "derivatives" / "tedana-audit", row)
