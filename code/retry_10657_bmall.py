#!/usr/bin/env python3
"""Five-run diagnostic only: never replace the cohort evaluation or eligibility."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

import evaluate_smoothness_6mm as evaluation
import measure_cohort_smoothness as baseline

TARGETS = {("doors", "1"), ("socialdoors", "1"), ("sharedreward", "1"),
           ("trust", "1"), ("trust", "2")}
LOCK_FDS = ()


def select_rows(plan):
    rows = [r for r in plan["rows"] if r["subject"] == "10657" and r["session"] == "01"
            and (r["task"], r["run"]) in TARGETS]
    if len(rows) != 5 or {(r["task"], r["run"]) for r in rows} != TARGETS:
        raise ValueError("Expected exactly the five reviewed 10657 ses-01 runs")
    if any(r["evaluation_action"] != "smooth" for r in rows):
        raise ValueError("A requested run was not active in the frozen evaluation")
    return rows


def image_name(row):
    return evaluation.image_name(row).replace("smoothToFWHM6_", "smoothToFWHM6Bmall_")


def contract():
    return {**evaluation.code_hashes(), Path(__file__).name: baseline.digest(__file__)}


def source_state(args):
    source = args.project / "derivatives/smoothness-evaluation-6mm-v1"
    p = json.loads((source / "plan.json").read_text())
    base = args.project / "work/cohort-smoothness-v1"
    if p["project"] != str(args.project) or p["baseline"] != str(base):
        raise ValueError("Unexpected source project/baseline")
    if p["code_sha256"] != evaluation.code_hashes() or p["tools"] != evaluation.tools_contract():
        raise ValueError("Frozen evaluation code/AFNI differs; do not bypass")
    if p["baseline_plan_sha256"] != baseline.digest(base / "plan.json"):
        raise ValueError("Baseline plan changed")
    for name, digest in p["wrappers"].items():
        if baseline.digest(source / "code" / name) != digest:
            raise ValueError("Frozen Shared Reward wrapper changed")
    rows = select_rows(p)
    protected = [source / "plan.json", source / "validation.json", base / "plan.json",
                 args.project / "qc/run_qc.tsv"]
    old = {}
    for row in rows:
        if baseline.signatures(row) != row["input_hashes"]:
            raise ValueError(f"Original input changed: {baseline.label(row)}")
        func = (args.project / "derivatives/fmriprep").resolve()
        if any(func not in Path(row[k]).resolve().parents for k in ("input_bold", "input_mask")):
            raise ValueError("Retry must use original fMRIPrep inputs")
        name = baseline.label(row)
        old[name] = evaluation.verify_run(source, row, p)
        if float(old[name]["classic_fwhm_combined"]) >= evaluation.LOWER:
            raise ValueError(f"Unexpected original target result: {name}")
        directory = evaluation.result_path(source, row)
        protected.extend(directory / f for f in ("receipt.json", "after.tsv", "command.log"))
        protected.append(directory / evaluation.image_name(row))
    return source, p, rows, old, {str(f): baseline.digest(f) for f in protected}


def command(row, image):
    # Same controller options as the frozen wrapper, except verbose and -bmall.
    return ["3dBlurToFWHM", "-FWHM", "6", "-mask", row["input_mask"],
            "-input", row["input_bold"], "-prefix", str(image), "-bmall"]


def initialize(args, source, p, rows, old, protected):
    plan = {"schema": 1, "code": contract(), "tools": p["tools"], "protected": protected,
            "rows": rows, "original_after": old, "target_mm": 6,
            "eligibility_changed": False, "production_promoted": False,
            "note": "10657 Shared Reward run 1 remains excluded; run 2 remains retained. "
                    "All five outputs are diagnostic only, with no new Trust exclusions."}
    existing = args.output / "plan.json"
    if existing.exists():
        if json.loads(existing.read_text()) != plan:
            raise ValueError("Retry inputs/code/protected results changed; preserve this directory")
        return plan
    for folder in ("code", "diagnostics", "attempts", "runs"):
        (args.output / folder).mkdir(exist_ok=True)
    for name in evaluation.SCRIPTS:
        shutil.copyfile(source / "code" / name, args.output / "code" / name)
    for row in rows:
        name = baseline.label(row)
        original = evaluation.result_path(source, row)
        shutil.copyfile(original / "command.log", args.output / "diagnostics" / f"{name}.original.log")
    baseline.atomic_json(existing, plan)
    return plan


def verify_new(args, row, plan):
    directory = args.output / "runs" / baseline.label(row)
    receipt = json.loads((directory / "receipt.json").read_text())
    image = directory / image_name(row)
    measured = Path(receipt["measured_path"])
    if (measured.name != image.name or args.output / "attempts" not in measured.parents
            or receipt["plan_sha256"] != baseline.digest(args.output / "plan.json")
            or receipt["input_hashes"] != row["input_hashes"]
            or receipt["command"] != command(row, measured)
            or receipt["tools"] != plan["tools"]):
        raise ValueError("Retry receipt lineage mismatch; not overwriting")
    for filename, digest in receipt["files"].items():
        path = (directory / filename).resolve()
        if directory.resolve() not in path.parents or baseline.digest(path) != digest:
            raise ValueError("Retry result changed; not overwriting")
    if not {image.name, "after.tsv", "command.log", "measurement.log"} <= set(receipt["files"]):
        raise ValueError("Incomplete retry receipt")
    evaluation.output_geometry(image, row)
    return baseline.read_result(directory / "after.tsv",
                                {"input_bold": str(measured), "input_mask": row["input_mask"]})


def execute(args, row, plan):
    name = baseline.label(row)
    destination = args.output / "runs" / name
    if destination.exists():
        return "verified", verify_new(args, row, plan)
    attempt = Path(tempfile.mkdtemp(prefix=name + "-", dir=args.output / "attempts"))
    attempt.chmod(0o777 & ~baseline.current_umask())
    image = attempt / image_name(row)
    env = {**os.environ, "AFNI_OMP_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
           "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    commands = [(command(row, image), "command.log"),
                (["bash", str(args.output / "code/measure_smoothness.sh"), "--input", str(image),
                  "--mask", row["input_mask"], "--output-tsv", str(attempt / "after.tsv"),
                  "--work-dir", str(attempt)], "measurement.log")]
    for cmd, logname in commands:
        print("COMMAND:", shlex.join(cmd), flush=True)
        with (attempt / logname).open("w") as log:
            result = subprocess.run(cmd, cwd=attempt, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, pass_fds=LOCK_FDS)
        if result.returncode:
            raise ValueError(f"Exit {result.returncode}; preserved log: {attempt / logname}")
    evaluation.output_geometry(image, row)
    values = baseline.read_result(attempt / "after.tsv",
                                 {"input_bold": str(image), "input_mask": row["input_mask"]})
    if baseline.signatures(row) != row["input_hashes"]:
        raise ValueError("Input changed during retry")
    receipt = {"plan_sha256": baseline.digest(args.output / "plan.json"),
               "input_hashes": row["input_hashes"], "tools": plan["tools"],
               "command": command(row, image), "measured_path": str(image),
               "files": {f: baseline.digest(attempt / f) for f in
                         (image.name, "after.tsv", "command.log", "measurement.log")}}
    baseline.atomic_json(attempt / "receipt.json", receipt)
    os.rename(attempt, destination)
    return "completed", values


def run(args):
    source, p, rows, old, protected = source_state(args)
    if args.command == "check" and not (args.output / "plan.json").is_file():
        raise ValueError("No retry plan; run diagnostic/retry first")
    plan = initialize(args, source, p, rows, old, protected)
    for name, digest in p["wrappers"].items():
        if baseline.digest(args.output / "code" / name) != digest:
            raise ValueError("Retry measurement wrapper changed")
    records, failures, outside = [], 0, 0
    for row in rows:
        name = baseline.label(row)
        dimensions = baseline.geometry(row["input_bold"], row["input_mask"])
        print(f"DIAGNOSTIC {name}: {json.dumps(dimensions)}", flush=True)
        print("ORIGINAL AFTER:", json.dumps(old[name]), flush=True)
        original_log = args.output / "diagnostics" / f"{name}.original.log"
        print("ORIGINAL LOG TAIL (quiet controller may omit stopping details):", flush=True)
        print("\n".join(original_log.read_text(errors="replace").splitlines()[-30:]), flush=True)
        result = {**{k: row[k] for k in baseline.KEYS}, **dimensions,
                  **{f"before_{k}": row["before"][k] for k in baseline.METRICS},
                  **{f"original_after_{k}": old[name][k] for k in baseline.METRICS},
                  "settled_note": "Shared Reward run 1 excluded; diagnostic only" if row["task"] == "sharedreward"
                                  else "No eligibility change", "reason": ""}
        try:
            if args.command == "check":
                status, values = "verified", verify_new(args, row, plan)
            else:
                status, values = execute(args, row, plan)
            within = evaluation.LOWER <= float(values["classic_fwhm_combined"]) <= evaluation.UPPER
            outside += int(not within)
            result.update(status="within_tolerance" if within else "outside_tolerance",
                          **{f"bmall_after_{k}": values[k] for k in baseline.METRICS})
            print(f"{status.upper()} {name}: {json.dumps(values)}; {result['status']}", flush=True)
            print("BMALL CONTROLLER LOG TAIL:", flush=True)
            print("\n".join((args.output / "runs" / name / "command.log").read_text(
                errors="replace").splitlines()[-40:]), flush=True)
        except (OSError, ValueError, KeyError) as exc:
            failures += 1
            result.update(status="failed", reason=str(exc))
            print(f"FAILED {name}: {exc}", flush=True)
        records.append(result)
    for path, digest in protected.items():
        if baseline.digest(path) != digest:
            raise ValueError(f"Protected original changed: {path}")
    for row in rows:
        if baseline.signatures(row) != row["input_hashes"]:
            raise ValueError("Protected input changed")
    fields = list(dict.fromkeys(k for r in records for k in r))
    baseline.write_tsv(args.output / "comparison.tsv", records, fields)
    state = {"technical_complete": failures == 0, "failed": failures, "outside_tolerance": outside,
             "n_runs": 5, "originals_verified_unchanged": True,
             "eligibility_changed": False, "production_promoted": False}
    baseline.atomic_json(args.output / "validation.json", state)
    print(json.dumps(state, indent=2), flush=True)
    print("Settled exclusions preserved, including Shared Reward run 1; no outputs promoted.")
    return 1 if failures else (2 if outside else 0)


def main():
    global LOCK_FDS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "check"))
    parser.add_argument("--project", type=Path, default=evaluation.ROOT)
    args = parser.parse_args()
    args.project = args.project.resolve()
    args.output = (args.project / "derivatives/smoothness-10657-bmall-v1").resolve()
    if (args.output.parent != (args.project / "derivatives").resolve()
            or args.output.name != "smoothness-10657-bmall-v1"
            or (args.project / "derivatives/smoothness-10657-bmall-v1").is_symlink()):
        parser.error("Retry output must remain under project derivatives")
    baseline.UMASK = os.umask(0)
    os.umask(baseline.UMASK)
    try:
        with ExitStack() as stack:
            # Acquire source locks without modifying their contents or deleting lock files.
            locks = [stack.enter_context((args.project / folder / ".lock").open("r")) for folder in
                     ("work/cohort-smoothness-v1", "derivatives/smoothness-evaluation-6mm-v1")]
            for lock in locks:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            args.output.mkdir(exist_ok=True)
            lock = stack.enter_context((args.output / ".lock").open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            LOCK_FDS = tuple(x.fileno() for x in [*locks, lock])
            return run(args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"STOPPED: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
