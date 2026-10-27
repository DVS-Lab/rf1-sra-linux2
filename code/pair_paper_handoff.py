#!/usr/bin/env python3
"""Require both Social Doors and Doors to pass, preserving verified UGR inputs."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import handoff_fd_tsnr as source

POLICY = dict(schema_version=1, socialdoors="both_socialdoors_and_doors_pass_same_session",
              ugr="unchanged_from_verified_fd_tsnr_handoff",
              inputs="matched_L1_pairs_not_cross_task_mean_L2",
              difference_contrast_generated=False)
PAIR_FIELDS = ["subject", "session", "contrast"] + [
    f"{task}_{field}" for task in ("socialdoors", "doors")
    for field in ("cope", "varcope", "mask", "dof", "feat_dir")]


def parse(text):
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    return reader.fieldnames, list(reader)


def pair_tables(tables, decisions):
    lookup = source.audit.indexed(decisions)
    indexed = {}
    fields = {}
    for task in ("socialdoors", "doors"):
        fields[task], rows = parse(tables[task])
        indexed[task] = {}
        for row in rows:
            if (row["analysis"], row["session"], row["level"], row["input_runs"]) != (task, "01", "L1", "1"):
                raise ValueError("Expected baseline single-run L1 inputs for " + task)
            key = row["subject"], row["session"], row["contrast"]
            if key in indexed[task]:
                raise ValueError("Duplicate selected contrast")
            indexed[task][key] = row
            run = lookup.get((row["subject"], row["session"], task, "1"), {})
            if run.get("selection_status") != "eligible":
                raise ValueError("Selected task input has no passing run decision")
        for sub, ses in {key[:2] for key in indexed[task]}:
            contrasts = {key[2] for key in indexed[task] if key[:2] == (sub, ses)}
            if contrasts != {"1", "2", "3", "4"}:
                raise ValueError("Incomplete selected task contrast set")
    members = {task: {key[:2] for key in indexed[task]} for task in indexed}
    paired = members["socialdoors"] & members["doors"]
    keys = sorted(key for key in indexed["socialdoors"] if key[:2] in paired)
    pairs = []
    for key in keys:
        pair = dict(zip(("subject", "session", "contrast"), key))
        for task in indexed:
            row = indexed[task][key]
            for field in ("cope", "varcope", "mask", "dof", "feat_dir"):
                pair[f"{task}_{field}"] = row[field]
        pairs.append(pair)
    membership = []
    for sub, ses in sorted(members["socialdoors"] | members["doors"]):
        missing = []
        for task in indexed:
            if (sub, ses) not in members[task]:
                decision = lookup.get((sub, ses, task, "1"), {})
                missing.append(task + ":" + (decision.get("selection_reason") or "no_selected_input"))
        membership.append(dict(subject=sub, session=ses,
                               selected=(sub, ses) in paired, reason=";".join(missing)))
    files = {}
    for task in indexed:
        rows = [indexed[task][key] for key in keys]
        files[f"{task}/selected_inputs.tsv"] = source.old.table(rows, fields[task])
        files[f"{task}/subjects.txt"] = "".join(sub + "\n" for sub, _ in sorted(paired))
    files["paired_socialdoors/selected_pairs.tsv"] = source.old.table(pairs, PAIR_FIELDS)
    files["paired_socialdoors/subjects.txt"] = files["socialdoors/subjects.txt"]
    files["paired_membership.tsv"] = source.old.table(membership, ["subject", "session", "selected", "reason"])
    return files, {task: len(ids) for task, ids in members.items()}, len(paired)


def generate(previous):
    # This independently verifies the source policies, decisions and L1/L2 files.
    source.check(SimpleNamespace(output=previous))
    saved = json.loads((previous / "provenance.json").read_text())
    inputs = [previous / "provenance.json", previous / "provenance.sha256"]
    inputs += [previous / name for name in saved["outputs"]]
    inputs += [Path(__file__).resolve(), Path(source.__file__).resolve()]
    signatures = [source.l1.signature(p) for p in sorted(set(inputs))]
    for name, digest in saved["outputs"].items():
        if source.audit.sha(previous / name) != digest:
            raise ValueError("Source handoff changed during pairing")
    tables = {task: (previous / task / "selected_inputs.tsv").read_text()
              for task in ("socialdoors", "doors")}
    _, decisions = parse((previous / "run_decisions.tsv").read_text())
    files, before, paired_n = pair_tables(tables, decisions)
    for name in ("ugr/selected_inputs.tsv", "ugr/subjects.txt", "run_decisions.tsv", "thresholds_used.tsv"):
        files[name] = (previous / name).read_text()
    _, ugr = parse(files["ugr/selected_inputs.tsv"])
    ugr_n = len({row["subject"] for row in ugr})
    counts = [dict(analysis="ugr", independent_imaging_n=ugr_n, selected_imaging_n=ugr_n),
              dict(analysis="socialdoors_minus_doors", independent_imaging_n="not_applicable", selected_imaging_n=paired_n)]
    files["counts.tsv"] = source.old.table(counts, list(counts[0]))
    files["summary.json"] = json.dumps(dict(policy=POLICY, run_qc_policy=source.POLICY,
        source_handoff=str(previous), independent_task_counts=before, counts=counts,
        paper_Ns="require_intersection_with_approved_October_26_survey_linkage_cohorts"), indent=2, sort_keys=True) + "\n"
    files["README.md"] = (
        "# Paired paper handoff\n\n"
        "Social Doors and Doors tables have identical subjects, sessions and contrast order.\n"
        "Both tasks pass their own FD/tSNR fences and >=95% coverage, with settled exclusions preserved.\n"
        "UGR is unchanged, including passing single-run L1 fallbacks.\n\n"
        "Use paired_socialdoors/selected_pairs.tsv for the Social Doors minus Doors analysis: each row\n"
        "names the two corresponding L1 estimates and variance/mask/DOF files. These are NOT precomputed\n"
        "difference images. The historical cross-task L2 mean is not a difference contrast.\n"
        "Use the established within-participant contrast procedure downstream; do not run an unpaired\n"
        "comparison of the two task cohorts or substitute an average. No new image processing was run.\n\n"
        f"Validated imaging pools: UGR {ugr_n}; paired Social Doors/Doors {paired_n}.\n"
        "Intersect with the unchanged October 26 survey/linkage cohorts for final paper Ns.\n")
    source.l1.verify_signatures(signatures)
    print(f"PAIRED IMAGING N={paired_n} (independent Social Doors={before['socialdoors']}; Doors={before['doors']})")
    print(f"UGR IMAGING N={ugr_n}; input table unchanged byte-for-byte")
    return files, signatures


def build(args):
    if args.output.exists():
        raise ValueError("Use a new output directory; nothing is overwritten")
    files, signatures = generate(args.previous)
    args.output.mkdir(parents=True)
    for name, content in files.items():
        path = args.output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    record = dict(policy=POLICY, previous=str(args.previous), sources=signatures,
                  outputs={name: source.audit.sha(args.output / name) for name in files})
    source.l1.write_json(args.output / "provenance.json", record)
    (args.output / "provenance.sha256").write_text(source.audit.sha(args.output / "provenance.json") + "\n")


def check(args):
    path = args.output / "provenance.json"
    if source.audit.sha(path) != (args.output / "provenance.sha256").read_text().strip():
        raise ValueError("Paired provenance changed")
    saved = json.loads(path.read_text())
    if saved["policy"] != POLICY:
        raise ValueError("Paired policy changed")
    source.l1.verify_signatures(saved["sources"])
    files, signatures = generate(Path(saved["previous"]))
    if signatures != saved["sources"] or set(files) != set(saved["outputs"]):
        raise ValueError("Paired inputs changed")
    for name, content in files.items():
        if source.audit.sha(args.output / name) != saved["outputs"][name] or (args.output / name).read_text() != content:
            raise ValueError("Paired output changed: " + name)
    print("CHECK PASSED: both tasks pass, matched L1 pairs/order, unchanged UGR and preserved run decisions; no processing run.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.previous:
        args.previous = args.previous.resolve()
    if args.command == "build" and args.previous is None:
        parser.error("build requires --previous")
    {"build": build, "check": check}[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
