#!/usr/bin/env python3
"""Audit TEDANA PCA dimensionality and downstream nuisance-design burden."""

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
import numpy as np
import pandas as pd

from genTedanaConfounds import (
    DESIRED_FMRIPREP_COLUMNS,
    build_confounds,
    rejected_component_columns,
)
from pipeline_utils import apply_umask_mode, ensure_safe_child_path


RUN_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "audit_status",
    "design_status",
    "design_issues",
    "software_versions",
    "number_of_original_volumes",
    "nss_count",
    "number_of_steady_state_volumes",
    "pca_selected_components",
    "ica_components",
    "accepted_components",
    "rejected_components",
    "aic_components",
    "kic_components",
    "mdl_components",
    "varex_90_components",
    "varex_95_components",
    "aic_explained_variance",
    "kic_explained_variance",
    "mdl_explained_variance",
    "pca_components_per_steady_state_volume",
    "rejected_components_per_steady_state_volume",
    "base_confound_columns",
    "base_confound_rank",
    "rejected_ica_columns",
    "rejected_ica_rank",
    "combined_confound_columns",
    "combined_confound_rank",
    "combined_rank_with_intercept",
    "combined_columns_per_volume",
    "combined_rank_per_volume",
    "residual_df_before_task",
    "zero_columns",
    "constant_nonzero_columns",
    "duplicate_columns",
    "standardized_condition_number",
    "existing_combined_present",
    "existing_combined_rows",
    "existing_combined_columns",
    "existing_combined_matches_reconstruction",
    "flag_pca_more_than_half_timepoints",
    "flag_aic_explains_more_than_98_percent",
    "flag_rejected_components_gte_75",
    "flag_combined_rank_fraction_gte_0_30",
    "flag_residual_df_lt_100",
    "review_reasons",
    "fmriprep_confounds",
    "tedana_metrics",
    "tedana_mixing",
    "tedana_pca_metrics",
    "tedana_pca_cross_component_metrics",
    "combined_confounds",
)

SUMMARY_COLUMNS = (
    "software_versions",
    "n_runs",
    "n_complete",
    "median_pca_components",
    "p95_pca_components",
    "median_rejected_components",
    "p95_rejected_components",
    "median_combined_rank_fraction",
    "p95_combined_rank_fraction",
    "median_residual_df_before_task",
    "n_pca_more_than_half_timepoints",
    "n_aic_explains_more_than_98_percent",
    "n_rejected_components_gte_75",
    "n_combined_rank_fraction_gte_0_30",
    "n_residual_df_lt_100",
)

OUTPUTS = (
    Path("cohort_design_burden.tsv"),
    Path("summary_by_scanner.tsv"),
    Path("review_runs.tsv"),
    Path("pca_method_benchmark.tsv"),
    Path("figures/design_burden.png"),
    Path("report.md"),
    Path("provenance.json"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory_digest(paths: Sequence[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(path.resolve() for path in paths)):
        stat = path.stat()
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(f"\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def boolean(value: bool) -> int:
    return int(bool(value))


def pca_cross_path(pca_metrics: Path, run_key: str) -> Path:
    return pca_metrics.with_name(f"{run_key}_desc-PCACrossComponent_metrics.json")


def parse_mapca(path: Path) -> dict[str, float | int]:
    payload = json.loads(path.read_text())
    result: dict[str, float | int] = {}
    for name in ("aic", "kic", "mdl", "varex_90", "varex_95"):
        entry = payload.get(name)
        if not isinstance(entry, dict):
            raise ValueError(f"missing {name} MAPCA result")
        count = int(entry["n_components"])
        if count < 1:
            raise ValueError(f"invalid {name} component count: {count}")
        result[f"{name}_components"] = count
        variance = finite(entry.get("explained_variance_total"))
        if variance is not None:
            result[f"{name}_explained_variance"] = variance
    return result


def selected_base_confounds(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep="\t")
    columns = [column for column in DESIRED_FMRIPREP_COLUMNS if column in frame]
    columns.extend(column for column in frame if column.startswith("cosine"))
    columns.extend(column for column in frame if column.startswith("non_steady_state"))
    return frame[columns].apply(pd.to_numeric, errors="coerce").fillna(0)


def matrix_diagnostics(frame: pd.DataFrame) -> dict[str, Any]:
    values = frame.to_numpy(dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2:
        raise ValueError(f"invalid confound shape: {values.shape}")
    if not np.all(np.isfinite(values)):
        raise ValueError("nonfinite confound value")
    rank = int(np.linalg.matrix_rank(values))
    rank_intercept = int(
        np.linalg.matrix_rank(np.column_stack((np.ones(len(values)), values)))
    )
    ranges = np.ptp(values, axis=0)
    zero = [str(frame.columns[index]) for index in np.flatnonzero(np.all(values == 0, axis=0))]
    constant = [
        str(frame.columns[index])
        for index in np.flatnonzero(ranges == 0)
        if str(frame.columns[index]) not in zero
    ]
    signatures: dict[bytes, list[str]] = defaultdict(list)
    for index, column in enumerate(frame.columns):
        canonical = np.ascontiguousarray(values[:, index]).copy()
        canonical[canonical == 0] = 0
        signatures[canonical.tobytes()].append(str(column))
    duplicate_groups = [names for names in signatures.values() if len(names) > 1]
    duplicate = sum(len(group) - 1 for group in duplicate_groups)
    varying = values[:, ranges > 0]
    condition = math.nan
    if varying.shape[1]:
        varying = varying - np.mean(varying, axis=0, keepdims=True)
        norms = np.linalg.norm(varying, axis=0)
        varying = varying[:, norms > 0] / norms[norms > 0]
        if varying.shape[1]:
            singular = np.linalg.svd(varying, compute_uv=False)
            tolerance = max(varying.shape) * np.finfo(float).eps * singular[0]
            positive = singular[singular > tolerance]
            condition = float(positive[0] / positive[-1]) if len(positive) else math.inf
            if len(positive) < varying.shape[1]:
                condition = math.inf
    return {
        "columns": int(values.shape[1]),
        "rank": rank,
        "rank_with_intercept": rank_intercept,
        "zero_columns": len(zero),
        "constant_nonzero_columns": len(constant),
        "duplicate_columns": duplicate,
        "standardized_condition_number": condition,
    }


def combined_path(root: Path, row: dict[str, str]) -> Path:
    return (
        root
        / f"sub-{row['subject']}"
        / f"{row['run_key']}_desc-TedanaPlusConfounds.tsv"
    )


def incomplete_row(row: dict[str, str], issue: str) -> dict[str, Any]:
    output = {column: "" for column in RUN_COLUMNS}
    output.update(
        {
            "subject": row.get("subject", ""),
            "session": row.get("session", ""),
            "task": row.get("task", ""),
            "run": row.get("run", ""),
            "run_key": row.get("run_key", ""),
            "audit_status": row.get("audit_status", ""),
            "design_status": "incomplete",
            "design_issues": issue,
            "software_versions": row.get("software_versions", ""),
            "number_of_original_volumes": row.get("number_of_original_volumes", ""),
            "nss_count": row.get("nss_count", ""),
            "number_of_steady_state_volumes": row.get(
                "number_of_steady_state_volumes", ""
            ),
            "fmriprep_confounds": row.get("fmriprep_confounds", ""),
            "tedana_metrics": row.get("tedana_metrics", ""),
            "tedana_mixing": row.get("tedana_mixing", ""),
            "tedana_pca_metrics": row.get("tedana_pca_metrics", ""),
        }
    )
    return output


def audit_run(
    project: Path,
    confounds_root: Path,
    row: dict[str, str],
) -> tuple[dict[str, Any], list[Path]]:
    if row.get("audit_status") != "complete":
        return incomplete_row(row, f"upstream_audit:{row.get('audit_issues', '')}"), []
    required_fields = (
        "fmriprep_confounds",
        "tedana_metrics",
        "tedana_mixing",
        "tedana_pca_metrics",
    )
    paths = {name: project / row.get(name, "") for name in required_fields}
    missing = [name for name, path in paths.items() if not row.get(name) or not path.is_file()]
    if missing:
        return incomplete_row(row, f"missing:{','.join(missing)}"), []
    pca_cross = pca_cross_path(paths["tedana_pca_metrics"], row["run_key"])
    if not pca_cross.is_file():
        return incomplete_row(row, "missing:tedana_pca_cross_component_metrics"), []
    inputs = [*paths.values(), pca_cross]
    try:
        metrics = pd.read_csv(paths["tedana_metrics"], sep="\t")
        mixing = pd.read_csv(paths["tedana_mixing"], sep="\t")
        pca = pd.read_csv(paths["tedana_pca_metrics"], sep="\t")
        classifications = metrics["classification"].astype(str).str.lower()
        if not classifications.isin(("accepted", "rejected")).all():
            raise ValueError("invalid TEDANA classification")
        rejected_indices = rejected_component_columns(metrics)
        if mixing.shape[1] != len(metrics):
            raise ValueError("ICA metrics/mixing component mismatch")
        if len(mixing) != int(row["number_of_original_volumes"]):
            raise ValueError("ICA mixing/original-volume mismatch")
        base = selected_base_confounds(paths["fmriprep_confounds"])
        combined = build_confounds(
            paths["fmriprep_confounds"], paths["tedana_mixing"], paths["tedana_metrics"]
        )
        rejected = mixing.iloc[:, rejected_indices]
        base_diag = matrix_diagnostics(base)
        rejected_diag = matrix_diagnostics(rejected) if rejected.shape[1] else {
            "columns": 0,
            "rank": 0,
        }
        combined_diag = matrix_diagnostics(combined)
        mapca = parse_mapca(pca_cross)
        nvolumes = int(row["number_of_original_volumes"])
        steady = int(row["number_of_steady_state_volumes"])
        n_pca = len(pca)
        n_ica = len(metrics)
        n_rejected = len(rejected_indices)
        existing = combined_path(confounds_root, row)
        existing_rows = existing_columns = ""
        existing_match: int | str = ""
        if existing.is_file():
            inputs.append(existing)
            existing_frame = pd.read_csv(existing, sep="\t", header=None)
            existing_rows, existing_columns = existing_frame.shape
            existing_match = boolean(
                existing_frame.shape == combined.shape
                and np.allclose(
                    existing_frame.to_numpy(dtype=float),
                    combined.to_numpy(dtype=float),
                    rtol=1e-9,
                    atol=1e-12,
                )
            )
        flags = {
            "pca_more_than_half_timepoints": n_pca > steady / 2,
            "aic_explains_more_than_98_percent": finite(
                mapca.get("aic_explained_variance")
            )
            is not None
            and float(mapca["aic_explained_variance"]) > 0.98,
            "rejected_components_gte_75": n_rejected >= 75,
            "combined_rank_fraction_gte_0_30": (
                combined_diag["rank_with_intercept"] / nvolumes >= 0.30
            ),
            "residual_df_lt_100": nvolumes - combined_diag["rank_with_intercept"] < 100,
        }
        reasons = [name for name, value in flags.items() if value]
        if existing.is_file() and not existing_match:
            reasons.append("existing_combined_differs_from_reconstruction")
        output: dict[str, Any] = {
            "subject": row["subject"],
            "session": row["session"],
            "task": row["task"],
            "run": row["run"],
            "run_key": row["run_key"],
            "audit_status": row["audit_status"],
            "design_status": "complete",
            "design_issues": "",
            "software_versions": row.get("software_versions", ""),
            "number_of_original_volumes": nvolumes,
            "nss_count": int(row["nss_count"]),
            "number_of_steady_state_volumes": steady,
            "pca_selected_components": n_pca,
            "ica_components": n_ica,
            "accepted_components": int((classifications == "accepted").sum()),
            "rejected_components": n_rejected,
            **mapca,
            "pca_components_per_steady_state_volume": n_pca / steady,
            "rejected_components_per_steady_state_volume": n_rejected / steady,
            "base_confound_columns": base_diag["columns"],
            "base_confound_rank": base_diag["rank"],
            "rejected_ica_columns": rejected_diag["columns"],
            "rejected_ica_rank": rejected_diag["rank"],
            "combined_confound_columns": combined_diag["columns"],
            "combined_confound_rank": combined_diag["rank"],
            "combined_rank_with_intercept": combined_diag["rank_with_intercept"],
            "combined_columns_per_volume": combined_diag["columns"] / nvolumes,
            "combined_rank_per_volume": combined_diag["rank_with_intercept"] / nvolumes,
            "residual_df_before_task": nvolumes - combined_diag["rank_with_intercept"],
            "zero_columns": combined_diag["zero_columns"],
            "constant_nonzero_columns": combined_diag["constant_nonzero_columns"],
            "duplicate_columns": combined_diag["duplicate_columns"],
            "standardized_condition_number": combined_diag[
                "standardized_condition_number"
            ],
            "existing_combined_present": boolean(existing.is_file()),
            "existing_combined_rows": existing_rows,
            "existing_combined_columns": existing_columns,
            "existing_combined_matches_reconstruction": existing_match,
            **{f"flag_{name}": boolean(value) for name, value in flags.items()},
            "review_reasons": ";".join(reasons),
            "fmriprep_confounds": relative(paths["fmriprep_confounds"], project),
            "tedana_metrics": relative(paths["tedana_metrics"], project),
            "tedana_mixing": relative(paths["tedana_mixing"], project),
            "tedana_pca_metrics": relative(paths["tedana_pca_metrics"], project),
            "tedana_pca_cross_component_metrics": relative(pca_cross, project),
            "combined_confounds": relative(existing, project),
        }
        if n_pca != int(mapca["aic_components"]):
            raise ValueError(
                f"PCA table/AIC count mismatch:{n_pca}!={mapca['aic_components']}"
            )
        return output, inputs
    except Exception as exc:
        return incomplete_row(row, f"{type(exc).__name__}:{exc}"), inputs


def quantile(rows: Sequence[dict[str, Any]], column: str, q: float) -> float | str:
    values = [finite(row.get(column)) for row in rows]
    clean = [value for value in values if value is not None]
    return float(np.quantile(clean, q)) if clean else ""


def scanner_summary(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("software_versions") or "unknown")].append(row)
    output = []
    for scanner, group in sorted(groups.items()):
        complete = [row for row in group if row["design_status"] == "complete"]
        output.append(
            {
                "software_versions": scanner,
                "n_runs": len(group),
                "n_complete": len(complete),
                "median_pca_components": quantile(complete, "pca_selected_components", 0.5),
                "p95_pca_components": quantile(complete, "pca_selected_components", 0.95),
                "median_rejected_components": quantile(complete, "rejected_components", 0.5),
                "p95_rejected_components": quantile(complete, "rejected_components", 0.95),
                "median_combined_rank_fraction": quantile(complete, "combined_rank_per_volume", 0.5),
                "p95_combined_rank_fraction": quantile(complete, "combined_rank_per_volume", 0.95),
                "median_residual_df_before_task": quantile(complete, "residual_df_before_task", 0.5),
                **{
                    f"n_{flag}": sum(int(row[f"flag_{flag}"]) for row in complete)
                    for flag in (
                        "pca_more_than_half_timepoints",
                        "aic_explains_more_than_98_percent",
                        "rejected_components_gte_75",
                        "combined_rank_fraction_gte_0_30",
                        "residual_df_lt_100",
                    )
                },
            }
        )
    return output


def review_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            row
            for row in rows
            if row["design_status"] != "complete" or row.get("review_reasons")
        ),
        key=lambda row: (
            row["design_status"] == "complete",
            -(finite(row.get("combined_rank_per_volume")) or -1),
            row["run_key"],
        ),
    )


def benchmark_manifest(
    current_rows: Sequence[dict[str, str]], audited: Sequence[dict[str, Any]], cap: int = 20
) -> list[dict[str, Any]]:
    by_key = {row["run_key"]: row for row in current_rows}
    complete = [row for row in audited if row["design_status"] == "complete"]
    selected: dict[str, str] = {}

    def add(entries: Sequence[dict[str, Any]], reason: str, limit: int) -> None:
        for row in entries:
            if len(selected) >= cap or limit <= 0:
                break
            if row["run_key"] not in selected:
                selected[row["run_key"]] = reason
                limit -= 1

    burden = sorted(
        complete,
        key=lambda row: (-float(row["combined_rank_per_volume"]), row["run_key"]),
    )
    pca = sorted(
        complete,
        key=lambda row: (
            -float(row["pca_components_per_steady_state_volume"]),
            row["run_key"],
        ),
    )
    add(burden, "highest_combined_rank_fraction", 12)
    add(pca, "highest_pca_fraction", 4)
    for scanner in sorted({str(row["software_versions"]) for row in complete}):
        group = [row for row in complete if str(row["software_versions"]) == scanner]
        if not group or len(selected) >= cap:
            continue
        median_rank = float(np.median([row["combined_rank_per_volume"] for row in group]))
        control = min(
            group,
            key=lambda row: (abs(row["combined_rank_per_volume"] - median_rank), row["run_key"]),
        )
        add([control], f"scanner_control:{scanner}", 1)
    add(burden[::-1], "low_burden_control", cap - len(selected))
    output = []
    for key, reason in selected.items():
        row = dict(by_key[key])
        row["selection_reason"] = reason
        output.append(row)
    return sorted(output, key=lambda row: row["run_key"])


def plot_design(rows: Sequence[dict[str, Any]], path: Path) -> None:
    complete = [row for row in rows if row["design_status"] == "complete"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    software = sorted({str(row["software_versions"]) for row in complete})
    colors = plt.cm.Set2(np.linspace(0, 1, max(len(software), 1)))
    for scanner, color in zip(software, colors):
        group = [row for row in complete if str(row["software_versions"]) == scanner]
        axes[0, 0].hist(
            [row["pca_selected_components"] for row in group],
            bins=30,
            alpha=0.45,
            color=color,
            label=scanner,
        )
        axes[0, 1].scatter(
            [row["rejected_components"] for row in group],
            [row["combined_rank_per_volume"] for row in group],
            s=8,
            alpha=0.45,
            color=color,
            label=scanner,
        )
    axes[0, 0].set(xlabel="PCA-selected components", ylabel="Runs")
    axes[0, 1].set(
        xlabel="Rejected TEDANA components", ylabel="Nuisance rank / volumes"
    )
    axes[0, 1].axhline(0.30, color="black", linestyle="--", linewidth=1)
    axes[1, 0].scatter(
        [row["aic_components"] for row in complete],
        [row["kic_components"] for row in complete],
        s=8,
        alpha=0.4,
    )
    upper = max(row["aic_components"] for row in complete)
    axes[1, 0].plot([0, upper], [0, upper], color="black", linewidth=1)
    axes[1, 0].set(xlabel="AIC components", ylabel="KIC components")
    axes[1, 1].scatter(
        [row["combined_rank_per_volume"] for row in complete],
        [row["residual_df_before_task"] for row in complete],
        s=8,
        alpha=0.4,
    )
    axes[1, 1].set(
        xlabel="Nuisance rank / volumes", ylabel="Residual DF before task model"
    )
    for axis in axes.ravel():
        axis.grid(alpha=0.2)
    axes[0, 0].legend(fontsize=7)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    apply_umask_mode(path)


def make_report(rows: Sequence[dict[str, Any]], path: Path) -> None:
    complete = [row for row in rows if row["design_status"] == "complete"]
    def count(flag: str) -> int:
        return sum(int(row[f"flag_{flag}"]) for row in complete)
    mismatches = sum(
        row["existing_combined_present"]
        and not row["existing_combined_matches_reconstruction"]
        for row in complete
    )
    lines = [
        "# TEDANA Dimensionality And Design-Burden Audit",
        "",
        "This is a read-only scientific audit. It does not change production TEDANA, fMRIPrep, confound files, classifications, or analysis exclusions.",
        "",
        "## Coverage",
        "",
        f"- Inventory rows: {len(rows)}",
        f"- Complete design audits: {len(complete)}",
        f"- Incomplete design audits: {len(rows) - len(complete)}",
        f"- Existing combined-confound files differing from exact reconstruction: {mismatches}",
        "",
        "## Prespecified Descriptive Flags",
        "",
        f"- PCA components greater than half the steady-state time points: {count('pca_more_than_half_timepoints')}",
        f"- AIC-selected PCA explaining more than 98% of variance: {count('aic_explains_more_than_98_percent')}",
        f"- At least 75 rejected TEDANA components: {count('rejected_components_gte_75')}",
        f"- Combined nuisance rank at least 30% of original volumes: {count('combined_rank_fraction_gte_0_30')}",
        f"- Fewer than 100 residual degrees of freedom before task regressors: {count('residual_df_lt_100')}",
        "",
        "The first two flags follow TEDANA 26.0.3 documentation as warning signs for unexpectedly high PCA dimensionality. The other thresholds describe RF1 design burden; they are review triggers, not automatic exclusions.",
        "",
        "## Interpretation",
        "",
        "`combined_rank_with_intercept` is the numerical rank of the exact production nuisance matrix plus a constant. `residual_df_before_task` subtracts that rank from the number of acquired volumes; task regressors and any additional contrasts will consume further degrees of freedom. Column count is also reported because it affects model size, but rank is the relevant estimability quantity.",
        "",
        "AIC, KIC, and MDL counts are taken from each completed TEDANA run's saved MAPCA cross-component JSON. They permit a cohort-wide comparison of dimensionality criteria without rerunning ICA. Actual KIC/MDL denoising must still be benchmarked on the generated targeted manifest before any production decision.",
        "",
        "## Decision Gate",
        "",
        "Review `review_runs.tsv`, the scanner summary, and the targeted `pca_method_benchmark.tsv`. Do not alter production TEDANA or confound construction solely because a run crosses one descriptive threshold. A production change requires matched NSS results, targeted KIC/MDL denoising QC, task-model rank review, and human component inspection.",
    ]
    path.write_text("\n".join(lines) + "\n")
    apply_umask_mode(path)


def install_directory(stage: Path, output: Path) -> None:
    backup = output.with_name(f".{output.name}.backup")
    if backup.exists():
        shutil.rmtree(backup)
    if output.exists():
        output.rename(backup)
    try:
        stage.rename(output)
    except Exception:
        if backup.exists() and not output.exists():
            backup.rename(output)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    confounds_root = ensure_safe_child_path(
        project / "derivatives", args.combined_confounds_dir
    )
    current = read_tsv(args.current_runs)
    if not current or len({row["run_key"] for row in current}) != len(current):
        raise ValueError("current run inventory is empty or contains duplicate run keys")
    if args.dry_run:
        print(f"Would audit TEDANA design burden for {len(current)} run(s).")
        print(f"Tracked output: {output}")
        print("Production derivatives will not be modified.")
        return 0
    if output.exists() and not args.overwrite:
        raise ValueError(f"output exists; review it or use --overwrite: {output}")
    audited = []
    inputs = [args.current_runs.resolve()]
    for index, row in enumerate(current, start=1):
        result, paths = audit_run(project, confounds_root, row)
        audited.append(result)
        inputs.extend(paths)
        if index % 100 == 0 or index == len(current):
            print(f"Audited {index}/{len(current)} run(s).", flush=True)
    summaries = scanner_summary(audited)
    review = review_rows(audited)
    benchmark = benchmark_manifest(current, audited, cap=args.benchmark_cap)
    benchmark_columns = (*current[0].keys(), "selection_reason")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tedana-design-", dir=output.parent) as temp:
        stage = Path(temp)
        write_tsv(stage / "cohort_design_burden.tsv", audited, RUN_COLUMNS)
        write_tsv(stage / "summary_by_scanner.tsv", summaries, SUMMARY_COLUMNS)
        write_tsv(stage / "review_runs.tsv", review, RUN_COLUMNS)
        write_tsv(stage / "pca_method_benchmark.tsv", benchmark, benchmark_columns)
        plot_design(audited, stage / "figures" / "design_burden.png")
        make_report(audited, stage / "report.md")
        provenance = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "current_runs": relative(args.current_runs, project),
            "current_runs_sha256": sha256(args.current_runs),
            "inventory_rows": len(current),
            "complete_rows": sum(row["design_status"] == "complete" for row in audited),
            "review_rows": len(review),
            "pca_method_benchmark_rows": len(benchmark),
            "input_inventory_digest_path_size_mtime": inventory_digest(inputs, project),
            "production_derivatives_modified": False,
            "task_regressors_used": False,
            "thresholds_are_automatic_exclusions": False,
            "outputs": {},
        }
        for item in OUTPUTS:
            if item.name != "provenance.json":
                provenance["outputs"][item.as_posix()] = sha256(stage / item)
        (stage / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        )
        apply_umask_mode(stage / "provenance.json")
        install_directory(stage, output)
    print(f"Complete design audits: {provenance['complete_rows']}/{len(current)}")
    print(f"Review rows: {len(review)}")
    print(f"Targeted PCA-method benchmark runs: {len(benchmark)}")
    print(f"Tracked report: {output / 'report.md'}")
    return 0


def check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    failures = []
    provenance_path = output / "provenance.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    if not provenance:
        failures.append(f"missing:{provenance_path}")
    current = read_tsv(args.current_runs)
    expected_keys = {row["run_key"] for row in current}
    burden_path = output / "cohort_design_burden.tsv"
    if burden_path.is_file():
        burden = read_tsv(burden_path)
        if len(burden) != len(current) or {row["run_key"] for row in burden} != expected_keys:
            failures.append("cohort_design_burden_coverage")
    else:
        failures.append(f"missing:{burden_path}")
    benchmark_path = output / "pca_method_benchmark.tsv"
    if benchmark_path.is_file():
        keys = [row["run_key"] for row in read_tsv(benchmark_path)]
        if len(keys) != len(set(keys)) or not set(keys).issubset(expected_keys):
            failures.append("pca_method_benchmark_coverage")
    for item in OUTPUTS:
        path = output / item
        if not path.is_file():
            failures.append(f"missing:{path}")
        elif item.name != "provenance.json" and provenance.get("outputs", {}).get(
            item.as_posix()
        ) != sha256(path):
            failures.append(f"checksum:{path}")
    if provenance.get("current_runs_sha256") != sha256(args.current_runs):
        failures.append("current_runs_checksum")
    if burden_path.is_file():
        try:
            live_inputs = [args.current_runs.resolve()]
            for row in read_tsv(burden_path):
                if row.get("design_status") != "complete":
                    continue
                for column in (
                    "fmriprep_confounds",
                    "tedana_metrics",
                    "tedana_mixing",
                    "tedana_pca_metrics",
                    "tedana_pca_cross_component_metrics",
                ):
                    live_inputs.append(project / row[column])
                if row.get("existing_combined_present") == "1":
                    live_inputs.append(project / row["combined_confounds"])
            if provenance.get(
                "input_inventory_digest_path_size_mtime"
            ) != inventory_digest(live_inputs, project):
                failures.append("live_input_inventory")
        except (OSError, ValueError, KeyError) as exc:
            failures.append(f"live_input_inventory:{exc}")
    for failure in failures:
        print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: {len(failures)} TEDANA design-audit issue(s).")
        return 1
    print(f"CHECK PASSED: TEDANA design audit validated for {len(current)} run(s).")
    return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-root", type=Path, default=project)
        child.add_argument(
            "--current-runs",
            type=Path,
            default=project / "qc" / "tedana_audit" / "current_runs.tsv",
        )
        child.add_argument(
            "--combined-confounds-dir",
            type=Path,
            default=project / "derivatives" / "fsl" / "confounds_tedana",
        )
        child.add_argument(
            "--output-dir",
            type=Path,
            default=project / "qc" / "tedana_audit" / "design",
        )
    build_parser = subparsers.choices["build"]
    build_parser.add_argument("--overwrite", action="store_true")
    build_parser.add_argument("--dry-run", action="store_true")
    build_parser.add_argument("--benchmark-cap", type=int, default=20)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if getattr(args, "benchmark_cap", 20) < 4:
            raise ValueError("--benchmark-cap must be at least 4")
        return build(args) if args.command == "build" else check(args)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
