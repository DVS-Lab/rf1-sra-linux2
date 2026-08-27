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


audit = load("audit_tedana", CODE / "audit_tedana.py")
benchmark = load("benchmark_tedana", CODE / "benchmark_tedana.py")


def confounds(nrows: int, nss_rows: tuple[int, ...] = ()) -> pd.DataFrame:
    data: dict[str, np.ndarray] = {}
    for index, name in enumerate(audit.MOTION_BASE, start=1):
        values = np.arange(nrows, dtype=float) / index
        derivative = np.r_[np.nan, np.diff(values)]
        data[name] = values
        data[f"{name}_derivative1"] = derivative
        data[f"{name}_power2"] = values**2
        data[f"{name}_derivative1_power2"] = derivative**2
    data["framewise_displacement"] = np.r_[np.nan, np.linspace(0.0, 0.4, nrows - 1)]
    data["std_dvars"] = np.r_[np.nan, np.linspace(0.8, 1.2, nrows - 1)]
    frame = pd.DataFrame(data)
    for index, row in enumerate(nss_rows):
        values = np.zeros(nrows)
        values[row] = 1
        frame[f"non_steady_state_outlier{index:02d}"] = values
    return frame


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ((), 0),
        ((0,), 1),
        ((0, 1, 2), 3),
    ],
)
def test_detect_nss_counts_contiguous_initial_rows(rows, expected) -> None:
    result = audit.detect_nss(confounds(10, rows))
    assert result.count == expected
    assert result.rows == rows
    assert result.issue == ""


def test_detect_nss_rejects_noncontiguous_and_non_one_hot() -> None:
    result = audit.detect_nss(confounds(10, (0, 2)))
    assert result.count is None
    assert result.issue.startswith("noncontiguous_nss_rows")

    frame = confounds(10, (0,))
    frame.loc[1, "non_steady_state_outlier00"] = 1
    result = audit.detect_nss(frame)
    assert result.count is None
    assert result.issue.endswith("not_one_hot")


def test_motion24_order_and_nan_policy() -> None:
    frame = confounds(12)
    matrix = audit.motion24(frame)
    assert matrix.shape == (12, 24)
    assert audit.MOTION24_COLUMNS[:6] == audit.MOTION_BASE
    assert audit.MOTION24_COLUMNS[6:12] == tuple(
        f"{name}_derivative1" for name in audit.MOTION_BASE
    )
    assert np.all(matrix[0, 6:12] == 0)

    frame.loc[4, "trans_x_derivative1"] = np.nan
    with pytest.raises(ValueError, match="unexpected nonfinite"):
        audit.motion24(frame)


def test_motion24_ols_identifies_exact_component_fit() -> None:
    rng = np.random.default_rng(42)
    motion = rng.normal(size=(80, 24))
    exact = 2 * motion[:, 0] - motion[:, 7]
    unrelated = rng.normal(size=80)
    r2, f_value, p_value = audit.fit_motion24(
        motion, np.column_stack((exact, unrelated))
    )
    assert r2[0] == pytest.approx(1.0)
    assert p_value[0] < 1e-10
    assert f_value[0] > f_value[1]


@pytest.mark.parametrize("nss", [0, 1, 3])
def test_pad_mixing_matrix(nss: int) -> None:
    mixing = pd.DataFrame({"ICA_00": [1.0, 2.0], "ICA_01": [3.0, 4.0]})
    padded = audit.pad_mixing_matrix(mixing, len(mixing) + nss, nss)
    assert len(padded) == len(mixing) + nss
    assert np.all(padded.iloc[:nss].to_numpy() == 0)
    assert np.array_equal(padded.iloc[nss:].to_numpy(), mixing.to_numpy())


def test_pad_mixing_matrix_rejects_wrong_difference() -> None:
    mixing = pd.DataFrame({"ICA_00": [1.0, 2.0]})
    with pytest.raises(ValueError, match="mixing row mismatch"):
        audit.pad_mixing_matrix(mixing, 8, 2)


def save_image(path: Path, data: np.ndarray, affine: np.ndarray, tr: float = 1.615) -> None:
    image = nib.Nifti1Image(data.astype(np.float32), affine)
    image.header.set_data_dtype(np.float32)
    zooms = (2.7, 2.7, 2.97, tr) if data.ndim == 4 else (2.7, 2.7, 2.97)
    image.header.set_zooms(zooms)
    image.set_qform(affine, 1)
    image.set_sform(affine, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(image, str(path))


@pytest.mark.parametrize("nss", [0, 1, 3])
def test_restore_temporal_grid_preserves_header_and_values(tmp_path: Path, nss: int) -> None:
    affine = np.diag([2.7, 2.7, 2.97, 1.0])
    full_data = np.arange(2 * 2 * 2 * 8, dtype=float).reshape((2, 2, 2, 8))
    denoised_data = np.full((2, 2, 2, 8 - nss), 99.0)
    full = tmp_path / "full.nii.gz"
    denoised = tmp_path / "denoised.nii.gz"
    restored = tmp_path / "audit" / "restored.nii.gz"
    save_image(full, full_data, affine)
    save_image(denoised, denoised_data, affine)

    audit.restore_temporal_grid(full, denoised, nss, restored)
    result = nib.load(str(restored))
    result_data = np.asanyarray(result.dataobj)
    assert result.shape == (2, 2, 2, 8)
    assert np.allclose(result.affine, affine)
    assert result.header.get_zooms() == pytest.approx((2.7, 2.7, 2.97, 1.615))
    assert np.array_equal(result_data[..., :nss], full_data[..., :nss])
    assert np.array_equal(result_data[..., nss:], denoised_data)


def test_restore_temporal_grid_rejects_bad_affine(tmp_path: Path) -> None:
    full = tmp_path / "full.nii.gz"
    denoised = tmp_path / "denoised.nii.gz"
    save_image(full, np.zeros((2, 2, 2, 4)), np.eye(4))
    save_image(denoised, np.zeros((2, 2, 2, 3)), np.diag([2, 2, 2, 1]))
    with pytest.raises(ValueError, match="affine mismatch"):
        audit.restore_temporal_grid(full, denoised, 1, tmp_path / "out.nii.gz")


def test_audit_destinations_cannot_escape_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    allowed = project / "derivatives" / "tedana-audit" / "benchmark"
    assert audit.require_audit_destination(project, allowed, "large") == allowed.resolve()
    with pytest.raises(ValueError, match="refusing large output"):
        audit.require_audit_destination(project, project / "derivatives" / "tedana", "large")
    with pytest.raises(ValueError, match="refusing tracked output"):
        audit.require_audit_destination(project, project / "qc", "tracked")


def sentinel_row(project: Path, nss: int = 2) -> dict[str, str]:
    prefix = "sub-10001_ses-01_task-trust_run-1"
    echo_files = []
    for echo in range(1, 5):
        path = project / "derivatives" / "fmriprep" / f"echo-{echo}.nii.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        echo_files.append(path.relative_to(project).as_posix())
    mask = project / "derivatives" / "fmriprep" / "mask.nii.gz"
    mask.touch()
    return {
        "run_key": prefix,
        "nss_count": str(nss),
        "number_of_original_volumes": "100",
        "echo_times": "0.0138;0.03154;0.04928;0.06702",
        "echo_files": ";".join(echo_files),
        "fmriprep_mask": mask.relative_to(project).as_posix(),
        "fmriprep_confounds": "derivatives/fmriprep/confounds.tsv",
    }


def test_benchmark_commands_are_explicit_and_isolated(tmp_path: Path) -> None:
    project = tmp_path / "project"
    audit_root = project / "derivatives" / "tedana-audit"
    row = sentinel_row(project)
    tedana = tmp_path / "tedana"
    t2smap = tmp_path / "t2smap"
    tree = audit_root / "config" / "tree.json"

    full = benchmark.build_job(project, audit_root, tedana, t2smap, tree, row, "t2s-full")
    excluded = benchmark.build_job(project, audit_root, tedana, t2smap, tree, row, "t2s-exclude-nss")
    fast = benchmark.build_job(project, audit_root, tedana, t2smap, tree, row, "nss-fastica")
    robust = benchmark.build_job(project, audit_root, tedana, t2smap, tree, row, "nss-robustica")

    assert "--exclude" not in full.command
    assert excluded.command[excluded.command.index("--exclude") + 1] == "0:2"
    for job in (fast, robust):
        assert job.output_dir.is_relative_to(audit_root)
        assert job.command[job.command.index("--dummy-scans") + 1] == "2"
        assert job.command[job.command.index("--fittype") + 1] == "curvefit"
        assert job.command[job.command.index("--tedpca") + 1] == "aic"
        assert job.command[job.command.index("--seed") + 1] == "42"
        assert job.command[job.command.index("--tree") + 1] == "tedana_orig"
    assert fast.command[fast.command.index("--ica-method") + 1] == "fastica"
    assert robust.command[robust.command.index("--ica-method") + 1] == "robustica"
    assert robust.command[robust.command.index("--n-robust-runs") + 1] == "30"


def test_sentinel_selection_is_deterministic_and_capped() -> None:
    rows = []
    for paradigm in ("sharedreward", "trust", "ugr", "socialdoors"):
        for index in range(20):
            rows.append(
                {
                    "subject": f"{10000 + index}",
                    "session": "01",
                    "paradigm": paradigm,
                    "task": "doors" if paradigm == "socialdoors" else paradigm,
                    "run": "1",
                    "run_key": f"sub-{10000 + index}_ses-01_task-{paradigm}_run-1",
                    "audit_status": "complete",
                    "nss_count": index % 4,
                    "n_ica": 10 + index,
                    "n_rejected": index,
                    "rejected_fraction": index / 25,
                    "rejected_normalized_variance": index / 30,
                    "mean_fd": index / 100,
                }
            )
    first = audit.select_sentinels(rows, target=48, cap=64)
    second = audit.select_sentinels(rows, target=48, cap=64)
    assert [row["run_key"] for row in first] == [row["run_key"] for row in second]
    assert len(first) == 48
    assert {int(row["nss_count"]) for row in first} == {0, 1, 2, 3}
    assert all(row["selection_reason"] for row in first)


def test_end_to_end_synthetic_audit_build_and_check(tmp_path: Path) -> None:
    project = tmp_path / "project"
    prefix = "sub-10001_ses-01_task-trust_run-1"
    bids_func = project / "bids" / "sub-10001" / "ses-01" / "func"
    fmriprep_func = (
        project / "derivatives" / "fmriprep" / "sub-10001" / "ses-01" / "func"
    )
    tedana_dir = project / "derivatives" / "tedana" / "sub-10001" / "ses-01"
    affine = np.diag([2.7, 2.7, 2.97, 1.0])
    data = np.ones((2, 2, 2, 30), dtype=np.float32)
    bids_func.mkdir(parents=True)
    fmriprep_func.mkdir(parents=True)
    tedana_dir.mkdir(parents=True)
    for echo, echo_time in enumerate((0.0138, 0.03154, 0.04928, 0.06702), start=1):
        save_image(bids_func / f"{prefix}_echo-{echo}_part-mag_bold.nii.gz", data, affine)
        (bids_func / f"{prefix}_echo-{echo}_part-mag_bold.json").write_text(
            json.dumps(
                {
                    "EchoTime": echo_time,
                    "RepetitionTime": 1.615,
                    "Manufacturer": "Siemens",
                    "ManufacturersModelName": "Prisma",
                    "SoftwareVersions": "XA30",
                    "MagneticFieldStrength": 3,
                }
            )
        )
        save_image(
            fmriprep_func / f"{prefix}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz",
            data,
            affine,
        )
    save_image(
        fmriprep_func / f"{prefix}_part-mag_desc-brain_mask.nii.gz",
        np.ones((2, 2, 2), dtype=np.float32),
        affine,
    )
    confounds(30, (0, 1)).to_csv(
        fmriprep_func / f"{prefix}_part-mag_desc-confounds_timeseries.tsv",
        sep="\t",
        index=False,
    )
    pd.DataFrame(
        {
            "Component": ["ICA_00", "ICA_01", "ICA_02"],
            "classification": ["accepted", "rejected", "rejected"],
            "classification_tags": ["Likely BOLD", "Unlikely BOLD", "Unlikely BOLD"],
            "kappa": [10, 2, 3],
            "rho": [2, 9, 8],
            "variance explained": [0.5, 0.3, 0.2],
            "normalized variance explained": [0.5, 0.3, 0.2],
        }
    ).to_csv(tedana_dir / f"{prefix}_desc-tedana_metrics.tsv", sep="\t", index=False)
    rng = np.random.default_rng(4)
    pd.DataFrame(rng.normal(size=(30, 3)), columns=("ICA_00", "ICA_01", "ICA_02")).to_csv(
        tedana_dir / f"{prefix}_desc-ICA_mixing.tsv", sep="\t", index=False
    )
    description = project / "derivatives" / "fmriprep" / "dataset_description.json"
    description.parent.mkdir(parents=True, exist_ok=True)
    description.write_text(json.dumps({"GeneratedBy": [{"Name": "fMRIPrep", "Version": "25.2.5"}]}))
    excluded = tmp_path / "exclusions"
    excluded.mkdir()
    output = project / "qc" / "tedana_audit"
    output.mkdir(parents=True)
    (output / "README.md").write_text("static documentation\n")
    component_dir = project / "derivatives" / "tedana-audit" / "current"
    args = Namespace(
        project_root=project,
        output_dir=output,
        component_dir=component_dir,
        excluded_source_root=excluded,
        tedana_command=Path("/not/executed"),
        tedana_version="26.0.3",
        sentinel_target=48,
        sentinel_cap=64,
        overwrite=False,
        dry_run=False,
    )
    assert audit.run_build(args) == 0
    assert (output / "README.md").read_text() == "static documentation\n"
    rows = audit.read_tsv(output / "current_runs.tsv")
    assert len(rows) == 1
    assert rows[0]["audit_status"] == "complete"
    assert rows[0]["nss_count"] == "2"
    assert rows[0]["n_ica"] == "3"
    assert len(audit.read_tsv(component_dir / "current_components.tsv")) == 3

    check = Namespace(project_root=project, output_dir=output, component_dir=component_dir)
    assert audit.run_check(check) == 0
