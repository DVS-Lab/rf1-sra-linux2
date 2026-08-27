#!/usr/bin/env python3
"""Summarize matched NSS and ICA dimensionality experiments for RF1 TEDANA."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import pandas as pd

from pipeline_utils import apply_umask_mode, ensure_safe_child_path


CONFIGS = ("full-fastica", "nss-fastica", "nss-robustica")
COUNT_METRICS = (
    "pca_components",
    "ica_components",
    "accepted_components",
    "rejected_components",
    "aic_components",
    "kic_components",
    "mdl_components",
    "varex_90_components",
    "varex_95_components",
)
COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "run_key",
    "nss_count",
    "number_of_original_volumes",
    "number_of_steady_state_volumes",
    "software_versions",
    "selection_reason",
    *(f"historical_{name}" for name in COUNT_METRICS[:4]),
    *(f"full_fastica_{name}" for name in COUNT_METRICS),
    *(f"nss_fastica_{name}" for name in COUNT_METRICS),
    *(f"nss_robustica_{name}" for name in COUNT_METRICS),
    *(f"nss_minus_full_{name}" for name in COUNT_METRICS),
    *(f"robustica_minus_fastica_{name}" for name in COUNT_METRICS[:4]),
    "nss_fastica_pca_minus_ica_components",
    "nss_robustica_pca_minus_ica_components",
    "nss_fastica_robustica_pca_contract_identical",
    "n0_metrics_identical",
    "n0_mixing_max_absolute_difference",
    "n0_denoised_max_absolute_difference",
    "flag_nss_changes_pca_by_at_least_5",
    "flag_nss_changes_rejected_by_at_least_5",
    "flag_robustica_changes_ica_count_by_at_least_10",
    "flag_robustica_changes_rejected_by_at_least_10",
    "review_reasons",
)
OUTPUTS = (
    Path("paired_dimensionality.tsv"),
    Path("review_runs.tsv"),
    Path("figures/matched_dimensionality.png"),
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


def parse_mapca(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text())
    result = {}
    for name in ("aic", "kic", "mdl", "varex_90", "varex_95"):
        entry = payload.get(name)
        if not isinstance(entry, dict) or "n_components" not in entry:
            raise ValueError(f"missing {name} MAPCA result: {path}")
        result[f"{name}_components"] = int(entry["n_components"])
    return result


def summarize_decomposition(directory: Path, run_key: str) -> tuple[dict[str, int], list[Path]]:
    paths = {
        "pca": directory / f"{run_key}_desc-PCA_metrics.tsv",
        "mapca": directory / f"{run_key}_desc-PCACrossComponent_metrics.json",
        "ica": directory / f"{run_key}_desc-tedana_metrics.tsv",
        "mixing": directory / f"{run_key}_desc-ICA_mixing.tsv",
        "denoised": directory / f"{run_key}_desc-denoised_bold.nii.gz",
        "provenance": directory / "rf1_audit_provenance.json",
    }
    missing = [path for path in paths.values() if not path.is_file()]
    if missing:
        raise ValueError(f"missing dimensionality input(s): {', '.join(map(str, missing))}")
    pca = pd.read_csv(paths["pca"], sep="\t")
    ica = pd.read_csv(paths["ica"], sep="\t")
    mixing = pd.read_csv(paths["mixing"], sep="\t")
    classification = ica["classification"].astype(str).str.lower()
    if not classification.isin(("accepted", "rejected")).all():
        raise ValueError(f"invalid ICA classification: {paths['ica']}")
    if mixing.shape[1] != len(ica):
        raise ValueError(f"ICA metrics/mixing mismatch: {directory}")
    result = {
        "pca_components": len(pca),
        "ica_components": len(ica),
        "accepted_components": int((classification == "accepted").sum()),
        "rejected_components": int((classification == "rejected").sum()),
        **parse_mapca(paths["mapca"]),
    }
    if result["pca_components"] != result["aic_components"]:
        raise ValueError(f"PCA table/AIC mismatch: {directory}")
    return result, list(paths.values())


def historical_summary(project: Path, row: dict[str, str]) -> tuple[dict[str, int], list[Path]]:
    pca = project / row["tedana_pca_metrics"]
    ica = project / row["tedana_metrics"]
    mixing = project / row["tedana_mixing"]
    required = [pca, ica, mixing]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"missing historical input(s): {', '.join(map(str, missing))}")
    pca_frame = pd.read_csv(pca, sep="\t")
    ica_frame = pd.read_csv(ica, sep="\t")
    mixing_frame = pd.read_csv(mixing, sep="\t")
    classification = ica_frame["classification"].astype(str).str.lower()
    if mixing_frame.shape[1] != len(ica_frame):
        raise ValueError(f"historical ICA metrics/mixing mismatch: {row['run_key']}")
    return {
        "pca_components": len(pca_frame),
        "ica_components": len(ica_frame),
        "accepted_components": int((classification == "accepted").sum()),
        "rejected_components": int((classification == "rejected").sum()),
    }, required


def max_image_difference(first: Path, second: Path) -> float:
    image_a = nib.load(str(first))
    image_b = nib.load(str(second))
    if image_a.shape != image_b.shape or not np.array_equal(image_a.affine, image_b.affine):
        raise ValueError(f"image grid differs: {first} versus {second}")
    data_a = np.asanyarray(image_a.dataobj)
    data_b = np.asanyarray(image_b.dataobj)
    return float(np.max(np.abs(data_a.astype(np.float64) - data_b.astype(np.float64))))


def n0_identity(audit_root: Path, row: dict[str, str]) -> tuple[dict[str, Any], list[Path]]:
    if int(row["nss_count"]) != 0:
        return {
            "n0_metrics_identical": "",
            "n0_mixing_max_absolute_difference": "",
            "n0_denoised_max_absolute_difference": "",
        }, []
    key = row["run_key"]
    full = audit_root / "benchmark" / "full-fastica" / key
    nss = audit_root / "benchmark" / "nss-fastica" / key
    full_metrics = full / f"{key}_desc-tedana_metrics.tsv"
    nss_metrics = nss / f"{key}_desc-tedana_metrics.tsv"
    full_mixing = full / f"{key}_desc-ICA_mixing.tsv"
    nss_mixing = nss / f"{key}_desc-ICA_mixing.tsv"
    full_denoised = full / f"{key}_desc-denoised_bold.nii.gz"
    nss_denoised = nss / f"{key}_desc-denoised_bold.nii.gz"
    paths = [
        full_metrics,
        nss_metrics,
        full_mixing,
        nss_mixing,
        full_denoised,
        nss_denoised,
    ]
    metrics_identical = full_metrics.read_bytes() == nss_metrics.read_bytes()
    mixing_a = pd.read_csv(full_mixing, sep="\t").to_numpy(dtype=float)
    mixing_b = pd.read_csv(nss_mixing, sep="\t").to_numpy(dtype=float)
    mixing_difference = (
        float(np.max(np.abs(mixing_a - mixing_b)))
        if mixing_a.shape == mixing_b.shape
        else math.inf
    )
    denoised_difference = max_image_difference(full_denoised, nss_denoised)
    if not metrics_identical or mixing_difference != 0 or denoised_difference != 0:
        raise ValueError(f"NSS=0 matched FastICA control differs: {key}")
    return {
        "n0_metrics_identical": 1,
        "n0_mixing_max_absolute_difference": mixing_difference,
        "n0_denoised_max_absolute_difference": denoised_difference,
    }, paths


def compare_run(
    project: Path, audit_root: Path, row: dict[str, str]
) -> tuple[dict[str, Any], list[Path]]:
    key = row["run_key"]
    historical, inputs = historical_summary(project, row)
    summaries = {}
    for config in CONFIGS:
        summary, paths = summarize_decomposition(
            audit_root / "benchmark" / config / key, key
        )
        summaries[config] = summary
        inputs.extend(paths)
    full = summaries["full-fastica"]
    fast = summaries["nss-fastica"]
    robust = summaries["nss-robustica"]
    pca_contract = all(fast[name] == robust[name] for name in (
        "pca_components",
        "aic_components",
        "kic_components",
        "mdl_components",
        "varex_90_components",
        "varex_95_components",
    ))
    if not pca_contract:
        raise ValueError(f"FastICA/RobustICA PCA contract differs: {key}")
    identity, identity_inputs = n0_identity(audit_root, row)
    inputs.extend(identity_inputs)
    output: dict[str, Any] = {
        "subject": row["subject"],
        "session": row["session"],
        "task": row["task"],
        "run": row["run"],
        "run_key": key,
        "nss_count": int(row["nss_count"]),
        "number_of_original_volumes": int(row["number_of_original_volumes"]),
        "number_of_steady_state_volumes": int(row["number_of_steady_state_volumes"]),
        "software_versions": row.get("software_versions", ""),
        "selection_reason": row.get("selection_reason", ""),
        **{f"historical_{name}": historical[name] for name in COUNT_METRICS[:4]},
        **{f"full_fastica_{name}": full[name] for name in COUNT_METRICS},
        **{f"nss_fastica_{name}": fast[name] for name in COUNT_METRICS},
        **{f"nss_robustica_{name}": robust[name] for name in COUNT_METRICS},
        **{f"nss_minus_full_{name}": fast[name] - full[name] for name in COUNT_METRICS},
        **{
            f"robustica_minus_fastica_{name}": robust[name] - fast[name]
            for name in COUNT_METRICS[:4]
        },
        "nss_fastica_pca_minus_ica_components": fast["pca_components"]
        - fast["ica_components"],
        "nss_robustica_pca_minus_ica_components": robust["pca_components"]
        - robust["ica_components"],
        "nss_fastica_robustica_pca_contract_identical": int(pca_contract),
        **identity,
    }
    flags = {
        "nss_changes_pca_by_at_least_5": abs(output["nss_minus_full_pca_components"]) >= 5,
        "nss_changes_rejected_by_at_least_5": abs(output["nss_minus_full_rejected_components"]) >= 5,
        "robustica_changes_ica_count_by_at_least_10": abs(
            output["robustica_minus_fastica_ica_components"]
        )
        >= 10,
        "robustica_changes_rejected_by_at_least_10": abs(
            output["robustica_minus_fastica_rejected_components"]
        )
        >= 10,
    }
    output.update({f"flag_{name}": int(value) for name, value in flags.items()})
    output["review_reasons"] = ";".join(name for name, value in flags.items() if value)
    return output, inputs


def median_iqr(rows: Sequence[dict[str, Any]], column: str) -> str:
    values = np.array([float(row[column]) for row in rows], dtype=float)
    return (
        f"{np.median(values):.2f} "
        f"(IQR {np.quantile(values, 0.25):.2f} to {np.quantile(values, 0.75):.2f})"
    )


def plot_rows(rows: Sequence[dict[str, Any]], path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    axes[0, 0].scatter(
        [row["full_fastica_pca_components"] for row in rows],
        [row["nss_fastica_pca_components"] for row in rows],
        c=[row["nss_count"] for row in rows],
        cmap="viridis",
        s=24,
    )
    upper = max(
        max(row["full_fastica_pca_components"], row["nss_fastica_pca_components"])
        for row in rows
    )
    axes[0, 0].plot([0, upper], [0, upper], color="black", linewidth=1)
    axes[0, 0].set(xlabel="Full FastICA PCA count", ylabel="NSS-aware FastICA PCA count")
    axes[0, 1].hist(
        [row["nss_minus_full_pca_components"] for row in rows], bins=20, color="#0072B2"
    )
    axes[0, 1].set(xlabel="NSS-aware minus full PCA count", ylabel="Runs")
    axes[1, 0].scatter(
        [row["nss_fastica_ica_components"] for row in rows],
        [row["nss_robustica_ica_components"] for row in rows],
        s=24,
        color="#D55E00",
    )
    axes[1, 0].plot([0, upper], [0, upper], color="black", linewidth=1)
    axes[1, 0].set(xlabel="NSS-aware FastICA count", ylabel="NSS-aware RobustICA count")
    axes[1, 1].scatter(
        [row["nss_fastica_pca_components"] for row in rows],
        [row["nss_fastica_rejected_components"] for row in rows],
        label="FastICA",
        s=22,
    )
    axes[1, 1].scatter(
        [row["nss_robustica_pca_components"] for row in rows],
        [row["nss_robustica_rejected_components"] for row in rows],
        label="RobustICA",
        s=22,
    )
    axes[1, 1].set(xlabel="PCA-selected components", ylabel="Rejected ICA components")
    axes[1, 1].legend()
    for axis in axes.ravel():
        axis.grid(alpha=0.2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
    apply_umask_mode(path)


def make_report(rows: Sequence[dict[str, Any]], path: Path) -> None:
    n0 = [row for row in rows if int(row["nss_count"]) == 0]
    lines = [
        "# Matched TEDANA Dimensionality Report",
        "",
        "This report is audit evidence, not a production-method decision.",
        "",
        "## Design",
        "",
        f"- Sentinel runs: {len(rows)}",
        f"- NSS=0 exact controls: {len(n0)}",
        "- FULL-FastICA and NSS-FastICA use identical fMRIPrep echoes, explicit native mask, curvefit, AIC, seed 42, `tedana_orig`, and FastICA. Only `--dummy-scans 0` versus the validated run-specific NSS count differs.",
        "- NSS-FastICA and NSS-RobustICA have an identical PCA contract. Their final ICA count can differ because RobustICA clusters stable components after the shared PCA step.",
        "- Historical production versus FULL-FastICA remains descriptive because the historical command did not explicitly pass the same fMRIPrep mask.",
        "",
        "## Matched NSS Effect",
        "",
        f"- NSS-aware minus full PCA count: {median_iqr(rows, 'nss_minus_full_pca_components')}",
        f"- NSS-aware minus full rejected count: {median_iqr(rows, 'nss_minus_full_rejected_components')}",
        f"- Runs with absolute PCA-count change >=5: {sum(row['flag_nss_changes_pca_by_at_least_5'] for row in rows)}",
        f"- Runs with absolute rejected-count change >=5: {sum(row['flag_nss_changes_rejected_by_at_least_5'] for row in rows)}",
        "",
        "## RobustICA Effect After Matched PCA",
        "",
        f"- RobustICA minus FastICA final ICA count: {median_iqr(rows, 'robustica_minus_fastica_ica_components')}",
        f"- RobustICA minus FastICA rejected count: {median_iqr(rows, 'robustica_minus_fastica_rejected_components')}",
        f"- Runs with absolute final-count change >=10: {sum(row['flag_robustica_changes_ica_count_by_at_least_10'] for row in rows)}",
        f"- Runs with absolute rejected-count change >=10: {sum(row['flag_robustica_changes_rejected_by_at_least_10'] for row in rows)}",
        "",
        "## Interpretation Gate",
        "",
        "Use `paired_dimensionality.tsv` together with the cohort design-burden audit, denoising QC, Motion24 audit, and component review. If matched NSS handling materially changes PCA counts, the report contains a reproducible versioned test case for upstream discussion. If it does not, investigate scanner-era signal properties and PCA criterion choice rather than attributing high dimensionality to NSS handling.",
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
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    sentinels = read_tsv(args.sentinel_tsv)
    if not sentinels or len({row["run_key"] for row in sentinels}) != len(sentinels):
        raise ValueError("sentinel manifest is empty or contains duplicate run keys")
    if args.dry_run:
        print(f"Would summarize matched dimensionality for {len(sentinels)} sentinel run(s).")
        print("Required configurations: full-fastica, nss-fastica, nss-robustica")
        print(f"Tracked output: {output}")
        return 0
    if output.exists() and not args.overwrite:
        raise ValueError(f"output exists; review it or use --overwrite: {output}")
    rows = []
    inputs = [args.sentinel_tsv.resolve()]
    for index, sentinel in enumerate(sentinels, start=1):
        row, paths = compare_run(project, audit_root, sentinel)
        rows.append(row)
        inputs.extend(paths)
        print(f"Summarized {index}/{len(sentinels)} {sentinel['run_key']}", flush=True)
    review = [row for row in rows if row["review_reasons"]]
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tedana-dimensionality-", dir=output.parent) as temp:
        stage = Path(temp)
        write_tsv(stage / "paired_dimensionality.tsv", rows, COLUMNS)
        write_tsv(stage / "review_runs.tsv", review, COLUMNS)
        plot_rows(rows, stage / "figures" / "matched_dimensionality.png")
        make_report(rows, stage / "report.md")
        provenance = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "sentinel_manifest": args.sentinel_tsv.resolve().relative_to(project).as_posix(),
            "sentinel_manifest_sha256": sha256(args.sentinel_tsv),
            "sentinel_count": len(sentinels),
            "configurations": list(CONFIGS),
            "input_inventory_digest_path_size_mtime": inventory_digest(inputs, project),
            "production_derivatives_modified": False,
            "task_regressors_used": False,
            "historical_comparison_is_matched": False,
            "full_vs_nss_fastica_comparison_is_matched": True,
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
    print(f"Matched dimensionality rows: {len(rows)}")
    print(f"Review rows: {len(review)}")
    print(f"Tracked report: {output / 'report.md'}")
    return 0


def check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    provenance_path = output / "provenance.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    failures = [] if provenance else [f"missing:{provenance_path}"]
    sentinels = read_tsv(args.sentinel_tsv)
    expected = {row["run_key"] for row in sentinels}
    paired_path = output / "paired_dimensionality.tsv"
    if paired_path.is_file():
        rows = read_tsv(paired_path)
        if len(rows) != len(sentinels) or {row["run_key"] for row in rows} != expected:
            failures.append("paired_dimensionality_coverage")
        if any(row["nss_fastica_robustica_pca_contract_identical"] != "1" for row in rows):
            failures.append("pca_contract_identity")
    else:
        failures.append(f"missing:{paired_path}")
    for item in OUTPUTS:
        path = output / item
        if not path.is_file():
            failures.append(f"missing:{path}")
        elif item.name != "provenance.json" and provenance.get("outputs", {}).get(
            item.as_posix()
        ) != sha256(path):
            failures.append(f"checksum:{path}")
    if provenance.get("sentinel_manifest_sha256") != sha256(args.sentinel_tsv):
        failures.append("sentinel_manifest_checksum")
    try:
        live_inputs = [args.sentinel_tsv.resolve()]
        for row in sentinels:
            _summary, paths = compare_run(project, audit_root, row)
            live_inputs.extend(paths)
        if provenance.get(
            "input_inventory_digest_path_size_mtime"
        ) != inventory_digest(live_inputs, project):
            failures.append("live_input_inventory")
    except (OSError, ValueError, KeyError) as exc:
        failures.append(f"live_input_inventory:{exc}")
    for failure in failures:
        print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: {len(failures)} dimensionality-summary issue(s).")
        return 1
    print(f"CHECK PASSED: matched TEDANA dimensionality validated for {len(sentinels)} run(s).")
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
            default=project / "qc" / "tedana_audit" / "dimensionality",
        )
    build_parser = subparsers.choices["build"]
    build_parser.add_argument("--overwrite", action="store_true")
    build_parser.add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return build(args) if args.command == "build" else check(args)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
