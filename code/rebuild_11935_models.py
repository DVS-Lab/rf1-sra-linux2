#!/usr/bin/env python3
"""Rebuild only repaired 11935 baseline Faces/Doors activation, never L3.

Consumes promote_11935.apply_plan()'s promotion.json: state="installed", plan
with project/socdoors_root, installs=[{"relpath": ..., "sha256": ...}], and
matching top-level installs/staged_hashes/changed_keys. All canonical inputs
returned by canonical_inputs() must be covered. promote.check() is used only
before creating EVs/models; resume checks canonical installed hashes without
requiring downstream absence or archived cohort outputs. The receipt does not
authorize overriding source exclusions or model holds.

prepare generates canonical EVs (existing EV/model outputs must already have
been archived by promotion). run/check consume an immutable private plan.
Neither old plans nor the historical coverage95 handoff are updated. The finish
executors hardcode their variant environment; these local executors reuse their
validators without mutating finish.VARIANT or any imported module globals.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import finish_no_tedana as finish
import promote_11935 as promote
from genTedanaConfounds import build_confounds
from run_reviewed_source_repairs import validate_bids

l1 = finish.l1
SUBJECT = "11935"
TASKS = ("socialdoors", "doors")
VARIANTS = (finish.VARIANT, "fsl")
MARKER = "rebuild_11935_success.json"
ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def signature(path):
    path = Path(path).absolute()
    if not path.exists():
        require(not path.is_symlink(), f"Broken symlink: {path}")
        return dict(path=str(path), absent=True)
    require(path.is_file(), f"Required regular file: {path}")
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) ==
            (after.st_size, after.st_mtime_ns, after.st_ino), f"File changed while hashing: {path}")
    return dict(path=str(path), size=after.st_size, mtime_ns=after.st_mtime_ns,
                sha256=digest.hexdigest())


def signatures(paths):
    return [signature(p) for p in sorted(set(map(Path, paths)))]


def verify_signatures(records):
    for record in records:
        require(signature(record["path"]) == record, f"Frozen input/output changed: {record['path']}")


def checked_path(root, path):
    path = Path(path)
    path = path if path.is_absolute() else root / path
    require(path.absolute() == path.resolve() and path.is_relative_to(root),
            f"Path escapes canonical root or uses a symlink: {path}")
    return path


def canonical_inputs(project, task):
    paths = l1.audit.input_paths(project, SUBJECT, "01", task, "1")
    stem = f"sub-{SUBJECT}_ses-01_task-{task}_run-1"
    raw = paths["events"].parent
    func = paths["bold"].parent
    source = func / f"{stem}_part-mag_desc-confounds_timeseries.tsv"
    tedana = project / f"derivatives/tedana/sub-{SUBJECT}/ses-01"
    mixing = tedana / f"{stem}_desc-ICA_mixing.tsv"
    metrics = tedana / f"{stem}_desc-tedana_metrics.tsv"
    required = [*paths.values(), source, mixing, metrics,
                func / f"{stem}_part-mag_desc-brain_mask.nii.gz",
                func / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz"]
    for echo in range(1, 5):
        required.append(func / f"{stem}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz")
        for part in ("mag", "phase"):
            required.extend(raw / f"{stem}_echo-{echo}_part-{part}_bold{suffix}"
                            for suffix in (".nii.gz", ".json"))
    refs = sorted(raw.glob(stem + "*_sbref.json"))
    require(refs, f"Missing canonical reference sidecars: {stem}")
    required.extend(refs)
    required.extend(p.with_suffix(".nii.gz") for p in refs)
    return paths, source, mixing, metrics, sorted(set(required))


def verify_promotion(project, receipt_path, socdoors):
    receipt = json.loads(receipt_path.read_text())
    plan = receipt.get("plan", {})
    require(receipt.get("state") == "installed" and plan.get("schema") == 1
            and plan.get("project") == str(project) and plan.get("socdoors_root") == str(socdoors),
            "Promotion receipt must certify installed sub-11935 ses-01 in this project")
    records = plan.get("installs")
    require(isinstance(records, list) and records and receipt.get("installs") == records
            and receipt.get("staged_hashes") == plan.get("staged_hashes")
            and receipt.get("changed_keys") == plan.get("changed_keys") == sorted(
                f"sub-{SUBJECT}_ses-01_task-{task}_run-1" for task in TASKS),
            "Promotion receipt needs consistent installed hashes and exact repaired run keys")
    expected = dict(plan["staged_hashes"])
    expected.pop(promote.SCANS, None)
    if plan.get("scans_merge"):
        expected[promote.SCANS] = hashlib.sha256(plan["scans_merge"]["content"].encode()).hexdigest()
    require({r["relpath"]: r["sha256"] for r in records} == expected,
            "Installed file map differs from staged hashes/merged scans")
    indexed = {}
    for record in records:
        name = record["relpath"]
        promote.relative(name)
        require(name == promote.SCANS or promote.product(name), "Out-of-scope promoted subject/task file")
        path = checked_path(project, record["relpath"])
        require(path not in indexed and re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", "")),
                "Duplicate or invalid promotion fingerprint")
        indexed[path] = record["sha256"]
    required = set(p for task in TASKS for p in canonical_inputs(project, task)[-1])
    require(required <= indexed.keys(), "Promotion receipt does not cover all canonical model/source inputs")
    for path in sorted(indexed):
        require(signature(path).get("sha256") == indexed[path], f"Promoted canonical input changed: {path}")
    validate_bids(project, SUBJECT)
    return receipt


def gates(project, exclusions_root):
    excluded = sorted(l1.exclusions(exclusions_root))
    require("sub-" + SUBJECT not in excluded, "11935 is source-excluded; no automatic lab override")
    roster = project / "bids/participants.tsv"
    fields, rows, _ = l1.read_tsv(roster)
    require({"participant_id", "age"} <= set(fields), "Participants table needs participant_id and age")
    require(sum(r["participant_id"] == "sub-" + SUBJECT for r in rows) == 1,
            "11935 must occur exactly once in approved participants.tsv")
    age = l1.ages(roster, {SUBJECT})[SUBJECT]
    require(age is not None, "11935 baseline age is unavailable; cannot establish base-only eligibility")
    holds_path = project / "code/task_availability_holds.tsv"
    require(holds_path.is_file(), "Settled task hold table unavailable")
    holds = l1.audit.indexed(l1.read_tsv(holds_path)[1])
    decisions_path = project / "qc/run_disposition.tsv"
    decisions = l1.audit.indexed(l1.read_tsv(decisions_path)[1]) if decisions_path.exists() else {}
    for task in TASKS:
        key = (SUBJECT, "01", task, "1")
        require(key not in holds, f"Settled model hold for {task}; explicit review required")
        decision = decisions.get(key, {}).get("decision", "not_recorded")
        require(decision in {"not_recorded", "include", ""},
                f"Settled disposition for {task}: {decision}; no automatic override")
    return age, excluded, [roster, holds_path, decisions_path]


def task_code(root):
    return [root / "code" / name for name in
            ("project_config.sh", "L1stats.sh", "L2stats.sh", "gen3colfiles.sh", "BIDSto3col.sh")] + [
        root / f"templates/L1_task-{task}_model-1_type-act.fsf" for task in TASKS] + [
        root / "templates/L2_task-socialdoors_model-1_type-act.fsf"]


def prerequisites(root):
    for name in ("bash", "awk", "feat", "feat_model", "fslnvols"):
        require(shutil.which(name), f"Required executable unavailable: {name}; load FSL before continuing")
    for path in task_code(root):
        require(path.is_file(), f"Required task script/template unavailable: {path}")
    config = (root / "code/project_config.sh").read_text()
    for name in ("BIDS_ROOT", "FMRIPREP_ROOT", "EV_FILES_ROOT", "FSL_DERIVATIVES_ROOT"):
        require(re.search(r'\b' + name + r'=.*\$\{' + name + r':-', config),
                f"Task project_config.sh must support {name} override")


def environment(project, root, variant):
    require(variant in VARIANTS, "Unknown model variant")
    return dict(os.environ, **l1.THREAD_ENV, FSLSUB_PARALLEL="1",
                RF1_SRA_UPSTREAM_ROOT=str(project), BIDS_ROOT=str(project / "bids"),
                FMRIPREP_ROOT=str(project / "derivatives/fmriprep"),
                CONFOUNDS_ROOT=str(project / "derivatives/fsl/confounds_tedana"),
                FSL_DERIVATIVES_ROOT=str(root / "derivatives" / variant),
                EV_FILES_ROOT=str(root / "derivatives/fsl/EVfiles"))


@contextmanager
def output_locks(root):
    with ExitStack() as stack:
        fds = []
        for variant in sorted(VARIANTS):
            folder = checked_path(root, root / "derivatives" / variant)
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / ".runner.lock"
            require(not path.is_symlink(), "Runner lock cannot be a symlink")
            handle = stack.enter_context(path.open("a+"))
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError(f"Model variant already locked: {path}") from exc
            fds.append(handle.fileno())
        yield tuple(fds)


def model_paths(root, variant, task, level="L1"):
    folder = root / f"derivatives/{variant}/sub-{SUBJECT}/ses-01"
    if level == "L1":
        output = folder / f"L1_task-{task}_ses-01_model-1_type-act_run-1_sm-5.feat"
        rendered = folder / f"L1_sub-{SUBJECT}_task-{task}_ses-01_model-1_type-act_run-1.fsf"
    else:
        output = folder / "L2_task-socialdoors_ses-01_model-1_type-act_sm-5.gfeat"
        rendered = folder / f"L2_sub-{SUBJECT}_task-socialdoors_ses-01_model-1_type-act.fsf"
    return checked_path(root, output), checked_path(root, rendered)


def assert_unowned_absent(root, variants):
    for variant in variants:
        for task, level in [(t, "L1") for t in TASKS] + [("socialdoors", "L2")]:
            output, rendered = model_paths(root, variant, task, level)
            for path in (output, rendered, rendered.with_suffix(".mat"), rendered.with_suffix(".con")):
                require(not path.exists(), f"Unowned/stale output exists; promotion must archive it: {path}")
    for task in TASKS:
        folder = checked_path(root, root / f"derivatives/fsl/EVfiles/sub-{SUBJECT}/ses-01/{task}")
        require(not list(folder.glob("run-1_*.txt")), f"Unowned/stale EVs must be archived by promotion: {folder}")


def validate_canonical(project, task):
    paths, source, mixing, metrics, required = canonical_inputs(project, task)
    require(all(p.is_file() for p in required), f"Missing canonical dependency for {task}")
    states = {k: l1.audit.file_state(p) for k, p in paths.items()}
    nvol, tr, _, findings = l1.audit.validate_inputs(paths, states, "socialdoors")
    require(nvol == 218 and not findings and all(s == "present" for s in states.values()),
            f"{task}: expected aligned 218-volume canonical input; findings={findings}")
    base = finish.base_confounds(source)
    l1.validate_alignment(base, paths["bold"])
    production = build_confounds(source, mixing, metrics)
    l1.validate_alignment(production, paths["bold"])
    l1.verify_existing(production, paths["confounds"])
    return paths, source, base, nvol, tr, required


def make_jobs(args, variants, promotion_hash):
    jobs = []
    for task in TASKS:
        paths, source, base, nvol, tr, required = validate_canonical(args.project_root, task)
        row = dict(subject=SUBJECT, session="01", task=task, run="1")
        evs = l1.ev_paths(args.socdoors_root, row)
        for variant in variants:
            output, rendered = model_paths(args.socdoors_root, variant, task)
            confounds = paths["confounds"]
            if variant == finish.VARIANT:
                confounds = args.private_dir / "confounds" / (f"sub-{SUBJECT}_ses-01_task-{task}_run-1"
                                                             "_desc-FmriprepOnlyConfounds.tsv")
                l1.atomic_write_tsv(base, confounds, preserve_existing=True)
            jobs.append(dict(key=f"sub-{SUBJECT}_ses-01_task-{task}_run-1", subject=SUBJECT,
                session="01", task=task, run="1", variant=variant, root=str(args.socdoors_root),
                project_root=str(args.project_root), private_dir=str(args.private_dir),
                promotion_sha256=promotion_hash, output=str(output), rendered=str(rendered),
                bold=str(paths["bold"]), confounds=str(confounds), source_confounds=str(source),
                columns=list(base) if variant == finish.VARIANT else [], nvol=nvol, tr=tr,
                inputs=signatures([*required, *evs, confounds, *task_code(args.socdoors_root)])))
    return jobs


def l2_jobs(jobs):
    result = []
    for variant in dict.fromkeys(j["variant"] for j in jobs):
        selected = [j for j in jobs if j["variant"] == variant]
        paired = finish.l2_jobs(selected)
        require(len(paired) == 1, "Expected exactly the Faces/Doors pair per variant")
        job = paired[0]
        output, rendered = model_paths(Path(job["root"]), variant, "socialdoors", "L2")
        job.update(variant=variant, project_root=selected[0]["project_root"],
                   private_dir=selected[0]["private_dir"], promotion_sha256=selected[0]["promotion_sha256"],
                   output=str(output), rendered=str(rendered))
        job["code"] = signatures(r["path"] for r in job["code"])
        result.append(job)
    return result


def prepare(args):
    require(not args.private_dir.exists(), "Use a new private directory; plans are immutable")
    prerequisites(args.socdoors_root)
    with output_locks(args.socdoors_root) as fds:
        verify_promotion(args.project_root, args.promotion_receipt, args.socdoors_root)
        age, excluded, gate_files = gates(args.project_root, args.exclusions_root)
        variants = VARIANTS if age >= 55 else ("fsl",)
        assert_unowned_absent(args.socdoors_root, variants)
        promote.check(args.promotion_receipt)
        for task in TASKS:
            validate_canonical(args.project_root, task)
        sources = signatures([*gate_files, args.promotion_receipt, *task_code(args.socdoors_root),
            Path(__file__), Path(finish.__file__), Path(l1.__file__),
            Path(promote.__file__),
            ROOT / "code/genTedanaConfounds.py", ROOT / "code/run_reviewed_source_repairs.py",
            ROOT / "code/participants.py", ROOT / "code/audit_task_availability.py"])
        args.private_dir.mkdir(parents=True, mode=0o700)
        (args.private_dir / "logs").mkdir()
        cmd = ["bash", str(args.socdoors_root / "code/gen3colfiles.sh"), "--subject", SUBJECT,
               "--session", "01", "--task", "all"]
        with (args.private_dir / "logs/generate_evs.log").open("w") as log:
            subprocess.run(cmd, env=environment(args.project_root, args.socdoors_root, "fsl"),
                           stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=fds)
        verify_signatures(sources)
        jobs = make_jobs(args, variants, l1.audit.sha(args.promotion_receipt))
        plan = dict(schema=1, subject=SUBJECT, session="01", project_root=str(args.project_root),
                    socdoors_root=str(args.socdoors_root), private_dir=str(args.private_dir),
                    promotion_receipt=str(args.promotion_receipt), exclusions_root=str(args.exclusions_root),
                    baseline_age=str(age), source_exclusions=excluded, sources=sources,
                    qc_used_for_selection=False, paper_eligibility="unchanged_not_reinstated",
                    l3_requires_rerun=True, jobs=jobs, l2_jobs=l2_jobs(jobs))
        l1.write_json(args.private_dir / "plan.json", plan)
        (args.private_dir / "plan.sha256").write_text(l1.audit.sha(args.private_dir / "plan.json") + "\n")
        load_plan(args)
        print(f"PREPARED: {len(jobs)} L1 / {len(plan['l2_jobs'])} L2 models; paper eligibility unchanged")


def load_plan(args):
    path = args.private_dir / "plan.json"
    require(l1.audit.sha(path) == (args.private_dir / "plan.sha256").read_text().strip(), "Plan changed")
    plan = json.loads(path.read_text())
    for name in ("project_root", "socdoors_root", "private_dir", "promotion_receipt", "exclusions_root"):
        require(plan[name] == str(getattr(args, name)), f"Plan {name} differs from CLI")
    require(plan["schema"] == 1 and plan["subject"] == SUBJECT and plan["session"] == "01"
            and plan["qc_used_for_selection"] is False and plan["l3_requires_rerun"] is True
            and plan["paper_eligibility"] == "unchanged_not_reinstated", "Unexpected plan policy/scope")
    verify_signatures(plan["sources"])
    verify_promotion(args.project_root, args.promotion_receipt, args.socdoors_root)
    age, excluded, _ = gates(args.project_root, args.exclusions_root)
    require(str(age) == plan["baseline_age"] and excluded == plan["source_exclusions"], "Eligibility changed")
    variants = VARIANTS if age >= 55 else ("fsl",)
    require({(j["variant"], j["task"]) for j in plan["jobs"]} ==
            {(v, t) for v in variants for t in TASKS} and len(plan["jobs"]) == len(variants) * 2,
            "Unexpected or duplicate job scope")
    for job in plan["jobs"]:
        output, rendered = model_paths(args.socdoors_root, job["variant"], job["task"])
        require(job["subject"] == SUBJECT and job["session"] == "01" and job["run"] == "1"
                and job["root"] == str(args.socdoors_root) and job["nvol"] == 218
                and job["output"] == str(output) and job["rendered"] == str(rendered), "Out-of-scope model")
        verify_signatures(job["inputs"])
        validate_canonical(args.project_root, job["task"])
        if job["variant"] == finish.VARIANT:
            base = finish.base_confounds(Path(job["source_confounds"]))
            require(list(base) == job["columns"], "Base confound columns changed")
            l1.verify_existing(base, Path(job["confounds"]))
    require(plan["l2_jobs"] == l2_jobs(plan["jobs"]), "L2 linkage/code changed")
    return plan


def command(job, render=False):
    cmd = ["bash", str(Path(job["root"]) / "code/L1stats.sh"), SUBJECT, "1", "0", job["task"],
           "--session", "01", "--bold", job["bold"], "--confounds", job["confounds"]]
    if render:
        cmd.append("--render-only")
    return cmd, environment(Path(job["project_root"]), Path(job["root"]), job["variant"])


def products(job):
    output = Path(job["output"])
    return signatures(p for p in output.rglob("*") if p.is_file() and
                      (p.suffix in {".fsf", ".mat", ".con"} or p.name.endswith(".nii.gz")
                       or p.name == "dof" or "reg" in p.relative_to(output).parts))


def verified_l1(job):
    marker = Path(job["output"]) / MARKER
    require(marker.is_file(), f"Unowned/stale L1 output has no rebuild receipt: {job['output']}")
    saved = json.loads(marker.read_text())
    require(saved["job"] == job, "Unowned model or different repair/plan; archive through promotion")
    verify_signatures(job["inputs"])
    require(saved["outputs"] == products(job), "Completed L1 products changed")
    l1.validate_output(job)
    require(l1.audit.file_state(Path(job["output"]) / "stats/dof") == "present", "Missing L1 residual DOF")


def l2_dependencies(job, jobs):
    result = []
    for key in job["input_keys"]:
        source = jobs[key]
        verified_l1(source)
        folder = Path(source["output"])
        result += signatures([folder / MARKER, folder / "stats/dof"] +
                             [p for p in (folder / "reg").rglob("*") if p.is_file()])
    return result


def verified_l2(job, jobs):
    marker = Path(job["output"]) / MARKER
    require(marker.is_file(), f"Unowned/stale L2 output has no rebuild receipt: {job['output']}")
    saved = json.loads(marker.read_text())
    require(saved["job"] == job and saved["dependencies"] == l2_dependencies(job, jobs),
            "Unowned L2 or changed L1 lineage")
    verify_signatures(job["code"])
    require(saved["outputs"] == products(job), "Completed L2 products changed")
    finish.validate_l2(job)


def execute_l1(job, private, lock_fds):
    verify_signatures(job["inputs"])
    if Path(job["output"]).exists():
        verified_l1(job)
        return "SKIPPED_COMPLETE"
    with (private / "logs" / f"{job['variant']}-{job['key']}.log").open("a") as log:
        cmd, env = command(job, True)
        subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
        fsf = Path(job["rendered"])
        l1.validate_fsf(fsf, job)
        subprocess.run(["feat_model", str(fsf.with_suffix("")), job["confounds"]], env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
        l1.validate_design(fsf.with_suffix(".mat"), fsf.with_suffix(".con"), job)
        cmd, env = command(job)
        subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
    l1.validate_output(job)
    require(l1.audit.file_state(Path(job["output"]) / "stats/dof") == "present", "Missing L1 residual DOF")
    verify_signatures(job["inputs"])
    l1.write_json(Path(job["output"]) / MARKER, dict(job=job, outputs=products(job)))
    return "COMPLETED"


def execute_l2(job, jobs, private, lock_fds, timeout):
    dependencies = l2_dependencies(job, jobs)
    verify_signatures(job["code"])
    if Path(job["output"]).exists():
        verified_l2(job, jobs)
        return "SKIPPED_COMPLETE"
    env = environment(Path(job["project_root"]), Path(job["root"]), job["variant"])
    with (private / "logs" / f"{job['variant']}-{job['key']}.log").open("a") as log:
        cmd = ["bash", str(Path(job["root"]) / "code/L2stats.sh"), SUBJECT, "act",
               "--session", "01", "--render-only"]
        subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
        finish.validate_l2_fsf(Path(job["rendered"]), job)
        subprocess.run(["feat", job["rendered"]], env=env, stdout=log,
                       stderr=subprocess.STDOUT, check=True, pass_fds=lock_fds)
        deadline = time.monotonic() + timeout
        while any(l1.audit.file_state(p) != "present" for p in finish.l2_products(job)):
            require(time.monotonic() < deadline, "L2 completion timed out; inspect child jobs before retry")
            time.sleep(1)
    finish.validate_l2(job)
    require(dependencies == l2_dependencies(job, jobs), "L1 changed while L2 ran")
    verify_signatures(job["code"])
    l1.write_json(Path(job["output"]) / MARKER,
                  dict(job=job, dependencies=dependencies, outputs=products(job)))
    return "COMPLETED"


def check_locked(args):
    plan = load_plan(args)
    for job in plan["jobs"]:
        verified_l1(job)
    for job in plan["l2_jobs"]:
        jobs = {j["key"]: j for j in plan["jobs"] if j["variant"] == job["variant"]}
        verified_l2(job, jobs)
    rows = [dict(subject=SUBJECT, session="01", variant=j["variant"], task=j["task"],
                 level="L1", output=j["output"], model_status="verified", paper_eligibility="unchanged_not_reinstated",
                 l3_requires_rerun=True) for j in plan["jobs"]]
    rows += [dict(subject=SUBJECT, session="01", variant=j["variant"], task="socialdoors_doors_mean",
                  level="L2", output=j["output"], model_status="verified", paper_eligibility="unchanged_not_reinstated",
                  l3_requires_rerun=True) for j in plan["l2_jobs"]]
    l1.audit.write_table(args.private_dir / "subject_ready.tsv", rows)
    l1.write_json(args.private_dir / "completion.json", dict(validated=True, l3_requires_rerun=True,
        paper_eligibility="unchanged_not_reinstated", plan_sha256=l1.audit.sha(args.private_dir / "plan.json"),
        ready=signature(args.private_dir / "subject_ready.tsv")))
    print(f"CHECK PASSED: {len(plan['jobs'])} L1 / {len(plan['l2_jobs'])} L2 models; L3 requires rerun; no cohort N claimed")


def run(args):
    prerequisites(args.socdoors_root)
    with output_locks(args.socdoors_root) as fds:
        l1.write_json(args.private_dir / "completion.json", dict(validated=False, status="running"))
        plan = load_plan(args)
        statuses = []
        for job in plan["jobs"]:
            status = execute_l1(job, args.private_dir, fds)
            statuses.append(dict(variant=job["variant"], key=job["key"], status=status))
            l1.write_json(args.private_dir / "run-status.json", statuses)
        for job in plan["l2_jobs"]:
            jobs = {j["key"]: j for j in plan["jobs"] if j["variant"] == job["variant"]}
            status = execute_l2(job, jobs, args.private_dir, fds, args.timeout)
            statuses.append(dict(variant=job["variant"], key=job["key"], status=status))
            l1.write_json(args.private_dir / "run-status.json", statuses)
        check_locked(args)


def check(args):
    with output_locks(args.socdoors_root):
        l1.write_json(args.private_dir / "completion.json", dict(validated=False, status="checking"))
        check_locked(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "check"))
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--socdoors-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-socdoors"))
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--promotion-receipt", type=Path, required=True)
    parser.add_argument("--exclusions-root", type=Path, default=EXCLUSIONS)
    parser.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            require(value.absolute() == value.resolve(), f"CLI path cannot use symlinks or '..': {value}")
            setattr(args, name, value.resolve())
    require(args.private_dir.is_relative_to(args.project_root / "work")
            and args.private_dir != args.project_root / "work" and args.timeout > 0,
            "Positive timeout and new private directory below project work/ required")
    {"prepare": prepare, "run": run, "check": check}[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except (ImportError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
