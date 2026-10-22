#!/usr/bin/env python3
"""Select verified no-TEDANA paper inputs using run-level coverage >=95%."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import sys

import finish_no_tedana as finish

l1, audit = finish.l1, finish.audit
TASKS = ("ugr", "socialdoors", "doors")
POLICY = dict(minimum_coverage_pct=95.0, session="01", minimum_age=55,
              variant=finish.VARIANT, other_qc_flags="descriptive_only",
              settled_decisions="preserved", scope="paper_handoff_only")


def table(rows, fields):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def coverage(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "review_missing_or_invalid"
    if not math.isfinite(number) or not 0 <= number <= 100:
        return "review_missing_or_invalid"
    return "exclude_below_95" if number < 95 else "pass"


def cohort_ids(path):
    """Require a unique explicit ID column; never infer a paper cohort from filenames."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="," if path.suffix.lower() == ".csv" else "\t")
        if len(reader.fieldnames or ()) != len(set(reader.fieldnames or ())):
            raise ValueError("Cohort contains duplicate column names")
        columns = set(reader.fieldnames or ()) & {"subject", "participant_id", "rf1_id"}
        if len(columns) != 1:
            raise ValueError("Cohort needs exactly one subject, participant_id or rf1_id column")
        column = columns.pop()
        ids = [audit.normalize_id(row[column].strip()) for row in reader]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Cohort is empty or contains duplicate participant IDs")
    return set(ids)


def dispositions(path):
    if path is None:
        return {}
    fields, rows, _ = l1.read_tsv(path)
    if not set((*audit.KEY, "decision", "reason", "evidence")) <= set(fields):
        raise ValueError("Dispositions need run key, decision, reason and evidence")
    if any(r["decision"] not in {"include", "exclude", "review", "unavailable"} for r in rows):
        raise ValueError("Unknown reviewed disposition")
    return audit.indexed(rows)


def decide_runs(plan, review, qc, holds, excluded, decisions):
    jobs = audit.indexed(plan["jobs"])
    reviewed = audit.indexed(review)
    if not set(jobs) <= set(reviewed):
        raise ValueError("Frozen review omits planned jobs")
    result = []
    for key, row in sorted(reviewed.items()):
        sub, ses, task, run = key
        if ses != "01" or task not in TASKS or run not in (("1", "2") if task == "ugr" else ("1",)):
            raise ValueError("Unexpected task/session/run in baseline plan")
        q = qc.get(key, {})
        cov = coverage(q.get("brain_coverage_pct"))
        reasons = []
        if row.get("roster_gate") != "member" or sub in excluded:
            reasons.append("source_or_roster_exclusion")
        if row.get("existing_hold") or key in holds:
            reasons.append("settled_run_hold")
        if row.get("existing_decision") in {"exclude", "review", "unavailable"}:
            reasons.append("frozen_disposition:" + row["existing_decision"])
        decision = decisions.get(key, {})
        if decision.get("decision") in {"exclude", "review", "unavailable"}:
            reasons.append("reviewed_disposition:" + decision["decision"])
        if reasons:
            status = "held_existing_decision"
        elif key not in jobs:
            status = "not_in_verified_plan"
            reasons.append(row.get("rerun_status", "unavailable") + ":" + row.get("rerun_reason", ""))
        elif cov != "pass":
            status = cov
            reasons.append(cov)
        else:
            status = "eligible"
        item = dict(zip(audit.KEY, key))
        item.update(coverage_pct=q.get("brain_coverage_pct", ""), coverage_decision=cov,
                    selection_status=status, selection_reason=";".join(reasons),
                    frozen_status=row.get("rerun_status", ""),
                    existing_hold=row.get("existing_hold", "") or holds.get(key, {}).get("reason", ""),
                    existing_decision=row.get("existing_decision", ""),
                    reviewed_decision=decision.get("decision", ""),
                    reviewed_reason=decision.get("reason", ""), reviewed_evidence=decision.get("evidence", ""))
        for name in audit.QC_FIELDS:
            item["flag_or_metric_" + name] = q.get(name, "")
        result.append(item)
    return result


def select(plan, runs):
    eligible = {audit.key(r) for r in runs if r["selection_status"] == "eligible"}
    candidates = finish.handoff_rows(plan)
    chosen = []
    for sub in sorted({key[0] for key in eligible}):
        for task in TASKS:
            available = sorted(k[3] for k in eligible if k[:3] == (sub, "01", task))
            if not available:
                continue
            subset = "+".join(available)
            level = "L2" if task == "ugr" and len(available) == 2 else "L1"
            rows = [r for r in candidates if r["subject"] == sub and r["analysis"] == task
                    and r["input_runs"] == subset and r["level"] == level]
            expected = set(range(1, 18 if task == "ugr" else 5))
            if len(rows) != len(expected) or {r["contrast"] for r in rows} != expected:
                raise ValueError("Missing/duplicate selected contrasts; cannot silently substitute a different run subset")
            chosen.extend(dict(r, selection="selected_coverage95_preserved_decisions") for r in rows)
    return chosen


def verify_products(plan):
    print("Verifying frozen L1/L2 inputs and completed outputs; no FEAT jobs will be launched.", flush=True)
    jobs = {j["key"]: j for j in plan["jobs"]}
    for i, job in enumerate(plan["jobs"], 1):
        l1.verified_complete(job)
        if audit.file_state(Path(job["output"]) / "stats/dof") != "present":
            raise ValueError("Missing L1 DOF: " + job["key"])
        if i % 50 == 0:
            print(f"Verified L1 {i}/{len(jobs)}", flush=True)
    for i, job in enumerate(plan["l2_jobs"], 1):
        finish.verified_l2(job, jobs)
        if i % 25 == 0:
            print(f"Verified L2 {i}/{len(plan['l2_jobs'])}", flush=True)
    print(f"Verified {len(jobs)} L1 and {len(plan['l2_jobs'])} L2 outputs.", flush=True)


def render(plan, runs, cohorts):
    selected = select(plan, runs)
    fields = list(finish.handoff_rows(plan)[0])
    files = {"run_decisions.tsv": table(runs, list(runs[0]))}
    counts, members = [], []
    for task in TASKS:
        rows = [r for r in selected if r["analysis"] == task]
        files[f"{task}/selected_inputs.tsv"] = table(rows, fields)
        subject_ids = sorted({r["subject"] for r in rows})
        files[f"{task}/subjects.txt"] = "".join(s + "\n" for s in subject_ids)
        planned = {j["subject"] for j in plan["jobs"] if j["task"] == task}
        counts.append(dict(scope="imaging", analysis=task, roster_source="frozen_age55_baseline_plan",
                           starting_n=len(planned), selected_n=len(subject_ids),
                           not_selected_n=len(planned - set(subject_ids)),
                           final_paper_n="not_established_without_paper_roster"))
    for name, (task, ids, path) in cohorts.items():
        rows = [r for r in selected if r["analysis"] == task and r["subject"] in ids]
        available = {r["subject"] for r in rows}
        files[f"papers/{name}/selected_inputs.tsv"] = table(rows, fields)
        files[f"papers/{name}/subjects.txt"] = "".join(s + "\n" for s in sorted(available))
        for sub in sorted(ids):
            findings = [r for r in runs if r["subject"] == sub and r["task"] == task]
            members.append(dict(paper=name, analysis=task, subject=sub,
                status="selected" if sub in available else "not_selected",
                input_runs=next((r["input_runs"] for r in rows if r["subject"] == sub), ""),
                reason="" if sub in available else "|".join(
                    f"run-{r['run']}:{r['selection_status']}:{r['selection_reason']}" for r in findings)
                    or "absent_from_frozen_age55_review"))
        counts.append(dict(scope=name, analysis=task, roster_source=str(path),
                           starting_n=len(ids), selected_n=len(available), not_selected_n=len(ids - available),
                           final_paper_n="selected_n_under_recorded_policy"))
    files["counts.tsv"] = table(counts, list(counts[0]))
    files["paper_membership.tsv"] = table(members, ["paper", "analysis", "subject", "status", "input_runs", "reason"])
    files["summary.json"] = json.dumps(dict(policy=POLICY, counts=counts,
        run_status_counts=dict(Counter(r["selection_status"] for r in runs)),
        paper_rosters_supplied=sorted(cohorts),
        note="Flags other than coverage do not exclude unless recorded as reviewed dispositions. "
             "No L3 fit was run. Paper counts are conditional on supplied approved pre-imaging rosters."),
        indent=2, sort_keys=True) + "\n"
    return files, counts


def inputs(config):
    private = Path(config["finish_dir"])
    plan = finish.load_plan(private)
    if not plan["jobs"]:
        raise ValueError("No frozen L1 jobs")
    project = Path(config["project_root"])
    qc_path = project / "qc/run_qc.tsv"
    # The canonical mask metric must be the one frozen with these imaging inputs.
    if not any(r["path"] == str(qc_path) for r in plan["sources"]):
        raise ValueError("Canonical QC path is not frozen in the source plan")
    qc = audit.indexed(l1.read_tsv(qc_path)[1])
    review = l1.read_tsv(private / "run_review.tsv")[1]
    hold_path = project / "code/task_availability_holds.tsv"
    holds = audit.indexed(l1.read_tsv(hold_path)[1])
    parent = l1.load_plan(Path(plan["parent_dir"]))
    exclusions_root = Path(parent["exclusions_root"])
    excluded = {audit.normalize_id(s) for s in l1.exclusions(exclusions_root)}
    decision_path = Path(config["dispositions"]) if config.get("dispositions") else None
    decisions = dispositions(decision_path)
    sources = [private / "plan.json", private / "plan.sha256", private / "run_review.tsv", qc_path,
               hold_path, Path(__file__), Path(finish.__file__), Path(l1.__file__), Path(audit.__file__)]
    if decision_path:
        sources.append(decision_path)
    cohorts = {}
    for name, task in (("katie", "socialdoors"), ("sophia", "ugr"), ("doors", "doors")):
        if config.get(name + "_cohort"):
            path = Path(config[name + "_cohort"])
            cohorts[name] = task, cohort_ids(path), path
            sources.append(path)
    # Capture before validation; reject any changed source before publishing.
    signatures = [l1.signature(p) for p in sorted(set(sources))]
    verify_products(plan)
    runs = decide_runs(plan, review, qc, holds, excluded, decisions)
    files, counts = render(plan, runs, cohorts)
    l1.verify_signatures(signatures)
    if excluded != {audit.normalize_id(s) for s in l1.exclusions(exclusions_root)}:
        raise ValueError("Source-exclusion directory changed during verification")
    return files, counts, signatures, sorted(excluded)


def build(args):
    if args.private_dir.exists():
        raise ValueError("Use a new private directory; never overwrite a prior handoff")
    config = {k: str(getattr(args, k)) if getattr(args, k) else None for k in
              ("finish_dir", "project_root", "dispositions", "katie_cohort", "sophia_cohort", "doors_cohort")}
    files, counts, sources, excluded = inputs(config)
    args.private_dir.mkdir(parents=True, mode=0o700)
    for name, text in files.items():
        path = args.private_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    record = dict(policy=POLICY, config=config, sources=sources, source_exclusions=excluded,
                  outputs={name: audit.sha(args.private_dir / name) for name in files})
    l1.write_json(args.private_dir / "provenance.json", record)
    (args.private_dir / "provenance.sha256").write_text(audit.sha(args.private_dir / "provenance.json") + "\n")
    print_counts(counts)
    print("BUILT: run-level coverage95 handoff. Run check before sharing with Jacob.")
    print(f"Private output: {args.private_dir}")


def check(args):
    p = args.private_dir / "provenance.json"
    if audit.sha(p) != (args.private_dir / "provenance.sha256").read_text().strip():
        raise ValueError("Handoff provenance changed")
    saved = json.loads(p.read_text())
    if saved["policy"] != POLICY:
        raise ValueError("Selection policy changed")
    l1.verify_signatures(saved["sources"])
    files, counts, sources, excluded = inputs(saved["config"])
    if sources != saved["sources"] or excluded != saved["source_exclusions"] or set(files) != set(saved["outputs"]):
        raise ValueError("Handoff sources or exclusions changed")
    for name, expected in files.items():
        path = args.private_dir / name
        if audit.sha(path) != saved["outputs"][name] or path.read_text() != expected:
            raise ValueError("Handoff output changed: " + name)
    print_counts(counts)
    print("CHECK PASSED: coverage >=95%, settled decisions, one input per subject/contrast, "
          "eligible run subsets and no-TEDANA output lineage verified.")


def print_counts(counts):
    for row in counts:
        print(f"{row['scope']} {row['analysis']}: starting N={row['starting_n']}; "
              f"selected N={row['selected_n']}; not selected N={row['not_selected_n']}")
    if not any(r["scope"] in {"katie", "sophia"} for r in counts):
        print("PAPER Ns NOT ESTABLISHED: no approved pre-imaging paper rosters supplied.")
    print("Other QC flags remain descriptive; explicit reviewed dispositions remain binding. L3 not run.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--finish-dir", type=Path)
    parser.add_argument("--project-root", type=Path, default=audit.ROOT)
    parser.add_argument("--dispositions", type=Path)
    for name in ("katie", "sophia", "doors"):
        parser.add_argument("--" + name + "-cohort", type=Path)
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    if args.project_root / "work" not in args.private_dir.parents:
        parser.error("private-dir must be under project work/")
    if args.command == "build" and args.finish_dir is None:
        parser.error("build requires the completed --finish-dir")
    {"build": build, "check": check}[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
