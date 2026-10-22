#!/usr/bin/env python3
"""Read-only inventory/mapping audit; findings never change run eligibility."""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

import heuristics_rf1
import heuristics_XA30

ROOT = Path(__file__).resolve().parents[1]
RULES = {"RF1": heuristics_rf1, "XA30": heuristics_XA30}
TASKS = {"trust", "sharedreward", "ugr", "socialdoors", "doors"}
FIELDS = ["subject", "session", "inventory", "view", "task", "part",
          "finding", "candidates", "selected", "omitted"]
SAFE_ERRORS = {"mapping_not_dictionary", "unsupported_mapping_key",
    "duplicate_task_mapping_key", "unsupported_mapping_values",
    "missing_inventory_columns", "invalid_image_type", "empty_inventory_or_series_id",
    "duplicate_series_identity", "unresolved_subject_session", "no_saved_conversion_mapping"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(value):
    # Keep scanner-series numbers useful without copying arbitrary header labels.
    match = re.match(r"^(\d+)(?:-|$)", value)
    number = match.group(1) if match else "unknown"
    return number + "@" + hashlib.sha256(value.encode()).hexdigest()[:12]


def refs(values):
    return ";".join(ref(v) for v in values)


def key(template):
    match = re.search(r"_task-([a-z]+)_", template)
    if not match or match.group(1) not in TASKS:
        return None
    part = "sbref" if template.endswith("_sbref") else (
        "mag" if "_part-mag_bold" in template else
        "phase" if "_part-phase_bold" in template else None)
    return (match.group(1), part) if part else None


def normalize(mapping):
    result = {}
    if not isinstance(mapping, dict):
        raise ValueError("mapping_not_dictionary")
    for k, values in mapping.items():
        if not isinstance(k, tuple) or not k or not isinstance(k[0], str):
            raise ValueError("unsupported_mapping_key")
        task_key = key(k[0])
        if task_key is None:
            continue
        if task_key in result:
            raise ValueError("duplicate_task_mapping_key")
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError("unsupported_mapping_values")
        result[task_key] = values
    return result


def read_inventory(path):
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"series_id", "protocol_name", "series_description", "image_type", "dim3", "dim4"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("missing_inventory_columns")
        rows = []
        for row in reader:
            image_type = ast.literal_eval(row["image_type"])
            if not isinstance(image_type, (tuple, list)) or not all(isinstance(v, str) for v in image_type):
                raise ValueError("invalid_image_type")
            rows.append(SimpleNamespace(series_id=row["series_id"],
                protocol_name=row["protocol_name"], series_description=row["series_description"],
                image_type=tuple(image_type), dim3=int(row["dim3"]), dim4=int(row["dim4"])))
    if not rows or any(not r.series_id for r in rows):
        raise ValueError("empty_inventory_or_series_id")
    if len({r.series_id for r in rows}) != len(rows):
        raise ValueError("duplicate_series_identity")
    return rows


def replay(rows, heuristic):
    # Prefix replay exposes assignments subsequently overwritten by the real rule.
    # Only bundled, trusted heuristics run; cached heuristic.py files are never run.
    seen = defaultdict(list)
    final = {}
    for end in range(1, len(rows) + 1):
        final = normalize(heuristic.infotodict(rows[:end]))
        for k, values in final.items():
            if k[1] == "sbref":
                continue
            for value in values:
                if value not in seen[k]:
                    seen[k].append(value)
    return dict(seen), final


def inspect(rows, mappings):
    findings, views = [], {}

    def add(view, k, finding, candidates=(), selected=()):
        omitted = [s for s in candidates if s not in selected]
        findings.append(dict(view=view, task=k[0], part=k[1], finding=finding,
            candidates=refs(candidates), selected=refs(selected), omitted=refs(omitted)))

    for name, heuristic in RULES.items():
        seen, final = replay(rows, heuristic)
        views[name] = seen
        for k, candidates in seen.items():
            # Alternative phase classification alone is not evidence of two runs.
            if not seen.get((k[0], "mag")):
                continue
            selected = final.get(k, [])
            if any(s not in selected for s in candidates):
                add("current_" + name, k, "current_rule_overwrites_match", candidates, selected)

    ids = {r.series_id for r in rows}
    for name, mapping in mappings.items():
        for k in set(mapping) | {k for seen in views.values() for k in seen}:
            values = mapping.get(k, [])
            if len(values) != len(set(values)):
                add(name, k, "same_series_assigned_repeatedly", values, values)
            if any(s not in ids for s in values):
                add(name, k, "mapped_series_not_in_inventory", (), values)
            for rule, seen in views.items():
                candidates = seen.get(k, [])
                if k[1] != "sbref" and seen.get((k[0], "mag")) and len(candidates) > 1:
                    if any(s not in values for s in candidates):
                        add(name + "_vs_" + rule, k, "candidate_omitted_from_saved_mapping", candidates, values)
        for task in TASKS:
            mag = mapping.get((task, "mag"), [])
            phase = mapping.get((task, "phase"), [])
            sbref = mapping.get((task, "sbref"), [])
            if len(mag) != len(phase):
                add(name, (task, "phase"), "saved_mag_phase_count_mismatch", mag, phase)
            if mag and len(sbref) != len(mag):
                add(name, (task, "sbref"), "saved_bold_sbref_count_mismatch", mag, sbref)
        owners = defaultdict(set)
        for k, values in mapping.items():
            if k[1] == "mag":
                for value in values:
                    owners[value].add(k[0])
        for value, tasks in owners.items():
            if len(tasks) > 1:
                for task in tasks:
                    add(name, (task, "mag"), "same_bold_series_multiple_tasks", [value], [value])
    return sorted(findings, key=lambda r: (r["view"], r["task"], r["part"], r["finding"]))


def image_role(row):
    """Require positive evidence; absence of NORM/Pha is not a phase/mag label."""
    tokens = {v.upper() for v in row.image_type}
    phase = "P" in tokens or "_pha" in row.series_description.lower()
    magnitude = bool(tokens & {"M", "NORM"})
    if phase and magnitude:
        return "conflict"
    if phase:
        return "phase"
    if magnitude:
        return "mag"
    return "unknown"


def reconcile_roles(rows, mappings, findings):
    """Partition findings without deleting the raw evidence or approving a run."""
    roles = {ref(r.series_id): image_role(r) for r in rows}
    unresolved, resolved = [], []
    for finding in findings:
        task, view = finding["task"], finding["view"]
        candidates = set(filter(None, finding["candidates"].split(";")))
        mag = {v for v in candidates if roles.get(v) == "mag"}
        phase = {v for v in candidates if roles.get(v) == "phase"}
        relevant = ([mappings[view.removesuffix("_vs_XA30")]]
                    if view.endswith("_vs_XA30") else list(mappings.values()))
        eligible = finding["part"] == "mag" and (
            (view.endswith("_vs_XA30") and
             finding["finding"] == "candidate_omitted_from_saved_mapping") or
            (view == "current_XA30" and
             finding["finding"] == "current_rule_overwrites_match" and len(mag) == 1))
        # Require every candidate role to be known and each relevant saved map
        # to retain every true magnitude and place every contaminant in phase.
        verified = eligible and mag and phase and candidates == mag | phase and relevant
        for mapping in relevant:
            saved_mag = {ref(v) for v in mapping.get((task, "mag"), [])}
            saved_phase = {ref(v) for v in mapping.get((task, "phase"), [])}
            verified = verified and saved_mag == mag and phase <= saved_phase
            verified = verified and not (saved_mag & saved_phase)
        if verified:
            resolved.append(dict(**finding,
                resolution="verified_XA30_magnitude_view_includes_saved_phase",
                verified_magnitude=";".join(sorted(mag)),
                verified_phase=";".join(sorted(phase))))
        else:
            unresolved.append(finding)
    return unresolved, resolved


def inventory_key(path, project):
    relative = path.relative_to(project / "bids/.heudiconv")
    subject = relative.parts[0].removeprefix("sub-")
    sessions = [v[4:] for v in relative.parts if re.fullmatch(r"ses-\d+", v)]
    if not subject.isdigit() or len(sessions) != 1:
        raise ValueError("unresolved_subject_session")
    return subject, sessions[0].zfill(2)


def write_table(path, fields, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def discover(project):
    return sorted((project / "bids/.heudiconv").rglob("dicominfo*.tsv"))


def live_sessions(project):
    return sorted({(p.parent.name[4:], p.name[4:].zfill(2))
        for p in (project / "bids").glob("sub-*/ses-*") if p.is_dir()})


def build(project, output):
    tables = discover(project)
    if not tables:
        raise ValueError("No saved acquisition inventories found")
    if output.exists():
        raise ValueError("Choose a new output directory")
    findings, raw_findings, resolved, role_rows = [], [], [], []
    checks, sources, sessions = [], {}, set()
    sources[str(Path(__file__).resolve())] = sha(Path(__file__))
    for module in RULES.values():
        sources[str(Path(module.__file__).resolve())] = sha(Path(module.__file__))
    sources[str(ROOT / "code/heudiconv_grouping.py")] = sha(ROOT / "code/heudiconv_grouping.py")
    for table in tables:
        rel = str(table.relative_to(project))
        sub = ses = "unknown"
        check = dict(inventory=rel, subject=sub, session=ses, status="error", detail="", series=0)
        try:
            sources[str(table)] = sha(table)
            sub, ses = inventory_key(table, project)
            check.update(subject=sub, session=ses)
            rows = read_inventory(table)
            check["series"] = len(rows)
            mappings = {}
            for suffix in ("auto", "edit"):
                for path in sorted(table.parent.glob(f"*.{suffix}.txt")):
                    sources[str(path)] = sha(path)
                    mappings[str(path.relative_to(project))] = normalize(ast.literal_eval(path.read_text()))
            if not mappings:
                raise ValueError("no_saved_conversion_mapping")
            raw = inspect(rows, mappings)
            pending, cleared = reconcile_roles(rows, mappings, raw)
            for target, values in [(raw_findings, raw), (findings, pending), (resolved, cleared)]:
                target.extend(dict(subject=sub, session=ses, inventory=rel, **r) for r in values)
            role_rows.extend(dict(subject=sub, session=ses, inventory=rel,
                series=ref(r.series_id), role=image_role(r),
                image_type_M="M" in {v.upper() for v in r.image_type},
                image_type_NORM="NORM" in {v.upper() for v in r.image_type},
                image_type_P="P" in {v.upper() for v in r.image_type},
                description_Pha="_pha" in r.series_description.lower()) for r in rows)
            sessions.add((sub, ses))
            check.update(status="read_ok", detail="not_an_eligibility_decision")
        except (ValueError, TypeError, SyntaxError, OSError, KeyError, IndexError) as exc:
            # Do not leak arbitrary raw DICOM labels from parser exceptions.
            check["detail"] = str(exc) if str(exc) in SAFE_ERRORS else type(exc).__name__
        checks.append(check)
    for sub, ses in live_sessions(project):
        if (sub, ses) not in sessions:
            checks.append(dict(inventory="", subject=sub, session=ses, status="error",
                               detail="no_successfully_audited_inventory_for_BIDS_session", series=0))
    errors = sum(r["status"] == "error" for r in checks)
    summary = dict(inventories=len(tables), audited_sessions=len(sessions),
        errors=errors, finding_rows=len(findings),
        raw_finding_rows=len(raw_findings), resolved_view_artifact_rows=len(resolved),
        resolved_view_artifact_sessions=len({(r["subject"], r["session"]) for r in resolved}),
        finding_sessions=len({(r["subject"], r["session"]) for r in findings}),
        findings_by_type=dict(Counter(r["finding"] for r in findings)),
        scope="all_saved_inventories_all_sessions_no_age_or_QC_filter",
        eligibility_changed=False, identity_approved=False)
    output.mkdir(parents=True)
    write_table(output / "findings.tsv", FIELDS, findings)
    write_table(output / "raw_findings.tsv", FIELDS, raw_findings)
    write_table(output / "resolved_view_artifacts.tsv", FIELDS +
                ["resolution", "verified_magnitude", "verified_phase"], resolved)
    write_table(output / "series_roles.tsv", ["subject", "session", "inventory", "series", "role",
                "image_type_M", "image_type_NORM", "image_type_P", "description_Pha"], role_rows)
    write_table(output / "inventory_checks.tsv", list(checks[0]), checks)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = dict(project=str(project), sources=sources,
        inventories=[str(p) for p in tables], bids_sessions=live_sessions(project),
        mappings=sorted(str(p) for t in tables for suffix in ("auto", "edit")
                        for p in t.parent.glob(f"*.{suffix}.txt")),
        outputs={p.name: sha(p) for p in output.iterdir() if p.is_file()})
    (output / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print("Findings are comparative rule/mapping candidates, NOT confirmed errors or exclusions.")
    print("Normal multi-run matches retained by a rule are not flagged merely for being multiple.")
    print("Current RF1/XA30 views do not establish which historical heuristic was used.")
    print("Only positive image-role evidence corroborated by saved mappings clears a view artifact.")
    print("Unknown/conflicting roles and real duplicate magnitude matches remain for review.")
    for subject, session in sorted({(r["subject"], r["session"]) for r in resolved}):
        print(f"RESOLVED VIEW ARTIFACTS sub-{subject} ses-{session}: "
              f"{sum((r['subject'], r['session']) == (subject, session) for r in resolved)} rows")
    for row in findings:
        print(" | ".join(str(row[k]) for k in FIELDS))
    for row in checks:
        if row["status"] == "error":
            print("COLLECTION ERROR", row)
    print("AUDIT INCOMPLETE" if errors else "AUDIT COLLECTED: review findings; no production changes.")
    return 1 if errors else 0


def check(project, output):
    manifest = json.loads((output / "provenance.json").read_text())
    if manifest["project"] != str(project):
        raise ValueError("Project differs")
    for path, digest in manifest["sources"].items():
        if sha(Path(path)) != digest:
            raise ValueError("Audit source changed")
    tables = discover(project)
    mappings = sorted(str(p) for t in tables for suffix in ("auto", "edit")
                      for p in t.parent.glob(f"*.{suffix}.txt"))
    if [str(p) for p in tables] != manifest["inventories"] or mappings != manifest["mappings"]:
        raise ValueError("Inventory/mapping file set changed")
    if [list(v) for v in live_sessions(project)] != manifest["bids_sessions"]:
        raise ValueError("BIDS session set changed")
    for name, digest in manifest["outputs"].items():
        if sha(output / name) != digest:
            raise ValueError("Audit output changed")
    summary = json.loads((output / "summary.json").read_text())
    if summary["errors"]:
        raise ValueError("Evidence collection incomplete")
    if "raw_finding_rows" in summary:
        if summary["raw_finding_rows"] != summary["finding_rows"] + summary["resolved_view_artifact_rows"]:
            raise ValueError("Finding partition incomplete")
        counters = {}
        for filename, count_key in [("raw_findings.tsv", "raw_finding_rows"),
                                    ("findings.tsv", "finding_rows"),
                                    ("resolved_view_artifacts.tsv", "resolved_view_artifact_rows")]:
            with (output / filename).open(newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))
            if len(rows) != summary[count_key]:
                raise ValueError("Finding table count differs")
            counters[filename] = Counter(tuple(r[k] for k in FIELDS) for r in rows)
        if counters["raw_findings.tsv"] != counters["findings.tsv"] + counters["resolved_view_artifacts.tsv"]:
            raise ValueError("Finding partition differs from raw evidence")
    print("CHECK PASSED: saved-inventory audit sources and reports unchanged; findings are not adjudicated.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        return (build if args.command == "build" else check)(args.project_root.resolve(), args.output_dir.resolve())
    except (ValueError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
