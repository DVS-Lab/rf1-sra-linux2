from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


design = load("audit_tedana_design", CODE / "audit_tedana_design.py")


def test_matrix_diagnostics_reports_rank_constants_and_duplicates() -> None:
    frame = pd.DataFrame(
        {
            "signal": [0.0, 1.0, 2.0, 3.0],
            "duplicate": [0.0, 1.0, 2.0, 3.0],
            "zero": [0.0, 0.0, 0.0, 0.0],
            "constant": [2.0, 2.0, 2.0, 2.0],
        }
    )

    result = design.matrix_diagnostics(frame)

    assert result["columns"] == 4
    assert result["rank"] == 2
    assert result["rank_with_intercept"] == 2
    assert result["zero_columns"] == 1
    assert result["constant_nonzero_columns"] == 1
    assert result["duplicate_columns"] == 1
    assert np.isinf(result["standardized_condition_number"])


def make_complete_run(project: Path) -> dict[str, str]:
    key = "sub-10001_ses-01_task-trust_run-1"
    ffunc = project / "derivatives" / "fmriprep" / "sub-10001" / "ses-01" / "func"
    tfunc = project / "derivatives" / "tedana" / "sub-10001" / "ses-01"
    ffunc.mkdir(parents=True)
    tfunc.mkdir(parents=True)
    confounds = pd.DataFrame(
        {
            "trans_x": np.arange(8, dtype=float),
            "trans_y": np.arange(8, dtype=float) ** 2,
            "framewise_displacement": np.r_[np.nan, np.ones(7)],
            "cosine00": np.cos(np.arange(8)),
            "non_steady_state_outlier00": [1.0, 0, 0, 0, 0, 0, 0, 0],
        }
    )
    confounds_path = ffunc / f"{key}_part-mag_desc-confounds_timeseries.tsv"
    confounds.to_csv(confounds_path, sep="\t", index=False)
    metrics = pd.DataFrame(
        {
            "Component": ["ICA_00", "ICA_01", "ICA_02"],
            "classification": ["accepted", "rejected", "rejected"],
        }
    )
    metrics_path = tfunc / f"{key}_desc-tedana_metrics.tsv"
    metrics.to_csv(metrics_path, sep="\t", index=False)
    mixing = pd.DataFrame(
        {
            "ICA_00": np.linspace(0, 1, 8),
            "ICA_01": np.sin(np.arange(8)),
            "ICA_02": np.cos(np.arange(8)),
        }
    )
    mixing_path = tfunc / f"{key}_desc-ICA_mixing.tsv"
    mixing.to_csv(mixing_path, sep="\t", index=False)
    pca_path = tfunc / f"{key}_desc-PCA_metrics.tsv"
    pd.DataFrame({"Component": ["PCA_00", "PCA_01", "PCA_02"]}).to_csv(
        pca_path, sep="\t", index=False
    )
    cross_path = tfunc / f"{key}_desc-PCACrossComponent_metrics.json"
    cross_path.write_text(
        json.dumps(
            {
                "aic": {"n_components": 3, "explained_variance_total": 0.99},
                "kic": {"n_components": 2, "explained_variance_total": 0.95},
                "mdl": {"n_components": 1, "explained_variance_total": 0.90},
                "varex_90": {"n_components": 1, "explained_variance_total": 0.90},
                "varex_95": {"n_components": 2, "explained_variance_total": 0.95},
            }
        )
    )
    combined = design.build_confounds(confounds_path, mixing_path, metrics_path)
    combined_path = (
        project
        / "derivatives"
        / "fsl"
        / "confounds_tedana"
        / "sub-10001"
        / f"{key}_desc-TedanaPlusConfounds.tsv"
    )
    combined_path.parent.mkdir(parents=True)
    combined.to_csv(combined_path, sep="\t", index=False, header=False)
    return {
        "subject": "10001",
        "session": "01",
        "paradigm": "trust",
        "task": "trust",
        "run": "1",
        "run_key": key,
        "audit_status": "complete",
        "audit_issues": "",
        "software_versions": "XA60",
        "number_of_original_volumes": "8",
        "nss_count": "1",
        "number_of_steady_state_volumes": "7",
        "fmriprep_confounds": confounds_path.relative_to(project).as_posix(),
        "tedana_metrics": metrics_path.relative_to(project).as_posix(),
        "tedana_mixing": mixing_path.relative_to(project).as_posix(),
        "tedana_pca_metrics": pca_path.relative_to(project).as_posix(),
        "echo_times": "0.01;0.02;0.03;0.04",
        "echo_files": "a;b;c;d",
        "fmriprep_mask": "mask.nii.gz",
    }


def test_end_to_end_design_build_and_check(tmp_path: Path) -> None:
    project = tmp_path / "project"
    current = project / "qc" / "tedana_audit" / "current_runs.tsv"
    output = project / "qc" / "tedana_audit" / "design"
    complete = make_complete_run(project)
    incomplete = dict(complete)
    incomplete.update(
        {
            "subject": "10002",
            "run_key": "sub-10002_ses-01_task-trust_run-1",
            "audit_status": "incomplete",
            "audit_issues": "missing_tedana",
        }
    )
    current.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([complete, incomplete]).to_csv(current, sep="\t", index=False)
    args = Namespace(
        project_root=project,
        current_runs=current,
        combined_confounds_dir=project
        / "derivatives"
        / "fsl"
        / "confounds_tedana",
        output_dir=output,
        overwrite=False,
        dry_run=False,
        benchmark_cap=4,
    )

    assert design.build(args) == 0
    assert design.check(args) == 0

    rows = design.read_tsv(output / "cohort_design_burden.tsv")
    assert len(rows) == 2
    assert rows[0]["design_status"] == "complete"
    assert rows[0]["aic_components"] == "3"
    assert rows[0]["kic_components"] == "2"
    assert rows[0]["flag_aic_explains_more_than_98_percent"] == "1"
    assert rows[0]["existing_combined_matches_reconstruction"] == "1"
    assert rows[1]["design_status"] == "incomplete"
    assert len(design.read_tsv(output / "pca_method_benchmark.tsv")) == 1
    assert (output / "figures" / "design_burden.png").is_file()
    assert "not automatic exclusions" in (output / "report.md").read_text()

    with (output / "cohort_design_burden.tsv").open("a") as handle:
        handle.write("tampered\n")
    assert design.check(args) == 1
