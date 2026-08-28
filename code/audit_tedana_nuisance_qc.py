#!/usr/bin/env python3
"""Compare BASE, full-volume TEDANA, and NSS-aware TEDANA nuisance models."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd

from audit_tedana import motion24
from audit_tedana_design import selected_base_confounds, software_era
from genTedanaConfounds import rejected_component_columns
from pipeline_utils import apply_umask_mode, ensure_safe_child_path


CONDITIONS = ("base", "tedana_full", "tedana_nss")
RUN_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_versions",
    "software_era", "nss_count", "number_of_original_volumes", "n_valid_voxels",
    "condition", "nuisance_columns", "nuisance_rank", "incremental_rank_vs_base",
    "incremental_rank_fraction", "median_tsnr", "median_standardized_dvars",
    "fd_dvars_spearman", "fraction_high_dvars", "motion24_global_signal_r_squared",
    "variance_removed_fraction", "median_lag1_autocorrelation",
    "median_temporal_standard_deviation", "median_temporal_rms",
)
PAIR_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_era", "nss_count",
    "comparison", "candidate_minus_reference_tsnr",
    "candidate_minus_reference_standardized_dvars",
    "candidate_minus_reference_fd_dvars_spearman",
    "candidate_minus_reference_fraction_high_dvars",
    "candidate_minus_reference_motion24_global_signal_r_squared",
    "candidate_minus_reference_variance_removed_fraction",
    "candidate_minus_reference_lag1_autocorrelation",
    "median_voxelwise_temporal_correlation", "median_volume_spatial_correlation",
    "normalized_rmse",
)
SUMMARY_COLUMNS = (
    "grouping", "group", "comparison", "metric", "n", "median", "q25", "q75",
    "p90", "p95",
)
OUTPUTS = (
    Path("run_metrics.tsv"), Path("paired_conditions.tsv"), Path("summary.tsv"),
    Path("figures/nuisance_qc.png"), Path("report.md"), Path("provenance.json"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    apply_umask_mode(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory_digest(paths: Sequence[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(item.resolve() for item in paths)):
        stat = path.stat()
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def finite_frame(frame: pd.DataFrame) -> np.ndarray:
    values = frame.apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(dtype=float)
    if values.ndim != 2 or not np.all(np.isfinite(values)):
        raise ValueError("invalid nuisance matrix")
    return values


def centered_basis(values: np.ndarray) -> tuple[np.ndarray, int]:
    centered = values - np.mean(values, axis=0, keepdims=True)
    if not centered.shape[1]:
        return np.empty((len(values), 0)), 0
    u, singular, _ = np.linalg.svd(centered, full_matrices=False)
    if not len(singular) or singular[0] == 0:
        return np.empty((len(values), 0)), 0
    tolerance = max(centered.shape) * np.finfo(float).eps * singular[0]
    rank = int(np.sum(singular > tolerance))
    return u[:, :rank], rank


def nuisance_adjust(data: np.ndarray, nuisance: np.ndarray) -> tuple[np.ndarray, int]:
    basis, rank = centered_basis(nuisance)
    if not rank:
        return data.copy(), 0
    adjusted = data - basis @ (basis.T @ data)
    return adjusted, rank


def correlation(first: np.ndarray, second: np.ndarray) -> float:
    x = np.asarray(first, dtype=float)
    y = np.asarray(second, dtype=float)
    x = x - np.mean(x)
    y = y - np.mean(y)
    denominator = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(np.dot(x, y) / denominator) if denominator else math.nan


def spearman(first: np.ndarray, second: np.ndarray) -> float:
    x = pd.Series(first).rank(method="average").to_numpy(dtype=float)
    y = pd.Series(second).rank(method="average").to_numpy(dtype=float)
    return correlation(x, y)


def dvars(data: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(np.diff(data, axis=0) ** 2, axis=1))


def standardized_dvars(data: np.ndarray) -> np.ndarray:
    scale = float(np.nanmedian(np.std(data, axis=0, ddof=1)))
    if not scale:
        raise ValueError("zero temporal scale")
    return dvars(data) / scale


def lag1(data: np.ndarray) -> np.ndarray:
    first = data[:-1] - np.mean(data[:-1], axis=0)
    second = data[1:] - np.mean(data[1:], axis=0)
    denominator = np.linalg.norm(first, axis=0) * np.linalg.norm(second, axis=0)
    return np.divide(
        np.sum(first * second, axis=0), denominator,
        out=np.full(data.shape[1], np.nan), where=denominator > 0,
    )


def model_r_squared(predictors: np.ndarray, outcome: np.ndarray) -> float:
    design = np.column_stack((np.ones(len(outcome)), predictors))
    fitted = design @ np.linalg.lstsq(design, outcome, rcond=None)[0]
    total = float(np.sum((outcome - np.mean(outcome)) ** 2))
    return 1 - float(np.sum((outcome - fitted) ** 2)) / total if total else 0.0


def metrics(
    original: np.ndarray,
    adjusted: np.ndarray,
    fd: np.ndarray,
    motion: np.ndarray,
) -> dict[str, float]:
    standard_deviation = np.std(adjusted, axis=0, ddof=1)
    tsnr = np.divide(
        np.mean(adjusted, axis=0), standard_deviation,
        out=np.full(adjusted.shape[1], np.nan), where=standard_deviation > 0,
    )
    std_dvars = standardized_dvars(adjusted)
    if len(fd) != len(std_dvars):
        raise ValueError("FD/DVARS row mismatch")
    original_variance = np.var(original, axis=0, ddof=1)
    adjusted_variance = np.var(adjusted, axis=0, ddof=1)
    valid = original_variance > 0
    removed = 1 - adjusted_variance[valid] / original_variance[valid]
    global_signal = np.mean(adjusted, axis=1)
    return {
        "median_tsnr": float(np.nanmedian(tsnr)),
        "median_standardized_dvars": float(np.nanmedian(std_dvars)),
        "fd_dvars_spearman": spearman(fd, std_dvars),
        "fraction_high_dvars": float(np.mean(std_dvars > 1.5)),
        "motion24_global_signal_r_squared": model_r_squared(motion, global_signal),
        "variance_removed_fraction": float(np.nanmedian(removed)),
        "median_lag1_autocorrelation": float(np.nanmedian(lag1(adjusted))),
        "median_temporal_standard_deviation": float(np.nanmedian(standard_deviation)),
        "median_temporal_rms": float(np.nanmedian(np.sqrt(np.mean(adjusted**2, axis=0)))),
    }


def rejected_matrix(directory: Path, key: str, full_grid: bool) -> pd.DataFrame:
    metrics_path = directory / f"{key}_desc-tedana_metrics.tsv"
    mixing_name = f"{key}_desc-ICA_mixingFullGrid.tsv" if full_grid else f"{key}_desc-ICA_mixing.tsv"
    mixing = pd.read_csv(directory / mixing_name, sep="\t")
    component_metrics = pd.read_csv(metrics_path, sep="\t")
    indices = rejected_component_columns(component_metrics)
    return mixing.iloc[:, indices] if indices else pd.DataFrame(index=mixing.index)


def canonical_bold(project: Path, row: dict[str, str]) -> Path:
    return (
        project / "derivatives" / "fmriprep" / f"sub-{row['subject']}"
        / f"ses-{row['session']}" / "func"
        / f"{row['run_key']}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
    )


def canonical_mask(project: Path, row: dict[str, str]) -> Path:
    bold = canonical_bold(project, row)
    candidate = bold.with_name(
        f"{row['run_key']}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"
    )
    return candidate if candidate.is_file() else project / row["fmriprep_mask"]


def image_data(path: Path, mask_path: Path) -> tuple[np.ndarray, np.ndarray]:
    image = nib.load(str(path))
    mask_image = nib.load(str(mask_path))
    if len(image.shape) != 4 or mask_image.shape != image.shape[:3]:
        raise ValueError("BOLD/mask shape mismatch")
    if not np.allclose(image.affine, mask_image.affine, atol=1e-5):
        raise ValueError("BOLD/mask affine mismatch")
    mask = np.asarray(mask_image.dataobj) > 0
    values = np.asarray(image.dataobj, dtype=np.float32)[mask].T
    valid = np.all(np.isfinite(values), axis=0) & (np.std(values, axis=0) > 0)
    if not np.any(valid):
        raise ValueError("no valid in-mask BOLD voxels")
    return values[:, valid].astype(np.float64), valid


def pair_metrics(
    reference: np.ndarray,
    candidate: np.ndarray,
    reference_metrics: dict[str, float],
    candidate_metrics: dict[str, float],
) -> dict[str, float]:
    temporal = np.array([correlation(reference[:, i], candidate[:, i]) for i in range(reference.shape[1])])
    spatial = np.array([correlation(reference[i], candidate[i]) for i in range(reference.shape[0])])
    rmse = float(np.sqrt(np.mean((candidate - reference) ** 2)))
    rms = float(np.sqrt(np.mean(reference**2)))
    names = (
        "median_tsnr", "median_standardized_dvars", "fd_dvars_spearman",
        "fraction_high_dvars", "motion24_global_signal_r_squared",
        "variance_removed_fraction", "median_lag1_autocorrelation",
    )
    output = {
        f"candidate_minus_reference_{name.removeprefix('median_')}":
        candidate_metrics[name] - reference_metrics[name]
        for name in names
    }
    output.update(
        {
            "median_voxelwise_temporal_correlation": float(np.nanmedian(temporal)),
            "median_volume_spatial_correlation": float(np.nanmedian(spatial)),
            "normalized_rmse": rmse / rms if rms else math.nan,
        }
    )
    return output


def audit_run(
    project: Path, audit_root: Path, row: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    key = row["run_key"]
    nss = int(row["nss_count"])
    total = int(row["number_of_original_volumes"])
    bold = canonical_bold(project, row)
    mask = canonical_mask(project, row)
    confounds_path = project / row["fmriprep_confounds"]
    full_dir = audit_root / "benchmark" / "full-fastica" / key
    nss_dir = audit_root / "benchmark" / "nss-fastica" / key
    required = [bold, mask, confounds_path]
    for directory, full_grid in ((full_dir, False), (nss_dir, True)):
        required.extend(
            [
                directory / f"{key}_desc-tedana_metrics.tsv",
                directory / (
                    f"{key}_desc-ICA_mixingFullGrid.tsv" if full_grid
                    else f"{key}_desc-ICA_mixing.tsv"
                ),
            ]
        )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"{key}: missing input(s): {', '.join(map(str, missing))}")
    data, _ = image_data(bold, mask)
    if len(data) != total:
        raise ValueError(f"{key}: BOLD volumes differ from inventory")
    confounds = pd.read_csv(confounds_path, sep="\t")
    base = selected_base_confounds(confounds_path)
    full_rejected = rejected_matrix(full_dir, key, full_grid=False)
    nss_rejected = rejected_matrix(nss_dir, key, full_grid=True)
    matrices = {
        "base": base,
        "tedana_full": pd.concat((base, full_rejected), axis=1),
        "tedana_nss": pd.concat((base, nss_rejected), axis=1),
    }
    for label, frame in matrices.items():
        if len(frame) != total:
            raise ValueError(f"{key}: {label} rows differ from BOLD")
    motion = motion24(confounds)[nss:]
    fd = pd.to_numeric(confounds["framewise_displacement"], errors="coerce").to_numpy(dtype=float)[nss + 1 :]
    if not np.all(np.isfinite(fd)):
        raise ValueError(f"{key}: nonfinite steady-state FD")
    original = data[nss:]
    adjusted: dict[str, np.ndarray] = {}
    condition_metrics: dict[str, dict[str, float]] = {}
    ranks: dict[str, int] = {}
    run_rows: list[dict[str, Any]] = []
    common = {
        name: row[name] for name in ("subject", "session", "task", "run", "run_key", "software_versions", "nss_count", "number_of_original_volumes")
    }
    common.update({"software_era": software_era(row["software_versions"]), "n_valid_voxels": data.shape[1]})
    for condition in CONDITIONS:
        nuisance = finite_frame(matrices[condition])
        adjusted_full, rank = nuisance_adjust(data, nuisance)
        current = adjusted_full[nss:]
        current_metrics = metrics(original, current, fd, motion)
        adjusted[condition] = current
        condition_metrics[condition] = current_metrics
        ranks[condition] = rank
        run_rows.append(
            {
                **common, "condition": condition, "nuisance_columns": nuisance.shape[1],
                "nuisance_rank": rank, "incremental_rank_vs_base": rank - ranks["base"],
                "incremental_rank_fraction": (rank - ranks["base"]) / total,
                **current_metrics,
            }
        )
    if nss == 0 and not np.array_equal(adjusted["tedana_full"], adjusted["tedana_nss"]):
        raise ValueError(f"{key}: N=0 FULL/NSS audit residuals are not identical")
    pair_rows: list[dict[str, Any]] = []
    for reference, candidate in (("base", "tedana_full"), ("tedana_full", "tedana_nss")):
        pair_rows.append(
            {
                **{name: common[name] for name in ("subject", "session", "task", "run", "run_key", "software_era", "nss_count")},
                "comparison": f"{reference}_vs_{candidate}",
                **pair_metrics(
                    adjusted[reference], adjusted[candidate],
                    condition_metrics[reference], condition_metrics[candidate],
                ),
            }
        )
    return run_rows, pair_rows, required


def summaries(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        comparison = str(row["comparison"])
        groups[("all", "all", comparison)].append(row)
        groups[("software_era", str(row["software_era"]), comparison)].append(row)
        nss = int(row["nss_count"])
        group = "0" if nss == 0 else "1" if nss == 1 else "2" if nss == 2 else "3+"
        groups[("nss_count", group, comparison)].append(row)
    metrics_to_report = PAIR_COLUMNS[8:]
    output = []
    for (grouping, group, comparison), members in sorted(groups.items()):
        for metric in metrics_to_report:
            values = np.asarray([float(row[metric]) for row in members if math.isfinite(float(row[metric]))])
            if not len(values):
                continue
            output.append(
                {
                    "grouping": grouping, "group": group, "comparison": comparison,
                    "metric": metric, "n": len(values), "median": np.quantile(values, 0.5),
                    "q25": np.quantile(values, 0.25), "q75": np.quantile(values, 0.75),
                    "p90": np.quantile(values, 0.90), "p95": np.quantile(values, 0.95),
                }
            )
    return output


def plot_pairs(rows: Sequence[dict[str, Any]], path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    comparisons = sorted({row["comparison"] for row in rows})
    colors = {comparison: color for comparison, color in zip(comparisons, ("#0072B2", "#D55E00"))}
    for comparison in comparisons:
        group = [row for row in rows if row["comparison"] == comparison]
        color = colors[comparison]
        axes[0, 0].hist([row["candidate_minus_reference_standardized_dvars"] for row in group], bins=20, alpha=0.55, label=comparison, color=color)
        axes[0, 1].hist([row["candidate_minus_reference_fd_dvars_spearman"] for row in group], bins=20, alpha=0.55, label=comparison, color=color)
        axes[1, 0].hist([row["candidate_minus_reference_variance_removed_fraction"] for row in group], bins=20, alpha=0.55, label=comparison, color=color)
        axes[1, 1].hist([row["median_voxelwise_temporal_correlation"] for row in group], bins=20, alpha=0.55, label=comparison, color=color)
    labels = ("Change in standardized DVARS", "Change in FD-DVARS Spearman", "Change in variance removed", "Voxelwise temporal correlation")
    for axis, label in zip(axes.ravel(), labels):
        axis.set_xlabel(label); axis.set_ylabel("Runs"); axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    fig.tight_layout(); path.parent.mkdir(parents=True, exist_ok=True); fig.savefig(path, dpi=180); plt.close(fig)
    apply_umask_mode(path)


def make_report(run_rows: Sequence[dict[str, Any]], pair_rows: Sequence[dict[str, Any]], path: Path) -> None:
    n0 = [row for row in pair_rows if row["comparison"] == "tedana_full_vs_tedana_nss" and int(row["nss_count"]) == 0]
    lines = [
        "# TEDANA Nuisance-Model QC", "",
        "This audit compares nuisance spaces fitted to the same full-length canonical fMRIPrep BOLD. It does not residualize, replace, or create a production BOLD input. RF1 continues to fit task and nuisance EVs simultaneously in FEAT.", "",
        "## Coverage", "", f"- Sentinel runs: {len(run_rows) // 3}",
        f"- Condition/run rows: {len(run_rows)}", f"- Pair rows: {len(pair_rows)}",
        f"- N=0 FULL/NSS numerical identity checks: {len(n0)}", "",
        "## Conditions", "", "- BASE: selected fMRIPrep confounds.",
        "- TEDANA-FULL: BASE plus rejected ICs from the matched full-volume decomposition.",
        "- TEDANA-NSS: BASE plus rejected ICs from the NSS-aware decomposition, with exactly N leading zero rows.", "",
        "Metrics are evaluated on N:T. Nuisance columns are mean-centered before projection so the adjusted series retains its temporal mean and tSNR remains interpretable. A standardized-DVARS value above 1.5 is a descriptive high-DVARS frame, not an exclusion rule.", "",
        "## Interpretation Gate", "",
        "Use BASE-vs-FULL to estimate artifact-control benefit and FULL-vs-NSS to isolate NSS handling. Combine these results with incremental rank and actual task-design efficiency. No single QC metric authorizes a production change.",
    ]
    path.write_text("\n".join(lines) + "\n"); apply_umask_mode(path)


def install(stage: Path, output: Path) -> None:
    backup = output.with_name(f".{output.name}.backup")
    if backup.exists(): shutil.rmtree(backup)
    if output.exists(): output.rename(backup)
    try: stage.rename(output)
    except Exception:
        if backup.exists() and not output.exists(): backup.rename(output)
        raise
    if backup.exists(): shutil.rmtree(backup)


def build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    sentinel = read_tsv(args.sentinel_tsv)
    if args.dry_run:
        print(f"Would compare three nuisance conditions for {len(sentinel)} sentinel run(s).")
        print(f"Audit derivatives: {audit_root}"); print(f"Tracked output: {output}")
        print("Production derivatives will not be modified."); return 0
    if output.exists() and not args.overwrite:
        raise ValueError(f"output exists; review it or use --overwrite: {output}")
    all_runs: list[dict[str, Any]] = []; all_pairs: list[dict[str, Any]] = []
    inputs = [args.sentinel_tsv.resolve()]
    for index, row in enumerate(sentinel, start=1):
        run_rows, pair_rows, paths = audit_run(project, audit_root, row)
        all_runs.extend(run_rows); all_pairs.extend(pair_rows); inputs.extend(paths)
        print(f"Audited {index}/{len(sentinel)} {row['run_key']}", flush=True)
    summary = summaries(all_pairs)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tedana-nuisance-qc-", dir=output.parent) as temp:
        stage = Path(temp)
        write_tsv(stage / "run_metrics.tsv", all_runs, RUN_COLUMNS)
        write_tsv(stage / "paired_conditions.tsv", all_pairs, PAIR_COLUMNS)
        write_tsv(stage / "summary.tsv", summary, SUMMARY_COLUMNS)
        plot_pairs(all_pairs, stage / "figures" / "nuisance_qc.png")
        make_report(all_runs, all_pairs, stage / "report.md")
        provenance = {
            "schema_version": 1, "generated_at": utc_now(),
            "sentinel_tsv": args.sentinel_tsv.resolve().relative_to(project).as_posix(),
            "sentinel_sha256": sha256(args.sentinel_tsv), "sentinel_runs": len(sentinel),
            "input_inventory_digest_path_size_mtime": inventory_digest(inputs, project),
            "production_derivatives_modified": False,
            "production_bold_residualized": False,
            "task_and_nuisance_fit_simultaneously_in_production": True,
            "outputs": {},
        }
        for item in OUTPUTS:
            if item.name != "provenance.json": provenance["outputs"][item.as_posix()] = sha256(stage / item)
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        apply_umask_mode(stage / "provenance.json"); install(stage, output)
    print(f"Nuisance-QC runs: {len(sentinel)}"); print(f"Tracked report: {output / 'report.md'}")
    return 0


def check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    failures = []; provenance_path = output / "provenance.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    sentinel = read_tsv(args.sentinel_tsv)
    run_path = output / "run_metrics.tsv"; pair_path = output / "paired_conditions.tsv"
    if not provenance: failures.append("missing_provenance")
    if not run_path.is_file() or len(read_tsv(run_path)) != 3 * len(sentinel): failures.append("run_coverage")
    if not pair_path.is_file() or len(read_tsv(pair_path)) != 2 * len(sentinel): failures.append("pair_coverage")
    for item in OUTPUTS:
        path = output / item
        if not path.is_file(): failures.append(f"missing:{path}")
        elif item.name != "provenance.json" and provenance.get("outputs", {}).get(item.as_posix()) != sha256(path): failures.append(f"checksum:{path}")
    if provenance.get("sentinel_sha256") != sha256(args.sentinel_tsv): failures.append("sentinel_checksum")
    for failure in failures: print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: {len(failures)} nuisance-QC issue(s)."); return 1
    print(f"CHECK PASSED: TEDANA nuisance-model QC validated for {len(sentinel)} run(s)."); return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description=__doc__)
    children = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = children.add_parser(name)
        child.add_argument("--project-root", type=Path, default=project)
        child.add_argument("--sentinel-tsv", type=Path, default=project / "qc" / "tedana_audit" / "sentinel_runs.tsv")
        child.add_argument("--audit-root", type=Path, default=project / "derivatives" / "tedana-audit")
        child.add_argument("--output-dir", type=Path, default=project / "qc" / "tedana_audit" / "nuisance_qc")
    children.choices["build"].add_argument("--overwrite", action="store_true")
    children.choices["build"].add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try: return build(args) if args.command == "build" else check(args)
    except Exception as exc:
        print(f"ERROR: {exc}"); return 1


if __name__ == "__main__":
    raise SystemExit(main())
