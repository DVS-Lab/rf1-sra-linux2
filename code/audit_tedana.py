#!/usr/bin/env python3
"""Audit production TEDANA outputs without modifying production derivatives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import nibabel as nib
import numpy as np
import pandas as pd
from scipy import stats

from build_run_qc import (
    RunKey,
    index_run_files,
    inventory_bids_runs,
    parse_entities,
)
from pipeline_utils import apply_umask_mode


TASK_TO_PARADIGM = {
    "sharedreward": "sharedreward",
    "trust": "trust",
    "ugr": "ugr",
    "socialdoors": "socialdoors",
    "doors": "socialdoors",
}
MOTION_BASE = ("trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z")
MOTION24_COLUMNS = (
    *MOTION_BASE,
    *(f"{base}_derivative1" for base in MOTION_BASE),
    *(f"{base}_power2" for base in MOTION_BASE),
    *(f"{base}_derivative1_power2" for base in MOTION_BASE),
)
COMPONENT_METRICS = (
    "kappa",
    "rho",
    "variance explained",
    "normalized variance explained",
    "d_table_score",
    "countsigFT2",
    "countsigFS0",
    "dice_FT2",
    "dice_FS0",
    "signal-noise_t",
)
RUN_COLUMNS = (
    "subject",
    "session",
    "paradigm",
    "task",
    "run",
    "run_key",
    "audit_status",
    "audit_issues",
    "repetition_time",
    "number_of_original_volumes",
    "echo_times",
    "fmriprep_version",
    "tedana_version",
    "tedana_version_source",
    "nss_count",
    "number_of_steady_state_volumes",
    "n_ica",
    "n_accepted",
    "n_rejected",
    "rejected_fraction",
    "accepted_normalized_variance",
    "rejected_normalized_variance",
    "largest_component_normalized_variance",
    "largest_rejected_component_normalized_variance",
    "ica_components_per_steady_state_volume",
    "accepted_components_per_steady_state_volume",
    "mean_fd",
    "median_fd",
    "p95_fd",
    "max_fd",
    "fraction_fd_gt_0_2",
    "fraction_fd_gt_0_5",
    "mean_standardized_dvars",
    "median_standardized_dvars",
    "p95_standardized_dvars",
    "max_standardized_dvars",
    "manufacturer",
    "manufacturers_model_name",
    "software_versions",
    "magnetic_field_strength",
    "variance_fraction_source",
    "bids_bold",
    "echo_files",
    "echo_jsons",
    "fmriprep_mask",
    "fmriprep_confounds",
    "tedana_metrics",
    "tedana_mixing",
    "tedana_pca_metrics",
    "tedana_cross_component_metrics",
    "tedana_decomposition",
    "tedana_status_table",
)
COMPONENT_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "component",
    "classification",
    "classification_tags",
    *COMPONENT_METRICS,
    "normalized_variance_fraction",
    "motion24_r2",
    "motion24_f",
    "motion24_p",
)
SUMMARY_METRICS = (
    "nss_count",
    "n_ica",
    "n_rejected",
    "rejected_fraction",
    "rejected_normalized_variance",
    "mean_fd",
    "p95_fd",
    "fraction_fd_gt_0_2",
    "fraction_fd_gt_0_5",
    "mean_standardized_dvars",
    "p95_standardized_dvars",
    "max_standardized_dvars",
)
TRACKED_OUTPUTS = (
    Path("current_runs.tsv"),
    Path("summary_by_task.tsv"),
    Path("sentinel_runs.tsv"),
    Path("report.md"),
    Path("provenance.json"),
    Path("figures") / "dimensionality.png",
    Path("figures") / "motion.png",
    Path("figures") / "nss.png",
)


@dataclass(frozen=True)
class NssResult:
    count: int | None
    rows: tuple[int, ...]
    issue: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float):
        return "" if not math.isfinite(value) else format(value, ".17g")
    return str(value)


def relative(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: format_value(row.get(column)) for column in columns})
    apply_umask_mode(path)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def require_audit_destination(project_root: Path, path: Path, kind: str) -> Path:
    resolved = path.resolve()
    if kind == "tracked":
        allowed = (project_root / "qc" / "tedana_audit").resolve()
    elif kind == "large":
        allowed = (project_root / "derivatives" / "tedana-audit").resolve()
    else:
        raise ValueError(f"unknown audit destination kind: {kind}")
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError(f"refusing {kind} output outside {allowed}: {resolved}")
    return resolved


def detect_nss(confounds: pd.DataFrame) -> NssResult:
    columns = [name for name in confounds.columns if name.startswith("non_steady_state_outlier")]
    if not columns:
        return NssResult(0, ())
    rows: list[int] = []
    for column in columns:
        values = pd.to_numeric(confounds[column], errors="coerce").to_numpy(dtype=float)
        if not np.all(np.isfinite(values)):
            return NssResult(None, (), f"{column}:nonfinite")
        if not np.all(np.isin(values, (0.0, 1.0))):
            return NssResult(None, (), f"{column}:not_binary")
        hits = np.flatnonzero(values == 1.0)
        if len(hits) != 1:
            return NssResult(None, (), f"{column}:not_one_hot")
        rows.append(int(hits[0]))
    ordered = tuple(sorted(rows))
    if len(set(ordered)) != len(ordered):
        return NssResult(None, ordered, "duplicate_nss_rows")
    expected = tuple(range(len(ordered)))
    if ordered != expected:
        return NssResult(None, ordered, f"noncontiguous_nss_rows:{','.join(map(str, ordered))}")
    return NssResult(len(ordered), ordered)


def _numeric_column(confounds: pd.DataFrame, name: str, allow_initial_nan: bool) -> np.ndarray:
    if name not in confounds.columns:
        raise ValueError(f"missing confound column:{name}")
    values = pd.to_numeric(confounds[name], errors="coerce").to_numpy(dtype=float).copy()
    bad = np.flatnonzero(~np.isfinite(values))
    if len(bad):
        if allow_initial_nan and np.array_equal(bad, np.array([0])):
            values[0] = 0.0
        else:
            raise ValueError(f"unexpected nonfinite values in {name}: rows {bad[:10].tolist()}")
    return values


def motion24(confounds: pd.DataFrame) -> np.ndarray:
    columns: list[np.ndarray] = []
    for name in MOTION24_COLUMNS:
        allow_initial = name.endswith("_derivative1") or name.endswith("_derivative1_power2")
        columns.append(_numeric_column(confounds, name, allow_initial))
    matrix = np.column_stack(columns)
    if matrix.shape != (len(confounds), 24):
        raise ValueError(f"invalid Motion24 shape: {matrix.shape}")
    return matrix


def summarize_series(confounds: pd.DataFrame, name: str) -> dict[str, float | None]:
    if name not in confounds.columns:
        return {metric: None for metric in ("mean", "median", "p95", "max")}
    values = pd.to_numeric(confounds[name], errors="coerce").to_numpy(dtype=float)
    bad = np.flatnonzero(~np.isfinite(values))
    if len(bad) and not np.array_equal(bad, np.array([0])):
        raise ValueError(f"unexpected nonfinite values in {name}: rows {bad[:10].tolist()}")
    values = values[np.isfinite(values)]
    if not len(values):
        return {metric: None for metric in ("mean", "median", "p95", "max")}
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }


def fit_motion24(motion: np.ndarray, mixing: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if motion.ndim != 2 or motion.shape[1] != 24:
        raise ValueError(f"Motion24 must have 24 columns: {motion.shape}")
    if mixing.ndim != 2 or len(motion) != len(mixing):
        raise ValueError(f"motion/mixing row mismatch: {motion.shape} vs {mixing.shape}")
    design = np.column_stack((np.ones(len(motion)), motion))
    rank = int(np.linalg.matrix_rank(design))
    model_df = rank - 1
    residual_df = len(motion) - rank
    if model_df < 1 or residual_df < 1:
        raise ValueError(f"insufficient degrees of freedom: n={len(motion)} rank={rank}")
    coefficients, *_ = np.linalg.lstsq(design, mixing, rcond=None)
    predicted = design @ coefficients
    residual_ss = np.sum((mixing - predicted) ** 2, axis=0)
    total_ss = np.sum((mixing - np.mean(mixing, axis=0)) ** 2, axis=0)
    r2 = np.divide(
        total_ss - residual_ss,
        total_ss,
        out=np.zeros_like(total_ss, dtype=float),
        where=total_ss > 0,
    )
    r2 = np.clip(r2, 0.0, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        f_value = ((total_ss - residual_ss) / model_df) / (residual_ss / residual_df)
    f_value = np.where(total_ss <= 0, 0.0, f_value)
    p_value = stats.f.sf(f_value, model_df, residual_df)
    return r2, f_value, p_value


def restore_temporal_grid(full_optcom: Path, denoised: Path, nss_count: int, output: Path) -> None:
    full = nib.load(str(full_optcom))
    reduced = nib.load(str(denoised))
    if len(full.shape) != 4 or len(reduced.shape) != 4:
        raise ValueError("temporal-grid restoration requires two 4D images")
    if full.shape[:3] != reduced.shape[:3]:
        raise ValueError(f"spatial shape mismatch: {full.shape[:3]} vs {reduced.shape[:3]}")
    if not np.allclose(full.affine, reduced.affine, atol=1e-5):
        raise ValueError("affine mismatch")
    if not np.allclose(full.header.get_zooms()[:3], reduced.header.get_zooms()[:3], atol=1e-6):
        raise ValueError("voxel-size mismatch")
    if not np.isclose(full.header.get_zooms()[3], reduced.header.get_zooms()[3], atol=1e-6):
        raise ValueError("TR mismatch")
    if reduced.shape[3] != full.shape[3] - nss_count:
        raise ValueError(
            f"volume mismatch: full={full.shape[3]} reduced={reduced.shape[3]} nss={nss_count}"
        )
    full_data = np.asanyarray(full.dataobj)
    reduced_data = np.asanyarray(reduced.dataobj)
    restored_data = np.concatenate((full_data[..., :nss_count], reduced_data), axis=3)
    header = full.header.copy()
    restored = nib.Nifti1Image(restored_data, full.affine, header=header)
    qform, qcode = full.get_qform(coded=True)
    sform, scode = full.get_sform(coded=True)
    restored.set_qform(qform, int(qcode))
    restored.set_sform(sform, int(scode))
    output.parent.mkdir(parents=True, exist_ok=True)
    nib.save(restored, str(output))
    apply_umask_mode(output)
    validate_temporal_grid(full_optcom, denoised, nss_count, output)


def validate_temporal_grid(
    full_optcom: Path,
    denoised: Path,
    nss_count: int,
    restored: Path,
) -> None:
    full = nib.load(str(full_optcom))
    reduced = nib.load(str(denoised))
    check = nib.load(str(restored))
    if len(full.shape) != 4 or len(reduced.shape) != 4 or len(check.shape) != 4:
        raise ValueError("temporal-grid validation requires 4D images")
    if reduced.shape != (*full.shape[:3], full.shape[3] - nss_count):
        raise ValueError("raw TEDANA image has incorrect shape")
    if check.shape != full.shape:
        raise ValueError("restored image has incorrect shape")
    for label, image in (("raw TEDANA", reduced), ("restored", check)):
        if not np.allclose(image.affine, full.affine, atol=1e-5):
            raise ValueError(f"{label} affine mismatch")
        if not np.allclose(image.header.get_zooms()[:4], full.header.get_zooms()[:4], atol=1e-6):
            raise ValueError(f"{label} voxel-size/TR mismatch")
    if check.get_qform(coded=True)[1] != full.get_qform(coded=True)[1]:
        raise ValueError("restored qform code mismatch")
    if check.get_sform(coded=True)[1] != full.get_sform(coded=True)[1]:
        raise ValueError("restored sform code mismatch")
    full_data = np.asanyarray(full.dataobj)
    reduced_data = np.asanyarray(reduced.dataobj)
    check_data = np.asanyarray(check.dataobj)
    if nss_count and not np.allclose(check_data[..., :nss_count], full_data[..., :nss_count]):
        raise ValueError("restored NSS volumes differ from full-grid optcom reference")
    if not np.allclose(check_data[..., nss_count:], reduced_data):
        raise ValueError("restored steady-state volumes differ from TEDANA output")


def pad_mixing_matrix(mixing: pd.DataFrame, full_rows: int, nss_count: int) -> pd.DataFrame:
    if len(mixing) != full_rows - nss_count:
        raise ValueError(
            f"mixing row mismatch: full={full_rows} mixing={len(mixing)} nss={nss_count}"
        )
    zeros = pd.DataFrame(np.zeros((nss_count, mixing.shape[1])), columns=mixing.columns)
    padded = pd.concat((zeros, mixing.reset_index(drop=True)), ignore_index=True)
    if len(padded) != full_rows:
        raise ValueError("zero-padded mixing matrix has incorrect length")
    return padded


def _single(index: dict[RunKey, list[Path]], key: RunKey) -> Path | None:
    paths = index.get(key, [])
    return paths[0] if len(paths) == 1 else None


def _json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        value = json.loads(path.read_text())
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _generated_version(dataset_description: Path, name: str) -> str:
    data = _json(dataset_description)
    for item in data.get("GeneratedBy", []):
        if str(item.get("Name", "")).lower() == name.lower():
            return str(item.get("Version", ""))
    return ""


def command_version(command: Path) -> str:
    try:
        result = subprocess.run(
            [str(command), "--version"], check=True, text=True, capture_output=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"cannot execute pinned TEDANA command {command}: {exc}") from exc
    output = (result.stdout or result.stderr).strip()
    match = re.search(r"(?:v|version\s+)?(\d+\.\d+\.\d+)", output, flags=re.I)
    if not match:
        raise RuntimeError(f"could not parse TEDANA version from: {output}")
    return match.group(1)


def _find_metric_column(frame: pd.DataFrame, requested: str) -> str | None:
    normalized = {str(column).strip().lower(): str(column) for column in frame.columns}
    return normalized.get(requested.lower())


def _component_value(row: pd.Series, frame: pd.DataFrame, requested: str) -> Any:
    column = _find_metric_column(frame, requested)
    return row.get(column, "") if column is not None else ""


def _inventory_digest(paths: Iterable[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        stat = path.stat()
        digest.update(relative(path, root).encode())
        digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def audit_run(
    key: RunKey,
    bold: Path,
    project_root: Path,
    fmriprep_version: str,
    tedana_version: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Path]]:
    prefix = key.prefix
    func = project_root / "bids" / f"sub-{key.subject}" / f"ses-{key.session}" / "func"
    ffunc = project_root / "derivatives" / "fmriprep" / f"sub-{key.subject}" / f"ses-{key.session}" / "func"
    tfunc = project_root / "derivatives" / "tedana" / f"sub-{key.subject}" / f"ses-{key.session}"
    tedana_description = tfunc / "dataset_description.json"
    echo_files = [ffunc / f"{prefix}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz" for echo in range(1, 5)]
    echo_jsons = [func / f"{prefix}_echo-{echo}_part-mag_bold.json" for echo in range(1, 5)]
    confounds_path = ffunc / f"{prefix}_part-mag_desc-confounds_timeseries.tsv"
    mask_path = ffunc / f"{prefix}_part-mag_desc-brain_mask.nii.gz"
    metrics_path = tfunc / f"{prefix}_desc-tedana_metrics.tsv"
    mixing_path = tfunc / f"{prefix}_desc-ICA_mixing.tsv"
    pca_metrics_path = tfunc / f"{prefix}_desc-PCA_metrics.tsv"
    cross_component_path = tfunc / f"{prefix}_desc-ICACrossComponent_metrics.json"
    decomposition_path = tfunc / f"{prefix}_desc-ICA_decomposition.json"
    status_path = tfunc / f"{prefix}_desc-ICA_status_table.tsv"
    issues: list[str] = []
    inputs = [bold]
    for index, path in enumerate(echo_jsons, start=1):
        if path.is_file():
            inputs.append(path)
        else:
            issues.append(f"missing_echo_{index}_json")
    for label, path in (
        *((f"echo_{index}", path) for index, path in enumerate(echo_files, start=1)),
        ("confounds", confounds_path),
        ("fmriprep_mask", mask_path),
        ("tedana_metrics", metrics_path),
        ("tedana_mixing", mixing_path),
    ):
        if not path.is_file():
            issues.append(f"missing_{label}")
        else:
            inputs.append(path)
    for path in (
        pca_metrics_path,
        cross_component_path,
        decomposition_path,
        status_path,
    ):
        if path.is_file():
            inputs.append(path)
    output_tedana_version = _generated_version(tedana_description, "tedana")
    if output_tedana_version:
        inputs.append(tedana_description)
        if output_tedana_version != tedana_version:
            issues.append(
                f"tedana_version_mismatch:output={output_tedana_version},runtime={tedana_version}"
            )
        reported_tedana_version = output_tedana_version
        tedana_version_source = "session_dataset_description"
    else:
        reported_tedana_version = tedana_version
        tedana_version_source = "pinned_runtime_no_per_run_metadata"
    metadata = _json(echo_jsons[0] if echo_jsons[0].is_file() else None)
    echo_times = []
    for path in echo_jsons:
        value = finite(_json(path if path.is_file() else None).get("EchoTime"))
        if value is None:
            issues.append(f"missing_echo_time:{path.name}")
        else:
            echo_times.append(value)
    nvolumes: int | None = None
    repetition_time = finite(metadata.get("RepetitionTime"))
    try:
        image = nib.load(str(bold))
        if len(image.shape) != 4:
            raise ValueError(f"not_4d:{image.shape}")
        nvolumes = int(image.shape[3])
        repetition_time = float(image.header.get_zooms()[3])
    except Exception as exc:
        issues.append(f"invalid_bids_bold:{type(exc).__name__}")
    confounds: pd.DataFrame | None = None
    nss = NssResult(None, (), "missing_confounds")
    motion: np.ndarray | None = None
    fd = {name: None for name in ("mean", "median", "p95", "max")}
    dvars = dict(fd)
    fd_gt_02: float | None = None
    fd_gt_05: float | None = None
    if confounds_path.is_file():
        try:
            confounds = pd.read_csv(confounds_path, sep="\t")
            if nvolumes is not None and len(confounds) != nvolumes:
                raise ValueError(f"confounds_rows:{len(confounds)}!=volumes:{nvolumes}")
            nss = detect_nss(confounds)
            if nss.issue:
                issues.append(f"malformed_nss:{nss.issue}")
            motion = motion24(confounds)
            fd = summarize_series(confounds, "framewise_displacement")
            dvars = summarize_series(confounds, "std_dvars")
            if "framewise_displacement" not in confounds:
                issues.append("missing_framewise_displacement")
            else:
                fd_values = pd.to_numeric(
                    confounds["framewise_displacement"], errors="coerce"
                ).to_numpy(dtype=float)
                fd_values = fd_values[np.isfinite(fd_values)]
                if len(fd_values):
                    fd_gt_02 = float(np.mean(fd_values > 0.2))
                    fd_gt_05 = float(np.mean(fd_values > 0.5))
        except Exception as exc:
            issues.append(f"invalid_confounds:{type(exc).__name__}:{exc}")
            motion = None
    metrics: pd.DataFrame | None = None
    mixing: pd.DataFrame | None = None
    components: list[dict[str, Any]] = []
    n_accepted = n_rejected = n_ica = None
    rejected_fraction = None
    accepted_variance = rejected_variance = largest = largest_rejected = None
    variance_source = ""
    if metrics_path.is_file() and mixing_path.is_file():
        try:
            metrics = pd.read_csv(metrics_path, sep="\t")
            mixing = pd.read_csv(mixing_path, sep="\t")
            classification_column = _find_metric_column(metrics, "classification")
            if classification_column is None:
                raise ValueError("classification column missing")
            classifications = metrics[classification_column].astype(str).str.lower().tolist()
            if not classifications or any(value not in {"accepted", "rejected"} for value in classifications):
                raise ValueError("invalid final classifications")
            if mixing.shape[1] != len(metrics):
                raise ValueError(f"mixing columns:{mixing.shape[1]}!=components:{len(metrics)}")
            if nvolumes is not None and len(mixing) != nvolumes:
                raise ValueError(f"mixing rows:{len(mixing)}!=volumes:{nvolumes}")
            n_ica = len(metrics)
            n_accepted = classifications.count("accepted")
            n_rejected = classifications.count("rejected")
            rejected_fraction = n_rejected / n_ica
            norm_column = _find_metric_column(metrics, "normalized variance explained")
            variance_column = _find_metric_column(metrics, "variance explained")
            source_column = norm_column or variance_column
            if source_column is None:
                raise ValueError("variance explained column missing")
            variance_values = pd.to_numeric(metrics[source_column], errors="coerce").to_numpy(dtype=float)
            if not np.all(np.isfinite(variance_values)) or np.any(variance_values < 0) or np.sum(variance_values) <= 0:
                raise ValueError("invalid component variance")
            variance_values = variance_values / np.sum(variance_values)
            variance_source = "normalized variance explained" if norm_column else "normalized fallback: variance explained"
            accepted_mask = np.array([value == "accepted" for value in classifications])
            rejected_mask = ~accepted_mask
            accepted_variance = float(np.sum(variance_values[accepted_mask]))
            rejected_variance = float(np.sum(variance_values[rejected_mask]))
            largest = float(np.max(variance_values))
            largest_rejected = float(np.max(variance_values[rejected_mask])) if np.any(rejected_mask) else 0.0
            r2 = f_values = p_values = np.full(n_ica, np.nan)
            if motion is not None and nss.count is not None:
                r2, f_values, p_values = fit_motion24(motion[nss.count :], mixing.to_numpy(dtype=float)[nss.count :])
            component_column = _find_metric_column(metrics, "Component")
            tags_column = _find_metric_column(metrics, "classification_tags")
            for index, metric_row in metrics.iterrows():
                component = metric_row.get(component_column, index) if component_column else index
                row = {
                    "subject": key.subject,
                    "session": key.session,
                    "task": key.task,
                    "run": key.run,
                    "run_key": prefix,
                    "component": component,
                    "classification": classifications[index],
                    "classification_tags": metric_row.get(tags_column, "") if tags_column else "",
                    "normalized_variance_fraction": variance_values[index],
                    "motion24_r2": finite(r2[index]),
                    "motion24_f": finite(f_values[index]),
                    "motion24_p": finite(p_values[index]),
                }
                for metric in COMPONENT_METRICS:
                    row[metric] = _component_value(metric_row, metrics, metric)
                components.append(row)
        except Exception as exc:
            issues.append(f"invalid_tedana:{type(exc).__name__}:{exc}")
    steady = nvolumes - nss.count if nvolumes is not None and nss.count is not None else None
    row = {
        "subject": key.subject,
        "session": key.session,
        "paradigm": TASK_TO_PARADIGM[key.task],
        "task": key.task,
        "run": key.run,
        "run_key": prefix,
        "audit_status": "complete" if not issues else "incomplete",
        "audit_issues": ";".join(issues),
        "repetition_time": repetition_time,
        "number_of_original_volumes": nvolumes,
        "echo_times": ";".join(format(value, ".10g") for value in echo_times),
        "fmriprep_version": fmriprep_version,
        "tedana_version": reported_tedana_version,
        "tedana_version_source": tedana_version_source,
        "nss_count": nss.count,
        "number_of_steady_state_volumes": steady,
        "n_ica": n_ica,
        "n_accepted": n_accepted,
        "n_rejected": n_rejected,
        "rejected_fraction": rejected_fraction,
        "accepted_normalized_variance": accepted_variance,
        "rejected_normalized_variance": rejected_variance,
        "largest_component_normalized_variance": largest,
        "largest_rejected_component_normalized_variance": largest_rejected,
        "ica_components_per_steady_state_volume": n_ica / steady if n_ica is not None and steady else None,
        "accepted_components_per_steady_state_volume": n_accepted / steady if n_accepted is not None and steady else None,
        "mean_fd": fd["mean"],
        "median_fd": fd["median"],
        "p95_fd": fd["p95"],
        "max_fd": fd["max"],
        "fraction_fd_gt_0_2": fd_gt_02,
        "fraction_fd_gt_0_5": fd_gt_05,
        "mean_standardized_dvars": dvars["mean"],
        "median_standardized_dvars": dvars["median"],
        "p95_standardized_dvars": dvars["p95"],
        "max_standardized_dvars": dvars["max"],
        "manufacturer": metadata.get("Manufacturer", ""),
        "manufacturers_model_name": metadata.get("ManufacturersModelName", ""),
        "software_versions": metadata.get("SoftwareVersions", ""),
        "magnetic_field_strength": metadata.get("MagneticFieldStrength", ""),
        "variance_fraction_source": variance_source,
        "bids_bold": relative(bold, project_root),
        "echo_files": ";".join(relative(path, project_root) for path in echo_files),
        "echo_jsons": ";".join(relative(path, project_root) for path in echo_jsons),
        "fmriprep_mask": relative(mask_path, project_root),
        "fmriprep_confounds": relative(confounds_path, project_root),
        "tedana_metrics": relative(metrics_path, project_root),
        "tedana_mixing": relative(mixing_path, project_root),
        "tedana_pca_metrics": (
            relative(pca_metrics_path, project_root) if pca_metrics_path.is_file() else ""
        ),
        "tedana_cross_component_metrics": (
            relative(cross_component_path, project_root)
            if cross_component_path.is_file()
            else ""
        ),
        "tedana_decomposition": (
            relative(decomposition_path, project_root) if decomposition_path.is_file() else ""
        ),
        "tedana_status_table": (
            relative(status_path, project_root) if status_path.is_file() else ""
        ),
    }
    return row, components, inputs


def quantile(values: Sequence[float], q: float) -> float | None:
    finite_values = [float(value) for value in values if math.isfinite(float(value))]
    return float(np.quantile(finite_values, q)) if finite_values else None


def summary_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[("task", row["task"], row["session"])].append(row)
        groups[("paradigm", row["paradigm"], "all")].append(row)
        groups[("session", row["session"], row["session"])].append(row)
        scanner = "|".join(
            str(row.get(field) or "unknown")
            for field in (
                "manufacturer",
                "manufacturers_model_name",
                "software_versions",
            )
        )
        groups[("scanner", scanner, "all")].append(row)
        groups[("overall", "all", "all")].append(row)
    result: list[dict[str, Any]] = []
    for (level, group, session), entries in sorted(groups.items()):
        output: dict[str, Any] = {
            "level": level,
            "group": group,
            "session": session,
            "n_runs": len(entries),
            "n_complete": sum(row["audit_status"] == "complete" for row in entries),
            "n_incomplete": sum(row["audit_status"] != "complete" for row in entries),
        }
        for metric in SUMMARY_METRICS:
            values = [finite(row.get(metric)) for row in entries]
            values = [value for value in values if value is not None]
            output[f"{metric}_median"] = quantile(values, 0.5)
            output[f"{metric}_q1"] = quantile(values, 0.25)
            output[f"{metric}_q3"] = quantile(values, 0.75)
        result.append(output)
    return result


def _distance_from_median(row: dict[str, Any], medians: dict[str, float]) -> float:
    score = 0.0
    for metric, median in medians.items():
        value = finite(row.get(metric))
        if value is None:
            return math.inf
        score += abs(value - median)
    return score


def select_sentinels(rows: Sequence[dict[str, Any]], target: int = 48, cap: int = 64) -> list[dict[str, Any]]:
    eligible = [
        dict(row)
        for row in rows
        if row.get("audit_status") == "complete"
        and row.get("nss_count") is not None
        and row.get("n_ica") is not None
    ]
    if not eligible:
        return []
    target = min(max(target, 1), cap, len(eligible))
    by_paradigm = {name: [row for row in eligible if row["paradigm"] == name] for name in sorted(set(row["paradigm"] for row in eligible))}
    selected: dict[str, dict[str, Any]] = {}

    def add(row: dict[str, Any], reason: str) -> None:
        existing = selected.get(row["run_key"])
        if existing is None:
            existing = dict(row)
            existing["selection_reason"] = reason
            selected[row["run_key"]] = existing
        elif reason not in existing["selection_reason"].split(";"):
            existing["selection_reason"] += f";{reason}"

    quotas = {name: target // len(by_paradigm) for name in by_paradigm}
    for name in list(quotas)[: target % len(by_paradigm)]:
        quotas[name] += 1
    for paradigm, group in by_paradigm.items():
        medians = {
            metric: float(np.median([float(row[metric]) for row in group]))
            for metric in ("n_ica", "rejected_fraction", "mean_fd")
            if all(finite(row.get(metric)) is not None for row in group)
        }
        rejected_cutoff = float(np.quantile([float(row["n_rejected"]) for row in group], 0.75))
        high_rejected = [row for row in group if float(row["n_rejected"]) >= rejected_cutoff]
        if high_rejected:
            add(
                min(high_rejected, key=lambda row: (float(row["mean_fd"]), row["run_key"])),
                "high_rejected_count_low_motion",
            )
            add(
                min(high_rejected, key=lambda row: (-float(row["mean_fd"]), row["run_key"])),
                "high_rejected_count_high_motion",
            )
        for reason, metric in (
            ("high_rejected_fraction", "rejected_fraction"),
            ("high_rejected_variance", "rejected_normalized_variance"),
            ("high_ica_dimensionality", "n_ica"),
        ):
            add(
                min(group, key=lambda row: (-float(row[metric]), row["run_key"])),
                reason,
            )
        motion_cutoff = float(np.quantile([float(row["mean_fd"]) for row in group], 0.75))
        rejected_median = float(np.median([float(row["n_rejected"]) for row in group]))
        high_motion = [row for row in group if float(row["mean_fd"]) >= motion_cutoff]
        if high_motion:
            add(
                min(
                    high_motion,
                    key=lambda row: (
                        abs(float(row["n_rejected"]) - rejected_median),
                        row["run_key"],
                    ),
                ),
                "high_motion_ordinary_classification",
            )
        zero_nss = [row for row in group if int(row["nss_count"]) == 0]
        if zero_nss:
            add(
                min(
                    zero_nss,
                    key=lambda row: (_distance_from_median(row, medians), row["run_key"]),
                ),
                "nss_zero_control",
            )
        controls = sorted(group, key=lambda row: (_distance_from_median(row, medians), row["run_key"]))
        while sum(item["paradigm"] == paradigm for item in selected.values()) < quotas[paradigm]:
            candidate = next((row for row in controls if row["run_key"] not in selected), None)
            if candidate is None:
                break
            add(candidate, "ordinary_control")
    observed_nss = sorted({int(row["nss_count"]) for row in eligible})
    represented = {int(row["nss_count"]) for row in selected.values()}
    for nss_count in observed_nss:
        if nss_count in represented or len(selected) >= cap:
            continue
        candidates = sorted(
            (row for row in eligible if int(row["nss_count"]) == nss_count),
            key=lambda row: (row["paradigm"], row["run_key"]),
        )
        if candidates:
            add(candidates[0], f"nss_count_{nss_count}_coverage")
            represented.add(nss_count)
    return sorted(selected.values(), key=lambda row: (row["paradigm"], row["run_key"]))


def _scatter(ax: Any, rows: Sequence[dict[str, Any]], x: str, y: str, xlabel: str, ylabel: str) -> None:
    for paradigm, color in zip(sorted(set(row["paradigm"] for row in rows)), ("#0072B2", "#D55E00", "#009E73", "#CC79A7")):
        group = [row for row in rows if row["paradigm"] == paradigm]
        xv = [finite(row.get(x)) for row in group]
        yv = [finite(row.get(y)) for row in group]
        points = [(a, b) for a, b in zip(xv, yv) if a is not None and b is not None]
        if points:
            ax.scatter([a for a, _ in points], [b for _, b in points], s=8, alpha=0.45, label=paradigm)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.2)


def make_figures(rows: Sequence[dict[str, Any]], figures: Path) -> None:
    from matplotlib import pyplot as plt

    figures.mkdir(parents=True, exist_ok=True)
    complete = [row for row in rows if row["audit_status"] == "complete"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    flat = axes.ravel()
    _scatter(flat[0], complete, "n_ica", "n_rejected", "Total ICA components", "Rejected components")
    _scatter(flat[1], complete, "n_ica", "rejected_fraction", "Total ICA components", "Rejected fraction")
    _scatter(flat[2], complete, "n_ica", "rejected_normalized_variance", "Total ICA components", "Rejected variance fraction")
    _scatter(flat[3], complete, "number_of_steady_state_volumes", "n_ica", "Steady-state volumes", "Total ICA components")
    flat[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(figures / "dimensionality.png", dpi=160)
    plt.close(fig)
    motion_predictors = (
        ("mean_fd", "Mean FD (mm)"),
        ("p95_fd", "95th-percentile FD (mm)"),
        ("max_fd", "Maximum FD (mm)"),
        ("fraction_fd_gt_0_2", "Fraction FD > 0.2 mm"),
        ("p95_standardized_dvars", "95th-percentile standardized DVARS"),
    )
    outcomes = (
        ("n_rejected", "Rejected components"),
        ("rejected_fraction", "Rejected fraction"),
        ("rejected_normalized_variance", "Rejected variance fraction"),
    )
    fig, axes = plt.subplots(len(motion_predictors), len(outcomes), figsize=(13, 16))
    for row_index, (predictor, xlabel) in enumerate(motion_predictors):
        for column_index, (outcome, ylabel) in enumerate(outcomes):
            _scatter(
                axes[row_index, column_index],
                complete,
                predictor,
                outcome,
                xlabel,
                ylabel,
            )
    fig.tight_layout()
    fig.savefig(figures / "motion.png", dpi=160)
    plt.close(fig)
    nss_groups = sorted({int(row["nss_count"]) for row in complete if row.get("nss_count") is not None})
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, metric, label in zip(axes, ("n_ica", "rejected_fraction", "rejected_normalized_variance"), ("Total ICA components", "Rejected fraction", "Rejected variance fraction")):
        values = [[float(row[metric]) for row in complete if row.get("nss_count") == nss and finite(row.get(metric)) is not None] for nss in nss_groups]
        if values:
            ax.boxplot(values, tick_labels=[str(value) for value in nss_groups], showfliers=False)
        ax.set_xlabel("NSS count")
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(figures / "nss.png", dpi=160)
    plt.close(fig)
    for path in figures.glob("*.png"):
        apply_umask_mode(path)


def spearman(rows: Sequence[dict[str, Any]], x: str, y: str) -> tuple[int, float | None]:
    pairs = [(finite(row.get(x)), finite(row.get(y))) for row in rows]
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    if len(pairs) < 3:
        return len(pairs), None
    result = stats.spearmanr([a for a, _ in pairs], [b for _, b in pairs])
    return len(pairs), float(result.statistic)


def make_report(rows: Sequence[dict[str, Any]], components: Sequence[dict[str, Any]], sentinels: Sequence[dict[str, Any]], path: Path) -> None:
    complete = [row for row in rows if row["audit_status"] == "complete"]
    incomplete = [row for row in rows if row["audit_status"] != "complete"]
    nss_counts: dict[int, int] = defaultdict(int)
    for row in rows:
        if row.get("nss_count") is not None:
            nss_counts[int(row["nss_count"])] += 1
    correlations = []
    for outcome in ("n_rejected", "rejected_fraction", "rejected_normalized_variance"):
        for predictor in (
            "n_ica",
            "mean_fd",
            "p95_fd",
            "max_fd",
            "fraction_fd_gt_0_2",
            "fraction_fd_gt_0_5",
            "p95_standardized_dvars",
            "nss_count",
        ):
            n, rho = spearman(complete, predictor, outcome)
            correlations.append((outcome, predictor, n, rho))
    accepted = [row for row in components if row.get("classification") == "accepted" and finite(row.get("motion24_r2")) is not None]
    rejected = [row for row in components if row.get("classification") == "rejected" and finite(row.get("motion24_r2")) is not None]
    lines = [
        "# RF1-SRA TEDANA Audit",
        "",
        "This report describes the historical production baseline. It does not change component classifications or production derivatives.",
        "",
        "## Cohort Inventory",
        "",
        f"- Acquired runs inventoried: {len(rows)}",
        f"- Complete audit rows: {len(complete)}",
        f"- Incomplete audit rows: {len(incomplete)}",
        f"- Sentinel runs selected: {len(sentinels)}",
        f"- NSS distribution: {', '.join(f'N={key}: {value}' for key, value in sorted(nss_counts.items()))}",
        "",
        "## Descriptive Associations",
        "",
        "Spearman correlations are descriptive and are not used for classification.",
        "",
        "| Outcome | Predictor | N | Spearman rho |",
        "| --- | --- | ---: | ---: |",
    ]
    for outcome, predictor, n, rho in correlations:
        lines.append(f"| `{outcome}` | `{predictor}` | {n} | {rho:.4f} |" if rho is not None else f"| `{outcome}` | `{predictor}` | {n} | NA |")
    lines.extend(["", "## Motion24 Component Fits", ""])
    for label, group in (("Accepted", accepted), ("Rejected", rejected)):
        values = [float(row["motion24_r2"]) for row in group]
        median = float(np.median(values)) if values else math.nan
        counts = ", ".join(f"R2>{cutoff:.2f}: {sum(value > cutoff for value in values)}" for cutoff in (0.10, 0.25, 0.50))
        lines.append(f"- {label}: N={len(values)}, median R2={median:.4f}; {counts}")
    lines.extend(
        [
            "",
            "## Benchmark Status",
            "",
            "The sentinel manifest is ready for controlled T2S-FULL, T2S-EXCLUDE-NSS, NSS-aware FastICA, and NSS-aware RobustICA runs. No benchmark result is interpreted until those isolated derivatives have completed and passed validation.",
            "",
            "## Production Decision",
            "",
            "No production change is authorized by this baseline audit. The benchmark must determine whether NSS handling or RobustICA materially improves the data before `tedana.sh`, confound construction, or QC thresholds are revised.",
        ]
    )
    if incomplete:
        lines.extend(["", "## Incomplete Runs", ""])
        for row in incomplete:
            lines.append(f"- `{row['run_key']}`: {row['audit_issues']}")
    path.write_text("\n".join(lines) + "\n")
    apply_umask_mode(path)


def run_build(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    output_dir = require_audit_destination(project_root, args.output_dir, "tracked")
    component_dir = require_audit_destination(project_root, args.component_dir, "large")
    tedana_version = args.tedana_version or command_version(args.tedana_command)
    if tedana_version != "26.0.3":
        raise ValueError(f"TEDANA audit requires 26.0.3, found {tedana_version}")
    fmriprep_version = _generated_version(
        project_root / "derivatives" / "fmriprep" / "dataset_description.json", "fMRIPrep"
    )
    if fmriprep_version != "25.2.5":
        found = fmriprep_version or "missing version metadata"
        raise ValueError(f"expected fMRIPrep 25.2.5, found {found}")
    inventory, excluded = inventory_bids_runs(
        project_root / "bids",
        set(TASK_TO_PARADIGM),
        args.excluded_source_root,
        include_source_excluded=False,
    )
    if args.dry_run:
        print(f"Would audit {len(inventory)} acquired run(s).")
        print(f"Would exclude {len(excluded)} source-excluded subject(s) from standard audit inventory.")
        return 0
    existing = [output_dir / path for path in TRACKED_OUTPUTS if (output_dir / path).exists()]
    component_output = component_dir / "current_components.tsv"
    if (existing or component_output.exists()) and not args.overwrite:
        raise ValueError("TEDANA audit outputs already exist; review them and rerun with --overwrite")
    rows: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    inputs: list[Path] = []
    for index, (key, bold_paths) in enumerate(sorted(inventory.items()), start=1):
        if len(bold_paths) != 1:
            continue
        row, component_rows, run_inputs = audit_run(
            key, bold_paths[0], project_root, fmriprep_version, tedana_version
        )
        rows.append(row)
        components.extend(component_rows)
        inputs.extend(run_inputs)
        if index % 100 == 0:
            print(f"Audited {index}/{len(inventory)} runs", flush=True)
    summaries = summary_rows(rows)
    sentinels = select_sentinels(rows, args.sentinel_target, args.sentinel_cap)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    component_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tedana-audit-", dir=output_dir.parent) as temporary:
        stage = Path(temporary)
        write_tsv(stage / "current_runs.tsv", rows, RUN_COLUMNS)
        summary_columns = tuple(summaries[0]) if summaries else ("level", "group", "session", "n_runs")
        write_tsv(stage / "summary_by_task.tsv", summaries, summary_columns)
        sentinel_columns = (*RUN_COLUMNS, "selection_reason")
        write_tsv(stage / "sentinel_runs.tsv", sentinels, sentinel_columns)
        make_figures(rows, stage / "figures")
        make_report(rows, components, sentinels, stage / "report.md")
        component_stage = component_dir / ".current_components.tsv.tmp"
        write_tsv(component_stage, components, COMPONENT_COLUMNS)
        provenance = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "production_baseline": True,
            "project_root": str(project_root),
            "fmriprep_version": fmriprep_version,
            "tedana_version": tedana_version,
            "tedana_command": str(args.tedana_command),
            "run_count": len(rows),
            "complete_run_count": sum(row["audit_status"] == "complete" for row in rows),
            "incomplete_run_count": sum(row["audit_status"] != "complete" for row in rows),
            "component_count": len(components),
            "sentinel_count": len(sentinels),
            "sentinel_target": args.sentinel_target,
            "sentinel_cap": args.sentinel_cap,
            "source_excluded_subject_count": len(excluded),
            "input_inventory_digest_path_size_mtime": _inventory_digest(inputs, project_root),
            "component_table": relative(component_output, project_root),
            "component_table_sha256": sha256(component_stage),
            "outputs": {},
            "constraints": {
                "production_tedana_modified": False,
                "task_regressors_used": False,
                "classifications_changed": False,
                "nss_authority": "fMRIPrep non_steady_state_outlier regressors",
            },
        }
        for path in TRACKED_OUTPUTS:
            if path == Path("provenance.json"):
                continue
            provenance["outputs"][path.as_posix()] = sha256(stage / path)
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        apply_umask_mode(stage / "provenance.json")
        readme = output_dir / "README.md"
        if readme.is_file():
            shutil.copy2(readme, stage / "README.md")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        os.replace(stage, output_dir)
        os.replace(component_stage, component_output)
        apply_umask_mode(component_output)
    print(f"Audited runs: {len(rows)}", flush=True)
    print(
        f"Complete audit rows: {sum(row['audit_status'] == 'complete' for row in rows)}",
        flush=True,
    )
    print(
        f"Incomplete audit rows: {sum(row['audit_status'] != 'complete' for row in rows)}",
        flush=True,
    )
    print(f"Component rows: {len(components)}", flush=True)
    print(f"Sentinel runs: {len(sentinels)}", flush=True)
    print(f"Tracked audit: {output_dir}", flush=True)
    print(f"Large component table: {component_output}", flush=True)
    return 0


def run_check(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    output_dir = require_audit_destination(project_root, args.output_dir, "tracked")
    component_dir = require_audit_destination(project_root, args.component_dir, "large")
    provenance_path = output_dir / "provenance.json"
    if not provenance_path.is_file():
        raise ValueError(f"missing audit provenance: {provenance_path}")
    provenance = json.loads(provenance_path.read_text())
    failures: list[str] = []
    for name, expected in provenance.get("outputs", {}).items():
        path = output_dir / name
        if not path.is_file():
            failures.append(f"missing:{path}")
        elif sha256(path) != expected:
            failures.append(f"checksum:{path}")
    component = component_dir / "current_components.tsv"
    if not component.is_file():
        failures.append(f"missing:{component}")
    elif sha256(component) != provenance.get("component_table_sha256"):
        failures.append(f"checksum:{component}")
    rows = read_tsv(output_dir / "current_runs.tsv") if (output_dir / "current_runs.tsv").is_file() else []
    if len(rows) != provenance.get("run_count"):
        failures.append("run_count")
    if any(row.get("audit_status") not in {"complete", "incomplete"} for row in rows):
        failures.append("invalid_status")
    complete_count = sum(row.get("audit_status") == "complete" for row in rows)
    incomplete_count = sum(row.get("audit_status") == "incomplete" for row in rows)
    if complete_count != provenance.get("complete_run_count"):
        failures.append("complete_run_count")
    if incomplete_count != provenance.get("incomplete_run_count"):
        failures.append("incomplete_run_count")
    if rows and complete_count == 0:
        failures.append("zero_complete_runs")
    sentinels = read_tsv(output_dir / "sentinel_runs.tsv") if (output_dir / "sentinel_runs.tsv").is_file() else []
    if len(sentinels) != provenance.get("sentinel_count"):
        failures.append("sentinel_count")
    expected_minimum = min(int(provenance.get("sentinel_target", 48)), complete_count)
    if len(sentinels) < expected_minimum:
        failures.append("too_few_sentinels")
    complete_keys = {
        row.get("run_key") for row in rows if row.get("audit_status") == "complete"
    }
    if any(row.get("run_key") not in complete_keys for row in sentinels):
        failures.append("ineligible_sentinel")
    for failure in failures:
        print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: TEDANA audit has {len(failures)} integrity issue(s).")
        return 1
    print(
        "CHECK PASSED: TEDANA audit integrity verified for "
        f"{len(rows)} run(s) and {len(sentinels)} sentinel run(s)."
    )
    return 0


def parser() -> argparse.ArgumentParser:
    repo = Path(__file__).resolve().parents[1]
    default_env = Path("/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3")
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for command in ("build", "check"):
        child = subparsers.add_parser(command)
        child.add_argument("--project-root", type=Path, default=repo)
        child.add_argument("--output-dir", type=Path, default=repo / "qc" / "tedana_audit")
        child.add_argument("--component-dir", type=Path, default=repo / "derivatives" / "tedana-audit" / "current")
    build = subparsers.choices["build"]
    build.add_argument("--excluded-source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    build.add_argument("--tedana-command", type=Path, default=default_env / "bin" / "tedana")
    build.add_argument("--tedana-version", help=argparse.SUPPRESS)
    build.add_argument("--sentinel-target", type=int, default=48)
    build.add_argument("--sentinel-cap", type=int, default=64)
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "build":
            return run_build(args)
        return run_check(args)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
