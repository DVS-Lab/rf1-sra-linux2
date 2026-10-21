#!/usr/bin/env python3
"""Frozen, resumable cohort-wide AIC/KIC/MDL experiments; never production edits."""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd

from audit_tedana import (
    TASK_TO_PARADIGM, command_version, detect_nss, pad_mixing_matrix,
    require_audit_destination, sha256, utc_now,
)
from audit_tedana_design import parse_mapca, selected_base_confounds
from benchmark_tedana import build_job, expected_files
from build_run_qc import inventory_bids_runs
from summarize_tedana_benchmark import component_summary


CONFIGS = ("nss-fastica", "nss-kic-fastica", "nss-mdl-fastica")
THREAD_ENV = {name: "1" for name in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
)}


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def write_table(path, rows, columns):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


@contextmanager
def exclusive(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".cohort.lock").open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another cohort command is active; no files changed") from exc
        yield handle


def signature(path):
    stat = path.stat()
    result = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if not path.name.endswith(".nii.gz"):
        result["sha256"] = sha256(path)
    return result


def current_signatures(project, row):
    return {name: signature(project / name) for name in row["inputs"]}


def inspect_run(project, key, bold_paths):
    if len(bold_paths) != 1:
        raise ValueError("ambiguous BIDS echo-2 input")
    prefix = key.prefix
    func = project / "bids" / f"sub-{key.subject}" / f"ses-{key.session}" / "func"
    preproc = project / "derivatives/fmriprep" / f"sub-{key.subject}" / f"ses-{key.session}" / "func"
    echoes = [preproc / f"{prefix}_echo-{i}_part-mag_desc-preproc_bold.nii.gz" for i in range(1, 5)]
    sidecars = [func / f"{prefix}_echo-{i}_part-mag_bold.json" for i in range(1, 5)]
    mask = preproc / f"{prefix}_part-mag_desc-brain_mask.nii.gz"
    confounds = preproc / f"{prefix}_part-mag_desc-confounds_timeseries.tsv"
    paths = [*bold_paths, *echoes, *sidecars, mask, confounds]
    for path in paths:
        if not path.is_file():
            raise ValueError(f"missing input: {path.relative_to(project)}")
    before = {str(p.relative_to(project)): signature(p) for p in paths}
    reference = nib.load(echoes[0])
    if len(reference.shape) != 4:
        raise ValueError("preprocessed echo is not 4D")
    total = reference.shape[3]
    if nib.load(bold_paths[0]).shape[-1] != total:
        raise ValueError("BIDS/preprocessed volume count mismatch")
    for path in echoes:
        image = nib.load(path)
        if image.shape != reference.shape or not np.allclose(image.affine, reference.affine):
            raise ValueError("preprocessed echo geometry mismatch")
        if not np.isclose(image.header.get_zooms()[3], reference.header.get_zooms()[3]):
            raise ValueError("preprocessed echo TR mismatch")
    image = nib.load(mask)
    if image.shape != reference.shape[:3] or not np.allclose(image.affine, reference.affine):
        raise ValueError("mask/echo geometry mismatch")
    mask_data = np.asanyarray(image.dataobj)
    if not np.isfinite(mask_data).all() or not np.any(mask_data > 0):
        raise ValueError("empty or nonfinite mask")
    metadata = [json.loads(p.read_text()) for p in sidecars]
    tes = [float(m["EchoTime"]) for m in metadata]
    if not all(np.isfinite(t) and 0 < t < 1 for t in tes) or not all(np.diff(tes) > 0):
        raise ValueError("EchoTime must be increasing seconds in (0,1)")
    frame = pd.read_csv(confounds, sep="\t")
    nss = detect_nss(frame)
    if len(frame) != total or nss.issue or nss.count is None or total - nss.count < 2:
        raise ValueError(f"confounds/NSS mismatch: {nss.issue}")
    row = {
        "subject": key.subject, "session": key.session, "task": key.task, "run": key.run,
        "run_key": prefix, "number_of_original_volumes": total, "nss_count": nss.count,
        "software_versions": str(metadata[0].get("SoftwareVersions", "unknown")),
        "echo_times": ";".join(map(str, tes)),
        "echo_files": ";".join(str(p.relative_to(project)) for p in echoes),
        "fmriprep_mask": str(mask.relative_to(project)),
        "fmriprep_confounds": str(confounds.relative_to(project)), "inputs": before,
    }
    if current_signatures(project, row) != before:
        raise ValueError("inputs changed during inventory")
    return row


def inventory(project, excluded_root):
    if not (project / "bids").is_dir() or not excluded_root.is_dir():
        raise ValueError("BIDS and source-exclusion roots must both exist")
    found, excluded = inventory_bids_runs(project / "bids", set(TASK_TO_PARADIGM), excluded_root)
    if not found:
        raise ValueError("no acquired BIDS runs found")
    return found, excluded


def prepare(args, project, root):
    found, excluded = inventory(project, args.excluded_source_root)
    rows, blocked = [], []
    for index, (key, paths) in enumerate(sorted(found.items()), 1):
        try:
            rows.append(inspect_run(project, key, paths))
        except Exception as exc:
            blocked.append({"run_key": key.prefix, "reason": str(exc)})
        if index % 100 == 0:
            print(f"INVENTORY {index}/{len(found)}", flush=True)
    manifest = {"schema": 1, "project_root": str(project), "configs": list(CONFIGS),
                "source_excluded": sorted(excluded), "rows": rows, "blocked": blocked}
    path = root / "manifest.json"
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError("frozen manifest differs; preserve this experiment and use a new --audit-root")
    else:
        write_json(path, manifest)
    write_table(root / "blocked.tsv", blocked, ("run_key", "reason"))
    print(f"Acquired runs: {len(found)}; processable: {len(rows)}; blocked: {len(blocked)}")
    print(f"Source-excluded subjects omitted: {len(excluded)}")
    print(f"Matched AIC/KIC/MDL jobs: {len(rows) * len(CONFIGS)}")
    print(f"Private manifest: {path}")
    print("No QC flags or task-analysis holds were used to select runs. No eligibility changed.")
    print("New experiment: legacy benchmarks remain untouched, not assumed current or reused.")
    return 1 if blocked else 0


def load_manifest(args, project, root):
    manifest = json.loads((root / "manifest.json").read_text())
    if (manifest.get("schema") != 1 or manifest.get("project_root") != str(project)
            or manifest.get("configs") != list(CONFIGS) or not manifest.get("rows")):
        raise ValueError("invalid or incompatible manifest; run prepare first")
    found, excluded = inventory(project, args.excluded_source_root)
    expected = {k.prefix for k in found}
    listed = [row["run_key"] for row in manifest["rows"] + manifest["blocked"]]
    if len(set(listed)) != len(listed) or set(listed) != expected or sorted(excluded) != manifest["source_excluded"]:
        raise ValueError("live BIDS roster/source exclusions differ from frozen manifest")
    if manifest["blocked"]:
        raise ValueError("manifest has blocked runs; inspect blocked.tsv before launching")
    for row in manifest["rows"]:
        if not re.fullmatch(r"sub-\d+_ses-\d+_task-(sharedreward|trust|ugr|socialdoors|doors)_run-\d+", row["run_key"]):
            raise ValueError("invalid run key")
        for name in row["inputs"]:
            if Path(name).is_absolute() or project not in (project / name).resolve().parents:
                raise ValueError("input path escapes project")
        if current_signatures(project, row) != row["inputs"]:
            raise ValueError(f"inputs changed: {row['run_key']}; use a new experiment")
    return manifest


def job_for(project, root, command, row, config):
    return build_job(project, root, command, command, root / "unused-tree.json", row, config)


def contract(job, version):
    return {"schema": 1, "tedana_version": version, "command": list(job.command),
            "inputs": job.row["inputs"], "nss_count": job.row["nss_count"],
            "number_of_original_volumes": job.row["number_of_original_volumes"]}


def output_signatures(job):
    return {p.name: signature(p) for p in sorted(job.output_dir.iterdir())
            if p.is_file() and p.name != "cohort_success.json"}


def validate_products(job):
    for path in expected_files(job):
        if not path.is_file():
            raise ValueError(f"missing output: {path.name}")
    prefix = job.run_key
    raw = pd.read_csv(job.output_dir / f"{prefix}_desc-ICA_mixing.tsv", sep="\t")
    metrics = pd.read_csv(job.output_dir / f"{prefix}_desc-tedana_metrics.tsv", sep="\t")
    n, nss = int(job.row["number_of_original_volumes"]), int(job.row["nss_count"])
    if len(raw) != n - nss or raw.shape[1] == 0 or not np.isfinite(raw.to_numpy(float)).all():
        raise ValueError("invalid ICA mixing dimensions/values")
    if len(metrics) != raw.shape[1] or "Component" not in metrics or list(metrics.Component) != list(raw.columns):
        raise ValueError("component labels/count differ between mixing and metrics")
    if not metrics.classification.isin(["accepted", "rejected", "ignored"]).all():
        raise ValueError("unknown component classification")
    component_summary(job.output_dir / f"{prefix}_desc-tedana_metrics.tsv")
    pca = pd.read_csv(job.output_dir / f"{prefix}_desc-PCA_metrics.tsv", sep="\t")
    mapca = parse_mapca(job.output_dir / f"{prefix}_desc-PCACrossComponent_metrics.json")
    criterion = {"nss-fastica": "aic", "nss-kic-fastica": "kic", "nss-mdl-fastica": "mdl"}[job.config]
    if int(mapca[f"{criterion}_components"]) != len(pca) or len(pca) != len(metrics):
        raise ValueError("selected PCA/ICA counts differ from requested criterion")
    reference = nib.load(job.project_root / job.row["echo_files"].split(";")[0])
    optcom = job.output_dir / f"{prefix}_desc-optcom_bold.nii.gz"
    for path in [optcom, job.output_dir / f"{prefix}_desc-denoised_bold.nii.gz"]:
        image = nib.load(path)
        if image.shape != (*reference.shape[:3], n - nss) or not np.allclose(image.affine, reference.affine):
            raise ValueError("output image geometry/length differs from steady-state input")
        if not np.isclose(image.header.get_zooms()[3], reference.header.get_zooms()[3]):
            raise ValueError("output TR differs")
        if path != optcom and not np.isfinite(np.asanyarray(image.dataobj)).all():
            raise ValueError("nonfinite denoised image")
    values = np.ascontiguousarray(np.asanyarray(nib.load(optcom).dataobj))
    if not np.isfinite(values).all():
        raise ValueError("nonfinite optimally combined image")
    digest = hashlib.sha256(values.dtype.str.encode() + str(values.shape).encode())
    digest.update(memoryview(values).cast("B"))
    return raw, metrics, digest.hexdigest()


def cached_success(job, version):
    path = job.output_dir / "cohort_success.json"
    saved = json.loads(path.read_text())
    if saved["contract"] != contract(job, version):
        raise ValueError("completion contract differs")
    if saved["outputs"] != output_signatures(job):
        raise ValueError("completed outputs changed")
    return saved


def run_one(job, version, retry_failed, min_free_gib, lock_fd):
    started = time.monotonic()
    try:
        if current_signatures(job.project_root, job.row) != job.row["inputs"]:
            raise ValueError("inputs changed after preflight")
        if (job.output_dir / "cohort_success.json").exists():
            cached_success(job, version)
            return {"run_key": job.run_key, "config": job.config, "status": "SKIPPED_COMPLETE"}
        if shutil.disk_usage(job.output_dir.parents[2]).free < min_free_gib * 1024**3:
            raise ValueError("free space below reserve; no new job launched")
        if job.output_dir.exists():
            if not retry_failed:
                raise ValueError("partial output exists; inspect it, then use --retry-failed to archive and retry")
            archive = job.output_dir.parents[2] / "failed-attempts" / job.config
            archive.mkdir(parents=True, exist_ok=True)
            job.output_dir.rename(archive / f"{job.run_key}-{uuid.uuid4().hex}")
        job.output_dir.mkdir(parents=True)
        # Logs live inside the attempt directory so failed-attempt archives preserve them.
        with (job.output_dir / "console.log").open("w") as handle:
            handle.write("COMMAND: " + shlex.join(job.command) + "\n")
            handle.flush()
            print(f"STARTED {job.config} {job.run_key}", flush=True)
            result = subprocess.run(job.command, stdout=handle, stderr=subprocess.STDOUT,
                                    env={**os.environ, **THREAD_ENV}, pass_fds=(lock_fd,))
        if result.returncode:
            raise ValueError(f"TEDANA exit {result.returncode}; see private console.log")
        raw, _metrics, optcom_hash = validate_products(job)
        padded = pad_mixing_matrix(raw, int(job.row["number_of_original_volumes"]), int(job.row["nss_count"]))
        padded.to_csv(job.output_dir / f"{job.run_key}_desc-ICA_mixingFullGrid.tsv", sep="\t", index=False)
        if current_signatures(job.project_root, job.row) != job.row["inputs"]:
            raise ValueError("inputs changed during execution")
        write_json(job.output_dir / "cohort_success.json", {
            "contract": contract(job, version), "outputs": output_signatures(job),
            "optcom_data_sha256": optcom_hash, "completed_at": utc_now(),
            "elapsed_seconds": round(time.monotonic() - started, 2),
        })
        return {"run_key": job.run_key, "config": job.config, "status": "COMPLETED"}
    except Exception as exc:
        return {"run_key": job.run_key, "config": job.config, "status": "FAILED", "reason": str(exc)}


def run_jobs(args, project, root, manifest, version, lock_fd):
    write_json(root / "validation.json", {"validated": False, "status": "running", "time": utc_now()})
    jobs = [job_for(project, root, args.tedana_command, row, config)
            for row in manifest["rows"] for config in CONFIGS]
    print(f"Queued {len(jobs)} jobs, {args.jobs} workers, 1 BLAS/ICA thread per worker", flush=True)
    statuses = []
    with (root / "progress.jsonl").open("a", buffering=1) as progress:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            pending = {executor.submit(run_one, j, version, args.retry_failed, args.min_free_gib, lock_fd) for j in jobs}
            while pending:
                done, pending = wait(pending, timeout=60, return_when=FIRST_COMPLETED)
                for future in done:
                    status = future.result()
                    statuses.append(status)
                    progress.write(json.dumps({**status, "time": utc_now()}) + "\n")
                    print(f"{status['status']} {status['config']} {status['run_key']} ({len(statuses)}/{len(jobs)})", flush=True)
                if not done:
                    print(f"HEARTBEAT finished={len(statuses)}/{len(jobs)} pending_or_running={len(pending)}", flush=True)
    write_table(root / "status.tsv", statuses, ("run_key", "config", "status", "reason"))
    failures = sum(s["status"] == "FAILED" for s in statuses)
    print(f"Complete or preserved: {len(statuses) - failures}/{len(jobs)}; failures: {failures}")
    return 1 if failures else check(args, project, root, manifest, version)


def check(args, project, root, manifest, version):
    write_json(root / "validation.json", {"validated": False, "status": "checking", "time": utc_now()})
    load_manifest(args, project, root)
    rows, failures = [], []
    for index, row in enumerate(manifest["rows"], 1):
        hashes = []
        for config in CONFIGS:
            job = job_for(project, root, args.tedana_command, row, config)
            try:
                saved = cached_success(job, version)
                raw, metrics, digest = validate_products(job)
                if digest != saved["optcom_data_sha256"]:
                    raise ValueError("optcom content changed")
                hashes.append(digest)
                padded = pd.read_csv(job.output_dir / f"{job.run_key}_desc-ICA_mixingFullGrid.tsv", sep="\t")
                expected = pad_mixing_matrix(raw, int(row["number_of_original_volumes"]), int(row["nss_count"]))
                if list(padded.columns) != list(expected.columns) or padded.shape != expected.shape or not np.allclose(padded, expected):
                    raise ValueError("full-grid mixing is not correctly zero padded")
                base = selected_base_confounds(project / row["fmriprep_confounds"])
                rejected = padded.loc[:, metrics.loc[metrics.classification == "rejected", "Component"]]
                base_values = np.column_stack([np.ones(len(base)), base.to_numpy(float)])
                rank_base = int(np.linalg.matrix_rank(base_values))
                rank_combined = int(np.linalg.matrix_rank(np.column_stack([base_values, rejected.to_numpy(float)])))
                component, _ = component_summary(job.output_dir / f"{job.run_key}_desc-tedana_metrics.tsv")
                rows.append({**{k: row[k] for k in ("subject", "session", "task", "run", "run_key", "software_versions")},
                             "config": config, "pca_components": len(metrics),
                             "total_components": len(metrics), "rejected_components": rejected.shape[1],
                             "accepted_components": int((metrics.classification == "accepted").sum()),
                             "rejected_fraction": rejected.shape[1] / len(metrics),
                             "rejected_normalized_variance": component["rejected_normalized_variance"],
                             "accepted_normalized_variance": component["accepted_normalized_variance"],
                             "base_rank_with_intercept": rank_base, "combined_rank_with_intercept": rank_combined,
                             "tedana_incremental_rank": rank_combined - rank_base,
                             "residual_df_before_task": len(base) - rank_combined})
            except Exception as exc:
                failures.append({"run_key": row["run_key"], "config": config, "reason": str(exc)})
        if len(set(hashes)) > 1:
            failures.append({"run_key": row["run_key"], "config": "paired", "reason": "optcom inputs differ across PCA variants"})
        if current_signatures(project, row) != row["inputs"]:
            failures.append({"run_key": row["run_key"], "config": "all", "reason": "inputs changed during check"})
        if index % 25 == 0 or index == len(manifest["rows"]):
            print(f"CHECKED {index}/{len(manifest['rows'])} runs; findings={len(failures)}", flush=True)
    if rows:
        write_table(root / "component_summary.tsv", rows, tuple(rows[0]))
    write_table(root / "check_failures.tsv", failures, ("run_key", "config", "reason"))
    result = {"time": utc_now(), "validated": not failures,
              "expected_runs": len(manifest["rows"]), "expected_jobs": len(manifest["rows"]) * 3,
              "summary_rows": len(rows), "failures": len(failures), "manifest_sha256": sha256(root / "manifest.json")}
    write_json(root / "validation.json", result)
    if not failures:
        frame = pd.DataFrame(rows)
        for config, group in frame.groupby("config"):
            print(f"SUMMARY {config}: runs={len(group)} median_ICA={group.total_components.median():.1f} "
                  f"median_rejected={group.rejected_components.median():.1f} "
                  f"median_incremental_rank={group.tedana_incremental_rank.median():.1f}")
    print(f"CHECK {'FAILED' if failures else 'PASSED'}: {len(rows)}/{len(manifest['rows']) * 3} method/run outputs; {len(failures)} findings")
    print("This validates experiment products, not task-model efficiency or a production method change.")
    return 1 if failures else 0


def parser():
    project = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("prepare", "run", "check"))
    result.add_argument("--project-root", type=Path, default=project)
    result.add_argument("--audit-root", type=Path)
    result.add_argument("--excluded-source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    result.add_argument("--tedana-command", type=Path, default=Path("/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/tedana"))
    result.add_argument("--jobs", type=int, default=8)
    result.add_argument("--min-free-gib", type=float, default=100)
    result.add_argument("--retry-failed", action="store_true")
    return result


def main():
    args = parser().parse_args()
    try:
        project = args.project_root.resolve()
        root = require_audit_destination(project, args.audit_root or project / "derivatives/tedana-audit/cohort-pca-v1", "large")
        if root == (project / "derivatives/tedana-audit").resolve():
            raise ValueError("use a dedicated audit subdirectory")
        if args.jobs < 1 or not np.isfinite(args.min_free_gib) or args.min_free_gib < 0:
            raise ValueError("invalid worker count or disk reserve")
        args.tedana_command = args.tedana_command.resolve()
        with exclusive(root) as lock:
            if args.command == "prepare":
                return prepare(args, project, root)
            write_json(root / "validation.json", {"validated": False, "status": "preflight", "time": utc_now()})
            version = command_version(args.tedana_command)
            if version != "26.0.3":
                raise ValueError(f"requires TEDANA 26.0.3, found {version}")
            manifest = load_manifest(args, project, root)
            if args.command == "run":
                return run_jobs(args, project, root, manifest, version, lock.fileno())
            return check(args, project, root, manifest, version)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
