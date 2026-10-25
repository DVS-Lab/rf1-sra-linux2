#!/usr/bin/env python3
"""Read-only cohort AFNI characterization using the authoritative RF1 wrapper."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from build_scanner_era_qc import software_era, linear_quantile, write_tsv

ROOT = Path(__file__).resolve().parents[1]
SPACE = "MNI152NLin6Asym"
KEYS = ("subject", "session", "task", "run")
METRICS = ("classic_fwhm_x", "classic_fwhm_y", "classic_fwhm_z",
           "classic_fwhm_combined", "acf_a", "acf_b", "acf_c", "acf_effective_fwhm")
COMMAND_FLAGS = ("-ShowMeClassicFWHM", "-detrend", "-acf NULL")


def code_hashes():
    return {name: digest(Path(__file__).parent / name) for name in
            ("measure_cohort_smoothness.py", "build_scanner_era_qc.py", "pipeline_utils.py")}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stamp(path):
    stat = Path(path).stat()
    return [stat.st_size, stat.st_mtime_ns]


def read_tsv(path):
    with Path(path).open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def entities(path):
    return dict(token.split("-", 1) for token in path.name.split("_") if "-" in token)


def key_for(path):
    e = entities(path)
    return tuple(e[k] for k in ("sub", "ses", "task", "run"))


def label(row):
    return "_".join(f"{prefix}-{row[field]}" for prefix, field in
                    zip(("sub", "ses", "task", "run"), KEYS))


def inventory(project, excluded_root):
    """Union raw, QC and active non-echo MNI inputs; never silently drop a run."""
    if not excluded_root.is_dir():
        raise ValueError(f"Source-exclusion root unavailable: {excluded_root}")
    excluded = set()
    for path in excluded_root.glob("Smith-SRA-*"):
        match = re.match(r"Smith-SRA-(\d+)(?:-|$)", path.name)
        if path.is_dir() and match:
            excluded.add(match[1])
    qc = {}
    for row in read_tsv(project / "qc/run_qc.tsv"):
        key = tuple(row[k] for k in KEYS)
        if key in qc:
            raise ValueError(f"Duplicate QC run: {key}")
        qc[key] = row
    raw, preproc = defaultdict(list), defaultdict(list)
    for path in sorted((project / "bids").glob("sub-*/ses-*/func/*_bold.nii.gz")):
        e = entities(path)
        if e.get("part") not in (None, "mag") or "space" in e:
            continue
        raw[key_for(path)].append(path)
    for path in sorted((project / "derivatives/fmriprep").glob(
            f"sub-*/ses-*/func/*_space-{SPACE}*_desc-preproc_bold.nii.gz")):
        e = entities(path)
        if "echo" not in e and e.get("part") in (None, "mag") and e.get("space") == SPACE:
            preproc[key_for(path)].append(path)
    rows = []
    for key in sorted(set(raw) | set(preproc) | set(qc)):
        row = dict(zip(KEYS, key))
        if not all(re.fullmatch(r"[A-Za-z0-9]+", value) for value in key):
            raise ValueError(f"Unsafe run identifier: {key}")
        row.update(software_era="unknown", input_bold="", input_mask="", status="ready",
                   reason="", qc_status=qc.get(key, {}).get("qc_status", "absent"),
                   imaging_qc_outlier=qc.get(key, {}).get("imaging_qc_outlier", ""))
        eras = set()
        for path in raw[key]:
            sidecar = Path(str(path).replace(".nii.gz", ".json"))
            if sidecar.is_file():
                eras.add(software_era(json.loads(sidecar.read_text()).get("SoftwareVersions")))
        row["software_era"] = next(iter(eras)) if len(eras) == 1 else "unknown"
        if key[0] in excluded:
            row.update(status="source_excluded", reason="Existing source exclusion; not reinstated")
        elif not raw[key]:
            row.update(status="unavailable", reason="No active raw BIDS BOLD")
        elif len(preproc[key]) != 1:
            row.update(status="unavailable", reason=f"Expected one non-echo MNI BOLD; found {len(preproc[key])}")
        else:
            bold = preproc[key][0]
            mask = bold.with_name(bold.name.replace("desc-preproc_bold", "desc-brain_mask"))
            row.update(input_bold=str(bold.resolve()), input_mask=str(mask.resolve()))
            if not mask.is_file() or not mask.stat().st_size or not bold.stat().st_size:
                row.update(status="unavailable", reason="Missing/empty BOLD or matching brain mask")
            else:
                row["input_stamp"], row["mask_stamp"] = stamp(bold), stamp(mask)
        rows.append(row)
    if not rows:
        raise ValueError("No runs discovered")
    return rows


def tools_contract():
    result = {}
    for name in ("3dFWHMx", "afni"):
        path = shutil.which(name)
        if not path:
            raise ValueError(f"Missing executable: {name}")
        result[name] = {"path": str(Path(path).resolve()), "sha256": digest(path)}
    return result


def plan(args):
    path = args.output / "plan.json"
    if path.exists():
        raise ValueError("Plan already exists; use run/check to resume, or a new output directory")
    wrapper = args.measure_script.resolve()
    source = wrapper.read_text()
    if not all(flag in source for flag in COMMAND_FLAGS):
        raise ValueError("Measurement wrapper lacks the reviewed classic/detrend/ACF command")
    rows = inventory(args.project, args.excluded_source_root)
    contract = tools_contract()
    args.output.joinpath("measure_smoothness.sh").write_bytes(wrapper.read_bytes())
    provenance = {"schema": 1, "project": str(args.project),
                  "excluded_source_root": str(args.excluded_source_root.resolve()),
                  "wrapper_source": str(wrapper), "wrapper_sha256": digest(wrapper),
                  "code_sha256": code_hashes(), "tools": contract,
                  "run_qc_sha256": digest(args.project / "qc/run_qc.tsv"),
                  "stage": "fmriprep_non_echo_MNI_pre_smoothing", "smoothing_applied": False,
                  "eligibility_changed": False, "rows": rows}
    atomic_json(path, provenance)
    write_tsv(args.output / "inventory.tsv", rows,
              (*KEYS, "software_era", "status", "reason", "qc_status", "imaging_qc_outlier",
               "input_bold", "input_mask"))
    print(f"Frozen inventory: {dict(Counter(row['status'] for row in rows))}")
    print("QC/age/task-validity flags do not filter descriptive measurements; source exclusions remain parked.")
    return 0


def load_plan(args):
    plan_data = json.loads((args.output / "plan.json").read_text())
    if plan_data["code_sha256"] != code_hashes():
        raise ValueError("Measurement code changed since plan; review before using a new output directory")
    if plan_data["wrapper_sha256"] != digest(args.output / "measure_smoothness.sh"):
        raise ValueError("Frozen measurement wrapper changed")
    if plan_data["tools"] != tools_contract():
        raise ValueError("AFNI executable identity changed since plan")
    project = Path(plan_data["project"])
    if plan_data["run_qc_sha256"] != digest(project / "qc/run_qc.tsv"):
        raise ValueError("QC inventory changed since plan; retain this batch and create a new plan")
    current = inventory(project, Path(plan_data["excluded_source_root"]))
    if current != plan_data["rows"]:
        raise ValueError("Live inputs/inventory changed since plan; no existing results overwritten")
    return plan_data


def geometry(bold, mask):
    import nibabel as nib
    import numpy as np
    image, brain = nib.load(bold), nib.load(mask)
    if (len(image.shape) != 4 or image.shape[3] < 2 or len(brain.shape) != 3
            or image.shape[:3] != brain.shape or
            not np.allclose(image.affine, brain.affine, atol=1e-5, rtol=0)):
        raise ValueError("BOLD/mask geometry mismatch or invalid dimensions")
    values = np.asarray(brain.dataobj)
    if not np.isfinite(values).all() or not np.any(values > 0) or np.any(values < 0):
        raise ValueError("Mask empty or invalid")
    return {"shape": list(image.shape), "zooms": list(map(float, image.header.get_zooms())),
            "mask_voxels": int(np.count_nonzero(values))}


def read_result(path, row):
    results = read_tsv(path)
    if len(results) != 1:
        raise ValueError("Expected exactly one measurement row")
    result = results[0]
    for field, expected in (("input", "input_bold"), ("mask", "input_mask")):
        if Path(result[field]).resolve() != Path(row[expected]).resolve():
            raise ValueError("Measurement input identity mismatch")
    for field in METRICS:
        value = float(result[field])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Nonfinite/nonpositive {field}")
    if float(result["acf_a"]) > 1 or not result.get("afni_version"):
        raise ValueError("Invalid ACF mixture or missing AFNI version")
    return {field: result[field] for field in (*METRICS, "afni_version")}


def signatures(row):
    return {name: digest(row[name]) for name in ("input_bold", "input_mask")}


def validate_existing(destination, row, plan_data, hashes):
    receipt = json.loads((destination / "receipt.json").read_text())
    if (receipt["input_hashes"] != hashes or receipt["wrapper_sha256"] != plan_data["wrapper_sha256"]
            or receipt["tools"] != plan_data["tools"]
            or receipt["result_sha256"] != digest(destination / "result.tsv")):
        raise ValueError("Stored result lineage mismatch; preserved for review")
    return read_result(destination / "result.tsv", row)


def measure(row, plan_data, output, threads):
    destination = output / "runs" / label(row)
    try:
        print(f"STARTED {label(row)}: validating input hashes", flush=True)
        hashes = signatures(row)
        if destination.exists():
            validate_existing(destination, row, plan_data, hashes)
            return "verified", ""
        dimensions = geometry(row["input_bold"], row["input_mask"])
        # Failed attempts remain available; only validated complete directories are promoted.
        temporary = Path(tempfile.mkdtemp(prefix=label(row) + "-", dir=output / "attempts"))
        temporary.chmod(0o777 & ~current_umask())
        command = ["bash", str(output / "measure_smoothness.sh"), "--input", row["input_bold"],
                   "--mask", row["input_mask"], "--output-tsv", str(temporary / "result.tsv"),
                   "--work-dir", str(temporary)]
        env = {**os.environ, "AFNI_OMP_NUM_THREADS": str(threads), "OMP_NUM_THREADS": str(threads),
               "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        with (temporary / "command.log").open("w") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    pass_fds=LOCK_FDS)
        if result.returncode:
            raise ValueError(f"AFNI exit {result.returncode}; see {temporary / 'command.log'}")
        read_result(temporary / "result.tsv", row)
        if hashes != signatures(row):
            raise ValueError("Input changed during measurement")
        atomic_json(temporary / "receipt.json", {"input_hashes": hashes, "geometry": dimensions,
                    "wrapper_sha256": plan_data["wrapper_sha256"], "tools": plan_data["tools"],
                    "result_sha256": digest(temporary / "result.tsv")})
        os.replace(temporary, destination)
        return "completed", ""
    except Exception as exc:
        return "failed", str(exc)


def current_umask():
    # Read once in main, never mutate the process umask in worker threads.
    return UMASK


UMASK = 0
LOCK_FDS = ()


def run(args):
    data = load_plan(args)
    for folder in ("attempts", "runs"):
        (args.output / folder).mkdir(exist_ok=True)
    rows = [row for row in data["rows"] if row["status"] == "ready"]
    counts = Counter()
    print(f"Measuring {len(rows)} runs; {args.jobs} jobs, {args.threads} AFNI threads/job", flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(measure, row, data, args.output, args.threads): row for row in rows}
        for number, future in enumerate(as_completed(futures), 1):
            status, reason = future.result()
            counts[status] += 1
            print(f"{status.upper()} {label(futures[future])} ({number}/{len(rows)}) {reason}", flush=True)
    print(f"Measurement outcomes: {dict(counts)}")
    return 1 if counts["failed"] else 0


def report(args):
    data = load_plan(args)
    rows = []
    for number, source in enumerate(data["rows"], 1):
        row = dict(source)
        if row["status"] == "ready":
            try:
                row.update(validate_existing(args.output / "runs" / label(row), row, data, signatures(row)))
                row["status"] = "complete"
            except Exception as exc:
                row.update(status="failed", reason=str(exc))
        rows.append(row)
        if number % 100 == 0:
            print(f"VERIFICATION {number}/{len(data['rows'])}", flush=True)
    write_tsv(args.output / "run_metrics.tsv", rows,
              (*KEYS, "software_era", "status", "reason", "qc_status", "imaging_qc_outlier", *METRICS,
               "afni_version", "input_bold", "input_mask"))
    groups = defaultdict(list)
    for row in rows:
        if row["status"] != "source_excluded":
            groups[(row["task"], row["session"], row["software_era"])].append(row)
    summary = []
    for (task, session, era), group in sorted(groups.items()):
        complete = [r for r in group if r["status"] == "complete"]
        for metric in METRICS:
            values = [float(r[metric]) for r in complete]
            summary.append(dict(task=task, session=session, software_era=era, metric=metric,
                                n_runs=len(values), n_subjects=len({r["subject"] for r in complete}),
                                n_inventory=len(group), n_missing=len(group) - len(values),
                                median=linear_quantile(values, .5) if values else "",
                                q1=linear_quantile(values, .25) if values else "",
                                q3=linear_quantile(values, .75) if values else ""))
    columns = ("task", "session", "software_era", "metric", "n_runs", "n_subjects", "n_inventory",
               "n_missing", "median", "q1", "q3")
    write_tsv(args.output / "summary.tsv", summary, columns)
    plot(args.output, rows)
    counts = dict(Counter(row["status"] for row in rows))
    failed = any(row["status"] not in ("complete", "source_excluded") for row in rows)
    text = ["# AFNI baseline smoothness", "", f"Inventory outcomes: {counts}", "",
            "Input: unsmoothed non-echo fMRIPrep MNI BOLD and its matching run brain mask.",
            "Method: authoritative Shared Reward 3dFWHMx classic FWHM + detrend + ACF.",
            "This is not raw-BIDS MRIQC FWHM, an applied kernel, or a model-residual ACF estimate.",
            "No age/QC-flag/behavioral eligibility filtering. Source exclusions remain parked.",
            "No new exclusions, smoothing, target selection, or cohort TEDANA processing.",
            "Summaries/plots are descriptive within task/session; multiple runs may belong to one subject.",
            "Unknown eras remain visible; do not assign them to an era by date.", "",
            "| Task | Session | Era | Runs | Subjects | Missing | Classic median mm | ACF median mm |",
            "|---|---|---|---:|---:|---:|---:|---:|"]
    for s in summary:
        if s["metric"] == "classic_fwhm_combined":
            acf = next(x for x in summary if (x["task"], x["session"], x["software_era"], x["metric"]) ==
                       (s["task"], s["session"], s["software_era"], "acf_effective_fwhm"))
            text.append(f"| {s['task']} | {s['session']} | {s['software_era']} | {s['n_runs']} | "
                        f"{s['n_subjects']} | {s['n_missing']} | {s['median']} | {acf['median']} |")
    (args.output / "report.md").write_text("\n".join(text) + "\n")
    print("\n".join(text))
    print("CHECK FAILED: unresolved inputs/results; inspect run_metrics.tsv" if failed else
          "CHECK PASSED: every active run measured; source exclusions separately accounted for")
    return int(failed)


def plot(output, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    directory = output / "figures"
    directory.mkdir(exist_ok=True)
    for task, session in sorted({(r["task"], r["session"]) for r in rows}):
        group = [r for r in rows if (r["task"], r["session"]) == (task, session) and r["status"] == "complete"]
        eras = [e for e in ("E11", "XA30", "XA60", "unknown") if any(r["software_era"] == e for r in group)]
        if not eras:
            continue
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
        for ax, metric, title in zip(axes, ("classic_fwhm_combined", "acf_effective_fwhm"),
                                    ("Classic combined FWHM", "ACF effective FWHM")):
            values = [[float(r[metric]) for r in group if r["software_era"] == e] for e in eras]
            ax.boxplot(values)
            ax.set_xticks(range(1, len(eras) + 1))
            ax.set_xticklabels([f"{e}\nn={len(v)}" for e, v in zip(eras, values)])
            ax.set(title=title, ylabel="mm")
        fig.suptitle(f"{task}, ses-{session}: unsmoothed fMRIPrep BOLD")
        fig.savefig(directory / f"task-{task}_ses-{session}.png", dpi=150)
        plt.close(fig)


def main():
    global UMASK, LOCK_FDS
    UMASK = os.umask(0)
    os.umask(UMASK)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("plan", "run", "check"))
    p.add_argument("--project", type=Path, default=ROOT)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--measure-script", type=Path,
                   default=Path("/ZPOOL/data/projects/rf1-sra-sharedreward/code/measure_smoothness.sh"))
    p.add_argument("--excluded-source-root", type=Path,
                   default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    p.add_argument("--jobs", type=int, default=8)
    p.add_argument("--threads", type=int, default=1)
    args = p.parse_args()
    if args.jobs < 1 or args.threads < 1:
        p.error("jobs and threads must be positive")
    args.project, args.output = args.project.resolve(), args.output.resolve()
    if args.project / "work" not in args.output.parents:
        p.error("output must be a dedicated directory inside project/work")
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            LOCK_FDS = (lock.fileno(),)
            return {"plan": plan, "run": run, "check": report}[args.command](args)
        except (OSError, ValueError, KeyError) as exc:
            print(f"ERROR: {exc}", flush=True)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
