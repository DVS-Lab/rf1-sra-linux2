#!/usr/bin/env python3
"""Replace a coverage-only handoff with task/session FD+tSNR+coverage selection.

Read-only with respect to processing, QC and the prior handoff. Only a new
handoff directory is written. Historical processing code need not be restored.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import sys

import build_run_qc as canonical
import handoff_coverage95 as old

audit, l1, finish = old.audit, old.l1, old.finish
POLICY = dict(schema_version=1, minimum_coverage_pct=95.0,
              fd_mean="upper_1.5_IQR", tsnr="lower_1.5_IQR",
              threshold_grouping=["task", "session"], threshold_passes=1,
              threshold_population="full_canonical_QC_not_paper_or_age_subset",
              selection="parallel_union_of_run_failures", session="01", minimum_age=55,
              tedana_exclusion=False, settled_decisions="preserved",
              variant=finish.VARIANT)


def number(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def validated_thresholds(rows, saved, policy):
    """Reproduce canonical fences once, without conditioning on exclusions."""
    if (policy.get("threshold_grouping") != ["task", "session"]
            or policy.get("iqr_multiplier") != 1.5
            or policy.get("threshold_passes") != 1
            or policy.get("quartile_method") != "linear"):
        raise ValueError("Expected canonical single-pass task/session 1.5-IQR policy")
    for metric, direction in (("fd_mean", "upper"), ("tsnr", "lower")):
        if policy["metrics"][metric]["direction"] != direction:
            raise ValueError("Unexpected QC direction: " + metric)
    typed = [dict(r, fd_mean=number(r.get("fd_mean")), tsnr=number(r.get("tsnr"))) for r in rows]
    config = dict(policy, task_map={t: p for p, tasks in policy["paradigms"].items() for t in tasks},
                  metrics={m: policy["metrics"][m] for m in ("fd_mean", "tsnr")})
    computed = canonical.compute_thresholds(typed, config)
    relevant = [r for r in saved if r["metric"] in config["metrics"]]
    def key(row):
        return row["task"], row["session"], row["metric"]
    lookup = {key(r): r for r in relevant}
    if len(lookup) != len(relevant) or set(lookup) != {key(r) for r in computed}:
        raise ValueError("Missing/duplicate canonical thresholds")
    for row in computed:
        recorded = lookup[key(row)]
        if int(recorded["n"]) != row["n"] or recorded["outlier_direction"] != row["outlier_direction"]:
            raise ValueError("Canonical threshold population/direction differs")
        for field in ("q1", "q3", "iqr", "lower_fence", "upper_fence"):
            a, b = number(recorded[field]), row[field]
            if (a is None) != (b is None) or (a is not None and not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError("Canonical threshold differs: " + str(key(row)))
    calculated = {key(r): r for r in computed}
    for row in typed:
        for metric in config["metrics"]:
            value = row[metric]
            threshold = calculated[(row["task"], row["session"], metric)]
            expected = None if value is None else (
                value > threshold["upper_fence"] if metric == "fd_mean" else value < threshold["lower_fence"])
            stored = str(row.get(metric + "_outlier", "")).lower()
            if expected is not None and stored != str(expected).lower():
                raise ValueError("Canonical QC flag disagrees with metric/fence: " + str(audit.key(row)))
            if expected:
                threshold["n_outliers"] += 1
    return calculated, computed


def decide(previous, qc, thresholds, holds, excluded):
    result = []
    for original in previous:
        row = dict(original)
        key = audit.key(row)
        sub, ses, task, run = key
        if ses != "01" or task not in old.TASKS or run not in (("1", "2") if task == "ugr" else ("1",)):
            raise ValueError("Unexpected baseline run key")
        q = qc.get(key, {})
        failures = []
        cov = old.coverage(q.get("brain_coverage_pct"))
        if cov != "pass":
            failures.append("coverage:" + cov)
        row.update(previous_selection_status=original["selection_status"],
                   previous_selection_reason=original["selection_reason"],
                   coverage_pct=q.get("brain_coverage_pct", ""), coverage_decision=cov)
        for metric, fence, reason in (("fd_mean", "upper_fence", "high_fd_mean"),
                                       ("tsnr", "lower_fence", "low_tsnr")):
            threshold = thresholds.get((task, ses, metric), {})
            value, limit = number(q.get(metric)), number(threshold.get(fence))
            state = "pass"
            if value is None or value < 0 or limit is None:
                state = "review_missing_or_invalid"
            elif (value > limit if metric == "fd_mean" else value < limit):
                state = reason
            if state != "pass":
                failures.append(metric + ":" + state)
            row.update({metric: q.get(metric, ""), metric + "_fence": limit,
                        metric + "_decision": state})
        for name in audit.QC_FIELDS:
            row["flag_or_metric_" + name] = q.get(name, "")
        row["qc_failure_reasons"] = ";".join(failures)
        # Never reinstate a previously withheld run or override a settled hold.
        if original["selection_status"] != "eligible":
            pass
        elif sub in excluded or key in holds:
            row["selection_status"] = "held_existing_decision"
            row["selection_reason"] = "source_exclusion" if sub in excluded else "settled_run_hold:" + holds[key].get("reason", "")
        elif failures:
            row["selection_status"] = "review_missing_or_invalid" if any("review_" in f for f in failures) else "excluded_run_qc"
            row["selection_reason"] = ";".join(failures)
        result.append(row)
    return result


def selection_changes(plan, previous, current):
    before, after = old.select(plan, previous), old.select(plan, current)
    def index(rows):
        return {(r["analysis"], r["subject"]): (r["level"], r["input_runs"]) for r in rows}
    a, b = index(before), index(after)
    changes = []
    for task, sub in sorted(set(a) | set(b)):
        prior, new = a.get((task, sub), ("", "")), b.get((task, sub), ("", ""))
        changes.append(dict(task=task, subject=sub, previous_level=prior[0], previous_runs=prior[1],
                            selected_level=new[0], selected_runs=new[1],
                            change="unchanged" if prior == new else "removed" if not new[0] else "run_subset_changed",
                            reasons="|".join(f"run-{r['run']}:{r['selection_reason']}" for r in current
                                             if r["subject"] == sub and r["task"] == task and r["selection_status"] != "eligible")))
    return changes


def verify_selected(plan, runs):
    selected = old.select(plan, runs)
    needed = {(r["subject"], r["session"], r["analysis"], run)
              for r in selected for run in r["input_runs"].split("+")}
    jobs = {j["key"]: j for j in plan["jobs"]}
    verified = 0
    for job in plan["jobs"]:
        if audit.key(job) not in needed:
            continue
        if Path(job["root"]) / "derivatives" / finish.VARIANT not in Path(job["output"]).parents:
            raise ValueError("Selected L1 outside isolated no-TEDANA outputs")
        l1.verified_complete(job)
        verified += 1
        if verified % 25 == 0:
            print(f"Verified selected L1 {verified}/{len(needed)}", flush=True)
    pairs = {r["subject"] for r in selected if r["analysis"] == "ugr" and r["level"] == "L2"}
    verified = 0
    for job in plan["l2_jobs"]:
        if job["task"] == "ugr" and job["subject"] in pairs:
            finish.verified_l2(job, jobs)
            verified += 1
            if verified % 25 == 0:
                print(f"Verified selected UGR L2 {verified}/{len(pairs)}", flush=True)
    for row in selected:
        for name in ("cope", "varcope", "mask", "dof"):
            if audit.file_state(Path(row[name])) != "present":
                raise ValueError("Selected input missing: " + row[name])
    print(f"VERIFIED: {len(needed)} selected L1 runs and {len(pairs)} selected UGR pairs; no processing launched.", flush=True)


def generate(config):
    sources = {}
    def read(path):
        path = Path(path)
        if not path.is_file():
            raise ValueError("Required input missing: " + str(path))
        signature = l1.signature(path)
        if str(path) in sources and sources[str(path)] != signature:
            raise ValueError("Input changed during read")
        sources[str(path)] = signature
        return path.read_text()
    def rows(path):
        return list(csv.DictReader(io.StringIO(read(path)), delimiter="\t"))
    previous = Path(config["previous"])
    project = Path(config["project"])
    record = read(previous / "provenance.json")
    if audit.sha(previous / "provenance.json") != read(previous / "provenance.sha256").strip():
        raise ValueError("Previous handoff provenance changed")
    saved = json.loads(record)
    if saved["policy"] != old.POLICY:
        raise ValueError("Expected original coverage95 handoff")
    if Path(saved["config"]["project_root"]).resolve() != project:
        raise ValueError("Previous handoff belongs to a different project")
    for name, digest in saved["outputs"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Unsafe prior output path")
        read(previous / name)
        if audit.sha(previous / name) != digest:
            raise ValueError("Previous handoff output changed: " + name)
    finish_dir = Path(saved["config"]["finish_dir"])
    plan_path = finish_dir / "plan.json"
    plan_text = read(plan_path)
    plan_hash = audit.sha(plan_path)
    pinned = next((s for s in saved["sources"] if s["path"] == str(plan_path)), {})
    if plan_hash != pinned.get("sha256") or plan_hash != read(finish_dir / "plan.sha256").strip():
        raise ValueError("Original completed processing plan changed")
    plan = json.loads(plan_text)
    if plan["variant"] != finish.VARIANT or plan["qc_used_for_selection"] is not False:
        raise ValueError("Unexpected processing plan")
    previous_runs = rows(previous / "run_decisions.tsv")
    audit.indexed(previous_runs)
    # Anchor regenerated paths/run subsets to the previously validated handoff.
    candidates = old.select(plan, previous_runs)
    for task in old.TASKS:
        expected = [{k: str(v) for k, v in r.items()} for r in candidates if r["analysis"] == task]
        if expected != rows(previous / task / "selected_inputs.tsv"):
            raise ValueError("Previous selection disagrees with pinned plan")
    qc_rows = rows(project / "qc/run_qc.tsv")
    qc = audit.indexed(qc_rows)
    policy = json.loads(read(project / "qc/qc_policy.json"))
    thresholds, computed = validated_thresholds(qc_rows, rows(project / "qc/thresholds.tsv"), policy)
    provenance = json.loads(read(project / "qc/provenance.json"))
    excluded = set(saved["source_exclusions"]) | set(provenance["inventory"]["source_excluded_subjects"])
    holds = audit.indexed(rows(project / "code/task_availability_holds.tsv"))
    cohorts = {}
    for name, task in (("katie", "socialdoors"), ("sophia", "ugr"), ("doors", "doors")):
        if config.get(name + "_cohort"):
            path = Path(config[name + "_cohort"])
            read(path)
            cohorts[name] = task, old.cohort_ids(path), path
    runs = decide(previous_runs, qc, thresholds, holds, excluded)
    verify_selected(plan, runs)
    files, counts = old.render(plan, runs, cohorts)
    for name in list(files):
        if name.endswith("selected_inputs.tsv"):
            files[name] = files[name].replace("selected_coverage95_preserved_decisions", "selected_coverage95_fd_tsnr_preserved_decisions")
    summary = json.loads(files["summary.json"])
    summary.update(policy=POLICY, previous=str(previous),
                   note="FD, tSNR and coverage applied together at run level. No TEDANA-count exclusion. "
                        "Paper Ns require approved survey/linkage rosters. No processing or L3 fit run.")
    files["summary.json"] = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    changes = selection_changes(plan, previous_runs, runs)
    files["selection_changes.tsv"] = old.table(changes, ["task", "subject", "previous_level", "previous_runs", "selected_level", "selected_runs", "change", "reasons"])
    files["thresholds_used.tsv"] = old.table(computed, list(computed[0]))
    for module in (sys.modules[__name__], old, finish, l1, audit, canonical):
        read(Path(module.__file__).resolve())
    l1.verify_signatures(list(sources.values()))
    for task in old.TASKS:
        c = [r for r in changes if r["task"] == task]
        print(f"CHANGE {task}: previous N={len(c)}; updated N={sum(bool(r['selected_level']) for r in c)}; "
              f"{dict(Counter(r['change'] for r in c))}")
        assessed = [r for r in runs if r["task"] == task and r["previous_selection_status"] == "eligible"]
        print(f"RUN QC {task} ses-01 (overlapping counts among previously selected runs): "
              f"high FD={sum(r['fd_mean_decision'] == 'high_fd_mean' for r in assessed)}; "
              f"low tSNR={sum(r['tsnr_decision'] == 'low_tsnr' for r in assessed)}; "
              f"coverage below 95={sum(r['coverage_decision'] == 'exclude_below_95' for r in assessed)}; "
              f"missing/invalid={sum('review_missing_or_invalid' in r['qc_failure_reasons'] for r in assessed)}")
        for metric, fence in (("fd_mean", "upper_fence"), ("tsnr", "lower_fence")):
            threshold = thresholds[(task, "01", metric)]
            print(f"FENCE {task} ses-01 {metric}: n={threshold['n']} {fence}={threshold[fence]}")
    for count in counts:
        print(f"{count['scope']} {count['analysis']}: selected N={count['selected_n']}; starting N={count['starting_n']}")
    if not cohorts:
        print("PAPER Ns NOT ESTABLISHED: imaging Ns only; intersect updated inputs with October 26 survey/linkage cohorts.")
    return files, sorted(sources.values(), key=lambda r: r["path"])


def build(args):
    if args.output.exists():
        raise ValueError("Use a new output directory; prior results are never overwritten")
    config = {k: str(getattr(args, k)) if getattr(args, k) else None
              for k in ("previous", "project", "katie_cohort", "sophia_cohort", "doors_cohort")}
    files, sources = generate(config)
    args.output.mkdir(parents=True)
    for name, content in files.items():
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    record = dict(policy=POLICY, config=config, sources=sources,
                  outputs={name: audit.sha(args.output / name) for name in files})
    l1.write_json(args.output / "provenance.json", record)
    (args.output / "provenance.sha256").write_text(audit.sha(args.output / "provenance.json") + "\n")
    print("BUILT: replacement handoff; run check before using it for L3.")


def check(args):
    path = args.output / "provenance.json"
    if audit.sha(path) != (args.output / "provenance.sha256").read_text().strip():
        raise ValueError("Replacement provenance changed")
    saved = json.loads(path.read_text())
    if saved["policy"] != POLICY:
        raise ValueError("Replacement policy changed")
    l1.verify_signatures(saved["sources"])
    files, sources = generate(saved["config"])
    if sources != saved["sources"] or set(files) != set(saved["outputs"]):
        raise ValueError("Replacement inputs changed")
    for name, content in files.items():
        if audit.sha(args.output / name) != saved["outputs"][name] or (args.output / name).read_text() != content:
            raise ValueError("Replacement output changed: " + name)
    print("CHECK PASSED: task/session FD+tSNR, coverage >=95%, preserved decisions and selected no-TEDANA L1/L2 products.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--project", type=Path, default=audit.ROOT)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    for name in ("katie", "sophia", "doors"):
        parser.add_argument("--" + name + "-cohort", type=Path)
    args = parser.parse_args()
    for k, v in vars(args).items():
        if isinstance(v, Path):
            setattr(args, k, v.resolve())
    if args.command == "build" and args.previous is None:
        parser.error("build requires --previous")
    if args.project / "work" not in args.output.parents:
        parser.error("output must be a new directory under project work/")
    {"build": build, "check": check}[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
