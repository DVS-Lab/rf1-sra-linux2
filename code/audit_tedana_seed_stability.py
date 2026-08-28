#!/usr/bin/env python3
"""Select and summarize the prespecified RF1 FastICA seed stability audit."""

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
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from audit_tedana import motion24
from audit_tedana_design import matrix_diagnostics, selected_base_confounds, software_era
from audit_tedana_nuisance_qc import (
    canonical_bold,
    canonical_mask,
    finite_frame,
    image_data,
    metrics,
    nuisance_adjust,
    pair_metrics,
    rejected_matrix,
)
from pipeline_utils import apply_umask_mode, ensure_safe_child_path
from summarize_tedana_benchmark import component_summary


SEEDS = (1, 10, 42, 100, 1000)
CONFIGS = tuple(f"nss-fastica-seed-{seed}" for seed in SEEDS)
SELECTION_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_versions",
    "software_era", "nss_count", "number_of_original_volumes", "echo_times",
    "echo_files", "echo_jsons", "fmriprep_mask", "fmriprep_confounds",
    "n_ica", "rejected_fraction", "mean_fd", "tedana_incremental_rank_fraction",
    "selection_reason",
)
RUN_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_era",
    "selection_reason", "seed", "configuration", "n_ica", "n_rejected",
    "rejected_fraction", "rejected_normalized_variance", "rejected_columns",
    "rejected_rank", "combined_nuisance_rank", "incremental_nuisance_rank",
    "incremental_rank_fraction", "median_tsnr", "median_standardized_dvars",
    "fd_dvars_spearman", "fraction_high_dvars",
    "motion24_global_signal_r_squared", "variance_removed_fraction",
    "median_lag1_autocorrelation", "median_temporal_standard_deviation",
    "median_temporal_rms",
)
PAIR_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_era",
    "selection_reason", "reference_seed", "candidate_seed",
    "candidate_minus_reference_n_ica", "candidate_minus_reference_n_rejected",
    "candidate_minus_reference_rejected_fraction",
    "candidate_minus_reference_rejected_normalized_variance",
    "candidate_minus_reference_incremental_nuisance_rank",
    "candidate_minus_reference_tsnr",
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
    "metric", "n", "median", "q25", "q75", "minimum", "maximum",
    "maximum_absolute",
)
OUTPUTS = (
    Path("run_metrics.tsv"), Path("pairwise_vs_seed42.tsv"), Path("summary.tsv"),
    Path("report.md"), Path("provenance.json"),
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
        writer.writeheader(); writer.writerows(rows)
    apply_umask_mode(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def joined_candidates(current: Sequence[dict[str, str]], burden: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    burden_by_key = {
        row["run_key"]: row for row in burden if row.get("design_status") == "complete"
    }
    output = []
    for row in current:
        other = burden_by_key.get(row.get("run_key", ""))
        if row.get("audit_status") != "complete" or other is None:
            continue
        merged = dict(row)
        merged["software_era"] = software_era(row.get("software_versions", ""))
        merged["tedana_incremental_rank_fraction"] = other["tedana_incremental_rank_fraction"]
        output.append(merged)
    return output


def select_runs(candidates: Sequence[dict[str, str]], count: int = 12) -> list[dict[str, str]]:
    eras = ("E11", "XA30", "XA60")
    if count < 2 * len(eras):
        raise ValueError("selection count is too small to cover all scanner eras")
    selected: dict[str, dict[str, str]] = {}
    reasons: dict[str, list[str]] = {}

    def choose(label: str, members: Sequence[dict[str, str]], score: Callable[[dict[str, str]], float], reverse: bool) -> None:
        ordered = sorted(members, key=lambda row: (score(row), row["run_key"]), reverse=reverse)
        for row in ordered:
            if row["run_key"] not in selected:
                selected[row["run_key"]] = row
                reasons[row["run_key"]] = [label]
                return

    for era in eras:
        members = [row for row in candidates if row["software_era"] == era]
        if not members:
            raise ValueError(f"no complete candidates for scanner era {era}")
        choose(f"{era}:high_incremental_rank", members, lambda row: float(row["tedana_incremental_rank_fraction"]), True)
        median_ica = float(np.median([float(row["n_ica"]) for row in members]))
        choose(f"{era}:typical_dimensionality", members, lambda row: abs(float(row["n_ica"]) - median_ica), False)

    objectives = (
        ("high_rejected_fraction", lambda row: float(row["rejected_fraction"]), True),
        ("high_rejected_fraction", lambda row: float(row["rejected_fraction"]), True),
        ("low_motion", lambda row: float(row["mean_fd"]), False),
        ("low_motion", lambda row: float(row["mean_fd"]), False),
        ("high_motion", lambda row: float(row["mean_fd"]), True),
        ("high_motion", lambda row: float(row["mean_fd"]), True),
    )
    for label, score, reverse in objectives:
        if len(selected) >= count:
            break
        choose(label, candidates, score, reverse)
    if len(selected) < count:
        choose("deterministic_fallback", candidates, lambda row: float(row["n_ica"]), True)
    if len(selected) != count:
        raise ValueError(f"could select only {len(selected)}/{count} seed-stability runs")
    output = []
    for key in sorted(selected):
        row = {name: selected[key].get(name, "") for name in SELECTION_COLUMNS}
        row["selection_reason"] = ";".join(reasons[key])
        output.append(row)
    return output


def select(args: argparse.Namespace) -> int:
    project = args.project_root.resolve()
    destination = ensure_safe_child_path(project / "qc" / "tedana_audit", args.selection_tsv)
    candidates = joined_candidates(read_tsv(args.current_runs), read_tsv(args.design_burden))
    rows = select_runs(candidates, args.count)
    if args.dry_run:
        print(f"Would select {len(rows)} seed-stability run(s) from {len(candidates)} complete candidates.")
        for era in ("E11", "XA30", "XA60"):
            print(f"  {era}: {sum(row['software_era'] == era for row in rows)}")
        print(f"Tracked manifest: {destination}")
        return 0
    if destination.exists() and not args.overwrite:
        raise ValueError(f"selection exists; review it or use --overwrite: {destination}")
    write_tsv(destination, rows, SELECTION_COLUMNS)
    print(f"Selected seed-stability runs: {len(rows)}")
    print(f"Tracked manifest: {destination}")
    return 0


def seed_inputs(audit_root: Path, row: dict[str, str], seed: int) -> tuple[Path, Path]:
    key = row["run_key"]
    directory = audit_root / "benchmark" / f"nss-fastica-seed-{seed}" / key
    return directory / f"{key}_desc-tedana_metrics.tsv", directory / f"{key}_desc-ICA_mixingFullGrid.tsv"


def audit_run(project: Path, audit_root: Path, row: dict[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    key = row["run_key"]; nss = int(row["nss_count"]); total = int(row["number_of_original_volumes"])
    bold, mask = canonical_bold(project, row), canonical_mask(project, row)
    confounds_path = project / row["fmriprep_confounds"]
    data, _ = image_data(bold, mask)
    if len(data) != total:
        raise ValueError(f"{key}: BOLD volumes differ from seed manifest")
    confounds = pd.read_csv(confounds_path, sep="\t")
    base = selected_base_confounds(confounds_path)
    base_rank = matrix_diagnostics(base)["rank"]
    motion = motion24(confounds)[nss:]
    fd = pd.to_numeric(confounds["framewise_displacement"], errors="coerce").to_numpy(dtype=float)[nss + 1:]
    if not np.all(np.isfinite(fd)):
        raise ValueError(f"{key}: nonfinite steady-state FD")
    original = data[nss:]; adjusted = {}; run_rows = []; paths = [bold, mask, confounds_path]
    common = {name: row[name] for name in ("subject", "session", "task", "run", "run_key", "software_era", "selection_reason")}
    for seed in SEEDS:
        metrics_path, mixing_path = seed_inputs(audit_root, row, seed)
        if not metrics_path.is_file() or not mixing_path.is_file():
            raise ValueError(f"{key}: missing seed {seed} benchmark outputs")
        summary, _ = component_summary(metrics_path)
        rejected = rejected_matrix(metrics_path.parent, key, full_grid=True)
        combined = pd.concat((base, rejected), axis=1)
        values = finite_frame(combined)
        current_full, combined_rank = nuisance_adjust(data, values)
        current = current_full[nss:]
        current_metrics = metrics(original, current, fd, motion)
        rejected_rank = matrix_diagnostics(rejected)["rank"] if rejected.shape[1] else 0
        adjusted[seed] = current
        run_rows.append(
            {
                **common, "seed": seed, "configuration": f"nss-fastica-seed-{seed}",
                **summary, "rejected_columns": rejected.shape[1], "rejected_rank": rejected_rank,
                "combined_nuisance_rank": combined_rank,
                "incremental_nuisance_rank": combined_rank - base_rank,
                "incremental_rank_fraction": (combined_rank - base_rank) / total,
                **current_metrics,
            }
        )
        paths.extend((metrics_path, mixing_path))
    by_seed = {int(item["seed"]): item for item in run_rows}; reference = by_seed[42]; pair_rows = []
    for seed in SEEDS:
        candidate = by_seed[seed]
        image_metrics = pair_metrics(adjusted[42], adjusted[seed], reference, candidate)
        pair_rows.append(
            {
                **common, "reference_seed": 42, "candidate_seed": seed,
                "candidate_minus_reference_n_ica": candidate["n_ica"] - reference["n_ica"],
                "candidate_minus_reference_n_rejected": candidate["n_rejected"] - reference["n_rejected"],
                "candidate_minus_reference_rejected_fraction": candidate["rejected_fraction"] - reference["rejected_fraction"],
                "candidate_minus_reference_rejected_normalized_variance": candidate["rejected_normalized_variance"] - reference["rejected_normalized_variance"],
                "candidate_minus_reference_incremental_nuisance_rank": candidate["incremental_nuisance_rank"] - reference["incremental_nuisance_rank"],
                **image_metrics,
            }
        )
    return run_rows, pair_rows, paths


def summary_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics_to_report = PAIR_COLUMNS[9:]
    output = []
    nonreference = [row for row in rows if int(row["candidate_seed"]) != 42]
    for name in metrics_to_report:
        values = np.asarray([float(row[name]) for row in nonreference if math.isfinite(float(row[name]))])
        if not len(values):
            continue
        output.append(
            {
                "metric": name, "n": len(values), "median": np.median(values),
                "q25": np.quantile(values, 0.25), "q75": np.quantile(values, 0.75),
                "minimum": np.min(values), "maximum": np.max(values),
                "maximum_absolute": np.max(np.abs(values)),
            }
        )
    return output


def make_report(selection: Sequence[dict[str, str]], pairs: Sequence[dict[str, Any]], path: Path) -> None:
    nonreference = [row for row in pairs if int(row["candidate_seed"]) != 42]
    lines = [
        "# FastICA Seed Stability Audit", "",
        "This audit compares five prespecified FastICA seeds without matching component numbers. It evaluates classifications, independent nuisance rank, and nuisance-adjusted QC on the same canonical full-length fMRIPrep BOLD. No residualized image is written and no production derivative is modified.", "",
        "## Coverage", "", f"- Selected runs: {len(selection)}", f"- Seed/run fits: {len(pairs)}",
        f"- Non-reference comparisons against seed 42: {len(nonreference)}", "",
        "## Decision Gate", "",
        "Ordinary FastICA remains supportable only if seed changes do not materially alter nuisance rank or the final nuisance-adjusted data. Component numbering is intentionally ignored. RobustICA should be reconsidered only if this audit demonstrates consequential seed instability.",
    ]
    path.write_text("\n".join(lines) + "\n"); apply_umask_mode(path)


def build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    selection = read_tsv(args.selection_tsv)
    if args.dry_run:
        print(f"Would summarize {len(selection)} run(s) across {len(SEEDS)} FastICA seeds.")
        print(f"Expected benchmark fits: {len(selection) * len(SEEDS)}")
        print("Production derivatives will not be modified."); return 0
    if output.exists() and not args.overwrite:
        raise ValueError(f"output exists; review it or use --overwrite: {output}")
    run_rows = []; pair_rows = []; inputs = [args.selection_tsv.resolve()]
    for index, row in enumerate(selection, start=1):
        current_runs, current_pairs, paths = audit_run(project, audit_root, row)
        run_rows.extend(current_runs); pair_rows.extend(current_pairs); inputs.extend(paths)
        print(f"Audited {index}/{len(selection)} {row['run_key']}", flush=True)
    summaries = summary_rows(pair_rows); output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tedana-seeds-", dir=output.parent) as temp:
        stage = Path(temp)
        write_tsv(stage / "run_metrics.tsv", run_rows, RUN_COLUMNS)
        write_tsv(stage / "pairwise_vs_seed42.tsv", pair_rows, PAIR_COLUMNS)
        write_tsv(stage / "summary.tsv", summaries, SUMMARY_COLUMNS)
        make_report(selection, pair_rows, stage / "report.md")
        provenance = {
            "schema_version": 1, "generated_at": utc_now(),
            "selection_sha256": sha256(args.selection_tsv), "runs": len(selection),
            "seeds": list(SEEDS), "production_derivatives_modified": False,
            "production_bold_residualized": False, "outputs": {},
        }
        for item in OUTPUTS:
            if item.name != "provenance.json": provenance["outputs"][item.as_posix()] = sha256(stage / item)
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        apply_umask_mode(stage / "provenance.json")
        backup = output.with_name(f".{output.name}.backup")
        if backup.exists(): shutil.rmtree(backup)
        if output.exists(): output.rename(backup)
        stage.rename(output)
        if backup.exists(): shutil.rmtree(backup)
    print(f"Seed-stability runs: {len(selection)}"); print(f"Tracked report: {output / 'report.md'}")
    return 0


def check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    selection = read_tsv(args.selection_tsv); provenance_path = output / "provenance.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}; failures = []
    run_path, pair_path = output / "run_metrics.tsv", output / "pairwise_vs_seed42.tsv"
    if not provenance: failures.append("missing_provenance")
    if not run_path.is_file() or len(read_tsv(run_path)) != len(selection) * len(SEEDS): failures.append("run_coverage")
    if not pair_path.is_file() or len(read_tsv(pair_path)) != len(selection) * len(SEEDS): failures.append("pair_coverage")
    for item in OUTPUTS:
        path = output / item
        if not path.is_file(): failures.append(f"missing:{path}")
        elif item.name != "provenance.json" and provenance.get("outputs", {}).get(item.as_posix()) != sha256(path): failures.append(f"checksum:{path}")
    if provenance.get("selection_sha256") != sha256(args.selection_tsv): failures.append("selection_checksum")
    for failure in failures: print(f"FAILED {failure}")
    if failures: print(f"CHECK FAILED: {len(failures)} seed-stability issue(s)."); return 1
    print(f"CHECK PASSED: FastICA seed stability validated for {len(selection)} run(s)."); return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]; result = argparse.ArgumentParser(description=__doc__); children = result.add_subparsers(dest="command", required=True)
    select_parser = children.add_parser("select"); select_parser.add_argument("--project-root", type=Path, default=project)
    select_parser.add_argument("--current-runs", type=Path, default=project / "qc" / "tedana_audit" / "current_runs.tsv")
    select_parser.add_argument("--design-burden", type=Path, default=project / "qc" / "tedana_audit" / "design" / "cohort_design_burden.tsv")
    select_parser.add_argument("--selection-tsv", type=Path, default=project / "qc" / "tedana_audit" / "seeds" / "seed_runs.tsv")
    select_parser.add_argument("--count", type=int, default=12); select_parser.add_argument("--overwrite", action="store_true"); select_parser.add_argument("--dry-run", action="store_true")
    for name in ("build", "check"):
        child = children.add_parser(name); child.add_argument("--project-root", type=Path, default=project)
        child.add_argument("--selection-tsv", type=Path, default=project / "qc" / "tedana_audit" / "seeds" / "seed_runs.tsv")
        child.add_argument("--audit-root", type=Path, default=project / "derivatives" / "tedana-audit")
        child.add_argument("--output-dir", type=Path, default=project / "qc" / "tedana_audit" / "seed_stability")
    children.choices["build"].add_argument("--overwrite", action="store_true"); children.choices["build"].add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "select": return select(args)
        return build(args) if args.command == "build" else check(args)
    except Exception as exc:
        print(f"ERROR: {exc}"); return 1


if __name__ == "__main__": raise SystemExit(main())
