#!/usr/bin/env python3
"""Build and verify private Social Doors/UGR handoff manifests, without running FEAT."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import audit_task_availability as audit


def table(fields, rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def disposition(row):
    # Recorded and recalculated QC flags are deliberately not used here.
    if row["roster_gate"] != "member":
        return "held", "upstream_roster_gate"
    if row["existing_hold"]:
        return "held", row["existing_hold"]
    if row["existing_decision"] in {"exclude", "review", "unavailable"}:
        return "held", row["existing_decision"] + ":" + row["decision_reason"]
    if row["technical_status"] != "inputs_present_aligned":
        reason = ";".join(filter(None, (row["missing_inputs"], row["input_findings"])))
        return "missing", reason or "technical_review_required"
    return "ready", ""


def manifests(rows):
    outputs = {}
    for task in ("ugr", "socialdoors"):
        keys = ["subject", "session", "run"] if task == "ugr" else list(audit.KEY)
        for state in ("ready", "missing", "held"):
            fields = keys if state == "ready" else [*keys, "reason"]
            selected = []
            for row in rows:
                status, reason = disposition(row)
                if row["task"] != task or status != state:
                    continue
                item = {field: row[field] for field in keys}
                if state != "ready":
                    item["reason"] = reason
                selected.append(item)
            outputs[f"{task}/L1-{state}.tsv"] = table(fields, selected)
    return outputs


def validate_builder_tables(output, rows):
    """Each expected member run must occur exactly once, with no wildcard omissions."""
    for task in ("ugr", "socialdoors"):
        expected = {audit.key(r): r for r in rows if r["task"] == task and r["roster_gate"] == "member"}
        found = {}
        for state in ("ready", "missing"):
            _, records, _ = audit.read_tsv(output / f"raw-{task}-{state}.tsv")
            for record in records:
                record.setdefault("task", task)
                key = audit.key(record)
                if key not in expected or key in found:
                    raise ValueError("builder contains duplicate or out-of-scope run keys")
                found[key] = state
        if set(found) != set(expected):
            raise ValueError("builder omitted expected run slots; update the task repositories")
        if any(found[k] != "ready" for k, r in expected.items()
               if r["technical_status"] == "inputs_present_aligned"):
            raise ValueError("builder disagrees with validated current inputs")
        # Builders check presence/model types; the upstream audit additionally checks
        # timing, image headers and row alignment before allowing a ready export.


def run_private(command, log):
    proc = subprocess.run(command, capture_output=True, text=True)
    log.write_text(proc.stdout + proc.stderr)
    if proc.returncode:
        raise ValueError("handoff prerequisite failed; inspect private command logs")


def build(args, output):
    if output.exists():
        raise ValueError("use a new private directory; previous snapshots are preserved")
    if args.sessions != "01":
        raise ValueError("this paper handoff is baseline-only; other sessions require a separate audit")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    command = [sys.executable, str(audit.ROOT / "code/audit_task_availability.py"),
               "--project-root", str(args.project_root), "--ugr-root", str(args.ugr_root),
               "--socdoors-root", str(args.socdoors_root), "--exclusions-root", str(args.exclusions_root),
               "--sessions", args.sessions, "--private-dir", str(output / "audit")]
    if args.dispositions:
        command += ["--dispositions", str(args.dispositions)]
    run_private(command, output / "audit-build.log")
    audit.check_saved(output / "audit")
    _, rows, _ = audit.read_tsv(output / "audit/run_review.tsv")
    sources = [Path(__file__).resolve()]
    for task, root in (("ugr", args.ugr_root), ("socialdoors", args.socdoors_root)):
        builder = root / "code/build_L1_manifest.py"
        sources.append(builder)
        command = [sys.executable, str(builder), "--bids-root", str(args.project_root / "bids"),
                   "--fmriprep-root", str(args.project_root / "derivatives/fmriprep"),
                   "--confounds-root", str(args.project_root / "derivatives/fsl/confounds_tedana"),
                   "--source-exclusions-root", str(args.exclusions_root), "--sessions", args.sessions,
                   "--output", str(output / f"raw-{task}-ready.tsv"),
                   "--missing-output", str(output / f"raw-{task}-missing.tsv")]
        if task == "socialdoors":
            command += ["--tasks", "socialdoors"]
        run_private(command, output / f"{task}-builder.log")
    validate_builder_tables(output, rows)
    audit.check_saved(output / "audit")
    for name, content in manifests(rows).items():
        path = output / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(content)
    # The full review table remains the place to inspect QC and prior decisions;
    # no paper-cohort filtering or L1/L2 scientific selection is performed.
    evidence = []
    for row in rows:
        state, reason = disposition(row)
        evidence.append(dict(row, handoff_status=state, handoff_reason=reason))
    audit.write_table(output / "run_review.tsv", evidence)
    summary = []
    for task in ("socialdoors", "ugr"):
        subset = [r for r in evidence if r["task"] == task]
        for field in ("handoff_status", "prior_manifest_state", "l1_status", "l2_status", "l1_input_link",
                      "recorded_threshold_scope", "recorded_qc_status", "task_session_qc_status"):
            for value, count in sorted(Counter(r[field] for r in subset).items()):
                summary.append(dict(task=task, session="01", measure=field, value=value or "unknown", runs=count))
        recovered = sum(r["handoff_status"] == "ready" and r["prior_manifest_state"] != "ready" for r in subset)
        summary.append(dict(task=task, session="01", measure="ready_not_previously_ready", value="runs", runs=recovered))
    audit.write_table(output / "summary.tsv", summary)
    provenance = {
        "schema_version": 1, "purpose": "technical_handoff_not_final_sample",
        "qc_used_for_eligibility": False, "final_eligibility_assigned": False,
        "sources": [{"path": str(p.resolve()), "sha256": audit.sha(p)} for p in sources],
        "outputs": {str(p.relative_to(output)): audit.sha(p) for p in output.rglob("*") if p.is_file()},
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    check(output)
    for item in summary:
        print(f"ses-01 {item['task']} {item['measure']} {item['value']}: {item['runs']}")
    print(f"Private handoff: {output}")
    print("Old manifests, imaging, canonical QC, FEAT outputs and settled decisions were not changed.")


def check(output):
    provenance = json.loads((output / "provenance.json").read_text())
    if (provenance.get("qc_used_for_eligibility") is not False
            or provenance.get("final_eligibility_assigned") is not False):
        raise ValueError("invalid handoff policy")
    for source in provenance["sources"]:
        if audit.sha(Path(source["path"])) != source["sha256"]:
            raise ValueError("handoff builder changed since build")
    for name, digest in provenance["outputs"].items():
        path = (output / name).resolve()
        if output not in path.parents or audit.sha(path) != digest:
            raise ValueError("handoff output hash/path mismatch")
    audit.check_saved(output / "audit")
    _, rows, _ = audit.read_tsv(output / "audit/run_review.tsv")
    validate_builder_tables(output, rows)
    for name, content in manifests(rows).items():
        if (output / name).read_text() != content:
            raise ValueError("manifest does not preserve audited scope, technical findings and holds")
    print(f"CHECK PASSED: {len(rows)} expected run slots reconciled; holds preserved; QC not used as exclusion.")
    print("Technical handoff verified, NOT final sample approval or FEAT current-input hash-lineage validation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--project-root", type=Path, default=audit.ROOT)
    parser.add_argument("--ugr-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-ugr"))
    parser.add_argument("--socdoors-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-socdoors"))
    parser.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--dispositions", type=Path, help="Existing reviewed decisions, using the availability audit schema")
    parser.add_argument("--sessions", default="01")
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.private_dir.resolve()
    if (args.project_root / "work").resolve() not in output.parents:
        raise ValueError("handoff output must be under project work/")
    if args.command == "build":
        build(args, output)
    else:
        check(output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"HANDOFF FAILED ({type(exc).__name__}); inspect private logs. Do not use unverified manifests.", file=sys.stderr)
        if isinstance(exc, ValueError):
            print(str(exc), file=sys.stderr)
        sys.exit(1)
