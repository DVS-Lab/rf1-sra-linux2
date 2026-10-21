#!/usr/bin/env python3
"""Isolated, age-55+ baseline activation rerun; QC flags never select runs."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
import pandas as pd

import audit_task_availability as audit
from genTedanaConfounds import (
    DESIRED_FMRIPREP_COLUMNS, atomic_write_tsv, validate_alignment, verify_existing,
)
from participants import age_years, exclusions, read_tsv
from refresh_task_handoff import disposition

VARIANT = "fsl-no-tedana-age55"
THREAD_ENV = {k: "1" for k in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
)}
UGR_EVS = [f"{kind}_{level}_{term}" for kind in ("nonsocial", "social")
           for level in ("high", "low") for term in ("constant", "pmod")]
UGR_EVS += ["rt_constant", "rt_pmod"]


def write_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def signature(path):
    path = Path(path).absolute()
    if not path.exists():
        return {"path": str(path), "absent": True}
    info = path.stat()
    result = {"path": str(path), "size": info.st_size, "mtime_ns": info.st_mtime_ns}
    if not path.name.endswith(".nii.gz"):
        result["sha256"] = audit.sha(path)
    return result


def verify_signatures(records):
    if any(signature(r["path"]) != r for r in records):
        raise ValueError("Frozen input changed; prepare a new plan, do not reuse existing outputs")


def base_confounds(path):
    frame = pd.read_csv(path, sep="\t")
    missing = set(DESIRED_FMRIPREP_COLUMNS) - set(frame)
    if missing:
        raise ValueError("Missing base confound columns: " + ",".join(sorted(missing)))
    columns = list(DESIRED_FMRIPREP_COLUMNS)
    columns += [c for c in frame if c.startswith("cosine")]
    columns += [c for c in frame if c.startswith("non_steady_state")]
    # Same column ordering and missing-value policy as production, without ICA.
    result = frame[columns].apply(pd.to_numeric, errors="raise").fillna(0)
    if not len(result) or not np.isfinite(result.to_numpy()).all():
        raise ValueError("Empty or nonfinite base confounds")
    return result


def ages(path, roster):
    fields, rows, _ = read_tsv(path)
    if not {"participant_id", "age"} <= set(fields):
        raise ValueError("Age table needs participant_id and age columns")
    found = {}
    for row in rows:
        subject = audit.normalize_id(row["participant_id"])
        if subject in found:
            raise ValueError("Duplicate participant in age table")
        value = age_years(row["age"])
        found[subject] = None if value == "n/a" else Decimal(value)
    return {s: found.get(s) for s in roster}


def classify(row, age):
    # Apply settled decisions before age or technical availability, never QC flags.
    state, reason = disposition(dict(row, technical_status="inputs_present_aligned"))
    if state == "held":
        return state, reason
    if age is None:
        return "age_unknown", "No usable age in the selected age table"
    if age < 55:
        return "under_55", "Age below 55"
    return "candidate", ""


def ev_paths(root, row):
    sub, ses, task, run = audit.key(row)
    folder = root / f"derivatives/fsl/EVfiles/sub-{sub}/ses-{ses}/{task}"
    if task == "ugr":
        folder /= "model-3"
    names = UGR_EVS if task == "ugr" else ["decision", "win", "loss"]
    required = [folder / f"run-{run}_{name}.txt" for name in names]
    optional = folder / f"run-{run}_{'missed_trial' if task == 'ugr' else 'decision-missed'}.txt"
    for path in required + [optional]:
        if path == optional and (not path.exists() or not path.stat().st_size):
            continue
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("Canonical task EV missing or empty")
        values = np.loadtxt(path, ndmin=2)
        if values.shape[1] != 3 or not np.isfinite(values).all() or (values[:, 1] < 0).any():
            raise ValueError("Invalid canonical three-column task EV")
    return required + [optional]


def prepare(args):
    private = args.private_dir
    if private.exists():
        raise ValueError("Use a new private directory; saved plans are immutable")
    private.mkdir(parents=True, mode=0o700)
    # Reuse the current source-exclusion/hold/disposition and QC audit contracts.
    args.sessions, args.sublist = "01", None
    rows, _thresholds, sources = audit.collect(args)
    roster = sorted({r["subject"] for r in rows})
    age_file = args.age_file or args.project_root / "bids/participants.tsv"
    age_map = ages(age_file, roster)
    jobs, review = [], []
    roots = {"ugr": args.ugr_root, "socialdoors": args.socdoors_root}
    for row in rows:
        state, reason = classify(row, age_map[row["subject"]])
        row = dict(row, selected_age=str(age_map[row["subject"]] or ""),
                   rerun_status=state, rerun_reason=reason)
        if state == "candidate":
            try:
                sub, ses, task, run = audit.key(row)
                stem = f"sub-{sub}_ses-{ses}_task-{task}_run-{run}"
                root = roots[task]
                source = args.project_root / f"derivatives/fmriprep/sub-{sub}/ses-{ses}/func/{stem}_part-mag_desc-confounds_timeseries.tsv"
                confounds = private / "confounds" / f"{stem}_desc-FmriprepOnlyConfounds.tsv"
                base = base_confounds(source)
                paths = audit.input_paths(args.project_root, sub, ses, task, run)
                paths["confounds"] = confounds
                validate_alignment(base, paths["bold"])
                evs = ev_paths(root, row)
                atomic_write_tsv(base, confounds, preserve_existing=True)
                states = {k: audit.file_state(p) for k, p in paths.items()}
                nvol, tr, _, findings = audit.validate_inputs(paths, states, task)
                if any(v != "present" for v in states.values()) or findings:
                    raise ValueError("Required input missing or invalid: " + ";".join(findings))
                model = "3" if task == "ugr" else "1"
                output = root / f"derivatives/{VARIANT}/sub-{sub}/ses-{ses}/L1_task-{task}_ses-{ses}_model-{model}_type-act_run-{run}_sm-5.feat"
                rendered = output.parent / f"L1_sub-{sub}_task-{task}_ses-{ses}_model-{model}_type-act_run-{run}.fsf"
                code = [root / "code/L1stats.sh", root / "code/project_config.sh",
                        root / f"templates/L1_task-{task}_model-{model}_type-act.fsf"]
                if "EV_FILES_ROOT" not in code[1].read_text():
                    raise ValueError("Task repository needs EV_FILES_ROOT support; pull updated code")
                jobs.append({"key": stem, "subject": sub, "session": ses, "task": task, "run": run,
                             "root": str(root), "output": str(output), "rendered": str(rendered),
                             "bold": str(paths["bold"]), "confounds": str(confounds),
                             "source_confounds": str(source), "columns": list(base), "nvol": nvol,
                             "tr": tr, "inputs": [signature(p) for p in [*paths.values(), source, *evs, *code]]})
                row["rerun_status"], row["rerun_reason"] = "ready", ""
            except (ValueError, OSError) as exc:
                row["rerun_status"], row["rerun_reason"] = "missing_or_invalid", str(exc)
        review.append(row)
    audit.write_table(private / "run_review.tsv", review)
    sources.extend([age_file, Path(__file__), Path(__file__).with_name("genTedanaConfounds.py"),
                    Path(__file__).with_name("refresh_task_handoff.py")])
    plan = {"schema": 1, "variant": VARIANT, "session": "01", "minimum_age": 55,
            "age_file": str(age_file), "qc_used_for_selection": False,
            "exclusions_root": str(args.exclusions_root),
            "source_exclusions": sorted(exclusions(args.exclusions_root)),
            "sources": [signature(p) for p in sorted(set(sources))], "jobs": jobs,
            "review": signature(private / "run_review.tsv")}
    write_json(private / "plan.json", plan)
    (private / "plan.sha256").write_text(audit.sha(private / "plan.json") + "\n")
    for task in roots:
        subset = [r for r in review if r["task"] == task]
        for state, count in sorted(Counter(r["rerun_status"] for r in subset).items()):
            subjects = len({r["subject"] for r in subset if r["rerun_status"] == state})
            print(f"{task} {state}: {count} runs, {subjects} participants")
    print(f"Prepared {len(jobs)} L1 runs. Private review and frozen plan: {private}")
    print("QC flags retained for review, not exclusion. No existing FEAT output changed.")
    if not jobs:
        raise ValueError("No ready age-55+ runs")


def load_plan(private):
    if audit.sha(private / "plan.json") != (private / "plan.sha256").read_text().strip():
        raise ValueError("Plan changed")
    plan = json.loads((private / "plan.json").read_text())
    if plan["variant"] != VARIANT or plan["qc_used_for_selection"] is not False:
        raise ValueError("Unexpected analysis policy")
    verify_signatures(plan["sources"] + [plan["review"]])
    if sorted(exclusions(Path(plan["exclusions_root"]))) != plan["source_exclusions"]:
        raise ValueError("Source exclusions changed")
    for job in plan["jobs"]:
        if Path(job["root"]) / "derivatives" / VARIANT not in Path(job["output"]).parents:
            raise ValueError("Output is outside the isolated analysis root")
        verify_signatures(job["inputs"])
        base = base_confounds(Path(job["source_confounds"]))
        if list(base) != job["columns"]:
            raise ValueError("Base confound columns changed")
        verify_existing(base, Path(job["confounds"]))
        validate_alignment(base, Path(job["bold"]))
    return plan


def command(job, render=False):
    root = Path(job["root"])
    cmd = ["bash", str(root / "code/L1stats.sh"), job["subject"], job["run"], "0"]
    if job["task"] == "socialdoors":
        cmd.append("socialdoors")
    cmd += ["--session", job["session"], "--bold", job["bold"], "--confounds", job["confounds"]]
    if render:
        cmd.append("--render-only")
    env = dict(os.environ, **THREAD_ENV, FSLSUB_PARALLEL="1", RF1_SRA_UPSTREAM_ROOT=str(audit.ROOT),
               FSL_DERIVATIVES_ROOT=str(root / "derivatives" / VARIANT),
               EV_FILES_ROOT=str(root / "derivatives/fsl/EVfiles"))
    return cmd, env


def validate_fsf(path, job):
    text = path.read_text()
    for field, expected in (("feat_files(1)", job["bold"]),
                            ("confoundev_files(1)", job["confounds"])):
        match = re.search(r'^set\s+' + re.escape(field) + r'\s+"([^"]+)"', text, re.M)
        if not match or Path(match[1]).resolve() != Path(expected).resolve():
            raise ValueError("Rendered BOLD/confounds linkage differs")
    match = re.search(r'^set fmri\(outputdir\)\s+"([^"]+)"', text, re.M)
    if not match or Path(match[1]).with_suffix(".feat").resolve() != Path(job["output"]).resolve():
        raise ValueError("Rendered output is not the isolated variant")
    if not re.search(r'^set fmri\(temphp_yn\)\s+0\s*$', text, re.M):
        raise ValueError("Unexpected temporal filtering policy")


def feat_matrix(path):
    text = path.read_text()
    if "/Matrix" not in text:
        raise ValueError("Missing FSL matrix")
    import io
    matrix = np.loadtxt(io.StringIO(text.split("/Matrix", 1)[1]), ndmin=2)
    if not matrix.size or not np.isfinite(matrix).all():
        raise ValueError("Empty or nonfinite FSL design")
    return matrix


def validate_design(matrix, contrasts, job):
    x, c = feat_matrix(matrix), feat_matrix(contrasts)
    if x.shape[0] != job["nvol"] or c.shape[1] != x.shape[1]:
        raise ValueError("Design/contrast dimensions disagree")
    if c.shape[0] != (17 if job["task"] == "ugr" else 4):
        raise ValueError("Unexpected canonical contrast count")
    # Zero-valued optional miss EVs can make the full design rank deficient;
    # require estimable canonical contrasts rather than full column rank.
    rank = int(np.linalg.matrix_rank(x))
    rank_with_mean = int(np.linalg.matrix_rank(np.column_stack([np.ones(len(x)), x])))
    if rank_with_mean >= len(x) or not np.allclose(c @ np.linalg.pinv(x) @ x, c, atol=1e-6, rtol=1e-6):
        raise ValueError("No residual degrees of freedom or unestimable canonical contrast")
    return {"design_columns": x.shape[1], "design_rank": rank,
            "rank_with_intercept": rank_with_mean, "residual_dof_unwhitened": len(x) - rank_with_mean}


def validate_output(job):
    output = Path(job["output"])
    state, missing = audit.feat_evidence(output, expected_contrasts=17 if job["task"] == "ugr" else 4)
    if state != "files_present":
        raise ValueError("Incomplete FEAT outputs: " + missing)
    validate_fsf(output / "design.fsf", job)
    return validate_design(output / "design.mat", output / "design.con", job)


def completion(job):
    return Path(job["output"]) / "no_tedana_success.json"


def verified_complete(job):
    saved = json.loads(completion(job).read_text())
    if saved["job"] != job:
        raise ValueError("Existing variant belongs to different inputs; preserved for review")
    verify_signatures(saved["outputs"])
    return validate_output(job)


def execute_one(job, private, render, lock_fds):
    try:
        verify_signatures(job["inputs"])
        if Path(job["output"]).exists():
            verified_complete(job)
            return {"key": job["key"], "status": "SKIPPED_COMPLETE"}
        cmd, env = command(job, render=True)
        log = private / "logs" / (job["key"] + ".log")
        with log.open("a") as handle:
            print(f"STARTED {job['key']}", flush=True)
            subprocess.run(cmd, env=env, stdout=handle, stderr=subprocess.STDOUT,
                           check=True, pass_fds=lock_fds)
            fsf = Path(job["rendered"])
            validate_fsf(fsf, job)
            # Explicitly include nuisance columns when constructing the design.
            subprocess.run(["feat_model", str(fsf.with_suffix("")), job["confounds"]],
                           env=env, stdout=handle, stderr=subprocess.STDOUT,
                           check=True, pass_fds=lock_fds)
            diag = validate_design(fsf.with_suffix(".mat"), fsf.with_suffix(".con"), job)
            if render:
                return {"key": job["key"], "status": "RENDERED", **diag}
            cmd, env = command(job)
            subprocess.run(cmd, env=env, stdout=handle, stderr=subprocess.STDOUT,
                           check=True, pass_fds=lock_fds)
        diag = validate_output(job)
        verify_signatures(job["inputs"])
        output = Path(job["output"])
        products = [p for p in output.rglob("*") if p.is_file() and
                    (p.suffix in {".fsf", ".mat", ".con"} or p.name.endswith(".nii.gz"))]
        write_json(completion(job), {"job": job, "outputs": [signature(p) for p in sorted(products)], **diag})
        return {"key": job["key"], "status": "COMPLETED", **diag}
    except Exception as exc:
        return {"key": job["key"], "status": "FAILED", "reason": str(exc)}


def run(args):
    plan = load_plan(args.private_dir)
    with ExitStack() as stack:
        # Locks are shared across different plans targeting these same variant roots.
        lock_fds = []
        for root in sorted({j["root"] for j in plan["jobs"]}):
            folder = Path(root) / "derivatives" / VARIANT
            folder.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context((folder / ".runner.lock").open("a"))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fds.append(handle.fileno())
        (args.private_dir / "logs").mkdir(exist_ok=True)
        statuses = []
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(execute_one, j, args.private_dir, args.command == "render", tuple(lock_fds))
                       for j in plan["jobs"]]
            for future in as_completed(futures):
                item = future.result()
                statuses.append(item)
                print(f"{item['status']} {item['key']} ({len(statuses)}/{len(futures)})", flush=True)
                write_json(args.private_dir / (args.command + "-status.json"), statuses)
        if any(r["status"] == "FAILED" for r in statuses):
            raise ValueError("Some runs failed; inspect private status and logs. Partial outputs were not deleted")
        if args.command == "run":
            check(args)


def check(args):
    plan = load_plan(args.private_dir)
    rows = []
    for job in plan["jobs"]:
        diag = verified_complete(job)
        rows.append({k: job[k] for k in ("subject", "session", "task", "run", "output")} | diag)
    audit.write_table(args.private_dir / "completed_runs.tsv", rows)
    for task in ("ugr", "socialdoors"):
        selected = [r for r in rows if r["task"] == task]
        print(f"VERIFIED {task}: {len(selected)} runs, {len({r['subject'] for r in selected})} participants")
    print("CHECK PASSED: isolated L1 outputs and frozen base-only input lineage verified.")
    print("L2/L3 have NOT been rerun. QC flags and survey/linkage criteria remain separate.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "render", "run", "check"))
    parser.add_argument("--project-root", type=Path, default=audit.ROOT)
    parser.add_argument("--ugr-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-ugr"))
    parser.add_argument("--socdoors-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-socdoors"))
    parser.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--age-file", type=Path, help="Approved participant_id/age TSV; default bids/participants.tsv")
    parser.add_argument("--dispositions", type=Path)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    for name in ("project_root", "ugr_root", "socdoors_root", "private_dir", "age_file", "dispositions"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve())
    if args.jobs < 1 or (args.project_root / "work").resolve() not in args.private_dir.parents:
        parser.error("positive --jobs and --private-dir under project work/ required")
    if args.command == "prepare":
        prepare(args)
    elif args.command == "check":
        check(args)
    else:
        run(args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
