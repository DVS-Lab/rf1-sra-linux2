#!/usr/bin/env python3
"""Run isolated TEDANA sentinel benchmarks under derivatives/tedana-audit."""

from __future__ import annotations

import argparse
import csv
import importlib.resources
import json
import os
import shlex
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import nibabel as nib
import numpy as np
import pandas as pd

from audit_tedana import (
    MOTION24_COLUMNS,
    command_version,
    motion24,
    pad_mixing_matrix,
    require_audit_destination,
    restore_temporal_grid,
    validate_temporal_grid,
)
from pipeline_utils import apply_umask_mode


DEFAULT_CONFIGS = (
    "t2s-full",
    "t2s-exclude-nss",
    "nss-fastica",
    "nss-robustica",
)
MOTION_CONFIGS = ("motion-fastica", "motion-robustica")


@dataclass(frozen=True)
class Job:
    run_key: str
    config: str
    command: tuple[str, ...]
    output_dir: Path
    log_path: Path
    row: dict[str, str]
    project_root: Path


def parse_configs(value: str) -> tuple[str, ...]:
    configs = tuple(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    allowed = set(DEFAULT_CONFIGS + MOTION_CONFIGS)
    invalid = sorted(set(configs) - allowed)
    if invalid:
        raise argparse.ArgumentTypeError(f"unknown benchmark configuration(s): {', '.join(invalid)}")
    return configs


def read_sentinels(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    required = {
        "run_key",
        "nss_count",
        "number_of_original_volumes",
        "echo_times",
        "echo_files",
        "fmriprep_mask",
    }
    missing = required - set(rows[0] if rows else ())
    if missing:
        raise ValueError(f"sentinel manifest missing columns: {', '.join(sorted(missing))}")
    if len({row["run_key"] for row in rows}) != len(rows):
        raise ValueError("sentinel manifest contains duplicate run keys")
    return rows


def resolve_project_paths(project_root: Path, value: str) -> list[Path]:
    return [project_root / part for part in value.split(";") if part]


def make_motion_file(project_root: Path, row: dict[str, str], output: Path) -> None:
    confounds = project_root / row["fmriprep_confounds"]
    frame = pd.read_csv(confounds, sep="\t")
    matrix = motion24(frame)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(matrix, columns=MOTION24_COLUMNS).to_csv(output, sep="\t", index=False)
    apply_umask_mode(output)


def make_motion_tree(output: Path) -> None:
    resource = importlib.resources.files("tedana").joinpath(
        "resources", "decision_trees", "tedana_orig.json"
    )
    base = json.loads(resource.read_text())
    nodes = json.loads(json.dumps(base["nodes"]))
    base["tree_id"] = "rf1_tedana_orig_motion24_audit"
    base["info"] = (
        str(base.get("info", ""))
        + " RF1 audit copy: calculates Motion24 external-regressor metrics without using them in any decision node."
    ).strip()
    base["external_regressor_config"] = [
        {
            "regress_ID": "motion24",
            "info": "Fits the 24 rigid-body motion expansion as one F-test model.",
            "report": "Motion24 resemblance was calculated for audit only and did not affect classification.",
            "detrend": True,
            "statistic": "F",
            "regressors": ["^.*$"],
        }
    ]
    for metric in (
        "Fstat motion24 model",
        "pval motion24 model",
        "R2stat motion24 model",
    ):
        if metric not in base["necessary_metrics"]:
            base["necessary_metrics"].append(metric)
    if base["nodes"] != nodes:
        raise ValueError("motion audit tree changed canonical tedana_orig nodes")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n")
    apply_umask_mode(output)


def expected_files(job: Job) -> tuple[Path, ...]:
    prefix = job.row["run_key"]
    if job.config.startswith("t2s-"):
        return (
            job.output_dir / f"{prefix}_desc-optcom_bold.nii.gz",
            job.output_dir / f"{prefix}_T2starmap.nii.gz",
        )
    return (
        job.output_dir / f"{prefix}_desc-denoised_bold.nii.gz",
        job.output_dir / f"{prefix}_desc-ICA_mixing.tsv",
        job.output_dir / f"{prefix}_desc-tedana_metrics.tsv",
    )


def complete(job: Job) -> bool:
    return all(path.is_file() for path in expected_files(job))


def provenance_path(job: Job) -> Path:
    return job.output_dir / "rf1_audit_provenance.json"


def ensure_provenance(job: Job) -> None:
    path = provenance_path(job)
    if path.is_file():
        return
    provenance = {
        "configuration": job.config,
        "run_key": job.run_key,
        "command": list(job.command),
        "nss_count": int(job.row["nss_count"]),
        "number_of_original_volumes": int(job.row["number_of_original_volumes"]),
    }
    path.write_text(json.dumps(provenance, indent=2) + "\n")
    apply_umask_mode(path)


def build_job(
    project_root: Path,
    audit_root: Path,
    tedana_command: Path,
    t2smap_command: Path,
    tree: Path,
    row: dict[str, str],
    config: str,
    robustica_threads: int = 1,
) -> Job:
    run_key = row["run_key"]
    nss = int(row["nss_count"])
    echo_files = resolve_project_paths(project_root, row["echo_files"])
    echo_times = [value for value in row["echo_times"].split(";") if value]
    mask = project_root / row["fmriprep_mask"]
    if len(echo_files) != len(echo_times) or len(echo_files) < 3:
        raise ValueError(f"{run_key}: invalid echo files/times")
    required = [*echo_files, mask]
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"{run_key}: missing benchmark input(s): {', '.join(map(str, missing))}")
    output = audit_root / "benchmark" / config / run_key
    log = audit_root / "logs" / config / f"{run_key}.log"
    n_threads = robustica_threads if config.endswith("robustica") else 1
    base = [
        "-d",
        *map(str, echo_files),
        "-e",
        *echo_times,
        "--out-dir",
        str(output),
        "--prefix",
        run_key,
        "--convention",
        "bids",
        "--mask",
        str(mask),
        "--fittype",
        "curvefit",
        "--n-threads",
        str(n_threads),
    ]
    if config in {"t2s-full", "t2s-exclude-nss"}:
        command = [str(t2smap_command), *base, "--fitmode", "all", "--combmode", "t2s"]
        if config == "t2s-exclude-nss" and nss:
            command.extend(("--exclude", f"0:{nss}"))
    else:
        command = [
            str(tedana_command),
            *base,
            "--dummy-scans",
            str(nss),
            "--combmode",
            "t2s",
            "--tedpca",
            "aic",
            "--seed",
            "42",
            "--tree",
            "tedana_orig",
            "--verbose",
        ]
        source_method = "fastica" if config.endswith("fastica") else "robustica"
        # With --mix, TEDANA does not run ICA. TEDANA 26.0.3 nevertheless tries
        # to report uninitialized RobustICA diagnostics when robustica is named,
        # so supplied matrices must use the neutral FastICA execution path.
        command_method = "fastica" if config in MOTION_CONFIGS else source_method
        command.extend(("--ica-method", command_method))
        if command_method == "robustica":
            command.extend(("--n-robust-runs", "30"))
        if config in MOTION_CONFIGS:
            source_config = f"nss-{source_method}"
            source = audit_root / "benchmark" / source_config / run_key
            mixing = source / f"{run_key}_desc-ICA_mixing.tsv"
            motion_file = audit_root / "external" / run_key / f"{run_key}_motion24.tsv"
            if not mixing.is_file():
                raise ValueError(f"{run_key}: {config} requires completed {source_config}")
            make_motion_file(project_root, row, motion_file)
            command[command.index("tedana_orig")] = str(tree)
            command.extend(("--mix", str(mixing), "--external", str(motion_file)))
    return Job(run_key, config, tuple(command), output, log, row, project_root)


def prepare_jobs(args: argparse.Namespace) -> tuple[list[Job], Path]:
    project_root = args.project_root.resolve()
    audit_root = require_audit_destination(project_root, args.audit_root, "large")
    if command_version(args.tedana_command) != "26.0.3":
        raise ValueError("benchmark requires TEDANA 26.0.3")
    if command_version(args.t2smap_command) != "26.0.3":
        raise ValueError("benchmark requires t2smap from TEDANA 26.0.3")
    if args.robustica_threads < 1:
        raise ValueError("--robustica-threads must be at least 1")
    rows = read_sentinels(args.sentinel_tsv)
    tree = audit_root / "config" / "tedana_orig_motion24_audit.json"
    if any(config in MOTION_CONFIGS for config in args.configs):
        make_motion_tree(tree)
    jobs = [
        build_job(
            project_root,
            audit_root,
            args.tedana_command,
            args.t2smap_command,
            tree,
            row,
            config,
            args.robustica_threads,
        )
        for row in rows
        for config in args.configs
    ]
    return jobs, audit_root


def run_one(job: Job, overwrite: bool) -> tuple[Job, str]:
    if complete(job) and not overwrite:
        ensure_provenance(job)
        return job, "skipped_complete"
    if job.output_dir.exists():
        if not overwrite:
            return job, "failed_incomplete_exists"
        shutil.rmtree(job.output_dir)
    job.output_dir.mkdir(parents=True)
    job.log_path.parent.mkdir(parents=True, exist_ok=True)
    lock = job.output_dir.with_name(f".{job.output_dir.name}.lock")
    try:
        lock.mkdir()
    except FileExistsError:
        return job, "failed_locked"
    try:
        with job.log_path.open("w") as log:
            log.write("COMMAND: " + shlex.join(job.command) + "\n\n")
            log.flush()
            print(f"STARTED {job.config} {job.run_key}", flush=True)
            result = subprocess.run(job.command, stdout=log, stderr=subprocess.STDOUT)
        apply_umask_mode(job.log_path)
        if result.returncode:
            return job, f"failed_exit_{result.returncode}"
        if not complete(job):
            return job, "failed_missing_outputs"
        ensure_provenance(job)
        if job.config.startswith("nss-"):
            mixing_path = job.output_dir / f"{job.run_key}_desc-ICA_mixing.tsv"
            padded_path = job.output_dir / f"{job.run_key}_desc-ICA_mixingFullGrid.tsv"
            mixing = pd.read_csv(mixing_path, sep="\t")
            padded = pad_mixing_matrix(
                mixing,
                int(job.row["number_of_original_volumes"]),
                int(job.row["nss_count"]),
            )
            padded.to_csv(padded_path, sep="\t", index=False)
            apply_umask_mode(padded_path)
        return job, "completed"
    finally:
        lock.rmdir()


def t2s_full_reference(job: Job) -> Path:
    benchmark_root = job.output_dir.parents[1]
    return (
        benchmark_root
        / "t2s-full"
        / job.run_key
        / f"{job.run_key}_desc-optcom_bold.nii.gz"
    )


def finalize_nss_grid(job: Job) -> None:
    reference = t2s_full_reference(job)
    if not reference.is_file():
        raise ValueError(f"missing completed t2s-full reference: {reference}")
    denoised = job.output_dir / f"{job.run_key}_desc-denoised_bold.nii.gz"
    restored = job.output_dir / f"{job.run_key}_desc-denoisedFullGrid_bold.nii.gz"
    restore_temporal_grid(reference, denoised, int(job.row["nss_count"]), restored)


def run_plan(args: argparse.Namespace) -> int:
    jobs, audit_root = prepare_jobs(args)
    print(f"Sentinel benchmark jobs: {len(jobs)}")
    for config in args.configs:
        print(f"  {config}: {sum(job.config == config for job in jobs)}")
    print(f"Audit root: {audit_root}")
    print(f"RobustICA threads per job: {args.robustica_threads}")
    print("Production derivatives will not be modified.")
    if args.show_commands:
        for job in jobs:
            print(shlex.join(job.command))
    return 0


def run_benchmark(args: argparse.Namespace) -> int:
    jobs, audit_root = prepare_jobs(args)
    audit_root.mkdir(parents=True, exist_ok=True)
    statuses: list[tuple[Job, str]] = []
    print(
        f"Queued {len(jobs)} benchmark job(s) with {args.jobs} run-level worker(s); "
        f"RobustICA receives {args.robustica_threads} thread(s) per job.",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(run_one, job, args.overwrite): job for job in jobs}
        for future in as_completed(futures):
            job, status = future.result()
            statuses.append((job, status))
            print(f"{status.upper()} {job.config} {job.run_key}", flush=True)
    finalized: list[tuple[Job, str]] = []
    for job, status in statuses:
        if status.startswith("failed") or not job.config.startswith("nss-"):
            finalized.append((job, status))
            continue
        try:
            finalize_nss_grid(job)
        except Exception as exc:
            status = f"failed_full_grid:{exc}"
            print(f"FAILED_FULL_GRID {job.config} {job.run_key}: {exc}", flush=True)
        finalized.append((job, status))
    statuses = finalized
    failures = [(job, status) for job, status in statuses if status.startswith("failed")]
    summary = audit_root / "benchmark_status.tsv"
    with summary.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(("configuration", "run_key", "status", "output_dir", "log"))
        for job, status in sorted(statuses, key=lambda value: (value[0].config, value[0].run_key)):
            writer.writerow((job.config, job.run_key, status, job.output_dir, job.log_path))
    apply_umask_mode(summary)
    print(f"Completed or previously complete: {len(statuses) - len(failures)}/{len(statuses)}")
    print(f"Failures: {len(failures)}")
    return 1 if failures else 0


def image_nvolumes(path: Path) -> int:
    image = nib.load(str(path))
    if len(image.shape) != 4:
        raise ValueError(f"not 4D: {path}")
    return int(image.shape[3])


def classifications(path: Path) -> list[str]:
    frame = pd.read_csv(path, sep="\t")
    return frame["classification"].astype(str).tolist()


def run_check(args: argparse.Namespace) -> int:
    jobs, _audit_root = prepare_jobs(args)
    failures: list[str] = []
    for job in jobs:
        if not complete(job):
            failures.append(f"missing outputs: {job.config} {job.run_key}")
            continue
        provenance = provenance_path(job)
        if not provenance.is_file():
            failures.append(f"missing provenance: {job.config} {job.run_key}")
        else:
            try:
                metadata = json.loads(provenance.read_text())
                if metadata.get("configuration") != job.config:
                    raise ValueError("configuration differs")
                if metadata.get("run_key") != job.run_key:
                    raise ValueError("run key differs")
                if int(metadata.get("nss_count")) != int(job.row["nss_count"]):
                    raise ValueError("NSS count differs")
                if int(metadata.get("number_of_original_volumes")) != int(
                    job.row["number_of_original_volumes"]
                ):
                    raise ValueError("original volume count differs")
            except Exception as exc:
                failures.append(
                    f"invalid provenance: {job.config} {job.run_key}: {exc}"
                )
        total = int(job.row["number_of_original_volumes"])
        nss = int(job.row["nss_count"])
        if job.config.startswith("t2s-"):
            optcom = job.output_dir / f"{job.run_key}_desc-optcom_bold.nii.gz"
            if image_nvolumes(optcom) != total:
                failures.append(f"wrong t2s length: {job.config} {job.run_key}")
        else:
            denoised = job.output_dir / f"{job.run_key}_desc-denoised_bold.nii.gz"
            if image_nvolumes(denoised) != total - nss:
                failures.append(f"wrong tedana length: {job.config} {job.run_key}")
            if job.config.startswith("nss-"):
                restored = job.output_dir / f"{job.run_key}_desc-denoisedFullGrid_bold.nii.gz"
                padded = job.output_dir / f"{job.run_key}_desc-ICA_mixingFullGrid.tsv"
                if not restored.is_file():
                    failures.append(f"wrong restored length: {job.config} {job.run_key}")
                else:
                    try:
                        validate_temporal_grid(
                            t2s_full_reference(job),
                            denoised,
                            nss,
                            restored,
                        )
                    except Exception as exc:
                        failures.append(
                            f"invalid restored grid: {job.config} {job.run_key}: {exc}"
                        )
                if not padded.is_file():
                    failures.append(f"missing padded mixing: {job.config} {job.run_key}")
                else:
                    raw_mixing = pd.read_csv(
                        job.output_dir / f"{job.run_key}_desc-ICA_mixing.tsv", sep="\t"
                    )
                    padded_mixing = pd.read_csv(padded, sep="\t")
                    try:
                        expected_padded = pad_mixing_matrix(raw_mixing, total, nss)
                        if padded_mixing.shape != expected_padded.shape or not np.allclose(
                            padded_mixing.to_numpy(dtype=float),
                            expected_padded.to_numpy(dtype=float),
                        ):
                            raise ValueError("values differ from zero-padded raw mixing")
                    except Exception as exc:
                        failures.append(
                            f"invalid padded mixing: {job.config} {job.run_key}: {exc}"
                        )
            if job.config in MOTION_CONFIGS:
                method = "fastica" if job.config.endswith("fastica") else "robustica"
                source = job.output_dir.parents[1] / f"nss-{method}" / job.run_key
                ordinary = classifications(source / f"{job.run_key}_desc-tedana_metrics.tsv")
                audited = classifications(job.output_dir / f"{job.run_key}_desc-tedana_metrics.tsv")
                if ordinary != audited:
                    failures.append(f"motion tree changed classification: {job.config} {job.run_key}")
    for failure in failures:
        print(f"FAILED {failure}")
    if failures:
        print(f"CHECK FAILED: {len(failures)} TEDANA benchmark validation issue(s).")
        return 1
    print(f"CHECK PASSED: {len(jobs)} TEDANA benchmark job(s) validated.")
    return 0


def parser() -> argparse.ArgumentParser:
    repo = Path(__file__).resolve().parents[1]
    environment = Path("/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3")
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("plan", "run", "check"):
        child = subparsers.add_parser(name)
        child.add_argument("--project-root", type=Path, default=repo)
        child.add_argument("--sentinel-tsv", type=Path, default=repo / "qc" / "tedana_audit" / "sentinel_runs.tsv")
        child.add_argument("--audit-root", type=Path, default=repo / "derivatives" / "tedana-audit")
        child.add_argument("--tedana-command", type=Path, default=environment / "bin" / "tedana")
        child.add_argument("--t2smap-command", type=Path, default=environment / "bin" / "t2smap")
        child.add_argument("--robustica-threads", type=int, default=1)
        child.add_argument("--configs", type=parse_configs, default=DEFAULT_CONFIGS)
    subparsers.choices["plan"].add_argument("--show-commands", action="store_true")
    run = subparsers.choices["run"]
    run.add_argument("--jobs", type=int, default=2)
    run.add_argument("--overwrite", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "plan":
            return run_plan(args)
        if args.command == "run":
            if args.jobs < 1:
                raise ValueError("--jobs must be positive")
            return run_benchmark(args)
        return run_check(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
