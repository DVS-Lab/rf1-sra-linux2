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


summary = load("summarize_tedana_benchmark", CODE / "summarize_tedana_benchmark.py")


def save_image(path: Path, data: np.ndarray) -> None:
    affine = np.diag([2.7, 2.7, 2.97, 1.0])
    image = nib.Nifti1Image(data.astype(np.float32), affine)
    zooms = (2.7, 2.7, 2.97, 1.615) if data.ndim == 4 else (2.7, 2.7, 2.97)
    image.header.set_zooms(zooms)
    image.set_qform(affine, 1)
    image.set_sform(affine, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(image, str(path))


def component_table(path: Path, robust: bool) -> None:
    if robust:
        frame = pd.DataFrame(
            {
                "Component": ["ICA_00", "ICA_01"],
                "classification": ["accepted", "rejected"],
                "normalized variance explained": [0.7, 0.3],
                "kappa": [12.0, 2.0],
                "rho": [2.0, 10.0],
            }
        )
    else:
        frame = pd.DataFrame(
            {
                "Component": ["ICA_00", "ICA_01", "ICA_02"],
                "classification": ["accepted", "rejected", "rejected"],
                "normalized variance explained": [50.0, 30.0, 20.0],
                "kappa": [12.0, 3.0, 2.0],
                "rho": [2.0, 8.0, 10.0],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t", index=False)


def sentinel_row(subject: str, nss: int) -> dict[str, str]:
    key = f"sub-{subject}_ses-01_task-trust_run-1"
    row = {
        "subject": subject,
        "session": "01",
        "task": "trust",
        "run": "1",
        "run_key": key,
        "nss_count": str(nss),
        "selection_reason": "synthetic_control",
        "number_of_original_volumes": "6",
        "fmriprep_mask": (
            f"derivatives/fmriprep/sub-{subject}/ses-01/func/"
            f"{key}_part-mag_desc-brain_mask.nii.gz"
        ),
        "fmriprep_confounds": (
            f"derivatives/fmriprep/sub-{subject}/ses-01/func/"
            f"{key}_part-mag_desc-confounds_timeseries.tsv"
        ),
    }
    historical = {
        "n_ica": 4,
        "n_accepted": 2,
        "n_rejected": 2,
        "rejected_fraction": 0.5,
        "accepted_normalized_variance": 0.6,
        "rejected_normalized_variance": 0.4,
        "largest_component_normalized_variance": 0.35,
        "largest_rejected_component_normalized_variance": 0.25,
    }
    row.update({name: str(value) for name, value in historical.items()})
    return row


def create_run_inputs(
    project: Path, audit_root: Path, row: dict[str, str], changed: bool
) -> None:
    key = row["run_key"]
    grid = np.arange(1, 9, dtype=np.float32).reshape((2, 2, 2))
    time = np.arange(6, dtype=np.float32)
    full_t2 = grid / 100
    full_optcom = grid[..., None] + time
    exclude_t2 = full_t2 * 1.1 if changed else full_t2.copy()
    exclude_optcom = full_optcom + 0.5 if changed else full_optcom.copy()
    save_image(project / row["fmriprep_mask"], np.ones((2, 2, 2)))
    confounds: dict[str, np.ndarray] = {}
    for index, name in enumerate(
        ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"), start=1
    ):
        values = np.arange(6, dtype=float) ** 2 / index
        derivative = np.r_[np.nan, np.diff(values)]
        confounds[name] = values
        confounds[f"{name}_derivative1"] = derivative
        confounds[f"{name}_power2"] = values**2
        confounds[f"{name}_derivative1_power2"] = derivative**2
    confounds["framewise_displacement"] = np.r_[np.nan, np.linspace(0.1, 0.5, 5)]
    confounds_path = project / row["fmriprep_confounds"]
    confounds_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(confounds).to_csv(confounds_path, sep="\t", index=False)
    for config, t2_data, optcom_data in (
        ("t2s-full", full_t2, full_optcom),
        ("t2s-exclude-nss", exclude_t2, exclude_optcom),
    ):
        directory = audit_root / "benchmark" / config / key
        save_image(directory / f"{key}_T2starmap.nii.gz", t2_data)
        save_image(directory / f"{key}_desc-optcom_bold.nii.gz", optcom_data)
    for config, robust in (("nss-fastica", False), ("nss-robustica", True)):
        directory = audit_root / "benchmark" / config / key
        component_table(directory / f"{key}_desc-tedana_metrics.tsv", robust)
        native_optcom = full_optcom[..., int(row["nss_count"]) :]
        temporal_mean = np.mean(native_optcom, axis=3, keepdims=True)
        scale = 0.7 if robust else 0.8
        denoised = temporal_mean + scale * (native_optcom - temporal_mean)
        save_image(directory / f"{key}_desc-optcom_bold.nii.gz", native_optcom)
        save_image(directory / f"{key}_desc-denoised_bold.nii.gz", denoised)
        (directory / f"{key}_tedana_report.html").write_text("<html>synthetic</html>\n")
        for component in range(3):
            figure = directory / "figures" / f"comp_{component:03d}.png"
            figure.parent.mkdir(parents=True, exist_ok=True)
            figure.write_bytes(b"synthetic figure")
    cross = (
        audit_root
        / "benchmark"
        / "nss-robustica"
        / key
        / f"{key}_desc-ICACrossComponent_metrics.json"
    )
    quality = 0.5 if changed else 0.9
    cross.write_text(
        json.dumps(
            {
                "robustica_mean_index_quality": quality,
                "fastica_convergence_warning_count": 1 if changed else 0,
            }
        )
    )


def test_component_summary_normalizes_reported_variance(tmp_path: Path) -> None:
    path = tmp_path / "metrics.tsv"
    component_table(path, robust=False)

    metrics, _frame = summary.component_summary(path)

    assert metrics["n_ica"] == 3
    assert metrics["rejected_fraction"] == pytest.approx(2 / 3)
    assert metrics["accepted_normalized_variance"] == pytest.approx(0.5)
    assert metrics["rejected_normalized_variance"] == pytest.approx(0.5)
    assert metrics["largest_rejected_component_normalized_variance"] == pytest.approx(
        0.3
    )


def test_read_only_arrays_are_not_modified() -> None:
    values = np.array([1.0, 2.0, 3.0])
    values.setflags(write=False)

    assert summary._correlation(values, values) == pytest.approx(1.0)
    assert summary._normalize_variance(values) == pytest.approx([1 / 6, 2 / 6, 3 / 6])
    assert np.array_equal(values, [1.0, 2.0, 3.0])


def test_n0_identity_check_rejects_different_outputs() -> None:
    same = np.arange(8, dtype=float)
    with pytest.raises(ValueError, match=r"NSS=0 T2\* control differs"):
        summary._assert_n0_identity(
            "sub-10001_ses-01_task-trust_run-1",
            same,
            same + 1,
            same,
            same,
        )


def test_end_to_end_summary_build_and_check(tmp_path: Path) -> None:
    project = tmp_path / "project"
    audit_root = project / "derivatives" / "tedana-audit"
    output = project / "qc" / "tedana_audit" / "benchmark"
    sentinel = project / "qc" / "tedana_audit" / "sentinel_runs.tsv"
    rows = [sentinel_row("10001", 0), sentinel_row("10002", 2)]
    sentinel.parent.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(sentinel, sep="\t", index=False)
    create_run_inputs(project, audit_root, rows[0], changed=False)
    create_run_inputs(project, audit_root, rows[1], changed=True)
    args = Namespace(
        project_root=project,
        sentinel_tsv=sentinel,
        audit_root=audit_root,
        output_dir=output,
        overwrite=False,
        dry_run=False,
    )

    assert summary.run_build(args) == 0
    assert summary.run_check(args) == 0

    t2_rows = summary.read_tsv(output / "paired_t2s.tsv")
    ica_rows = summary.read_tsv(output / "paired_ica.tsv")
    denoising_rows = summary.read_tsv(output / "paired_denoising.tsv")
    review_rows = summary.read_tsv(output / "review_manifest.tsv")
    assert len(t2_rows) == len(ica_rows) == len(denoising_rows) == 2
    assert float(t2_rows[0]["t2star_median_absolute_difference_seconds"]) == 0
    assert float(
        t2_rows[1]["t2star_median_absolute_percent_difference"]
    ) == pytest.approx(10.0, rel=1e-5)
    assert float(t2_rows[1]["t2star_log_spatial_correlation"]) == pytest.approx(1.0)
    assert float(
        t2_rows[1]["t2star_fraction_absolute_percent_difference_gt_5"]
    ) == pytest.approx(1.0)
    assert float(ica_rows[0]["robustica_minus_fastica_n_ica"]) == -1
    assert float(denoising_rows[0]["robustica_minus_fastica_denoised_tsnr"]) != 0
    assert len(review_rows) == 5
    assert all(row["report_path"] for row in review_rows)
    assert all(row["component_figure_path"] for row in review_rows)
    assert (output / "figures" / "t2star_nss_effect.png").is_file()
    assert "production TEDANA outputs" in (output / "report.md").read_text()

    with (output / "paired_t2s.tsv").open("a") as handle:
        handle.write("tampered\n")
    assert summary.run_check(args) == 1
