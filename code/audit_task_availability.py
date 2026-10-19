#!/usr/bin/env python3
"""Read-only Social Doors/UGR availability reconciliation, never an eligibility list."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

import build_run_qc as qc
from participants import exclusions, read_tsv

ROOT = Path(__file__).resolve().parents[1]
UNITS = (("socialdoors", "1"), ("ugr", "1"), ("ugr", "2"))
KEY = ("subject", "session", "task", "run")
QC_FIELDS = [*qc.METRIC_FLAGS, "tedana_total_components", "tedana_accepted_components",
             "tedana_rejected_fraction", *qc.METRIC_FLAGS.values(), "qc_status",
             "outlier_reasons", "missing_metrics"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_state(path):
    """Only ENOENT means absent; permission and other I/O failures abort."""
    try:
        info = path.stat()
    except FileNotFoundError:
        if path.is_symlink():
            return "broken_symlink"
        return "absent"
    if not stat.S_ISREG(info.st_mode):
        return "not_file"
    with path.open("rb") as handle:
        handle.read(1)
    return "present" if info.st_size else "empty"


def normalize_id(value):
    value = value.removeprefix("sub-")
    if not re.fullmatch(r"\d{5}", value):
        raise ValueError("invalid subject ID")
    return value


def key(row):
    return (normalize_id(row["subject"]), row["session"].removeprefix("ses-").zfill(2),
            row["task"], str(int(row["run"])))


def indexed(rows):
    result = {}
    for row in rows:
        k = key(row)
        if k in result:
            raise ValueError("duplicate run key")
        result[k] = row
    return result


def write_table(path, rows):
    if not rows:
        raise ValueError("refusing empty table")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows({k: ("TRUE" if v else "FALSE") if isinstance(v, bool) else v
                          for k, v in row.items()} for row in rows)


def prior_manifest(task_root, task):
    result, sources = [], []
    for name, state in (("L1-ready.tsv", "ready"), ("L1-missing.tsv", "missing")):
        path = task_root / "logs/runlists" / name
        if file_state(path) != "present":
            continue
        _, records, _ = read_tsv(path)
        sources.append(path)
        for row in records:
            row = dict(row, snapshot_state=state)
            row.setdefault("task", task)
            result.append(row)
    return result, sources


def snapshot_state(records, sources, run_key):
    if not sources:
        return "snapshot_unavailable"
    sub, ses, task, run = run_key
    found = []
    for row in records:
        if normalize_id(row["subject"]) != sub or row["session"].removeprefix("ses-").zfill(2) != ses:
            continue
        if row["task"] not in {task, "*", ""}:
            continue
        if row["run"] in {"", "*"} or row["task"] in {"", "*"}:
            found.append("session_level_" + row["snapshot_state"])
        elif str(int(row["run"])) == run:
            found.append(row["snapshot_state"])
    return ";".join(sorted(set(found))) or ("absent_from_both" if len(sources) == 2 else "absent_from_available_snapshot")


def input_paths(project, sub, ses, task, run):
    stem = f"sub-{sub}_ses-{ses}_task-{task}_run-{run}"
    return {
        "bids_bold": project / f"bids/sub-{sub}/ses-{ses}/func/{stem}_echo-2_part-mag_bold.nii.gz",
        "events": project / f"bids/sub-{sub}/ses-{ses}/func/{stem}_events.tsv",
        "bold": project / f"derivatives/fmriprep/sub-{sub}/ses-{ses}/func/{stem}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz",
        "confounds": project / f"derivatives/fsl/confounds_tedana/sub-{sub}/{stem}_desc-TedanaPlusConfounds.tsv",
    }


def validate_inputs(paths, states, task):
    import nibabel as nib

    findings = []
    nvol = tr = confound_rows = ""
    if states["bold"] == "present":
        try:
            image = nib.load(paths["bold"])
            if len(image.shape) != 4 or image.shape[3] <= 0:
                raise ValueError("not a 4D image")
            nvol, tr = image.shape[3], float(image.header.get_zooms()[3])
            if not math.isfinite(tr) or tr <= 0:
                raise ValueError("invalid TR")
        except (ValueError, nib.filebasedimages.ImageFileError):
            findings.append("invalid_bold_header")
            nvol = tr = ""
    if states["bids_bold"] == "present":
        try:
            raw = nib.load(paths["bids_bold"])
            if len(raw.shape) != 4 or raw.shape[3] <= 0:
                raise ValueError("not a 4D BIDS image")
            if nvol and (raw.shape[3] != nvol or not math.isclose(float(raw.header.get_zooms()[3]), tr, abs_tol=1e-4)):
                findings.append("bids_preproc_length_or_tr_mismatch")
        except (ValueError, nib.filebasedimages.ImageFileError):
            findings.append("invalid_bids_bold_header")
    if states["confounds"] == "present":
        try:
            count, width = 0, None
            with paths["confounds"].open() as handle:
                for line in handle:
                    values = [float(v) for v in line.split()]
                    if not values or not all(math.isfinite(v) for v in values):
                        raise ValueError("invalid confounds")
                    if width is not None and len(values) != width:
                        raise ValueError("ragged confounds")
                    width = len(values)
                    count += 1
            confound_rows = count
            if nvol and count != nvol:
                findings.append("bold_confound_row_mismatch")
        except ValueError:
            findings.append("invalid_confounds")
    if states["events"] == "present":
        try:
            fields, rows, _ = read_tsv(paths["events"])
            if not rows or not {"onset", "duration", "trial_type"} <= set(fields):
                raise ValueError("invalid events header")
            for row in rows:
                onset, duration = float(row["onset"]), float(row["duration"])
                if not all(math.isfinite(v) for v in (onset, duration)) or duration < 0:
                    raise ValueError("invalid event timing")
                if nvol and onset + duration > nvol * tr + 0.01:
                    findings.append("event_extends_past_bold")
            if task == "socialdoors":
                absent = {"decision", "win", "loss"} - {r["trial_type"] for r in rows}
                if absent:
                    findings.append("missing_model_trial_types:" + "+".join(sorted(absent)))
        except (ValueError, KeyError):
            findings.append("invalid_events")
    return nvol, tr, confound_rows, sorted(set(findings))


def feat_evidence(base, *, l2=False, expected_contrasts=None):
    """Structural evidence only: no inference of current-input lineage from existence."""
    try:
        mode = base.stat().st_mode
    except FileNotFoundError:
        return "absent", "FEAT directory"
    if not stat.S_ISDIR(mode):
        return "partial", "not a FEAT directory"
    required = ["design.mat", "design.con", "design.fsf"]
    count = expected_contrasts
    con = base / "design.con"
    if not l2 and file_state(con) == "present":
        match = re.search(r"/NumContrasts\s+(\d+)", con.read_text())
        parsed = int(match[1]) if match else 0
        if parsed < 1 or (count is not None and parsed != count):
            required.append("INVALID_CONTRAST_COUNT")
        count = count or parsed
    if l2:
        for i in range(1, (count or 0) + 1):
            required.extend(f"cope{i}.feat/{name}" for name in
                            ("design.mat", "design.con", "mask.nii.gz", "stats/cope1.nii.gz",
                             "stats/varcope1.nii.gz", "stats/zstat1.nii.gz"))
    else:
        required.append("mask.nii.gz")
        for i in range(1, (count or 0) + 1):
            required.extend(f"stats/{kind}{i}.nii.gz" for kind in ("cope", "varcope", "zstat"))
    missing = [name for name in required if file_state(base / name) != "present"]
    status = "files_present" if not missing else "partial"
    return status, ";".join(missing)


def feat_paths(task_root, sub, ses, task, run):
    model = "3" if task == "ugr" else "1"
    root = task_root / f"derivatives/fsl/sub-{sub}/ses-{ses}"
    return (root / f"L1_task-{task}_ses-{ses}_model-{model}_type-act_run-{run}_sm-5.feat",
            root / f"L2_task-{task}_ses-{ses}_model-{model}_type-act_sm-5.gfeat")


def fsf_links(feat, expected):
    fsf = feat / "design.fsf"
    if file_state(fsf) != "present":
        return "not_checked", ""
    text = fsf.read_text()
    result = []
    for field, path in (("feat_files", expected["bold"]), ("confoundev_files", expected["confounds"])):
        match = re.search(r'^set\s+' + field + r'\(1\)\s+"([^"]+)"', text, re.M)
        if not match:
            result.append(field + ":unresolved")
        elif Path(match[1]).resolve() != path.resolve():
            result.append(field + ":different_path")
    return ("path_match_only" if not result else "review"), ";".join(result)


def scoped_qc(rows, policy):
    typed = []
    for row in rows:
        item = dict(row)
        item["subject"], item["session"], item["task"], item["run"] = key(row)
        for metric in qc.METRIC_FLAGS:
            value = row[metric]
            item[metric] = None if value in {"", "n/a", "NA"} else float(value)
            if item[metric] is not None and not math.isfinite(item[metric]):
                item[metric] = None
            if item[metric] is None:
                item["missing_metrics"] = ";".join(filter(None, [item.get("missing_metrics", ""), metric + ":missing_recorded_measurement"]))
        typed.append(item)
    thresholds = qc.compute_thresholds(typed, policy)
    qc.apply_thresholds(typed, thresholds, policy)
    return indexed(typed), thresholds


def collect(args):
    project = args.project_root.resolve()
    for root in (project / "bids", project / "derivatives/fmriprep",
                 project / "derivatives/fsl/confounds_tedana",
                 args.ugr_root / "derivatives/fsl", args.socdoors_root / "derivatives/fsl"):
        if not root.is_dir():
            raise ValueError("required live root unavailable (not evidence of missing participants)")
    excluded = {s[4:] for s in exclusions(args.exclusions_root)}
    roster = project / "bids/participants.tsv"
    _, roster_rows, _ = read_tsv(roster)
    subjects = [normalize_id(r["participant_id"]) for r in roster_rows]
    if not subjects or len(subjects) != len(set(subjects)):
        raise ValueError("empty or duplicate participant roster")
    roster_ids = set(subjects)
    if args.sublist:
        subjects = [normalize_id(s.strip()) for s in args.sublist.read_text().splitlines() if s.strip()]
        if not subjects or len(subjects) != len(set(subjects)):
            raise ValueError("empty or duplicate requested IDs")
    _, qc_rows, _ = read_tsv(project / "qc/run_qc.tsv")
    threshold_fields, _, _ = read_tsv(project / "qc/thresholds.tsv")
    legacy = indexed(qc_rows)
    policy = qc.load_policy(ROOT / "qc/qc_policy.json")
    # Threshold reference is the full approved MRI population, never the paper subset.
    reference = [r for r in qc_rows if normalize_id(r["subject"]) in roster_ids - excluded]
    current, thresholds = scoped_qc(reference, policy)
    _, hold_rows, _ = read_tsv(ROOT / "code/task_availability_holds.tsv")
    holds = indexed(hold_rows)
    # Never silently ignore a later disposition contract introduced in this repository.
    if (project / "qc/run_disposition.tsv").exists() and not args.dispositions:
        raise ValueError("run-disposition contract exists; supply --dispositions explicitly")
    decisions = {}
    if args.dispositions:
        fields, records, _ = read_tsv(args.dispositions)
        if not set((*KEY, "decision", "reason", "evidence")) <= set(fields):
            raise ValueError("disposition schema must include decision, reason, evidence and run key")
        decisions = indexed(records)
        if any(r["decision"] not in {"include", "exclude", "review", "unavailable"}
               or not r["reason"] or not r["evidence"] for r in records):
            raise ValueError("invalid or unsupported reviewed disposition")
    snapshots = {task: prior_manifest(root, task) for task, root in
                 (("ugr", args.ugr_root), ("socialdoors", args.socdoors_root))}
    rows = []
    l2_cache = {}
    for index, sub in enumerate(sorted(subjects), 1):
        for ses in args.sessions.split(","):
            if not re.fullmatch(r"\d{2}", ses):
                raise ValueError("sessions must be two-digit comma-separated labels")
            for task, run in UNITS:
                k = (sub, ses, task, run)
                row = dict(zip(KEY, k))
                row["in_mri_roster"] = sub in roster_ids
                row["roster_gate"] = "blocked" if sub in excluded or sub not in roster_ids else "member"
                hold = holds.get(k, {})
                decision = decisions.get(k, {})
                row["existing_decision"] = decision.get("decision", "not_recorded")
                row["decision_reason"] = decision.get("reason", "")
                row["decision_evidence"] = decision.get("evidence", "")
                row["existing_hold"] = hold.get("reason", "")
                row["hold_evidence"] = hold.get("evidence", "")
                row["final_analysis_eligibility"] = "not_assigned_by_audit"
                records, snapshot_sources = snapshots[task]
                row["prior_manifest_state"] = snapshot_state(records, snapshot_sources, k)
                paths = input_paths(project, *k)
                states = {name: file_state(path) for name, path in paths.items()}
                for name, path in paths.items():
                    row[name + "_path"] = str(path)
                    row[name + "_state"] = states[name]
                    row[name + "_size_bytes"] = path.stat().st_size if states[name] == "present" else ""
                    row[name + "_mtime_ns"] = path.stat().st_mtime_ns if states[name] == "present" else ""
                missing = [name + ":" + state for name, state in states.items() if state != "present"]
                nvol, tr, nrows, findings = validate_inputs(paths, states, task)
                row.update(n_volumes=nvol, tr_seconds=tr, confound_rows=nrows,
                           missing_inputs=";".join(missing), input_findings=";".join(findings))
                row["technical_status"] = "inputs_present_aligned" if not missing and not findings else "needs_review"
                row["events_sha256"] = sha(paths["events"]) if states["events"] == "present" else ""
                row["confounds_sha256"] = sha(paths["confounds"]) if states["confounds"] == "present" else ""
                row["source_mapping"] = "existing_upstream_mapping_not_readjudicated"
                task_root = args.ugr_root if task == "ugr" else args.socdoors_root
                l1, l2 = feat_paths(task_root, *k)
                row["l1_path"] = str(l1)
                row["l1_status"], row["l1_missing_files"] = feat_evidence(l1, expected_contrasts=17 if task == "ugr" else None)
                row["l1_input_link"], row["l1_link_findings"] = fsf_links(l1, paths)
                row["l1_design_sha256"] = sha(l1 / "design.fsf") if file_state(l1 / "design.fsf") == "present" else ""
                row["feat_current_input_lineage"] = "not_hash_verified"
                row["l2_path"] = str(l2) if task == "ugr" else ""
                if task == "ugr" and l2 not in l2_cache:
                    l2_cache[l2] = feat_evidence(l2, l2=True, expected_contrasts=17)
                row["l2_status"], row["l2_missing_files"] = l2_cache[l2] if task == "ugr" else ("not_applicable", "")
                row["l2_design_sha256"] = sha(l2 / "design.fsf") if task == "ugr" and file_state(l2 / "design.fsf") == "present" else ""
                old, new = legacy.get(k, {}), current.get(k, {})
                row["qc_record_state"] = "present" if old else "absent"
                row["recorded_threshold_scope"] = "task_session" if {"task", "session"} <= set(threshold_fields) else "legacy_pooled_paradigm"
                for name in QC_FIELDS:
                    row["recorded_" + name] = old.get(name, "")
                row["qc_reference_scope"] = "full_roster_exact_task_session"
                for name in (*qc.METRIC_FLAGS.values(), "qc_status", "outlier_reasons"):
                    row["task_session_" + name] = new.get(name, "")
                for metric in qc.METRIC_FLAGS:
                    fence = next((t for t in thresholds if (t["task"], t["session"], t["metric"]) == (task, ses, metric)), {})
                    row[metric + "_reference_n"] = fence.get("n", "")
                    row[metric + "_fence"] = fence.get("lower_fence" if policy["metrics"][metric]["direction"] == "lower" else "upper_fence", "")
                row["next_action"] = ("preserve_existing_block" if row["roster_gate"] == "blocked" or hold or decision.get("decision") in {"exclude", "review", "unavailable"}
                                      else "inspect_technical_findings" if missing or findings
                                      else "inspect_missing_qc_measurements" if not new or new.get("qc_status") == "incomplete"
                                      else "inspect_model_outputs" if row["l1_status"] != "files_present" or row["l1_input_link"] != "path_match_only"
                                      else "technical_evidence_ready_for_task_review")
                rows.append(row)
        if index % 25 == 0:
            print(f"Inspected {index}/{len(subjects)} participants; {len(rows)} expected run rows", flush=True)
    if len(indexed(rows)) != len(subjects) * len(args.sessions.split(",")) * len(UNITS):
        raise ValueError("run reconciliation failed")
    sources = [roster, project / "qc/run_qc.tsv", project / "qc/thresholds.tsv",
               ROOT / "qc/qc_policy.json", ROOT / "code/task_availability_holds.tsv",
               Path(__file__), ROOT / "code/build_run_qc.py"]
    sources.extend(p for p in (args.sublist, args.dispositions) if p)
    sources.extend(p for _, paths in snapshots.values() for p in paths)
    return rows, thresholds, sources


def check_saved(output):
    provenance = json.loads((output / "provenance.json").read_text())
    if provenance.get("final_eligibility_assigned") is not False:
        raise ValueError("audit must not assign eligibility")
    excluded = sorted(exclusions(Path(provenance["exclusions_root"])))
    if hashlib.sha256("\n".join(excluded).encode()).hexdigest() != provenance["exclusions_inventory_sha256"]:
        raise ValueError("authoritative exclusion inventory changed")
    for record in provenance["sources"]:
        if sha(Path(record["path"])) != record["sha256"]:
            raise ValueError("source changed since audit; regenerate")
    for name, digest in provenance["outputs"].items():
        if Path(name).name != name or sha(output / name) != digest:
            raise ValueError("output hash mismatch")
    _, rows, _ = read_tsv(output / "run_review.tsv")
    if len(indexed(rows)) != provenance["run_rows"]:
        raise ValueError("run key/count mismatch")
    for row in rows:
        if row["final_analysis_eligibility"] != "not_assigned_by_audit":
            raise ValueError("unexpected eligibility assignment")
        for name in ("bids_bold", "events", "bold", "confounds"):
            path = Path(row[name + "_path"])
            if file_state(path) != row[name + "_state"]:
                raise ValueError("live input availability changed")
            if row[name + "_state"] == "present":
                info = path.stat()
                if (str(info.st_size), str(info.st_mtime_ns)) != (row[name + "_size_bytes"], row[name + "_mtime_ns"]):
                    raise ValueError("live input changed")
                if name in {"events", "confounds"} and sha(path) != row[name + "_sha256"]:
                    raise ValueError("live text input changed")
        for level in ("l1", "l2"):
            if level == "l2" and row["task"] != "ugr":
                continue
            base = Path(row[level + "_path"])
            status, missing = feat_evidence(base, l2=level == "l2", expected_contrasts=17 if row["task"] == "ugr" else None)
            if (status, missing) != (row[level + "_status"], row[level + "_missing_files"]):
                raise ValueError("FEAT output evidence changed")
            if row[level + "_design_sha256"] and sha(base / "design.fsf") != row[level + "_design_sha256"]:
                raise ValueError("FEAT input specification changed")
    print(f"CHECK PASSED: {len(rows)} unique run rows, source/output hashes and live input states unchanged.")
    print("This certifies the reconciliation, not scientific eligibility or FEAT input lineage.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--ugr-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-ugr"))
    parser.add_argument("--socdoors-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-socdoors"))
    parser.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--sublist", type=Path, help="Optional IDs-only list; otherwise full participants.tsv roster")
    parser.add_argument("--dispositions", type=Path, help="Existing reviewed decisions; never inferred from QC")
    parser.add_argument("--sessions", default="01", help="Separate sessions; default baseline only")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Verify a saved private audit against live inputs")
    args = parser.parse_args()
    output = args.private_dir.resolve()
    work = (args.project_root / "work").resolve()
    if work not in output.parents:
        raise ValueError("private output must be under project work/")
    if args.check:
        return check_saved(output)
    if output.exists():
        raise ValueError("use a new private output directory under project work/")
    print("Read-only availability audit; no input, manifest, QC or eligibility changes.", flush=True)
    rows, thresholds, sources = collect(args)
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    write_table(output / "run_review.tsv", rows)
    write_table(output / "task_session_thresholds.tsv", thresholds)
    summaries = []
    for ses, task in sorted({(r["session"], r["task"]) for r in rows}):
        subset = [r for r in rows if (r["session"], r["task"]) == (ses, task)]
        for field in ("technical_status", "qc_record_state", "task_session_qc_status", "l1_status", "next_action"):
            for value, n in sorted(Counter(str(r[field]) for r in subset).items()):
                summaries.append(dict(session=ses, task=task, measure=field, value=value, runs=n))
    write_table(output / "summary.tsv", summaries)
    for item in summaries:
        print(f"ses-{item['session']} {item['task']} {item['measure']} {item['value'] or 'unknown'}: {item['runs']}")
    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "schema_version": 1,
        "scope": "full MRI roster" if not args.sublist else "explicit sublist",
        "sessions": args.sessions, "run_rows": len(rows), "final_eligibility_assigned": False,
        "qc_threshold_scope": "exact_task_session_full_approved_roster",
        "exclusions_root": str(args.exclusions_root.resolve()),
        "exclusions_inventory_sha256": hashlib.sha256("\n".join(sorted(exclusions(args.exclusions_root))).encode()).hexdigest(),
        "limitations": ["Existing QC measurements are reused, not recomputed from imaging.",
                        "NIfTI headers/row alignment are checked, not all voxel data.",
                        "FEAT output presence and paths do not prove current-input hash lineage.",
                        "Source mapping is not re-adjudicated. No paper cohort membership is inferred."],
        "sources": [{"path": str(p), "sha256": sha(p)} for p in sources],
        "outputs": {p.name: sha(p) for p in output.iterdir() if p.is_file()},
    }
    for name, root in (("linux2", args.project_root), ("ugr", args.ugr_root), ("socdoors", args.socdoors_root)):
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
        provenance[name + "_revision"] = proc.stdout.strip() if proc.returncode == 0 else "unavailable"
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"AUDIT COMPLETE: {len(rows)} run rows; private results in {output}")
    print("Exit 0 means audit completed, not that all runs passed or samples are approved.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"AUDIT FAILED ({type(exc).__name__}); inspect inputs privately. No eligibility decisions made.", file=sys.stderr)
        if isinstance(exc, ValueError):
            print(str(exc), file=sys.stderr)
        sys.exit(1)
