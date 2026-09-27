#!/usr/bin/env python3
"""Stage a behavior-only Trust schema migration and export deidentified source QC.

Private logs are inspected here, upstream only. No source contents/paths are exported.
Snapshot/check require unchanged historical columns and an unchanged imaging stat
inventory; source equivalence is independently checked by check_events.py.
"""
from __future__ import annotations
import argparse
import contextlib
import csv
import hashlib
import io
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from build_events_qc import source_excluded_subjects, sha256_file
from check_events import audit_subject_session, _event_runs
from convert_behavior import (discover_bold_runs, event_path, load_curation_approvals,
    resolve_sources, convert_source, issue_is_approved, ConversionError, _format_value)

ROOT = Path(__file__).resolve().parents[1]
ADDED = {"scheduled_reciprocation", "cLeft", "cRight"}
TRUST_EVENT_RE = re.compile(r"^sub-\d+_ses-\d+_task-trust_run-\d+_events\.tsv$")
IMAGING_TEMPLATE_RE = re.compile(r"^sub-\d+_ses-\d+_task-trust_run-\d+_part-(?:mag|phase)_events\.tsv$")


def read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))



def canonical_trust_files(bids):
    """Separate canonical behavior from known empty HeuDiConv templates."""
    canonical = []
    for path in sorted(bids.glob("sub-*/ses-01/func/*_task-trust*_events.tsv")):
        if TRUST_EVENT_RE.fullmatch(path.name):
            canonical.append(path)
        elif IMAGING_TEMPLATE_RE.fullmatch(path.name) and not read(path):
            continue
        else:
            raise ValueError(f"unreviewed or nonempty noncanonical Trust events file: {path}")
    return canonical


def canonical_snapshot_events(saved, bids):
    """Read old snapshots without rewriting their pre-conversion evidence.

The first handoff release also captured empty part-mag/part-phase templates.
They are only omitted from behavioral schema checks if empty both before and now.
"""
    canonical, ignored = {}, {}
    for rel, rows in saved['events'].items():
        path = bids / rel
        if TRUST_EVENT_RE.fullmatch(path.name):
            canonical[rel] = rows
        elif IMAGING_TEMPLATE_RE.fullmatch(path.name) and not rows and not read(path):
            ignored[rel] = sha256_file(path)
        else:
            raise ValueError(f"snapshot contains unreviewed or nonempty noncanonical Trust events: {rel}")
    if not canonical:
        raise ValueError("snapshot contains no canonical Trust runs")
    return canonical, ignored


def check_snapshot_events(saved, bids):
    canonical, ignored = canonical_snapshot_events(saved, bids)
    zeros = 0
    for rel, rows in canonical.items():
        try:
            zeros += compare_extension(rows, read(bids / rel))
        except (ValueError, OSError, csv.Error) as exc:
            raise ValueError(f"{rel}: {exc}") from exc
    return zeros, canonical, ignored


def write(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, delimiter="\t")
        w.writeheader(); w.writerows(rows)


def imaging_inventory(bids):
    # File metadata, not a claim to have rehashed terabytes of image contents.
    return {str(p.relative_to(bids)): [p.stat().st_size, p.stat().st_mtime_ns,
            p.stat().st_ctime_ns, p.stat().st_ino]
            for p in sorted(bids.rglob("*")) if p.is_file() and
            (p.name.endswith((".nii", ".nii.gz", ".bval", ".bvec")))}


def schema_check(rows):
    if not rows or not ADDED.issubset(rows[0]):
        raise ValueError("Trust schema additions are missing")
    by_id = {}
    for row in rows:
        by_id.setdefault(row["trial_id"], []).append(row)
    zeros = 0
    for trial_id, block in by_id.items():
        decisions = [r for r in block if r["trial_type"].startswith("choice_") or r["trial_type"] == "missed_trial"]
        outcomes = [r for r in block if r["trial_type"].startswith("outcome_")]
        if len(decisions) != 1 or len(block) != len(decisions) + len(outcomes):
            raise ValueError(f"ambiguous trial {trial_id}")
        d = decisions[0]
        low, high = float(d["cLow"]), float(d["cHigh"])
        if not low < high or sorted([float(d["cLeft"]), float(d["cRight"])]) != [low, high]:
            raise ValueError(f"invalid offer sides at trial {trial_id}")
        if d["scheduled_reciprocation"] not in {"recip", "defect"}:
            raise ValueError(f"missing latent schedule at trial {trial_id}")
        if d["reciprocate"] != "n/a":
            raise ValueError("decision rows cannot invent observed outcomes")
        miss = d["trial_type"] == "missed_trial"
        if miss:
            if d["trust_value"] != "n/a" or d["choice"] != "n/a" or outcomes:
                raise ValueError("miss with choice/feedback")
            continue
        amount = float(d["trust_value"])
        if amount not in {low, high} or d["choice"] != ("high" if amount == high else "low"):
            raise ValueError(f"selected amount/choice inconsistent at trial {trial_id}")
        if amount == 0:
            zeros += 1
            if outcomes:
                raise ValueError("zero choice acquired feedback")
        elif len(outcomes) != 1:
            raise ValueError("positive choice must have exactly one outcome")
        else:
            o = outcomes[0]
            if o["reciprocate"] != d["scheduled_reciprocation"]:
                raise ValueError("observed/scheduled outcome mismatch")
            for col in ("partner", "cLow", "cHigh", "cLeft", "cRight", "trust_value", "choice", "scheduled_reciprocation"):
                if o[col] != d[col]:
                    raise ValueError(f"choice/outcome {col} mismatch")
    return zeros


def compare_extension(before, after):
    if len(before) != len(after):
        raise ValueError("schema migration changed row count")
    for old, new in zip(before, after):
        for col, value in old.items():
            if new.get(col) != value:
                raise ValueError(f"schema migration changed historical {col}")
    return schema_check(after)



def cohort_run_plan(bids, behavior, excluded, curation, subjects):
    """Plan source-valid runs; unresolved BOLD-only runs remain explicit exclusions.

An unresolved run with existing canonical events still stops for review: this
migration must not silently demote or overwrite an existing behavioral dataset.
"""
    approvals = load_curation_approvals(curation)
    rows = []
    for sub in sorted(subjects):
        bold = set(discover_bold_runs(bids, sub, '01', ['trust']))
        keys = bold | _event_runs(bids, sub, '01', ['trust'])
        resolutions = resolve_sources(behavior, sub, '01', 'trust', sorted(k.run for k in keys), approvals) if sub not in excluded else {}
        for key in sorted(keys):
            if key.run not in {1, 2}:
                raise ValueError(f'unreviewed Trust run number: {key.event_name}')
            reason = ''; digest = ''; fingerprint = ''
            if sub in excluded:
                reason = 'source_excluded'
            elif key not in bold:
                reason = 'bold_missing'
            else:
                source = resolutions[key.run]
                if source.status != 'available' or source.path is None:
                    reason = 'source_' + source.status
                else:
                    digest = sha256_file(source.path)
                    try:
                        converted = convert_source('trust', source.path)
                    except ConversionError as exc:
                        reason = 'invalid_source: ' + str(exc)
                    else:
                        fingerprint = converted.trial_fingerprint
                        unapproved = [issue for issue in converted.review_issues if not issue_is_approved(key, issue, converted, approvals)]
                        if unapproved:
                            reason = 'unapproved_curation: ' + ','.join(unapproved)
                        else:
                            try:
                                schema_check([{k: _format_value(v) for k,v in row.items()} for row in converted.rows])
                            except ValueError as exc:
                                reason = 'invalid_trial_semantics: ' + str(exc)
            if reason and sub not in excluded and event_path(bids, key).exists():
                raise ValueError(f'{key.event_name}: existing canonical events have unresolved source ({reason}); review before migration')
            rows.append(dict(participant_id='sub-'+sub, session='01', run=key.run,
                events_path=str(event_path(bids,key).relative_to(bids)),
                conversion_status='excluded' if reason else 'ready', exclusion_reason=reason,
                source_sha256=digest, trial_fingerprint=fingerprint))
    return rows


def checked_cohort_plan(a, excluded, *, create=False):
    subjects = sorted(p.name[4:] for p in a.bids_root.glob('sub-*') if p.is_dir())
    curation = ROOT/'code/behavior_curation.tsv'
    rows = cohort_run_plan(a.bids_root, a.behavior_root, excluded, curation, subjects)
    payload = dict(runs=rows, source_excluded_subjects=sorted(excluded),
        converter_sha256=sha256_file(ROOT/'code/convert_behavior.py'),
        curation_sha256=sha256_file(curation))
    path = a.work/'cohort_run_plan.json'
    if path.exists():
        if json.loads(path.read_text()) != payload:
            raise ValueError('cohort sources/curation changed since run planning; review before resuming')
    elif create:
        path.write_text(json.dumps(payload,indent=2)+'\n')
    else:
        raise ValueError('cohort run plan missing; run the cohort stage to create it')
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["snapshot", "plan", "check", "export"])
    p.add_argument("--scope", choices=["validation", "cohort"], default="validation")
    p.add_argument("--bids-root", type=Path, default=ROOT / "bids")
    p.add_argument("--behavior-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra/stimuli"))
    p.add_argument("--excluded-source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    p.add_argument("--work", type=Path, default=ROOT / "work/trust_schema")
    p.add_argument("--output", type=Path, default=ROOT / "qc/trust_analysis")
    a = p.parse_args()
    if not a.excluded_source_root.is_dir():
        raise ValueError("authoritative source-exclusion directory is unavailable; refusing empty fallback")
    excluded = source_excluded_subjects(a.excluded_source_root)
    files = canonical_trust_files(a.bids_root)
    if not files:
        raise ValueError("no live Trust events")
    subjects = sorted(({f.name.split('_')[0][4:] for f in files} | {
        p.name.split('_')[0][4:] for p in a.bids_root.glob('sub-*/ses-01/func/*_task-trust*_bold.nii*')}) - excluded)
    a.work.mkdir(parents=True, exist_ok=True)
    snap = a.work / (a.scope + '.json')
    if a.command == 'plan':
        rows = checked_cohort_plan(a, excluded, create=True)
        ready = [r for r in rows if r['conversion_status']=='ready']
        if not ready:
            raise ValueError('no source-valid Trust runs')
        write(a.output/'cohort_run_plan.tsv', rows, list(rows[0]))
        for run in (1,2):
            ids = sorted(r['participant_id'][4:] for r in ready if r['run']==run)
            (a.work/f'cohort_run{run}_subjects.txt').write_text('\n'.join(ids)+('\n' if ids else ''))
        print(f"COHORT PLAN: {len(ready)} source-valid runs; {len(rows)-len(ready)} excluded runs")
        for r in rows:
            if r['conversion_status']=='excluded':
                print(f"EXCLUDED {r['events_path']}: {r['exclusion_reason']}")
    elif a.command == "snapshot":
        if snap.exists():
            raise ValueError(f"snapshot already exists; retain it and use a new --work directory: {snap}")
        if a.scope == "cohort":
            gate = json.loads((a.work / 'validation_passed.json').read_text())
            if gate['converter_sha256'] != sha256_file(ROOT / 'code/convert_behavior.py'):
                raise ValueError("converter changed after validation")
            if gate['bids_root'] != str(a.bids_root.resolve()) or any(sha256_file(a.bids_root/rel)!=digest for rel,digest in gate['events_sha256'].items()):
                raise ValueError('validation inputs changed after the validation gate')
        else:
            if not {'10317', '10953'}.issubset(subjects):
                raise ValueError("requested validation subjects absent; review a replacement set")
            zero_subject = next((f.name.split('_')[0][4:] for f in files
                if f.name.split('_')[0][4:] in subjects and any(r.get('trust_value') in {'0', '0.0'} for r in read(f))), None)
            if zero_subject is None:
                raise ValueError("no actual zero choice available for validation")
            subjects = sorted({'10317', '10953', zero_subject})
        before = {str(f.relative_to(a.bids_root)): read(f) for f in files if f.name.split('_')[0][4:] in subjects}
        snap.write_text(json.dumps(dict(subjects=subjects, events=before, imaging=imaging_inventory(a.bids_root),
            git_sha=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()), indent=2)+'\n')
        (a.work / (a.scope + '_subjects.txt')).write_text('\n'.join(subjects)+'\n')
        print(f"Snapshot: {len(subjects)} participants / {len(before)} runs; {snap}")
    elif a.command == "check":
        saved = json.loads(snap.read_text())
        if saved['imaging'] != imaging_inventory(a.bids_root):
            raise ValueError("imaging stat inventory changed; investigate before proceeding")
        zeros, canonical, ignored = check_snapshot_events(saved, a.bids_root)
        if zeros == 0:
            raise ValueError("validation did not exercise an actual zero choice")
        approvals = load_curation_approvals(ROOT / 'code/behavior_curation.tsv')
        plan = checked_cohort_plan(a, excluded) if a.scope=='cohort' else None
        if plan is not None:
            ready = [r for r in plan if r['conversion_status']=='ready']
            # Cover newly converted canonical runs as well as the original snapshot.
            canonical = {r['events_path']: read(a.bids_root/r['events_path']) for r in ready}
            for rel, rows in canonical.items():
                try:
                    schema_check(rows)
                except ValueError as exc:
                    raise ValueError(f'{rel}: {exc}') from exc
        for sub in sorted(set(saved['subjects']) | ({r['participant_id'][4:] for r in ready} if plan is not None else set())):
            runs = [r['run'] for r in ready if r['participant_id']=='sub-'+sub] if plan is not None else None
            if runs == []:
                continue
            failed, _ = audit_subject_session(a.bids_root, a.behavior_root, sub, '01', ['trust'], approvals=approvals, runs=runs)
            if failed:
                raise ValueError(f"check_events audit failed for sub-{sub}; inspect before advancing")
        report = dict(status='passed', subjects=saved['subjects'], runs=len(canonical), zero_choices=zeros,
            excluded_runs=[r for r in plan if r['conversion_status']=='excluded'] if plan is not None else [],
            ignored_empty_imaging_templates=ignored,
            historical_columns_unchanged=True, imaging_stat_inventory_unchanged=True,
            bids_root=str(a.bids_root.resolve()), events_sha256={rel:sha256_file(a.bids_root/rel) for rel in canonical},
            converter_sha256=sha256_file(ROOT / 'code/convert_behavior.py'), generated_at=datetime.now(timezone.utc).isoformat())
        (a.work / (a.scope + '_passed.json')).write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
    else:
        gate = json.loads((a.work / 'cohort_passed.json').read_text())
        if gate['converter_sha256'] != sha256_file(ROOT / 'code/convert_behavior.py'):
            raise ValueError('converter changed after cohort validation')
        if gate['bids_root'] != str(a.bids_root.resolve()) or any(sha256_file(a.bids_root/rel)!=digest for rel,digest in gate['events_sha256'].items()):
            raise ValueError('cohort events changed after validation')
        plan = checked_cohort_plan(a, excluded)
        planned_ready = {r['events_path'] for r in plan if r['conversion_status']=='ready'}
        # Revalidate the canonical QC against live data before exporting an analysis contract.
        subprocess.run([__import__('sys').executable, str(ROOT/'code/build_events_qc.py'), 'check',
                        '--bids-root', str(a.bids_root), '--excluded-source-root', str(a.excluded_source_root)], check=True)
        approvals = load_curation_approvals(ROOT / 'code/behavior_curation.tsv')
        rows = []
        all_subjects = sorted({f.name.split('_')[0][4:] for f in files} | {
            f.name[4:] for f in a.bids_root.glob('sub-*') if f.is_dir()})
        for sub in all_subjects:
            keys = set(discover_bold_runs(a.bids_root, sub, '01', ['trust'])) | _event_runs(a.bids_root, sub, '01', ['trust'])
            for key in sorted(keys):
                event = event_path(a.bids_root, key)
                reasons = ''
                failed = sub in excluded
                if not failed:
                    with contextlib.redirect_stdout(io.StringIO()):
                        failed, counts = audit_subject_session(a.bids_root, a.behavior_root, sub, '01', ['trust'],
                            approvals=approvals, runs=[key.run])
                    reasons = ';'.join(f'{k}={v}' for k,v in sorted(counts.items()) if v and k not in {'OK','events files found','BOLD runs found','behavioral source runs found'})
                    if failed and str(event.relative_to(a.bids_root)) in planned_ready:
                        raise ValueError(f'{key.event_name}: a planned source-valid run failed final certification')
                    if not failed:
                        schema_check(read(event))
                rows.append(dict(participant_id='sub-'+sub, session='01', run=key.run,
                    events_path=str(event.relative_to(a.bids_root)), events_sha256=sha256_file(event) if event.exists() else '',
                    source_excluded=str(sub in excluded).lower(), structural_status='unresolved' if failed else 'pass',
                    structural_reasons='source_excluded' if sub in excluded else reasons))
        write(a.output/'run_eligibility.tsv', rows, ['participant_id','session','run','events_path','events_sha256','source_excluded','structural_status','structural_reasons'])
        write(a.output/'source_exclusions.tsv', [{'participant_id':'sub-'+s} for s in sorted(excluded)], ['participant_id'])
        provenance = dict(schema_version=1, generated_at=datetime.now(timezone.utc).isoformat(),
            upstream_git_sha=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
            converter_sha256=sha256_file(ROOT/'code/convert_behavior.py'),
            cohort_run_plan_sha256=sha256_file(a.output/'cohort_run_plan.tsv'),
            curation_sha256=sha256_file(ROOT/'code/behavior_curation.tsv'),
            qc_provenance_sha256=sha256_file(ROOT/'qc/events/results/provenance.json'),
            run_eligibility_sha256=sha256_file(a.output/'run_eligibility.tsv'),
            source_exclusions_sha256=sha256_file(a.output/'source_exclusions.tsv'),
            cohort_validation=gate, source_exclusion_inventory_count=len(excluded),
            source_excluded_trust_participants=len({r['participant_id'] for r in rows if r['source_excluded']=='true'}))
        (a.output/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
        print(f"Exported {len(rows)} Trust run eligibility records to {a.output}")

if __name__ == '__main__':
    main()
