#!/usr/bin/env python3
"""Extend the frozen baseline age-55+ batch without changing its code or outputs."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
import pandas as pd

import run_no_tedana_l1 as l1

audit = l1.audit
VARIANT = l1.VARIANT


def base_confounds(path):
    frame = pd.read_csv(path, sep="\t")
    # Production selects available aCompCor columns, not necessarily six.
    required = [c for c in l1.DESIRED_FMRIPREP_COLUMNS if not c.startswith("a_comp_cor")]
    if not set(required) <= set(frame) or "a_comp_cor_00" not in frame:
        raise ValueError("Missing motion/FD or all aCompCor columns; inspect upstream confounds")
    columns = [c for c in l1.DESIRED_FMRIPREP_COLUMNS if c in frame]
    columns += [c for c in frame if c.startswith("cosine")]
    columns += [c for c in frame if c.startswith("non_steady_state")]
    base = frame[columns].apply(pd.to_numeric, errors="raise").fillna(0)
    if not len(base) or not np.isfinite(base.to_numpy()).all():
        raise ValueError("Empty or nonfinite base confounds")
    return base


def collect_rows(args):
    args.sessions, args.sublist = "01", None
    rows, _, sources = audit.collect(args)
    rows = list(rows)
    # Doors is a separate task, never a copy of Social Doors flags or decisions.
    _, qc_rows, _ = l1.read_tsv(args.project_root / "qc/run_qc.tsv")
    qc = audit.indexed(qc_rows)
    _, holds, _ = l1.read_tsv(audit.ROOT / "code/task_availability_holds.tsv")
    holds = audit.indexed(holds)
    decisions = audit.indexed(l1.read_tsv(args.dispositions)[1]) if args.dispositions else {}
    for source in list(rows):
        if source["task"] != "socialdoors":
            continue
        key = (source["subject"], "01", "doors", "1")
        hold, decision = holds.get(key, {}), decisions.get(key, {})
        row = dict(zip(audit.KEY, key))
        row.update(roster_gate=source["roster_gate"], existing_hold=hold.get("reason", ""),
                   hold_evidence=hold.get("evidence", ""),
                   existing_decision=decision.get("decision", "not_recorded"),
                   decision_reason=decision.get("reason", ""),
                   decision_evidence=decision.get("evidence", ""),
                   qc_record_state="present" if key in qc else "absent")
        for name in audit.QC_FIELDS:
            row["recorded_" + name] = qc.get(key, {}).get(name, "")
        rows.append(row)
    return rows, sources


def make_job(args, row):
    sub, ses, task, run = audit.key(row)
    root = args.ugr_root if task == "ugr" else args.socdoors_root
    stem = f"sub-{sub}_ses-{ses}_task-{task}_run-{run}"
    paths = audit.input_paths(args.project_root, sub, ses, task, run)
    source = paths["bold"].parent / f"{stem}_part-mag_desc-confounds_timeseries.tsv"
    base = base_confounds(source)
    l1.validate_alignment(base, paths["bold"])
    evs = l1.ev_paths(root, row)
    paths["confounds"] = args.private_dir / "confounds" / f"{stem}_desc-FmriprepOnlyConfounds.tsv"
    l1.atomic_write_tsv(base, paths["confounds"], preserve_existing=True)
    states = {k: audit.file_state(p) for k, p in paths.items()}
    nvol, tr, _, findings = audit.validate_inputs(paths, states, "socialdoors" if task == "doors" else task)
    if any(v != "present" for v in states.values()) or findings:
        raise ValueError("Required input missing or invalid: " + ";".join(findings))
    model = "3" if task == "ugr" else "1"
    folder = root / f"derivatives/{VARIANT}/sub-{sub}/ses-{ses}"
    output = folder / f"L1_task-{task}_ses-{ses}_model-{model}_type-act_run-{run}_sm-5.feat"
    code = [root / "code/L1stats.sh", root / "code/project_config.sh",
            root / f"templates/L1_task-{task}_model-{model}_type-act.fsf"]
    if any(not p.is_file() for p in code):
        raise ValueError("Missing canonical task code/template")
    if "EV_FILES_ROOT" not in code[1].read_text():
        raise ValueError("Task repository needs EV_FILES_ROOT support")
    return dict(key=stem, subject=sub, session=ses, task=task, run=run, root=str(root),
                output=str(output), rendered=str(folder / f"L1_sub-{sub}_task-{task}_ses-{ses}_model-{model}_type-act_run-{run}.fsf"),
                bold=str(paths["bold"]), confounds=str(paths["confounds"]),
                source_confounds=str(source), columns=list(base), nvol=nvol, tr=tr,
                inputs=[l1.signature(p) for p in [*paths.values(), source, *evs, *code]])


def l2_jobs(jobs):
    indexed = {j["key"]: j for j in jobs}
    result = []
    for sub in sorted({j["subject"] for j in jobs}):
        for task, units in (("ugr", [("ugr", "1"), ("ugr", "2")]),
                            ("socialdoors", [("socialdoors", "1"), ("doors", "1")])):
            keys = [f"sub-{sub}_ses-01_task-{t}_run-{r}" for t, r in units]
            if not all(k in indexed for k in keys):
                continue
            root = Path(indexed[keys[0]]["root"])
            model = "3" if task == "ugr" else "1"
            folder = root / f"derivatives/{VARIANT}/sub-{sub}/ses-01"
            code = [root / "code/L2stats.sh", root / "code/project_config.sh",
                    root / f"templates/L2_task-{task}_model-{model}_type-act.fsf"]
            if any(not p.is_file() for p in code):
                raise ValueError("Missing canonical L2 code/template")
            result.append(dict(key=f"sub-{sub}_ses-01_L2-{task}", subject=sub, session="01", task=task,
                root=str(root), input_keys=keys, inputs=[indexed[k]["output"] for k in keys],
                code=[l1.signature(p) for p in code], ncopes=17 if task == "ugr" else 4,
                rendered=str(folder / f"L2_sub-{sub}_task-{task}_ses-01_model-{model}_type-act.fsf"),
                output=str(folder / f"L2_task-{task}_ses-01_model-{model}_type-act_sm-5.gfeat")))
    return result


def prepare(args):
    if args.private_dir.exists():
        raise ValueError("Use a new private directory; plans are immutable")
    parent = l1.load_plan(args.parent_dir)
    for job in parent["jobs"]:
        l1.verified_complete(job)
    print(f"Verified {len(parent['jobs'])} existing L1 outputs; none will be regenerated.", flush=True)
    args.private_dir.mkdir(parents=True, mode=0o700)
    rows, sources = collect_rows(args)
    age_file = args.project_root / "bids/participants.tsv"
    age_map = l1.ages(age_file, {r["subject"] for r in rows})
    previous = {j["key"]: j for j in parent["jobs"]}
    jobs, review, reused = [], [], set()
    for row in rows:
        state, reason = l1.classify(row, age_map[row["subject"]])
        row = dict(row, rerun_status=state, rerun_reason=reason)
        if state == "candidate":
            key = "sub-{}_ses-{}_task-{}_run-{}".format(*audit.key(row))
            if key in previous:
                job = previous[key]
                expected_root = args.ugr_root if row["task"] == "ugr" else args.socdoors_root
                if Path(job["root"]) != expected_root:
                    raise ValueError("Parent and follow-up task roots differ")
                reused.add(key)
                jobs.append(job)
                row["rerun_status"], row["rerun_reason"] = "reused_verified", ""
            else:
                try:
                    job = make_job(args, row)
                    if Path(job["output"]).exists():
                        raise ValueError("Unowned output exists; inspect privately, never overwrite")
                    jobs.append(job)
                    row["rerun_status"], row["rerun_reason"] = "ready_new", ""
                except (OSError, ValueError) as exc:
                    row["rerun_status"], row["rerun_reason"] = "missing_or_invalid", str(exc)
        review.append(row)
    if reused != set(previous):
        raise ValueError("Parent run no longer eligible under current gates; review before proceeding")
    fields = list(dict.fromkeys(k for row in review for k in row))
    audit.write_table(args.private_dir / "run_review.tsv",
                      [{k: row.get(k, "") for k in fields} for row in review])
    sources += [age_file, Path(__file__), Path(l1.__file__), args.parent_dir / "plan.json",
                args.parent_dir / "plan.sha256"]
    plan = dict(schema=1, variant=VARIANT, qc_used_for_selection=False, parent_dir=str(args.parent_dir),
                sources=[l1.signature(p) for p in sorted(set(sources))],
                review=l1.signature(args.private_dir / "run_review.tsv"),
                jobs=jobs, reused_keys=sorted(reused), l2_jobs=l2_jobs(jobs))
    l1.write_json(args.private_dir / "plan.json", plan)
    (args.private_dir / "plan.sha256").write_text(audit.sha(args.private_dir / "plan.json") + "\n")
    for task in ("ugr", "socialdoors", "doors"):
        print(task, dict(Counter(r["rerun_status"] for r in review if r["task"] == task)))
    print(f"Prepared {len(jobs)-len(reused)} new L1s, {len(reused)} verified existing L1s, {len(plan['l2_jobs'])} L2s.")
    print(f"Private review: {args.private_dir / 'run_review.tsv'}")
    print("QC flags are descriptive; no final paper-cohort selection or L3 fit is performed.")


def load_plan(private):
    if audit.sha(private / "plan.json") != (private / "plan.sha256").read_text().strip():
        raise ValueError("Plan changed")
    plan = json.loads((private / "plan.json").read_text())
    if plan["variant"] != VARIANT or plan["qc_used_for_selection"] is not False:
        raise ValueError("Unexpected analysis policy")
    l1.verify_signatures(plan["sources"] + [plan["review"]])
    parent = l1.load_plan(Path(plan["parent_dir"]))
    previous = {j["key"]: j for j in parent["jobs"]}
    for job in plan["jobs"]:
        if Path(job["root"]) / "derivatives" / VARIANT not in Path(job["output"]).parents:
            raise ValueError("Output outside isolated root")
        l1.verify_signatures(job["inputs"])
        if job["key"] in plan["reused_keys"] and job != previous[job["key"]]:
            raise ValueError("Imported parent job changed")
        base = base_confounds(Path(job["source_confounds"]))
        if list(base) != job["columns"]:
            raise ValueError("Confound columns changed")
        l1.verify_existing(base, Path(job["confounds"]))
        l1.validate_alignment(base, Path(job["bold"]))
    if plan["l2_jobs"] != l2_jobs(plan["jobs"]):
        raise ValueError("L2 inputs or canonical code changed")
    return plan


def command(job, render=False):
    cmd, env = l1.command(job, render)
    if job["task"] == "doors":
        cmd.insert(5, "doors")
    return cmd, env


def execute_l1(job, private, lock_fds):
    try:
        l1.verify_signatures(job["inputs"])
        if Path(job["output"]).exists():
            l1.verified_complete(job)
            return dict(key=job["key"], status="SKIPPED_COMPLETE")
        with (private / "logs" / (job["key"] + ".log")).open("a") as log:
            print(f"STARTED {job['key']}", flush=True)
            cmd, env = command(job, True)
            subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
            fsf = Path(job["rendered"])
            l1.validate_fsf(fsf, job)
            subprocess.run(["feat_model", str(fsf.with_suffix("")), job["confounds"]],
                           env=env, stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
            l1.validate_design(fsf.with_suffix(".mat"), fsf.with_suffix(".con"), job)
            cmd, env = command(job)
            subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
        diag = l1.validate_output(job)
        l1.verify_signatures(job["inputs"])
        products = [p for p in Path(job["output"]).rglob("*") if p.is_file() and
                    (p.suffix in {".fsf", ".mat", ".con"} or p.name.endswith(".nii.gz"))]
        l1.write_json(l1.completion(job), dict(job=job, outputs=[l1.signature(p) for p in sorted(products)], **diag))
        return dict(key=job["key"], status="COMPLETED")
    except Exception as exc:
        return dict(key=job["key"], status="FAILED", reason=str(exc))


def validate_l2_fsf(path, job):
    text = path.read_text()
    for field, expected in [("fmri(outputdir)", str(Path(job["output"]).with_suffix(""))),
                            *[(f"feat_files({i})", p) for i, p in enumerate(job["inputs"], 1)]]:
        match = re.search(r'^set\s+' + re.escape(field) + r'\s+"([^"]+)"', text, re.M)
        if not match or Path(match[1]).resolve() != Path(expected).resolve():
            raise ValueError("L2 input/output linkage differs from isolated plan")
    for field, value in (("mixed_yn", 3), ("npts", 2), ("ncopeinputs", job["ncopes"]),
                         ("evg1.1", 1), ("evg2.1", 1), ("con_real1.1", 1), ("ncon_real", 1)):
        if not re.search(r'^set fmri\(' + re.escape(field) + r'\)\s+' + str(value) + r'\s*$', text, re.M):
            raise ValueError("Unexpected canonical fixed-effects mean model: " + field)


def l2_products(job):
    output = Path(job["output"])
    names = ["design.fsf", "design.mat", "design.con"]
    for cope in range(1, job["ncopes"] + 1):
        names += [f"cope{cope}.feat/{p}" for p in ("design.mat", "design.con", "mask.nii.gz",
                   "stats/cope1.nii.gz", "stats/varcope1.nii.gz", "stats/zstat1.nii.gz", "stats/tdof_t1.nii.gz")]
    return [output / p for p in names]


def validate_l2(job):
    if any(audit.file_state(p) != "present" for p in l2_products(job)):
        raise ValueError("Incomplete L2 cope/varcope/zstat/dof/mask/design products")
    validate_l2_fsf(Path(job["output"]) / "design.fsf", job)
    for folder in [Path(job["output"])] + [Path(job["output"]) / f"cope{i}.feat" for i in range(1, job["ncopes"] + 1)]:
        x, c = l1.feat_matrix(folder / "design.mat"), l1.feat_matrix(folder / "design.con")
        if x.shape != (2, 1) or c.shape != (1, 1) or not np.allclose(x, 1) or not np.allclose(c, 1):
            raise ValueError("Unexpected fixed-effects design matrices")


def l2_dependencies(job, jobs):
    records = []
    for key in job["input_keys"]:
        source = jobs[key]
        l1.verified_complete(source)
        # L2 consumes DOF/registration metadata as well as the statistical maps.
        folder = Path(source["output"])
        dof = folder / "stats/dof"
        if audit.file_state(dof) != "present":
            raise ValueError("Missing L1 residual DOF for L2: " + key)
        records.append(l1.signature(dof))
        records.append(l1.signature(l1.completion(source)))
        records.extend(l1.signature(p) for p in sorted((folder / "reg").rglob("*")) if p.is_file())
    return records


def verified_l2(job, jobs):
    saved = json.loads((Path(job["output"]) / "no_tedana_l2_success.json").read_text())
    if saved["job"] != job or saved["dependencies"] != l2_dependencies(job, jobs):
        raise ValueError("L2 belongs to different inputs")
    l1.verify_signatures(saved["outputs"])
    validate_l2(job)


def execute_l2(job, jobs, private, lock_fds, timeout):
    try:
        dependencies = l2_dependencies(job, jobs)
        l1.verify_signatures(job["code"])
        if Path(job["output"]).exists():
            verified_l2(job, jobs)
            return dict(key=job["key"], status="SKIPPED_COMPLETE")
        root = Path(job["root"])
        env = dict(os.environ, **l1.THREAD_ENV, FSLSUB_PARALLEL="1",
                   FSL_DERIVATIVES_ROOT=str(root / "derivatives" / VARIANT))
        with (private / "logs" / (job["key"] + ".log")).open("a") as log:
            print(f"STARTED {job['key']}", flush=True)
            cmd = ["bash", str(root / "code/L2stats.sh"), job["subject"], "act", "--session", "01", "--render-only"]
            subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
            validate_l2_fsf(Path(job["rendered"]), job)
            subprocess.run(["feat", job["rendered"]], env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, pass_fds=lock_fds)
            deadline = time.monotonic() + timeout
            while any(audit.file_state(p) != "present" for p in l2_products(job)):
                if time.monotonic() >= deadline:
                    raise ValueError("L2 completion timed out; inspect log and child jobs before retry")
                time.sleep(10)
        validate_l2(job)
        if dependencies != l2_dependencies(job, jobs):
            raise ValueError("L1 inputs changed while L2 ran")
        l1.verify_signatures(job["code"])
        l1.write_json(Path(job["output"]) / "no_tedana_l2_success.json",
                      dict(job=job, dependencies=dependencies, outputs=[l1.signature(p) for p in l2_products(job)]))
        return dict(key=job["key"], status="COMPLETED")
    except Exception as exc:
        return dict(key=job["key"], status="FAILED", reason=str(exc))


def run(args):
    plan = load_plan(args.private_dir)
    jobs = {j["key"]: j for j in plan["jobs"]}
    with ExitStack() as stack:
        fds = []
        for root in sorted({j["root"] for j in plan["jobs"]}):
            folder = Path(root) / "derivatives" / VARIANT
            folder.mkdir(parents=True, exist_ok=True)
            handle = stack.enter_context((folder / ".runner.lock").open("a"))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fds.append(handle.fileno())
        (args.private_dir / "logs").mkdir(exist_ok=True)
        for stage, selected in (("l1", plan["jobs"]), ("l2", plan["l2_jobs"])):
            statuses = []
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futures = [pool.submit(execute_l1, j, args.private_dir, tuple(fds)) if stage == "l1" else
                           pool.submit(execute_l2, j, jobs, args.private_dir, tuple(fds), args.timeout)
                           for j in selected]
                for future in as_completed(futures):
                    item = future.result()
                    statuses.append(item)
                    print(f"{item['status']} {item['key']} ({len(statuses)}/{len(selected)})", flush=True)
                    l1.write_json(args.private_dir / f"{stage}-status.json", statuses)
            if any(r["status"] == "FAILED" for r in statuses):
                raise ValueError(f"{stage} failed; inspect private logs/status. Existing outputs preserved")
        check(args)


def handoff_rows(plan):
    rows = []
    for job in plan["jobs"]:
        for i in range(1, 18 if job["task"] == "ugr" else 5):
            folder = Path(job["output"])
            rows.append(dict(subject=job["subject"], session="01", analysis=job["task"],
                input_runs=job["run"], level="L1", contrast=i, cope=str(folder / f"stats/cope{i}.nii.gz"),
                varcope=str(folder / f"stats/varcope{i}.nii.gz"), mask=str(folder / "mask.nii.gz"),
                dof=str(folder / "stats/dof"), feat_dir=str(folder), selection="candidate_only_not_final_cohort"))
    for job in plan["l2_jobs"]:
        for i in range(1, job["ncopes"] + 1):
            folder = Path(job["output"]) / f"cope{i}.feat"
            rows.append(dict(subject=job["subject"], session="01",
                analysis="ugr" if job["task"] == "ugr" else "socialdoors_doors_mean",
                input_runs="1+2" if job["task"] == "ugr" else "socialdoors:1+doors:1", level="L2",
                contrast=i, cope=str(folder / "stats/cope1.nii.gz"), varcope=str(folder / "stats/varcope1.nii.gz"),
                mask=str(folder / "mask.nii.gz"), dof=str(folder / "stats/tdof_t1.nii.gz"),
                feat_dir=str(folder), selection="candidate_only_not_final_cohort"))
    return rows


def check(args):
    plan = load_plan(args.private_dir)
    jobs = {j["key"]: j for j in plan["jobs"]}
    for job in plan["jobs"]:
        l1.verified_complete(job)
        if audit.file_state(Path(job["output"]) / "stats/dof") != "present":
            raise ValueError("Missing L1 DOF for handoff: " + job["key"])
    for job in plan["l2_jobs"]:
        verified_l2(job, jobs)
    audit.write_table(args.private_dir / "handoff_candidates.tsv", handoff_rows(plan))
    for task in ("ugr", "socialdoors", "doors"):
        subset = [j for j in plan["jobs"] if j["task"] == task]
        print(f"VERIFIED {task}: {len(subset)} L1 runs, {len({j['subject'] for j in subset})} participants")
    print("VERIFIED L2:", dict(Counter(j["task"] for j in plan["l2_jobs"])))
    print("CHECK PASSED: no-TEDANA L1/L2 products and frozen lineage verified.")
    print("Handoff contains alternatives, NOT a final cohort: choose one eligible UGR run subset per subject.")
    print("A QC-rejected run must not enter through the paired L2. Social/Doors L1s remain independently usable.")
    print("Canonical Social Doors L2 is a fixed-effects mean, NOT social-minus-doors. L3 has NOT been run.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "check"))
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--parent-dir", type=Path)
    parser.add_argument("--project-root", type=Path, default=audit.ROOT)
    parser.add_argument("--ugr-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-ugr"))
    parser.add_argument("--socdoors-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-socdoors"))
    parser.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--dispositions", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    if args.jobs < 1 or args.timeout < 1 or args.project_root / "work" not in args.private_dir.parents:
        parser.error("positive jobs/timeout and private directory under project work/ required")
    if args.command == "prepare" and not args.parent_dir:
        parser.error("prepare requires --parent-dir for the successfully completed original batch")
    {"prepare": prepare, "run": run, "check": check}[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
