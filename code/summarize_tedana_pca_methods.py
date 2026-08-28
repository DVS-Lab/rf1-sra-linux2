#!/usr/bin/env python3
"""Summarize matched AIC, KIC, and MDL TEDANA benchmark outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from audit_tedana import motion24
from audit_tedana_design import (
    matrix_diagnostics,
    parse_mapca,
    rejected_component_columns,
    selected_base_confounds,
)
from pipeline_utils import apply_umask_mode, ensure_safe_child_path
from summarize_tedana_benchmark import (
    ICA_METRICS,
    _correlation,
    _denoising_metrics,
    _image,
    _matching_geometry,
    _review_row,
    _temporal_correlations,
    component_summary,
    install_directory,
)


METHODS = {
    "aic": "nss-fastica",
    "kic": "nss-kic-fastica",
    "mdl": "nss-mdl-fastica",
}

IDENTITY_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "software_versions",
    "nss_count",
    "number_of_original_volumes",
    "number_of_steady_state_volumes",
    "selection_reason",
)

METHOD_COLUMNS = (
    *IDENTITY_COLUMNS,
    "criterion",
    "configuration",
    "pca_components",
    *ICA_METRICS,
    "combined_confound_columns",
    "combined_confound_rank",
    "combined_rank_with_intercept",
    "combined_rank_fraction",
    "residual_df_before_task",
    "zero_columns",
    "duplicate_columns",
    "standardized_condition_number",
    "median_optcom_tsnr",
    "median_denoised_tsnr",
    "median_tsnr_change",
    "median_variance_removed_fraction",
    "median_signal_percent_change",
    "optcom_median_dvars",
    "denoised_median_dvars",
    "dvars_percent_change",
    "fd_denoised_dvars_spearman",
    "motion24_global_signal_r_squared",
)

PAIR_METRICS = (
    "pca_components",
    "n_ica",
    "n_accepted",
    "n_rejected",
    "rejected_fraction",
    "rejected_normalized_variance",
    "combined_rank_with_intercept",
    "combined_rank_fraction",
    "residual_df_before_task",
    "median_denoised_tsnr",
    "median_variance_removed_fraction",
    "median_signal_percent_change",
    "denoised_median_dvars",
    "fd_denoised_dvars_spearman",
    "motion24_global_signal_r_squared",
)

PAIR_COLUMNS = (
    *IDENTITY_COLUMNS,
    "candidate_criterion",
    *(f"aic_{name}" for name in PAIR_METRICS),
    *(f"candidate_{name}" for name in PAIR_METRICS),
    *(f"candidate_minus_aic_{name}" for name in PAIR_METRICS),
    "candidate_minus_aic_denoised_tsnr_percent",
    "candidate_minus_aic_denoised_dvars_percent",
    "aic_candidate_median_voxelwise_temporal_correlation",
    "aic_candidate_median_volume_spatial_correlation",
    "aic_candidate_normalized_rmse",
    "review_reasons",
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
    Path("method_runs.tsv"),
    Path("paired_methods.tsv"),
    Path("review_manifest.tsv"),
    Path("figures/pca_method_comparison.png"),
    Path("report.md"),
    Path("provenance.json"),
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
    for path in sorted(set(item.resolve() for item in paths)):
        stat = path.stat()
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, delimiter="\t", extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    apply_umask_mode(path)


def number(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"nonfinite numeric value: {value}")
    return result


def summary(values: Sequence[Any], digits: int = 3) -> str:
    clean = np.asarray([number(value) for value in values], dtype=float)
    q1, median, q3 = np.quantile(clean, (0.25, 0.5, 0.75))
    return f"{median:.{digits}f} (IQR {q1:.{digits}f} to {q3:.{digits}f})"


def required_paths(
    project: Path, audit_root: Path, row: dict[str, str]
) -> list[Path]:
    key = row["run_key"]
    paths = [project / row["fmriprep_mask"], project / row["fmriprep_confounds"]]
    for config in METHODS.values():
        directory = audit_root / "benchmark" / config / key
        paths.extend(
            (
                directory / f"{key}_desc-tedana_metrics.tsv",
                directory / f"{key}_desc-ICA_mixingFullGrid.tsv",
                directory / f"{key}_desc-PCA_metrics.tsv",
                directory / f"{key}_desc-PCACrossComponent_metrics.json",
                directory / f"{key}_desc-optcom_bold.nii.gz",
                directory / f"{key}_desc-denoised_bold.nii.gz",
            )
        )
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"{key}: missing benchmark input: {missing[0]}")
    return paths


def _method_identity(row: dict[str, str]) -> dict[str, Any]:
    return {
        name: row.get(name, "")
        for name in IDENTITY_COLUMNS
    }


def _config_stats(
    project: Path,
    audit_root: Path,
    row: dict[str, str],
    criterion: str,
    base: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    key = row["run_key"]
    config = METHODS[criterion]
    directory = audit_root / "benchmark" / config / key
    metrics_path = directory / f"{key}_desc-tedana_metrics.tsv"
    mixing_path = directory / f"{key}_desc-ICA_mixingFullGrid.tsv"
    pca_path = directory / f"{key}_desc-PCA_metrics.tsv"
    cross_path = directory / f"{key}_desc-PCACrossComponent_metrics.json"
    component, frame = component_summary(metrics_path)
    mixing = pd.read_csv(mixing_path, sep="\t")
    pca = pd.read_csv(pca_path, sep="\t")
    if len(mixing) != int(row["number_of_original_volumes"]):
        raise ValueError(f"{key} {criterion}: full-grid mixing row mismatch")
    if mixing.shape[1] != len(frame):
        raise ValueError(f"{key} {criterion}: metrics/mixing component mismatch")
    mapca = parse_mapca(cross_path)
    selected = int(mapca[f"{criterion}_components"])
    if len(pca) != selected or component["n_ica"] != selected:
        raise ValueError(
            f"{key} {criterion}: selected PCA/ICA count mismatch "
            f"({selected}, {len(pca)}, {component['n_ica']})"
        )
    rejected = mixing.iloc[:, rejected_component_columns(frame)]
    combined = pd.concat((base.reset_index(drop=True), rejected.reset_index(drop=True)), axis=1)
    diagnostics = matrix_diagnostics(combined)
    nvolumes = int(row["number_of_original_volumes"])
    output = {
        **_method_identity(row),
        "criterion": criterion,
        "configuration": config,
        "pca_components": selected,
        **component,
        "combined_confound_columns": diagnostics["columns"],
        "combined_confound_rank": diagnostics["rank"],
        "combined_rank_with_intercept": diagnostics["rank_with_intercept"],
        "combined_rank_fraction": diagnostics["rank_with_intercept"] / nvolumes,
        "residual_df_before_task": nvolumes - diagnostics["rank_with_intercept"],
        "zero_columns": diagnostics["zero_columns"],
        "duplicate_columns": diagnostics["duplicate_columns"],
        "standardized_condition_number": diagnostics["standardized_condition_number"],
    }
    return output, frame


def _load_denoising(
    project: Path,
    audit_root: Path,
    row: dict[str, str],
    criterion: str,
    mask_image: Any,
    mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    key = row["run_key"]
    directory = audit_root / "benchmark" / METHODS[criterion] / key
    optcom_image = _image(directory / f"{key}_desc-optcom_bold.nii.gz", 4)
    denoised_image = _image(directory / f"{key}_desc-denoised_bold.nii.gz", 4)
    _matching_geometry(optcom_image, denoised_image)
    expected = int(row["number_of_original_volumes"]) - int(row["nss_count"])
    if optcom_image.shape[:3] != mask.shape or not np.allclose(
        optcom_image.affine, mask_image.affine, atol=1e-5
    ):
        raise ValueError(f"{key} {criterion}: mask geometry mismatch")
    if optcom_image.shape[3] != expected:
        raise ValueError(f"{key} {criterion}: steady-state volume mismatch")
    return (
        np.asarray(optcom_image.dataobj, dtype=np.float32)[mask],
        np.asarray(denoised_image.dataobj, dtype=np.float32)[mask],
    )


def _pair_similarity(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    temporal = _temporal_correlations(reference, candidate)
    spatial = np.asarray(
        [_correlation(reference[:, index], candidate[:, index]) for index in range(reference.shape[1])]
    )
    rmse = float(np.sqrt(np.mean((candidate - reference) ** 2)))
    reference_rms = float(np.sqrt(np.mean(reference**2)))
    return {
        "aic_candidate_median_voxelwise_temporal_correlation": float(np.nanmedian(temporal)),
        "aic_candidate_median_volume_spatial_correlation": float(np.nanmedian(spatial)),
        "aic_candidate_normalized_rmse": rmse / reference_rms if reference_rms else math.nan,
    }


def summarize_run(
    project: Path, audit_root: Path, row: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    base = selected_base_confounds(project / row["fmriprep_confounds"])
    mask_image = _image(project / row["fmriprep_mask"], 3)
    mask = np.asarray(mask_image.dataobj) > 0
    stats: dict[str, dict[str, Any]] = {}
    frames: dict[str, pd.DataFrame] = {}
    arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for criterion in METHODS:
        stats[criterion], frames[criterion] = _config_stats(
            project, audit_root, row, criterion, base
        )
        arrays[criterion] = _load_denoising(
            project, audit_root, row, criterion, mask_image, mask
        )
    finite = np.logical_and.reduce(
        [np.all(array, axis=1) for pair in arrays.values() for array in pair]
    )
    if not np.any(finite):
        raise ValueError(f"{row['run_key']}: no common finite denoising voxels")
    reference_optcom = arrays["aic"][0][finite].astype(np.float64)
    for criterion in ("kic", "mdl"):
        candidate_optcom = arrays[criterion][0][finite].astype(np.float64)
        if not np.array_equal(reference_optcom, candidate_optcom):
            raise ValueError(f"{row['run_key']}: optcom differs across PCA criteria")
    nss = int(row["nss_count"])
    confounds = pd.read_csv(project / row["fmriprep_confounds"], sep="\t")
    motion = motion24(confounds)[nss:]
    fd = pd.to_numeric(confounds["framewise_displacement"], errors="coerce").to_numpy(
        dtype=float
    )[nss + 1 :]
    expected = int(row["number_of_steady_state_volumes"])
    if len(motion) != expected or len(fd) != expected - 1 or not np.all(np.isfinite(fd)):
        raise ValueError(f"{row['run_key']}: invalid denoising confounds")
    for criterion in METHODS:
        optcom, denoised = (
            array[finite].astype(np.float64) for array in arrays[criterion]
        )
        stats[criterion].update(_denoising_metrics(optcom, denoised, fd, motion))
    pairs: list[dict[str, Any]] = []
    aic = stats["aic"]
    aic_denoised = arrays["aic"][1][finite].astype(np.float64)
    for criterion in ("kic", "mdl"):
        candidate = stats[criterion]
        output: dict[str, Any] = {
            **_method_identity(row),
            "candidate_criterion": criterion,
        }
        for metric in PAIR_METRICS:
            output[f"aic_{metric}"] = aic[metric]
            output[f"candidate_{metric}"] = candidate[metric]
            output[f"candidate_minus_aic_{metric}"] = candidate[metric] - aic[metric]
        for metric, label in (
            ("median_denoised_tsnr", "denoised_tsnr"),
            ("denoised_median_dvars", "denoised_dvars"),
        ):
            denominator = aic[metric]
            output[f"candidate_minus_aic_{label}_percent"] = (
                100 * (candidate[metric] - denominator) / denominator if denominator else 0.0
            )
        output.update(
            _pair_similarity(
                aic_denoised,
                arrays[criterion][1][finite].astype(np.float64),
            )
        )
        reasons = []
        if abs(output["candidate_minus_aic_pca_components"]) >= 10:
            reasons.append("pca_count_change_gte_10")
        if abs(output["candidate_minus_aic_n_rejected"]) >= 10:
            reasons.append("rejected_count_change_gte_10")
        if abs(output["candidate_minus_aic_combined_rank_with_intercept"]) >= 10:
            reasons.append("design_rank_change_gte_10")
        if output["aic_candidate_median_voxelwise_temporal_correlation"] < 0.95:
            reasons.append("denoised_temporal_correlation_lt_0_95")
        if abs(output["candidate_minus_aic_denoised_dvars_percent"]) >= 5:
            reasons.append("denoised_dvars_change_gte_5_percent")
        output["review_reasons"] = ";".join(reasons)
        pairs.append(output)
    review: list[dict[str, Any]] = []
    for criterion, config in METHODS.items():
        candidate = _review_row(
            project,
            audit_root,
            row,
            config,
            frames[criterion],
            f"largest_rejected_variance_{criterion}",
            accepted=False,
        )
        if candidate:
            review.append(candidate)
    return list(stats.values()), pairs, review


def plot_outputs(method_rows: Sequence[dict[str, Any]], pair_rows: Sequence[dict[str, Any]], path: Path) -> None:
    from matplotlib import pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    pairs = {criterion: [row for row in pair_rows if row["candidate_criterion"] == criterion] for criterion in ("kic", "mdl")}
    colors = {"kic": "#0072B2", "mdl": "#D55E00"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    scatter_metrics = (
        ("pca_components", "PCA components"),
        ("n_rejected", "Rejected components"),
        ("combined_rank_fraction", "Nuisance rank / volumes"),
        ("residual_df_before_task", "Residual df before task"),
    )
    for ax, (metric, label) in zip(axes.ravel()[:4], scatter_metrics):
        values = []
        for criterion in ("kic", "mdl"):
            x = [number(row[f"aic_{metric}"]) for row in pairs[criterion]]
            y = [number(row[f"candidate_{metric}"]) for row in pairs[criterion]]
            values.extend(x + y)
            ax.scatter(x, y, alpha=0.75, label=criterion.upper(), color=colors[criterion])
        low, high = min(values), max(values)
        ax.plot((low, high), (low, high), color="black", linewidth=1)
        ax.set(xlabel=f"AIC {label}", ylabel=f"Candidate {label}")
        ax.legend()
    ax = axes.ravel()[4]
    for criterion in ("kic", "mdl"):
        ax.scatter(
            [number(row["aic_median_denoised_tsnr"]) for row in pairs[criterion]],
            [number(row["candidate_median_denoised_tsnr"]) for row in pairs[criterion]],
            alpha=0.75,
            label=criterion.upper(),
            color=colors[criterion],
        )
    values = [number(row["median_denoised_tsnr"]) for row in method_rows]
    ax.plot((min(values), max(values)), (min(values), max(values)), color="black", linewidth=1)
    ax.set(xlabel="AIC median denoised tSNR", ylabel="Candidate median denoised tSNR")
    ax.legend()
    ax = axes.ravel()[5]
    ax.boxplot(
        [
            [number(row["aic_candidate_median_voxelwise_temporal_correlation"]) for row in pairs[criterion]]
            for criterion in ("kic", "mdl")
        ],
        tick_labels=("KIC", "MDL"),
    )
    ax.set_ylabel("AIC/candidate voxelwise temporal correlation")
    fig.suptitle("Matched TEDANA PCA-criterion sensitivity", fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)
    apply_umask_mode(path)


def make_report(method_rows: Sequence[dict[str, Any]], pair_rows: Sequence[dict[str, Any]], path: Path) -> None:
    by_method = {criterion: [row for row in method_rows if row["criterion"] == criterion] for criterion in METHODS}
    by_pair = {criterion: [row for row in pair_rows if row["candidate_criterion"] == criterion] for criterion in ("kic", "mdl")}
    lines = [
        "# TEDANA PCA-Method Sensitivity Report",
        "",
        "This is an audit-only matched comparison. It does not modify production TEDANA or authorize a method change.",
        "",
        "## Coverage",
        "",
        f"- Target runs: {len(by_method['aic'])}",
        f"- Validated method/run outputs: {len(method_rows)}",
        "- Methods: NSS-aware FastICA with AIC, KIC, and MDL; all other explicit settings are identical.",
        "- Optimally combined inputs were required to be exactly identical across criteria.",
        "",
        "## Model Order And Design Cost",
        "",
    ]
    for criterion in ("kic", "mdl"):
        rows = by_pair[criterion]
        lines.extend(
            (
                f"### {criterion.upper()} minus AIC",
                "",
                f"- PCA components: {summary([row['candidate_minus_aic_pca_components'] for row in rows])}",
                f"- Rejected components: {summary([row['candidate_minus_aic_n_rejected'] for row in rows])}",
                f"- Nuisance rank with intercept: {summary([row['candidate_minus_aic_combined_rank_with_intercept'] for row in rows])}",
                f"- Residual df before task regressors: {summary([row['candidate_minus_aic_residual_df_before_task'] for row in rows])}",
                "",
            )
        )
    lines.extend(("## Denoising Proxies", ""))
    for criterion in ("kic", "mdl"):
        rows = by_pair[criterion]
        lines.extend(
            (
                f"### {criterion.upper()} versus AIC",
                "",
                f"- Denoised tSNR change (%): {summary([row['candidate_minus_aic_denoised_tsnr_percent'] for row in rows])}",
                f"- Denoised DVARS change (%): {summary([row['candidate_minus_aic_denoised_dvars_percent'] for row in rows])}",
                f"- Variance-removed fraction change: {summary([row['candidate_minus_aic_median_variance_removed_fraction'] for row in rows])}",
                f"- FD-versus-denoised-DVARS Spearman change: {summary([row['candidate_minus_aic_fd_denoised_dvars_spearman'] for row in rows])}",
                f"- AIC/candidate voxelwise temporal correlation: {summary([row['aic_candidate_median_voxelwise_temporal_correlation'] for row in rows], 6)}",
                f"- AIC/candidate normalized RMSE: {summary([row['aic_candidate_normalized_rmse'] for row in rows], 6)}",
                "",
            )
        )
    lines.extend(
        (
            "## Interpretation Boundary",
            "",
            "There is no gold-standard clean fMRI series. Higher tSNR and lower DVARS may reflect artifact attenuation, but can also accompany removal of neural signal. Lower nuisance rank preserves degrees of freedom, but underestimating model order can merge signal and noise sources. Selection therefore requires convergent evidence: reasonable dimensionality, reduced motion coupling, preserved signal scale, acceptable image similarity, and targeted component review.",
            "",
            "The TEDANA documentation identifies AIC as least aggressive, KIC as intermediate, and MDL as most aggressive, and recommends considering KIC/MDL when AIC retains more than half the time points or explains over 98% of variance. Li et al. (2007) showed that overestimated ICA order reduces component stability and can degrade task activation estimates; underestimation can merge distinct sources. ME-ICA validation supports TE-dependence as a physically motivated classifier, but does not make any PCA criterion a universal ground truth.",
            "",
            "## Decision Gate",
            "",
            "Do not choose a criterion from tSNR or component count alone. Review `paired_methods.tsv`, the largest rejected components in `review_manifest.tsv`, and task-model safety checks before changing production. A cohort-wide change should use one prespecified rule rather than choosing a different criterion after inspecting each run.",
            "",
            "## Primary References",
            "",
            "- [TEDANA denoising approach and PCA criteria](https://tedana.readthedocs.io/en/26.0.3/approach.html)",
            "- [Li, Adalı, and Calhoun (2007), model-order estimation](https://doi.org/10.1002/hbm.20359)",
            "- [Kundu et al. (2013), integrated multi-echo denoising](https://doi.org/10.1073/pnas.1301725110)",
            "- [Gonzalez-Castillo et al. (2016), task ME-ICA evaluation](https://doi.org/10.1016/j.neuroimage.2016.07.039)",
            "- [Ciric et al. (2017), denoising benchmarks and degrees-of-freedom trade-offs](https://doi.org/10.1016/j.neuroimage.2017.03.020)",
            "",
        )
    )
    path.write_text("\n".join(lines))
    apply_umask_mode(path)


def run_build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    rows = read_tsv(args.target_tsv)
    if not rows:
        raise ValueError("target manifest is empty")
    if args.dry_run:
        print(f"Would summarize {len(rows)} targeted run(s) across AIC, KIC, and MDL.")
        print(f"Tracked output: {output}")
        return 0
    if output.exists() and not args.overwrite:
        raise ValueError(f"output exists; add --overwrite after review: {output}")
    method_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    inputs: list[Path] = [args.target_tsv.resolve()]
    for index, row in enumerate(rows, start=1):
        inputs.extend(required_paths(project, audit_root, row))
        methods, pairs, review = summarize_run(project, audit_root, row)
        method_rows.extend(methods)
        pair_rows.extend(pairs)
        review_rows.extend(review)
        print(f"Summarized {index}/{len(rows)} {row['run_key']}")
    with tempfile.TemporaryDirectory(prefix="tedana-pca-methods-", dir=output.parent) as temporary:
        stage = Path(temporary)
        write_tsv(stage / "method_runs.tsv", method_rows, METHOD_COLUMNS)
        write_tsv(stage / "paired_methods.tsv", pair_rows, PAIR_COLUMNS)
        write_tsv(stage / "review_manifest.tsv", review_rows, REVIEW_COLUMNS)
        plot_outputs(method_rows, pair_rows, stage / "figures" / "pca_method_comparison.png")
        make_report(method_rows, pair_rows, stage / "report.md")
        provenance = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "target_manifest": args.target_tsv.resolve().relative_to(project).as_posix(),
            "target_manifest_sha256": sha256(args.target_tsv),
            "target_run_count": len(rows),
            "methods": METHODS,
            "input_inventory_digest_path_size_mtime": inventory_digest(inputs, project),
            "production_derivatives_modified": False,
            "task_regressors_used": False,
            "gold_standard_claimed": False,
            "outputs": {},
        }
        for relative in OUTPUTS:
            if relative.name != "provenance.json":
                provenance["outputs"][relative.as_posix()] = sha256(stage / relative)
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        apply_umask_mode(stage / "provenance.json")
        install_directory(stage, output)
    print(f"Method/run rows: {len(method_rows)}")
    print(f"Paired comparison rows: {len(pair_rows)}")
    print(f"Component review rows: {len(review_rows)}")
    print(f"Tracked report: {output / 'report.md'}")
    return 0


def run_check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    failures: list[str] = []
    provenance_path = output / "provenance.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    if not provenance:
        failures.append(f"missing:{provenance_path}")
    targets = read_tsv(args.target_tsv)
    expected_keys = {row["run_key"] for row in targets}
    tables = {
        "method_runs.tsv": (len(targets) * len(METHODS), METHOD_COLUMNS),
        "paired_methods.tsv": (len(targets) * 2, PAIR_COLUMNS),
        "review_manifest.tsv": (None, REVIEW_COLUMNS),
    }
    for name, (expected_count, columns) in tables.items():
        path = output / name
        if not path.is_file():
            failures.append(f"missing:{path}")
            continue
        rows = read_tsv(path)
        if expected_count is not None and len(rows) != expected_count:
            failures.append(f"row_count:{name}:{len(rows)}!={expected_count}")
        if rows and tuple(rows[0]) != tuple(columns):
            failures.append(f"columns:{name}")
        if any(row.get("run_key") not in expected_keys for row in rows):
            failures.append(f"run_key:{name}")
    method_path = output / "method_runs.tsv"
    if method_path.is_file():
        method_rows = read_tsv(method_path)
        observed = {(row["run_key"], row["criterion"]) for row in method_rows}
        expected = {(key, criterion) for key in expected_keys for criterion in METHODS}
        if observed != expected:
            failures.append("method_coverage")
    for relative in OUTPUTS:
        path = output / relative
        if not path.is_file():
            failures.append(f"missing:{path}")
        elif relative.name != "provenance.json" and provenance.get("outputs", {}).get(relative.as_posix()) != sha256(path):
            failures.append(f"checksum:{path}")
    if provenance.get("target_manifest_sha256") != sha256(args.target_tsv):
        failures.append("target_manifest_checksum")
    try:
        inputs: list[Path] = [args.target_tsv.resolve()]
        for row in targets:
            inputs.extend(required_paths(project, audit_root, row))
        if provenance.get("input_inventory_digest_path_size_mtime") != inventory_digest(inputs, project):
            failures.append("benchmark_input_inventory")
    except (OSError, ValueError) as exc:
        failures.append(f"benchmark_inputs:{exc}")
    for failure in failures:
        print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: {len(failures)} PCA-method summary issue(s).")
        return 1
    print(f"CHECK PASSED: AIC/KIC/MDL sensitivity validated for {len(targets)} run(s).")
    return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-root", type=Path, default=project)
        child.add_argument(
            "--target-tsv",
            type=Path,
            default=project / "qc" / "tedana_audit" / "design" / "pca_method_benchmark.tsv",
        )
        child.add_argument(
            "--audit-root", type=Path, default=project / "derivatives" / "tedana-audit"
        )
        child.add_argument(
            "--output-dir", type=Path, default=project / "qc" / "tedana_audit" / "pca_methods"
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
