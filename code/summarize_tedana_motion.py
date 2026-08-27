#!/usr/bin/env python3
"""Summarize the validated TEDANA Motion24 sentinel audit."""

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

import numpy as np
import pandas as pd

from pipeline_utils import apply_umask_mode, ensure_safe_child_path


CONFIGS = {
    "fastica": ("nss-fastica", "motion-fastica"),
    "robustica": ("nss-robustica", "motion-robustica"),
}
THRESHOLDS = (0.10, 0.25, 0.50)
IDENTITY_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "nss_count",
    "selection_reason",
)
COMPONENT_COLUMNS = (
    *IDENTITY_COLUMNS,
    "configuration",
    "source_configuration",
    "component",
    "classification",
    "normalized_variance_fraction",
    "kappa",
    "rho",
    "motion24_r2",
    "motion24_f",
    "motion24_p",
    "metrics_path",
    "report_path",
    "component_figure_path",
)
SUMMARY_COLUMNS = (
    *IDENTITY_COLUMNS,
    "configuration",
    "classification",
    "n_components",
    "normalized_variance_fraction",
    "motion24_r2_min",
    "motion24_r2_q25",
    "motion24_r2_median",
    "motion24_r2_q75",
    "motion24_r2_p95",
    "motion24_r2_max",
    "motion24_r2_variance_weighted_mean",
    *(f"motion24_r2_gt_{int(value * 100):02d}_count" for value in THRESHOLDS),
    *(f"motion24_r2_gt_{int(value * 100):02d}_fraction" for value in THRESHOLDS),
    *(f"motion24_r2_gt_{int(value * 100):02d}_variance" for value in THRESHOLDS),
)
TASK_COLUMNS = (
    "task",
    "configuration",
    "classification",
    "n_runs",
    "n_components",
    "motion24_r2_q25",
    "motion24_r2_median",
    "motion24_r2_q75",
    *(f"motion24_r2_gt_{int(value * 100):02d}_count" for value in THRESHOLDS),
    *(f"motion24_r2_gt_{int(value * 100):02d}_fraction" for value in THRESHOLDS),
)
REVIEW_COLUMNS = (
    *IDENTITY_COLUMNS,
    "configuration",
    "component",
    "classification",
    "normalized_variance_fraction",
    "kappa",
    "rho",
    "motion24_r2",
    "motion24_f",
    "motion24_p",
    "reason_for_review",
    "metrics_path",
    "report_path",
    "component_figure_path",
)
OUTPUTS = (
    Path("summary_by_run_classification.tsv"),
    Path("summary_by_task.tsv"),
    Path("review_manifest.tsv"),
    Path("figures/motion24_by_classification.png"),
    Path("figures/motion24_vs_variance.png"),
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


def number(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected finite numeric value, found {value!r}") from exc
    if not math.isfinite(result):
        raise ValueError(f"expected finite numeric value, found {value!r}")
    return result


def normalized_columns(frame: pd.DataFrame) -> dict[str, Any]:
    return {str(column).strip().lower(): column for column in frame.columns}


def required_column(frame: pd.DataFrame, name: str, path: Path) -> Any:
    column = normalized_columns(frame).get(name.lower())
    if column is None:
        raise ValueError(f"missing column {name!r}: {path}")
    return column


def component_number(value: Any) -> int | None:
    digits = "".join(character for character in str(value) if character.isdigit())
    return int(digits) if digits else None


def metric_paths(
    project: Path, audit_root: Path, config: str, run_key: str
) -> tuple[Path, str, str]:
    directory = audit_root / "benchmark" / config / run_key
    metrics = directory / f"{run_key}_desc-tedana_metrics.tsv"
    report = directory / f"{run_key}_tedana_report.html"
    return (
        metrics,
        report.relative_to(project).as_posix() if report.is_file() else "",
        directory.relative_to(project).as_posix(),
    )


def component_rows(
    project: Path,
    audit_root: Path,
    sentinel: dict[str, str],
    label: str,
) -> tuple[list[dict[str, Any]], list[Path]]:
    source_config, motion_config = CONFIGS[label]
    key = sentinel["run_key"]
    source_path, _source_report, _source_directory = metric_paths(
        project, audit_root, source_config, key
    )
    motion_path, report, motion_directory = metric_paths(
        project, audit_root, motion_config, key
    )
    if not source_path.is_file() or not motion_path.is_file():
        missing = source_path if not source_path.is_file() else motion_path
        raise ValueError(f"missing Motion24 summary input: {missing}")
    source = pd.read_csv(source_path, sep="\t")
    motion = pd.read_csv(motion_path, sep="\t")
    source_component = required_column(source, "Component", source_path)
    source_class = required_column(source, "classification", source_path)
    motion_component = required_column(motion, "Component", motion_path)
    motion_class = required_column(motion, "classification", motion_path)
    if (
        source[source_component].astype(str).tolist()
        != motion[motion_component].astype(str).tolist()
    ):
        raise ValueError(f"component identity changed in Motion24 pass: {label} {key}")
    if (
        source[source_class].astype(str).str.lower().tolist()
        != motion[motion_class].astype(str).str.lower().tolist()
    ):
        raise ValueError(f"classification changed in Motion24 pass: {label} {key}")
    variance_column = normalized_columns(motion).get("normalized variance explained")
    if variance_column is None:
        variance_column = required_column(motion, "variance explained", motion_path)
    variance = pd.to_numeric(motion[variance_column], errors="coerce").to_numpy(
        dtype=float
    )
    if not np.all(np.isfinite(variance)) or np.any(variance < 0) or variance.sum() <= 0:
        raise ValueError(f"invalid component variance: {motion_path}")
    variance = variance / variance.sum()
    columns = normalized_columns(motion)
    r2_column = required_column(motion, "R2stat motion24 model", motion_path)
    f_column = required_column(motion, "Fstat motion24 model", motion_path)
    p_column = required_column(motion, "pval motion24 model", motion_path)
    kappa_column = columns.get("kappa")
    rho_column = columns.get("rho")
    rows: list[dict[str, Any]] = []
    for index, metric_row in motion.iterrows():
        classification = str(metric_row[motion_class]).lower()
        if classification not in {"accepted", "rejected"}:
            raise ValueError(
                f"invalid classification in {motion_path}: {classification}"
            )
        r2 = number(metric_row[r2_column])
        f_stat = number(metric_row[f_column])
        p_value = number(metric_row[p_column])
        if not -1e-8 <= r2 <= 1 + 1e-8 or f_stat < 0 or not 0 <= p_value <= 1:
            raise ValueError(f"invalid Motion24 metric in {motion_path}: row {index}")
        component = metric_row[motion_component]
        component_index = component_number(component)
        figure = (
            f"{motion_directory}/figures/comp_{component_index:03d}.png"
            if component_index is not None
            and (
                project
                / motion_directory
                / "figures"
                / f"comp_{component_index:03d}.png"
            ).is_file()
            else ""
        )
        rows.append(
            {
                **{name: sentinel.get(name, "") for name in IDENTITY_COLUMNS},
                "configuration": label,
                "source_configuration": source_config,
                "component": component,
                "classification": classification,
                "normalized_variance_fraction": float(variance[index]),
                "kappa": number(metric_row[kappa_column]) if kappa_column else "",
                "rho": number(metric_row[rho_column]) if rho_column else "",
                "motion24_r2": min(1.0, max(0.0, r2)),
                "motion24_f": f_stat,
                "motion24_p": p_value,
                "metrics_path": motion_path.relative_to(project).as_posix(),
                "report_path": report,
                "component_figure_path": figure,
            }
        )
    inputs = [source_path, motion_path]
    if report:
        inputs.append(project / report)
    inputs.extend(
        project / row["component_figure_path"]
        for row in rows
        if row["component_figure_path"]
    )
    return rows, inputs


def summarize_group(
    rows: Sequence[dict[str, Any]], identity: dict[str, Any]
) -> dict[str, Any]:
    r2 = np.array([number(row["motion24_r2"]) for row in rows], dtype=float)
    variance = np.array(
        [number(row["normalized_variance_fraction"]) for row in rows], dtype=float
    )
    result: dict[str, Any] = {
        **identity,
        "n_components": len(rows),
        "normalized_variance_fraction": float(variance.sum()),
        "motion24_r2_min": float(np.min(r2)),
        "motion24_r2_q25": float(np.quantile(r2, 0.25)),
        "motion24_r2_median": float(np.median(r2)),
        "motion24_r2_q75": float(np.quantile(r2, 0.75)),
        "motion24_r2_p95": float(np.quantile(r2, 0.95)),
        "motion24_r2_max": float(np.max(r2)),
        "motion24_r2_variance_weighted_mean": float(np.average(r2, weights=variance)),
    }
    for threshold in THRESHOLDS:
        token = int(threshold * 100)
        high = r2 > threshold
        result[f"motion24_r2_gt_{token:02d}_count"] = int(high.sum())
        result[f"motion24_r2_gt_{token:02d}_fraction"] = float(high.mean())
        result[f"motion24_r2_gt_{token:02d}_variance"] = float(variance[high].sum())
    return result


def run_summaries(component_data: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in component_data:
        key = (row["run_key"], row["configuration"], row["classification"])
        grouped.setdefault(key, []).append(row)
    output = []
    for (_key, config, classification), rows in sorted(grouped.items()):
        identity = {name: rows[0][name] for name in IDENTITY_COLUMNS}
        identity.update({"configuration": config, "classification": classification})
        output.append(summarize_group(rows, identity))
    return output


def task_summaries(component_data: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in component_data:
        key = (row["task"], row["configuration"], row["classification"])
        grouped.setdefault(key, []).append(row)
    output = []
    for (task, config, classification), rows in sorted(grouped.items()):
        r2 = np.array([number(row["motion24_r2"]) for row in rows])
        item: dict[str, Any] = {
            "task": task,
            "configuration": config,
            "classification": classification,
            "n_runs": len({row["run_key"] for row in rows}),
            "n_components": len(rows),
            "motion24_r2_q25": float(np.quantile(r2, 0.25)),
            "motion24_r2_median": float(np.median(r2)),
            "motion24_r2_q75": float(np.quantile(r2, 0.75)),
        }
        for threshold in THRESHOLDS:
            token = int(threshold * 100)
            high = r2 > threshold
            item[f"motion24_r2_gt_{token:02d}_count"] = int(high.sum())
            item[f"motion24_r2_gt_{token:02d}_fraction"] = float(high.mean())
        output.append(item)
    return output


def review_manifest(component_data: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in component_data:
        grouped.setdefault((row["run_key"], row["configuration"]), []).append(row)
    output: list[dict[str, Any]] = []
    for _key, rows in sorted(grouped.items()):
        candidates: dict[tuple[str, str], set[str]] = {}
        accepted = [row for row in rows if row["classification"] == "accepted"]
        rejected = [row for row in rows if row["classification"] == "rejected"]
        selections = []
        if accepted:
            selections.append(
                (
                    max(accepted, key=lambda row: row["motion24_r2"]),
                    "accepted_highest_motion24_r2",
                )
            )
        if rejected:
            selections.extend(
                (
                    (
                        min(rejected, key=lambda row: row["motion24_r2"]),
                        "rejected_lowest_motion24_r2",
                    ),
                    (
                        max(
                            rejected,
                            key=lambda row: row["normalized_variance_fraction"],
                        ),
                        "rejected_largest_variance",
                    ),
                )
            )
        row_lookup = {(row["component"], row["classification"]): row for row in rows}
        for row, reason in selections:
            candidate_key = (row["component"], row["classification"])
            candidates.setdefault(candidate_key, set()).add(reason)
        for candidate_key, reasons in sorted(candidates.items()):
            row = row_lookup[candidate_key]
            output.append(
                {
                    **{name: row[name] for name in REVIEW_COLUMNS if name in row},
                    "reason_for_review": ";".join(sorted(reasons)),
                }
            )
    return output


def plot_outputs(component_data: Sequence[dict[str, Any]], root: Path) -> None:
    from matplotlib import pyplot as plt

    root.mkdir(parents=True, exist_ok=True)
    groups = [
        [
            row["motion24_r2"]
            for row in component_data
            if row["configuration"] == config
            and row["classification"] == classification
        ]
        for config in CONFIGS
        for classification in ("accepted", "rejected")
    ]
    labels = [
        f"{config}\n{classification}"
        for config in CONFIGS
        for classification in ("accepted", "rejected")
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot(groups, tick_labels=labels, showfliers=False)
    ax.set(
        ylabel="Motion24 R-squared",
        title="Motion resemblance by ICA and classification",
    )
    fig.tight_layout()
    fig.savefig(root / "motion24_by_classification.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)
    colors = {"accepted": "#237a57", "rejected": "#b84a3a"}
    for ax, config in zip(axes, CONFIGS):
        for classification in ("accepted", "rejected"):
            selected = [
                row
                for row in component_data
                if row["configuration"] == config
                and row["classification"] == classification
            ]
            ax.scatter(
                [row["normalized_variance_fraction"] for row in selected],
                [row["motion24_r2"] for row in selected],
                s=12,
                alpha=0.45,
                color=colors[classification],
                label=classification,
            )
        ax.set(title=config, xlabel="Normalized variance fraction")
    axes[0].set_ylabel("Motion24 R-squared")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(root / "motion24_vs_variance.png", dpi=180)
    plt.close(fig)
    for path in root.glob("*.png"):
        apply_umask_mode(path)


def format_summary(values: Sequence[Any]) -> str:
    array = np.array([number(value) for value in values], dtype=float)
    return (
        f"{np.median(array):.4f} "
        f"(IQR {np.quantile(array, 0.25):.4f} to {np.quantile(array, 0.75):.4f})"
    )


def make_report(component_data: Sequence[dict[str, Any]], path: Path) -> None:
    lines = [
        "# TEDANA Motion24 Sentinel Audit",
        "",
        "This audit measures how strongly each existing ICA timecourse resembles the conventional 24-parameter rigid-body motion model. Motion metrics did not participate in classification, and production derivatives were not modified.",
        "",
        "## Validation",
        "",
        f"- Sentinel runs: {len({row['run_key'] for row in component_data})}",
        f"- Component rows: {len(component_data)}",
        "- Motion24 classifications were required to match the corresponding ordinary NSS-aware run exactly.",
        "",
        "## Continuous Distributions",
        "",
    ]
    for config in CONFIGS:
        for classification in ("accepted", "rejected"):
            selected = [
                row["motion24_r2"]
                for row in component_data
                if row["configuration"] == config
                and row["classification"] == classification
            ]
            high = sum(value > 0.25 for value in selected)
            lines.append(
                f"- {config} {classification}: Motion24 R-squared {format_summary(selected)}; "
                f"{high}/{len(selected)} components exceed the descriptive 0.25 threshold."
            )
    accepted_high = sum(
        row["classification"] == "accepted" and row["motion24_r2"] > 0.25
        for row in component_data
    )
    rejected_low = sum(
        row["classification"] == "rejected" and row["motion24_r2"] < 0.10
        for row in component_data
    )
    lines.extend(
        (
            "",
            "## Review Priorities",
            "",
            f"- Accepted components with Motion24 R-squared >0.25: {accepted_high}",
            f"- Rejected components with Motion24 R-squared <0.10: {rejected_low}",
            "- `review_manifest.tsv` selects the highest-motion accepted component, lowest-motion rejected component, and largest-variance rejected component for each run and ICA configuration. Duplicate selections are combined.",
            "",
            "## Interpretation Gate",
            "",
            "The 0.10, 0.25, and 0.50 values are descriptive summaries, not classification thresholds. Motion resemblance alone does not override TE dependence. Human component review is required before considering any motion-informed decision rule or production migration.",
        )
    )
    path.write_text("\n".join(lines) + "\n")
    apply_umask_mode(path)


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
        raise ValueError(f"stale output backup requires review: {backup}")
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


def run_build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    raw_components = ensure_safe_child_path(audit_root, args.component_table)
    sentinels = read_tsv(args.sentinel_tsv)
    if not sentinels or len({row["run_key"] for row in sentinels}) != len(sentinels):
        raise ValueError("sentinel manifest is empty or contains duplicate run keys")
    if args.dry_run:
        print(f"Would summarize Motion24 outputs for {len(sentinels)} sentinel run(s).")
        print(f"Tracked output: {output}")
        print(f"Ignored component table: {raw_components}")
        return 0
    if output.exists() and not args.overwrite:
        raise ValueError(
            f"summary output exists; review it or use --overwrite: {output}"
        )
    components: list[dict[str, Any]] = []
    inputs = [args.sentinel_tsv.resolve()]
    for index, sentinel in enumerate(sentinels, start=1):
        for config in CONFIGS:
            rows, paths = component_rows(project, audit_root, sentinel, config)
            components.extend(rows)
            inputs.extend(paths)
        print(f"Summarized {index}/{len(sentinels)} {sentinel['run_key']}", flush=True)
    run_rows = run_summaries(components)
    task_rows = task_summaries(components)
    review_rows = review_manifest(components)
    raw_components.parent.mkdir(parents=True, exist_ok=True)
    write_tsv(raw_components, components, COMPONENT_COLUMNS)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="tedana-motion-summary-", dir=output.parent
    ) as temporary:
        stage = Path(temporary)
        write_tsv(
            stage / "summary_by_run_classification.tsv", run_rows, SUMMARY_COLUMNS
        )
        write_tsv(stage / "summary_by_task.tsv", task_rows, TASK_COLUMNS)
        write_tsv(stage / "review_manifest.tsv", review_rows, REVIEW_COLUMNS)
        plot_outputs(components, stage / "figures")
        make_report(components, stage / "report.md")
        provenance = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "sentinel_manifest": args.sentinel_tsv.resolve()
            .relative_to(project)
            .as_posix(),
            "sentinel_manifest_sha256": sha256(args.sentinel_tsv),
            "sentinel_count": len(sentinels),
            "component_count": len(components),
            "component_table": raw_components.relative_to(project).as_posix(),
            "component_table_sha256": sha256(raw_components),
            "input_inventory_digest_path_size_mtime": inventory_digest(inputs, project),
            "production_derivatives_modified": False,
            "task_regressors_used": False,
            "classifications_changed": False,
            "motion_thresholds_are_descriptive": list(THRESHOLDS),
            "outputs": {},
        }
        for relative in OUTPUTS:
            if relative.name != "provenance.json":
                provenance["outputs"][relative.as_posix()] = sha256(stage / relative)
        (stage / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        )
        apply_umask_mode(stage / "provenance.json")
        install_directory(stage, output)
    print(f"Wrote ignored component rows: {len(components)}")
    print(f"Wrote run/classification rows: {len(run_rows)}")
    print(f"Wrote review candidates: {len(review_rows)}")
    print(f"Tracked report: {output / 'report.md'}")
    return 0


def run_check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    raw_components = ensure_safe_child_path(audit_root, args.component_table)
    failures: list[str] = []
    provenance_path = output / "provenance.json"
    provenance = (
        json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    )
    if not provenance:
        failures.append(f"missing:{provenance_path}")
    sentinels = read_tsv(args.sentinel_tsv)
    expected_keys = {row["run_key"] for row in sentinels}
    components: list[dict[str, str]] = []
    if not raw_components.is_file():
        failures.append(f"missing:{raw_components}")
    else:
        components = read_tsv(raw_components)
        if {row["run_key"] for row in components} != expected_keys:
            failures.append("component_run_keys")
        observed_components = {
            (row["run_key"], row["configuration"]) for row in components
        }
        expected_components = {
            (key, config) for key in expected_keys for config in CONFIGS
        }
        if observed_components != expected_components:
            failures.append("component_configurations")
        if provenance.get("component_table_sha256") != sha256(raw_components):
            failures.append("component_table_checksum")
    summary_path = output / "summary_by_run_classification.tsv"
    if summary_path.is_file():
        summary = read_tsv(summary_path)
        if {row["run_key"] for row in summary} != expected_keys:
            failures.append("summary_run_keys")
        observed = {
            (row["run_key"], row["configuration"], row["classification"])
            for row in summary
        }
        expected = {
            (row["run_key"], row["configuration"], row["classification"])
            for row in components
        }
        if observed != expected:
            failures.append("summary_configurations")
    for relative in OUTPUTS:
        path = output / relative
        if not path.is_file():
            failures.append(f"missing:{path}")
        elif relative.name != "provenance.json" and provenance.get("outputs", {}).get(
            relative.as_posix()
        ) != sha256(path):
            failures.append(f"checksum:{path}")
    if provenance.get("sentinel_manifest_sha256") != sha256(args.sentinel_tsv):
        failures.append("sentinel_manifest_checksum")
    if provenance.get("classifications_changed") is not False:
        failures.append("classification_provenance")
    try:
        inputs = [args.sentinel_tsv.resolve()]
        for sentinel in sentinels:
            for label in CONFIGS:
                _rows, paths = component_rows(project, audit_root, sentinel, label)
                inputs.extend(paths)
        if provenance.get("input_inventory_digest_path_size_mtime") != inventory_digest(
            inputs, project
        ):
            failures.append("motion_input_inventory")
    except (OSError, ValueError) as exc:
        failures.append(f"motion_inputs:{exc}")
    for failure in failures:
        print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: {len(failures)} TEDANA Motion24 summary issue(s).")
        return 1
    print(
        f"CHECK PASSED: TEDANA Motion24 summary validated for {len(sentinels)} run(s)."
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
            "--component-table",
            type=Path,
            default=project
            / "derivatives"
            / "tedana-audit"
            / "motion24_components.tsv",
        )
        child.add_argument(
            "--output-dir",
            type=Path,
            default=project / "qc" / "tedana_audit" / "motion",
        )
    subparsers.choices["build"].add_argument("--overwrite", action="store_true")
    subparsers.choices["build"].add_argument("--dry-run", action="store_true")
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
