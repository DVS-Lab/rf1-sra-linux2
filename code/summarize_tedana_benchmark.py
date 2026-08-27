#!/usr/bin/env python3
"""Summarize validated RF1 TEDANA sentinel benchmark outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import nibabel as nib
import numpy as np
import pandas as pd

from audit_tedana import motion24
from pipeline_utils import apply_umask_mode, ensure_safe_child_path


T2_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "nss_count",
    "selection_reason",
    "n_valid_t2_voxels",
    "t2star_spatial_correlation",
    "t2star_log_spatial_correlation",
    "t2star_spearman_correlation",
    "t2star_median_absolute_difference_seconds",
    "t2star_median_absolute_percent_difference",
    "t2star_p95_absolute_percent_difference",
    "t2star_fraction_absolute_percent_difference_gt_1",
    "t2star_fraction_absolute_percent_difference_gt_5",
    "t2star_fraction_absolute_percent_difference_gt_10",
    "t2star_rmse_seconds",
    "n_valid_optcom_voxels",
    "optcom_median_voxelwise_temporal_correlation",
    "optcom_median_volume_spatial_correlation",
    "optcom_normalized_rmse",
    "optcom_median_signal_percent_difference",
    "optcom_full_median_tsnr",
    "optcom_exclude_median_tsnr",
    "optcom_median_tsnr_difference",
)

ICA_METRICS = (
    "n_ica",
    "n_accepted",
    "n_rejected",
    "rejected_fraction",
    "accepted_normalized_variance",
    "rejected_normalized_variance",
    "largest_component_normalized_variance",
    "largest_rejected_component_normalized_variance",
)

ICA_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "nss_count",
    "selection_reason",
    *(f"historical_{name}" for name in ICA_METRICS),
    *(f"fastica_{name}" for name in ICA_METRICS),
    *(f"robustica_{name}" for name in ICA_METRICS),
    *(f"robustica_minus_fastica_{name}" for name in ICA_METRICS),
    "robustica_mean_index_quality",
    "robustica_fastica_convergence_warning_count",
)

DENOISING_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "nss_count",
    "selection_reason",
    "n_steady_state_volumes",
    "n_valid_voxels",
    "fastica_median_optcom_tsnr",
    "fastica_median_denoised_tsnr",
    "fastica_median_tsnr_change",
    "fastica_median_variance_removed_fraction",
    "fastica_median_signal_percent_change",
    "fastica_optcom_median_dvars",
    "fastica_denoised_median_dvars",
    "fastica_dvars_percent_change",
    "fastica_fd_denoised_dvars_spearman",
    "fastica_motion24_global_signal_r_squared",
    "robustica_median_optcom_tsnr",
    "robustica_median_denoised_tsnr",
    "robustica_median_tsnr_change",
    "robustica_median_variance_removed_fraction",
    "robustica_median_signal_percent_change",
    "robustica_optcom_median_dvars",
    "robustica_denoised_median_dvars",
    "robustica_dvars_percent_change",
    "robustica_fd_denoised_dvars_spearman",
    "robustica_motion24_global_signal_r_squared",
    "robustica_minus_fastica_denoised_tsnr",
    "robustica_minus_fastica_variance_removed_fraction",
    "robustica_minus_fastica_denoised_dvars",
    "fastica_robustica_median_voxelwise_temporal_correlation",
    "fastica_robustica_median_volume_spatial_correlation",
    "fastica_robustica_normalized_rmse",
)

REVIEW_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "configuration",
    "component",
    "classification",
    "normalized_variance_fraction",
    "kappa",
    "rho",
    "reason_for_review",
    "metrics_path",
    "report_path",
    "component_figure_path",
)

OUTPUTS = (
    Path("paired_t2s.tsv"),
    Path("paired_ica.tsv"),
    Path("paired_denoising.tsv"),
    Path("review_manifest.tsv"),
    Path("figures/t2star_nss_effect.png"),
    Path("figures/ica_dimensionality.png"),
    Path("figures/ica_classification_deltas.png"),
    Path("figures/denoising_qc.png"),
    Path("report.md"),
    Path("provenance.json"),
)

T2_NUMERIC_COLUMNS = tuple(
    column
    for column in T2_COLUMNS
    if column
    not in {
        "subject",
        "session",
        "task",
        "run",
        "run_key",
        "selection_reason",
    }
)

ICA_NUMERIC_COLUMNS = tuple(
    column
    for column in ICA_COLUMNS
    if column
    not in {
        "subject",
        "session",
        "task",
        "run",
        "run_key",
        "selection_reason",
    }
)

DENOISING_NUMERIC_COLUMNS = tuple(
    column
    for column in DENOISING_COLUMNS
    if column
    not in {
        "subject",
        "session",
        "task",
        "run",
        "run_key",
        "selection_reason",
    }
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory_digest(paths: Sequence[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        stat = path.stat()
        digest.update(path.resolve().relative_to(root).as_posix().encode())
        digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(
    path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    apply_umask_mode(path)


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def median(values: Sequence[Any]) -> float | None:
    clean = [value for value in (number(item) for item in values) if value is not None]
    return float(np.median(clean)) if clean else None


def iqr(values: Sequence[Any]) -> tuple[float | None, float | None]:
    clean = [value for value in (number(item) for item in values) if value is not None]
    if not clean:
        return None, None
    return float(np.quantile(clean, 0.25)), float(np.quantile(clean, 0.75))


def _correlation(x: np.ndarray, y: np.ndarray) -> float:
    x = np.array(x, dtype=np.float64, copy=True).ravel()
    y = np.array(y, dtype=np.float64, copy=True).ravel()
    finite = np.isfinite(x) & np.isfinite(y)
    x = x[finite]
    y = y[finite]
    if len(x) < 2:
        return math.nan
    x -= np.mean(x)
    y -= np.mean(y)
    denominator = np.linalg.norm(x) * np.linalg.norm(y)
    return float(np.dot(x, y) / denominator) if denominator else math.nan


def _normalize_variance(values: Sequence[Any]) -> np.ndarray:
    variance = np.array(values, dtype=float, copy=True)
    if (
        not np.all(np.isfinite(variance))
        or np.any(variance < 0)
        or np.sum(variance) <= 0
    ):
        raise ValueError("invalid TEDANA component variance")
    return variance / np.sum(variance)


def _image(path: Path, ndim: int) -> nib.spatialimages.SpatialImage:
    image = nib.load(str(path))
    if len(image.shape) != ndim:
        raise ValueError(f"expected {ndim}D image, found {image.shape}: {path}")
    return image


def _matching_geometry(
    reference: nib.spatialimages.SpatialImage, other: nib.spatialimages.SpatialImage
) -> None:
    if reference.shape != other.shape:
        raise ValueError(f"image shape mismatch: {reference.shape} != {other.shape}")
    if not np.allclose(reference.affine, other.affine, atol=1e-5):
        raise ValueError("image affine mismatch")
    if not np.allclose(
        reference.header.get_zooms(), other.header.get_zooms(), atol=1e-6
    ):
        raise ValueError("image zoom/TR mismatch")


def _temporal_correlations(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    x = x - np.mean(x, axis=1, keepdims=True)
    y = y - np.mean(y, axis=1, keepdims=True)
    denominator = np.linalg.norm(x, axis=1) * np.linalg.norm(y, axis=1)
    result = np.full(len(x), np.nan)
    valid = denominator > 0
    result[valid] = np.sum(x[valid] * y[valid], axis=1) / denominator[valid]
    return result


def _assert_n0_identity(
    key: str,
    full_t2: np.ndarray,
    exclude_t2: np.ndarray,
    full_optcom: np.ndarray,
    exclude_optcom: np.ndarray,
) -> None:
    """Require the two no-exclusion controls to be numerically identical."""
    if not np.allclose(full_t2, exclude_t2, rtol=1e-6, atol=1e-8, equal_nan=True):
        maximum = float(np.nanmax(np.abs(full_t2 - exclude_t2)))
        raise ValueError(f"NSS=0 T2* control differs for {key}; max abs diff={maximum}")
    if not np.allclose(
        full_optcom,
        exclude_optcom,
        rtol=1e-6,
        atol=1e-6,
        equal_nan=True,
    ):
        maximum = float(np.nanmax(np.abs(full_optcom - exclude_optcom)))
        raise ValueError(
            f"NSS=0 optcom control differs for {key}; max abs diff={maximum}"
        )


def compare_t2s(project: Path, audit_root: Path, row: dict[str, str]) -> dict[str, Any]:
    key = row["run_key"]
    full_dir = audit_root / "benchmark" / "t2s-full" / key
    exclude_dir = audit_root / "benchmark" / "t2s-exclude-nss" / key
    full_t2 = _image(full_dir / f"{key}_T2starmap.nii.gz", 3)
    exclude_t2 = _image(exclude_dir / f"{key}_T2starmap.nii.gz", 3)
    _matching_geometry(full_t2, exclude_t2)
    mask_image = _image(project / row["fmriprep_mask"], 3)
    if mask_image.shape != full_t2.shape or not np.allclose(
        mask_image.affine, full_t2.affine, atol=1e-5
    ):
        raise ValueError(f"mask geometry mismatch: {key}")
    mask = np.asarray(mask_image.dataobj) > 0
    full_t2_data = np.asarray(full_t2.dataobj, dtype=np.float32)
    exclude_t2_data = np.asarray(exclude_t2.dataobj, dtype=np.float32)
    valid_t2 = mask & np.isfinite(full_t2_data) & np.isfinite(exclude_t2_data)
    valid_t2 &= (full_t2_data > 0) & (exclude_t2_data > 0)
    x_t2 = full_t2_data[valid_t2].astype(np.float64)
    y_t2 = exclude_t2_data[valid_t2].astype(np.float64)
    if not len(x_t2):
        raise ValueError(f"no common valid T2* voxels: {key}")
    t2_diff = y_t2 - x_t2
    t2_percent = 100 * np.abs(t2_diff) / np.abs(x_t2)

    full_opt = _image(full_dir / f"{key}_desc-optcom_bold.nii.gz", 4)
    exclude_opt = _image(exclude_dir / f"{key}_desc-optcom_bold.nii.gz", 4)
    _matching_geometry(full_opt, exclude_opt)
    if full_opt.shape[:3] != mask.shape:
        raise ValueError(f"optcom-mask shape mismatch: {key}")
    nss = int(row["nss_count"])
    full_data = np.asarray(full_opt.dataobj, dtype=np.float32)[..., nss:]
    exclude_data = np.asarray(exclude_opt.dataobj, dtype=np.float32)[..., nss:]
    if nss == 0:
        _assert_n0_identity(
            key,
            full_t2_data[mask],
            exclude_t2_data[mask],
            full_data[mask],
            exclude_data[mask],
        )
    x = full_data[mask]
    y = exclude_data[mask]
    finite_voxels = np.all(np.isfinite(x), axis=1) & np.all(np.isfinite(y), axis=1)
    x = x[finite_voxels].astype(np.float64)
    y = y[finite_voxels].astype(np.float64)
    if not len(x):
        raise ValueError(f"no common valid optcom voxels: {key}")
    temporal = _temporal_correlations(x, y)
    spatial = np.array(
        [_correlation(x[:, index], y[:, index]) for index in range(x.shape[1])]
    )
    rmse = float(np.sqrt(np.mean((y - x) ** 2)))
    reference_rms = float(np.sqrt(np.mean(x**2)))
    signal_reference = float(np.median(x))
    x_std = np.std(x, axis=1, ddof=1)
    y_std = np.std(y, axis=1, ddof=1)
    x_tsnr = np.divide(
        np.mean(x, axis=1), x_std, out=np.full(len(x), np.nan), where=x_std > 0
    )
    y_tsnr = np.divide(
        np.mean(y, axis=1), y_std, out=np.full(len(y), np.nan), where=y_std > 0
    )
    full_median_tsnr = float(np.nanmedian(x_tsnr))
    exclude_median_tsnr = float(np.nanmedian(y_tsnr))
    return {
        "subject": row["subject"],
        "session": row["session"],
        "task": row["task"],
        "run": row["run"],
        "run_key": key,
        "nss_count": nss,
        "selection_reason": row.get("selection_reason", ""),
        "n_valid_t2_voxels": len(x_t2),
        "t2star_spatial_correlation": _correlation(x_t2, y_t2),
        "t2star_log_spatial_correlation": _correlation(np.log(x_t2), np.log(y_t2)),
        "t2star_spearman_correlation": _spearman(x_t2, y_t2),
        "t2star_median_absolute_difference_seconds": float(np.median(np.abs(t2_diff))),
        "t2star_median_absolute_percent_difference": float(np.median(t2_percent)),
        "t2star_p95_absolute_percent_difference": float(np.quantile(t2_percent, 0.95)),
        "t2star_fraction_absolute_percent_difference_gt_1": float(
            np.mean(t2_percent > 1)
        ),
        "t2star_fraction_absolute_percent_difference_gt_5": float(
            np.mean(t2_percent > 5)
        ),
        "t2star_fraction_absolute_percent_difference_gt_10": float(
            np.mean(t2_percent > 10)
        ),
        "t2star_rmse_seconds": float(np.sqrt(np.mean(t2_diff**2))),
        "n_valid_optcom_voxels": len(x),
        "optcom_median_voxelwise_temporal_correlation": float(np.nanmedian(temporal)),
        "optcom_median_volume_spatial_correlation": float(np.nanmedian(spatial)),
        "optcom_normalized_rmse": rmse / reference_rms if reference_rms else math.nan,
        "optcom_median_signal_percent_difference": (
            100 * (float(np.median(y)) - signal_reference) / abs(signal_reference)
            if signal_reference
            else math.nan
        ),
        "optcom_full_median_tsnr": full_median_tsnr,
        "optcom_exclude_median_tsnr": exclude_median_tsnr,
        "optcom_median_tsnr_difference": exclude_median_tsnr - full_median_tsnr,
    }


def component_summary(path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    frame = pd.read_csv(path, sep="\t")
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    classification_column = normalized.get("classification")
    variance_column = normalized.get("normalized variance explained") or normalized.get(
        "variance explained"
    )
    if classification_column is None or variance_column is None or len(frame) == 0:
        raise ValueError(f"invalid TEDANA metrics table: {path}")
    classifications = frame[classification_column].astype(str).str.lower()
    if not classifications.isin(("accepted", "rejected")).all():
        raise ValueError(f"invalid TEDANA classifications: {path}")
    try:
        variance = _normalize_variance(
            pd.to_numeric(frame[variance_column], errors="coerce").to_numpy(dtype=float)
        )
    except ValueError as exc:
        raise ValueError(f"invalid TEDANA component variance: {path}") from exc
    frame = frame.copy()
    frame["_classification"] = classifications
    frame["_normalized_variance_fraction"] = variance
    rejected = classifications == "rejected"
    accepted = classifications == "accepted"
    summary = {
        "n_ica": len(frame),
        "n_accepted": int(np.sum(accepted)),
        "n_rejected": int(np.sum(rejected)),
        "rejected_fraction": float(np.mean(rejected)),
        "accepted_normalized_variance": float(np.sum(variance[accepted])),
        "rejected_normalized_variance": float(np.sum(variance[rejected])),
        "largest_component_normalized_variance": float(np.max(variance)),
        "largest_rejected_component_normalized_variance": (
            float(np.max(variance[rejected])) if np.any(rejected) else 0.0
        ),
    }
    return summary, frame


def _cross_metrics(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"invalid cross-component metrics: {path}")
    return data


def _review_row(
    project: Path,
    audit_root: Path,
    row: dict[str, str],
    config: str,
    frame: pd.DataFrame,
    reason: str,
    accepted: bool,
) -> dict[str, Any] | None:
    target = "accepted" if accepted else "rejected"
    candidates = frame[frame["_classification"] == target]
    if candidates.empty:
        return None
    metric_row = candidates.loc[candidates["_normalized_variance_fraction"].idxmax()]
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    component_column = normalized.get("component")
    metrics_absolute = (
        audit_root
        / "benchmark"
        / config
        / row["run_key"]
        / (f"{row['run_key']}_desc-tedana_metrics.tsv")
    )
    metrics = metrics_absolute.relative_to(project)
    report_absolute = metrics_absolute.parent / f"{row['run_key']}_tedana_report.html"
    report = report_absolute.relative_to(project)
    component_value = (
        metric_row.get(component_column, metric_row.name)
        if component_column is not None
        else metric_row.name
    )
    component_match = "".join(
        character for character in str(component_value) if character.isdigit()
    )
    component_figure_absolute = (
        metrics_absolute.parent / "figures" / f"comp_{int(component_match):03d}.png"
        if component_match
        else None
    )
    return {
        "subject": row["subject"],
        "session": row["session"],
        "task": row["task"],
        "run": row["run"],
        "run_key": row["run_key"],
        "configuration": config,
        "component": component_value,
        "classification": target,
        "normalized_variance_fraction": metric_row["_normalized_variance_fraction"],
        "kappa": metric_row.get(normalized.get("kappa", ""), ""),
        "rho": metric_row.get(normalized.get("rho", ""), ""),
        "reason_for_review": reason,
        "metrics_path": metrics.as_posix(),
        "report_path": report.as_posix() if report_absolute.is_file() else "",
        "component_figure_path": (
            component_figure_absolute.relative_to(project).as_posix()
            if component_figure_absolute is not None
            and component_figure_absolute.is_file()
            else ""
        ),
    }


def benchmark_inputs(
    project: Path, audit_root: Path, row: dict[str, str]
) -> list[Path]:
    key = row["run_key"]
    inputs = [
        project / row["fmriprep_mask"],
        project / row["fmriprep_confounds"],
    ]
    for config in ("t2s-full", "t2s-exclude-nss"):
        directory = audit_root / "benchmark" / config / key
        inputs.extend(
            (
                directory / f"{key}_T2starmap.nii.gz",
                directory / f"{key}_desc-optcom_bold.nii.gz",
            )
        )
    for config in ("nss-fastica", "nss-robustica"):
        directory = audit_root / "benchmark" / config / key
        inputs.extend(
            (
                directory / f"{key}_desc-tedana_metrics.tsv",
                directory / f"{key}_desc-optcom_bold.nii.gz",
                directory / f"{key}_desc-denoised_bold.nii.gz",
            )
        )
    inputs.append(
        audit_root
        / "benchmark"
        / "nss-robustica"
        / key
        / f"{key}_desc-ICACrossComponent_metrics.json"
    )
    missing = [path for path in inputs if not path.is_file()]
    if missing:
        raise ValueError(f"missing benchmark input for {key}: {missing[0]}")
    return inputs


def compare_ica(
    project: Path, audit_root: Path, row: dict[str, str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    key = row["run_key"]
    summaries: dict[str, dict[str, Any]] = {}
    frames: dict[str, pd.DataFrame] = {}
    for label, config in (("fastica", "nss-fastica"), ("robustica", "nss-robustica")):
        path = (
            audit_root / "benchmark" / config / key / f"{key}_desc-tedana_metrics.tsv"
        )
        summaries[label], frames[label] = component_summary(path)
    cross_path = (
        audit_root
        / "benchmark"
        / "nss-robustica"
        / key
        / f"{key}_desc-ICACrossComponent_metrics.json"
    )
    cross = _cross_metrics(cross_path)
    output: dict[str, Any] = {
        "subject": row["subject"],
        "session": row["session"],
        "task": row["task"],
        "run": row["run"],
        "run_key": key,
        "nss_count": int(row["nss_count"]),
        "selection_reason": row.get("selection_reason", ""),
        "robustica_mean_index_quality": cross.get("robustica_mean_index_quality", ""),
        "robustica_fastica_convergence_warning_count": cross.get(
            "fastica_convergence_warning_count", ""
        ),
    }
    for metric in ICA_METRICS:
        historical = number(row.get(metric))
        fast = summaries["fastica"][metric]
        robust = summaries["robustica"][metric]
        output[f"historical_{metric}"] = historical
        output[f"fastica_{metric}"] = fast
        output[f"robustica_{metric}"] = robust
        output[f"robustica_minus_fastica_{metric}"] = robust - fast
    review: list[dict[str, Any]] = []
    for config, label in (("nss-fastica", "fastica"), ("nss-robustica", "robustica")):
        candidate = _review_row(
            project,
            audit_root,
            row,
            config,
            frames[label],
            "largest_rejected_variance",
            accepted=False,
        )
        if candidate:
            review.append(candidate)
    quality = number(output["robustica_mean_index_quality"])
    if quality is not None and quality < 0.6:
        candidate = _review_row(
            project,
            audit_root,
            row,
            "nss-robustica",
            frames["robustica"],
            "robustica_index_quality_below_0.6_largest_accepted",
            accepted=True,
        )
        if candidate:
            review.append(candidate)
    return output, review


def _tsnr(data: np.ndarray) -> np.ndarray:
    standard_deviation = np.std(data, axis=1, ddof=1)
    return np.divide(
        np.mean(data, axis=1),
        standard_deviation,
        out=np.full(len(data), np.nan),
        where=standard_deviation > 0,
    )


def _dvars(data: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(np.diff(data, axis=1) ** 2, axis=0))


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    x_rank = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    y_rank = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    return _correlation(x_rank, y_rank)


def _model_r_squared(predictors: np.ndarray, outcome: np.ndarray) -> float:
    predictors = np.asarray(predictors, dtype=float)
    outcome = np.asarray(outcome, dtype=float)
    if len(predictors) != len(outcome) or len(outcome) < 2:
        raise ValueError("motion model row mismatch")
    design = np.column_stack((np.ones(len(outcome)), predictors))
    fitted = design @ np.linalg.lstsq(design, outcome, rcond=None)[0]
    total = float(np.sum((outcome - np.mean(outcome)) ** 2))
    return 1 - float(np.sum((outcome - fitted) ** 2)) / total if total else 0.0


def _denoising_metrics(
    optcom: np.ndarray,
    denoised: np.ndarray,
    framewise_displacement: np.ndarray,
    motion: np.ndarray,
) -> dict[str, float]:
    optcom_tsnr = _tsnr(optcom)
    denoised_tsnr = _tsnr(denoised)
    optcom_variance = np.var(optcom, axis=1, ddof=1)
    denoised_variance = np.var(denoised, axis=1, ddof=1)
    valid_variance = optcom_variance > 0
    if not np.any(valid_variance):
        raise ValueError("no nonzero optcom temporal variance")
    variance_removed = (
        1 - denoised_variance[valid_variance] / optcom_variance[valid_variance]
    )
    optcom_signal = np.mean(optcom, axis=1)
    denoised_signal = np.mean(denoised, axis=1)
    valid_signal = np.abs(optcom_signal) > np.finfo(float).eps
    if not np.any(valid_signal):
        raise ValueError("no nonzero optcom mean signal")
    signal_change = (
        100
        * (denoised_signal[valid_signal] - optcom_signal[valid_signal])
        / np.abs(optcom_signal[valid_signal])
    )
    optcom_dvars = _dvars(optcom)
    denoised_dvars = _dvars(denoised)
    optcom_median_dvars = float(np.median(optcom_dvars))
    denoised_median_dvars = float(np.median(denoised_dvars))
    if len(framewise_displacement) != len(denoised_dvars):
        raise ValueError("FD-DVARS row mismatch")
    return {
        "median_optcom_tsnr": float(np.nanmedian(optcom_tsnr)),
        "median_denoised_tsnr": float(np.nanmedian(denoised_tsnr)),
        "median_tsnr_change": float(np.nanmedian(denoised_tsnr - optcom_tsnr)),
        "median_variance_removed_fraction": float(np.median(variance_removed)),
        "median_signal_percent_change": float(np.median(signal_change)),
        "optcom_median_dvars": optcom_median_dvars,
        "denoised_median_dvars": denoised_median_dvars,
        "dvars_percent_change": (
            100 * (denoised_median_dvars - optcom_median_dvars) / optcom_median_dvars
            if optcom_median_dvars
            else 0.0
        ),
        "fd_denoised_dvars_spearman": _spearman(framewise_displacement, denoised_dvars),
        "motion24_global_signal_r_squared": _model_r_squared(
            motion, np.mean(denoised, axis=0)
        ),
    }


def compare_denoising(
    project: Path, audit_root: Path, row: dict[str, str]
) -> dict[str, Any]:
    key = row["run_key"]
    nss = int(row["nss_count"])
    expected_volumes = int(row["number_of_original_volumes"]) - nss
    mask_image = _image(project / row["fmriprep_mask"], 3)
    mask = np.asarray(mask_image.dataobj) > 0
    series: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for label, config in (("fastica", "nss-fastica"), ("robustica", "nss-robustica")):
        directory = audit_root / "benchmark" / config / key
        optcom_image = _image(directory / f"{key}_desc-optcom_bold.nii.gz", 4)
        denoised_image = _image(directory / f"{key}_desc-denoised_bold.nii.gz", 4)
        _matching_geometry(optcom_image, denoised_image)
        if optcom_image.shape[:3] != mask.shape or not np.allclose(
            optcom_image.affine, mask_image.affine, atol=1e-5
        ):
            raise ValueError(f"denoising-mask geometry mismatch: {key} {config}")
        if optcom_image.shape[3] != expected_volumes:
            raise ValueError(
                f"steady-state volume mismatch: {key} {config}; "
                f"expected {expected_volumes}, found {optcom_image.shape[3]}"
            )
        optcom = np.asarray(optcom_image.dataobj, dtype=np.float32)[mask]
        denoised = np.asarray(denoised_image.dataobj, dtype=np.float32)[mask]
        series[label] = (optcom, denoised)
    all_series = tuple(item for pair in series.values() for item in pair)
    finite = np.logical_and.reduce([np.all(item, axis=1) for item in all_series])
    if not np.any(finite):
        raise ValueError(f"no common valid denoising voxels: {key}")
    confounds = pd.read_csv(project / row["fmriprep_confounds"], sep="\t")
    motion = motion24(confounds)[nss:]
    fd = pd.to_numeric(confounds["framewise_displacement"], errors="coerce").to_numpy(
        dtype=float
    )[nss + 1 :]
    if len(motion) != expected_volumes or not np.all(np.isfinite(fd)):
        raise ValueError(f"invalid denoising confounds: {key}")
    output: dict[str, Any] = {
        "subject": row["subject"],
        "session": row["session"],
        "task": row["task"],
        "run": row["run"],
        "run_key": key,
        "nss_count": nss,
        "selection_reason": row.get("selection_reason", ""),
        "n_steady_state_volumes": expected_volumes,
        "n_valid_voxels": int(np.sum(finite)),
    }
    config_metrics: dict[str, dict[str, float]] = {}
    for label in ("fastica", "robustica"):
        optcom, denoised = (item[finite].astype(np.float64) for item in series[label])
        config_metrics[label] = _denoising_metrics(optcom, denoised, fd, motion)
        for metric, value in config_metrics[label].items():
            output[f"{label}_{metric}"] = value
    output["robustica_minus_fastica_denoised_tsnr"] = (
        config_metrics["robustica"]["median_denoised_tsnr"]
        - config_metrics["fastica"]["median_denoised_tsnr"]
    )
    output["robustica_minus_fastica_variance_removed_fraction"] = (
        config_metrics["robustica"]["median_variance_removed_fraction"]
        - config_metrics["fastica"]["median_variance_removed_fraction"]
    )
    output["robustica_minus_fastica_denoised_dvars"] = (
        config_metrics["robustica"]["denoised_median_dvars"]
        - config_metrics["fastica"]["denoised_median_dvars"]
    )
    fast = series["fastica"][1][finite].astype(np.float64)
    robust = series["robustica"][1][finite].astype(np.float64)
    temporal = _temporal_correlations(fast, robust)
    spatial = np.array(
        [
            _correlation(fast[:, index], robust[:, index])
            for index in range(expected_volumes)
        ]
    )
    rmse = float(np.sqrt(np.mean((robust - fast) ** 2)))
    reference_rms = float(np.sqrt(np.mean(fast**2)))
    output["fastica_robustica_median_voxelwise_temporal_correlation"] = float(
        np.nanmedian(temporal)
    )
    output["fastica_robustica_median_volume_spatial_correlation"] = float(
        np.nanmedian(spatial)
    )
    output["fastica_robustica_normalized_rmse"] = (
        rmse / reference_rms if reference_rms else math.nan
    )
    return output


def _plot_outputs(
    t2_rows: Sequence[dict[str, Any]],
    ica_rows: Sequence[dict[str, Any]],
    denoising_rows: Sequence[dict[str, Any]],
    root: Path,
) -> None:
    from matplotlib import pyplot as plt

    root.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    t2_metrics = (
        (
            "t2star_median_absolute_percent_difference",
            "Median absolute T2* difference (%)",
        ),
        ("t2star_spatial_correlation", "Raw T2* spatial correlation"),
        ("t2star_log_spatial_correlation", "Log T2* spatial correlation"),
        (
            "t2star_fraction_absolute_percent_difference_gt_5",
            "T2* voxel fraction with >5% difference",
        ),
        ("optcom_normalized_rmse", "Optcom normalized RMSE"),
        ("optcom_median_tsnr_difference", "Optcom median tSNR difference"),
    )
    for ax, (metric, label) in zip(axes.ravel(), t2_metrics):
        ax.scatter(
            [row["nss_count"] for row in t2_rows],
            [row[metric] for row in t2_rows],
            alpha=0.75,
        )
        ax.set(xlabel="Initial NSS volumes", ylabel=label)
    fig.tight_layout()
    fig.savefig(root / "t2star_nss_effect.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 6))
    fast = np.array([row["fastica_n_ica"] for row in ica_rows], dtype=float)
    robust = np.array([row["robustica_n_ica"] for row in ica_rows], dtype=float)
    limits = (min(np.min(fast), np.min(robust)), max(np.max(fast), np.max(robust)))
    ax.scatter(fast, robust, alpha=0.75)
    ax.plot(limits, limits, color="black", linestyle="--", linewidth=1)
    ax.set(
        xlabel="NSS-aware FastICA components", ylabel="NSS-aware RobustICA components"
    )
    fig.tight_layout()
    fig.savefig(root / "ica_dimensionality.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].hist(
        [row["robustica_minus_fastica_rejected_fraction"] for row in ica_rows], bins=15
    )
    axes[0].set(xlabel="RobustICA - FastICA rejected fraction", ylabel="Runs")
    axes[1].hist(
        [
            row["robustica_minus_fastica_rejected_normalized_variance"]
            for row in ica_rows
        ],
        bins=15,
    )
    axes[1].set(xlabel="RobustICA - FastICA rejected variance", ylabel="Runs")
    fig.tight_layout()
    fig.savefig(root / "ica_classification_deltas.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    axes[0].scatter(
        [row["fastica_median_denoised_tsnr"] for row in denoising_rows],
        [row["robustica_median_denoised_tsnr"] for row in denoising_rows],
        alpha=0.75,
    )
    tsnr_values = [
        row[f"{config}_median_denoised_tsnr"]
        for row in denoising_rows
        for config in ("fastica", "robustica")
    ]
    limits = (min(tsnr_values), max(tsnr_values))
    axes[0].plot(limits, limits, color="black", linestyle="--", linewidth=1)
    axes[0].set(xlabel="FastICA median tSNR", ylabel="RobustICA median tSNR")
    axes[1].hist(
        [row["robustica_minus_fastica_denoised_dvars"] for row in denoising_rows],
        bins=15,
    )
    axes[1].set(xlabel="RobustICA - FastICA median DVARS", ylabel="Runs")
    axes[2].hist(
        [
            row["fastica_robustica_median_voxelwise_temporal_correlation"]
            for row in denoising_rows
        ],
        bins=15,
    )
    axes[2].set(
        xlabel="FastICA/RobustICA voxelwise temporal correlation", ylabel="Runs"
    )
    fig.tight_layout()
    fig.savefig(root / "denoising_qc.png", dpi=180)
    plt.close(fig)
    for path in root.glob("*.png"):
        apply_umask_mode(path)


def _format_summary(values: Sequence[Any], digits: int = 4) -> str:
    middle = median(values)
    low, high = iqr(values)
    if middle is None or low is None or high is None:
        return "not available"
    return f"{middle:.{digits}f} (IQR {low:.{digits}f} to {high:.{digits}f})"


def validate_numeric_rows(
    rows: Sequence[dict[str, Any]], columns: Sequence[str], label: str
) -> None:
    for row in rows:
        for column in columns:
            if number(row.get(column)) is None:
                raise ValueError(
                    f"nonfinite or missing {label} metric {column}: {row.get('run_key', '')}"
                )


def validate_run_keys(
    rows: Sequence[dict[str, Any]], expected_keys: set[str], label: str
) -> None:
    keys = [str(row.get("run_key", "")) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate run keys in {label}")
    if set(keys) != expected_keys:
        missing = sorted(expected_keys - set(keys))
        extra = sorted(set(keys) - expected_keys)
        raise ValueError(
            f"run-key mismatch in {label}; missing={missing[:3]} extra={extra[:3]}"
        )


def apply_tree_modes(root: Path) -> None:
    apply_umask_mode(root, directory=True)
    for directory, _subdirectories, filenames in os.walk(root):
        directory_path = Path(directory)
        apply_umask_mode(directory_path, directory=True)
        for filename in filenames:
            apply_umask_mode(directory_path / filename)


def install_directory(stage: Path, output: Path) -> None:
    backup = output.with_name(f".{output.name}.previous-{os.getpid()}")
    if backup.exists():
        raise ValueError(f"stale summary backup requires review: {backup}")
    if output.exists():
        os.replace(output, backup)
    try:
        os.replace(stage, output)
    except Exception:
        if backup.exists() and not output.exists():
            os.replace(backup, output)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    apply_tree_modes(output)


def make_report(
    t2_rows: Sequence[dict[str, Any]],
    ica_rows: Sequence[dict[str, Any]],
    denoising_rows: Sequence[dict[str, Any]],
    path: Path,
) -> None:
    n0 = [row for row in t2_rows if int(row["nss_count"]) == 0]
    quality = [number(row["robustica_mean_index_quality"]) for row in ica_rows]
    quality = [value for value in quality if value is not None]
    warnings = [
        number(row["robustica_fastica_convergence_warning_count"]) for row in ica_rows
    ]
    warnings = [value for value in warnings if value is not None]
    lines = [
        "# TEDANA Sentinel Benchmark Report",
        "",
        "This report summarizes isolated audit derivatives. It does not modify or authorize a change to production TEDANA outputs.",
        "",
        "## Inventory",
        "",
        f"- Sentinel runs: {len(t2_rows)}",
        "- Controlled configurations per run: T2S-FULL, T2S-EXCLUDE-NSS, NSS-aware FastICA, NSS-aware RobustICA.",
        f"- N=0 controls: {len(n0)}",
        f"- N=0 numerical identity checks passed: {len(n0)}",
        "",
        "## T2*/Optimal Combination",
        "",
        f"- T2* median absolute percent difference: {_format_summary([row['t2star_median_absolute_percent_difference'] for row in t2_rows])}",
        f"- T2* raw spatial correlation: {_format_summary([row['t2star_spatial_correlation'] for row in t2_rows], 6)}",
        f"- T2* log spatial correlation: {_format_summary([row['t2star_log_spatial_correlation'] for row in t2_rows], 6)}",
        f"- T2* voxel fraction with >5% absolute difference: {_format_summary([row['t2star_fraction_absolute_percent_difference_gt_5'] for row in t2_rows], 6)}",
        f"- Optcom normalized RMSE: {_format_summary([row['optcom_normalized_rmse'] for row in t2_rows], 6)}",
        f"- Optcom median voxelwise temporal correlation: {_format_summary([row['optcom_median_voxelwise_temporal_correlation'] for row in t2_rows], 6)}",
        "",
        "N=0 controls receive identical commands and serve as a numerical pipeline check. Run-level effects remain in `paired_t2s.tsv`; no arbitrary consequential-effect threshold is imposed here.",
        "",
        "## FastICA Versus RobustICA",
        "",
        f"- Historical to NSS-aware FastICA ICA-count change: {_format_summary([row['fastica_n_ica'] - row['historical_n_ica'] for row in ica_rows])}",
        f"- Historical to NSS-aware FastICA rejected-fraction change: {_format_summary([row['fastica_rejected_fraction'] - row['historical_rejected_fraction'] for row in ica_rows])}",
        f"- Change in ICA count: {_format_summary([row['robustica_minus_fastica_n_ica'] for row in ica_rows])}",
        f"- Change in rejected fraction: {_format_summary([row['robustica_minus_fastica_rejected_fraction'] for row in ica_rows])}",
        f"- Change in rejected variance: {_format_summary([row['robustica_minus_fastica_rejected_normalized_variance'] for row in ica_rows])}",
        f"- RobustICA mean index quality: {_format_summary(quality)}",
        f"- Runs with index quality below 0.6: {sum(value < 0.6 for value in quality)}",
        f"- RobustICA FastICA convergence warnings: {int(sum(warnings)) if warnings else 'not available'} total across {len(warnings)} reported runs.",
        "",
        "## Denoising QC",
        "",
        f"- RobustICA minus FastICA denoised tSNR: {_format_summary([row['robustica_minus_fastica_denoised_tsnr'] for row in denoising_rows])}",
        f"- RobustICA minus FastICA median DVARS: {_format_summary([row['robustica_minus_fastica_denoised_dvars'] for row in denoising_rows])}",
        f"- FastICA/RobustICA voxelwise temporal correlation: {_format_summary([row['fastica_robustica_median_voxelwise_temporal_correlation'] for row in denoising_rows], 6)}",
        f"- FastICA FD-versus-denoised-DVARS Spearman correlation: {_format_summary([row['fastica_fd_denoised_dvars_spearman'] for row in denoising_rows])}",
        f"- RobustICA FD-versus-denoised-DVARS Spearman correlation: {_format_summary([row['robustica_fd_denoised_dvars_spearman'] for row in denoising_rows])}",
        "",
        "## Interpretation Gate",
        "",
        "These paired summaries determine which effects need visual review and whether the optional Motion24 audit should proceed. They do not select a production winner, use task regressors, alter classifications, or justify a cohort-wide RobustICA rerun by themselves.",
        "",
        "The next reviewed pass should inspect `review_manifest.tsv`, examine run-level outliers, and add Motion24 metrics only after confirming that these aggregate calculations are scientifically sensible.",
    ]
    path.write_text("\n".join(lines) + "\n")
    apply_umask_mode(path)


def run_build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    rows = read_tsv(args.sentinel_tsv)
    if not rows or len({row["run_key"] for row in rows}) != len(rows):
        raise ValueError("sentinel manifest is empty or contains duplicate run keys")
    if args.dry_run:
        print(f"Would summarize {len(rows)} validated sentinel run(s).")
        print(f"Audit root: {audit_root}")
        print(f"Tracked output: {output}")
        return 0
    if output.exists() and not args.overwrite:
        raise ValueError(
            f"summary output already exists; review it or use --overwrite: {output}"
        )
    t2_rows: list[dict[str, Any]] = []
    ica_rows: list[dict[str, Any]] = []
    denoising_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    inputs = [args.sentinel_tsv.resolve()]
    for index, row in enumerate(rows, start=1):
        inputs.extend(benchmark_inputs(project, audit_root, row))
        t2_rows.append(compare_t2s(project, audit_root, row))
        ica_row, candidates = compare_ica(project, audit_root, row)
        ica_rows.append(ica_row)
        denoising_rows.append(compare_denoising(project, audit_root, row))
        review_rows.extend(candidates)
        print(f"Summarized {index}/{len(rows)} {row['run_key']}", flush=True)
    expected_keys = {row["run_key"] for row in rows}
    validate_run_keys(t2_rows, expected_keys, "paired T2*/optcom table")
    validate_run_keys(ica_rows, expected_keys, "paired ICA table")
    validate_run_keys(denoising_rows, expected_keys, "paired denoising table")
    validate_numeric_rows(t2_rows, T2_NUMERIC_COLUMNS, "T2*/optcom")
    validate_numeric_rows(ica_rows, ICA_NUMERIC_COLUMNS, "ICA")
    validate_numeric_rows(denoising_rows, DENOISING_NUMERIC_COLUMNS, "denoising")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="tedana-benchmark-summary-", dir=output.parent
    ) as temporary:
        stage = Path(temporary)
        write_tsv(stage / "paired_t2s.tsv", t2_rows, T2_COLUMNS)
        write_tsv(stage / "paired_ica.tsv", ica_rows, ICA_COLUMNS)
        write_tsv(stage / "paired_denoising.tsv", denoising_rows, DENOISING_COLUMNS)
        write_tsv(stage / "review_manifest.tsv", review_rows, REVIEW_COLUMNS)
        _plot_outputs(t2_rows, ica_rows, denoising_rows, stage / "figures")
        make_report(t2_rows, ica_rows, denoising_rows, stage / "report.md")
        provenance = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "sentinel_manifest": args.sentinel_tsv.resolve()
            .relative_to(project)
            .as_posix(),
            "sentinel_manifest_sha256": sha256(args.sentinel_tsv),
            "sentinel_count": len(rows),
            "audit_root": audit_root.relative_to(project).as_posix(),
            "input_inventory_digest_path_size_mtime": inventory_digest(inputs, project),
            "production_derivatives_modified": False,
            "task_regressors_used": False,
            "classifications_changed": False,
            "outputs": {},
        }
        for relative_path in OUTPUTS:
            if relative_path.name == "provenance.json":
                continue
            provenance["outputs"][relative_path.as_posix()] = sha256(
                stage / relative_path
            )
        (stage / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        )
        apply_umask_mode(stage / "provenance.json")
        install_directory(stage, output)
    print(f"Wrote paired T2*/optcom rows: {len(t2_rows)}")
    print(f"Wrote paired ICA rows: {len(ica_rows)}")
    print(f"Wrote paired denoising rows: {len(denoising_rows)}")
    print(f"Wrote review candidates: {len(review_rows)}")
    print(f"Tracked report: {output / 'report.md'}")
    return 0


def run_check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    failures: list[str] = []
    provenance_path = output / "provenance.json"
    if not provenance_path.is_file():
        failures.append(f"missing:{provenance_path}")
        provenance: dict[str, Any] = {}
    else:
        provenance = json.loads(provenance_path.read_text())
    sentinel_rows = read_tsv(args.sentinel_tsv)
    expected_count = len(sentinel_rows)
    expected_keys = {row["run_key"] for row in sentinel_rows}
    numeric_columns = {
        "paired_t2s.tsv": T2_NUMERIC_COLUMNS,
        "paired_ica.tsv": ICA_NUMERIC_COLUMNS,
        "paired_denoising.tsv": DENOISING_NUMERIC_COLUMNS,
    }
    for name, columns in numeric_columns.items():
        path = output / name
        if not path.is_file():
            failures.append(f"missing:{path}")
            continue
        table_rows = read_tsv(path)
        try:
            validate_run_keys(table_rows, expected_keys, name)
            validate_numeric_rows(table_rows, columns, name)
        except ValueError as exc:
            failures.append(f"content:{exc}")
    review_path = output / "review_manifest.tsv"
    if review_path.is_file():
        for row in read_tsv(review_path):
            if row.get("run_key") not in expected_keys:
                failures.append(f"review_run_key:{row.get('run_key', '')}")
            if row.get("configuration") not in {"nss-fastica", "nss-robustica"}:
                failures.append(f"review_configuration:{row.get('configuration', '')}")
    for relative_path in OUTPUTS:
        path = output / relative_path
        if not path.is_file():
            failures.append(f"missing:{path}")
            continue
        if relative_path.name == "provenance.json":
            continue
        expected = provenance.get("outputs", {}).get(relative_path.as_posix())
        if expected != sha256(path):
            failures.append(f"checksum:{path}")
    if provenance.get("sentinel_manifest_sha256") != sha256(args.sentinel_tsv):
        failures.append("sentinel_manifest_checksum")
    try:
        inputs = [args.sentinel_tsv.resolve()]
        for row in sentinel_rows:
            inputs.extend(benchmark_inputs(project, audit_root, row))
        if provenance.get("input_inventory_digest_path_size_mtime") != inventory_digest(
            inputs, project
        ):
            failures.append("benchmark_input_inventory")
    except (OSError, ValueError) as exc:
        failures.append(f"benchmark_inputs:{exc}")
    for failure in failures:
        print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: {len(failures)} TEDANA benchmark summary issue(s).")
        return 1
    print(
        f"CHECK PASSED: TEDANA benchmark summary validated for {expected_count} run(s)."
    )
    return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-root", type=Path, default=project)
        child.add_argument(
            "--sentinel-tsv",
            type=Path,
            default=project / "qc" / "tedana_audit" / "sentinel_runs.tsv",
        )
        child.add_argument(
            "--audit-root", type=Path, default=project / "derivatives" / "tedana-audit"
        )
        child.add_argument(
            "--output-dir",
            type=Path,
            default=project / "qc" / "tedana_audit" / "benchmark",
        )
    build = subparsers.choices["build"]
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return run_build(args) if args.command == "build" else run_check(args)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
