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
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from build_events_qc import source_excluded_subjects, sha256_file
from check_events import audit_subject_session, _event_runs
from convert_behavior import discover_bold_runs, event_path, load_curation_approvals

ROOT = Path(__file__).resolve().parents[1]
ADDED = {"scheduled_reciprocation", "cLeft", "cRight"}


def read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["snapshot", "check", "export"])
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
    files = sorted(a.bids_root.glob("sub-*/ses-01/func/*_task-trust*_events.tsv"))
    if not files:
        raise ValueError("no live Trust events")
    subjects = sorted(({f.name.split('_')[0][4:] for f in files} | {
        p.name.split('_')[0][4:] for p in a.bids_root.glob('sub-*/ses-01/func/*_task-trust*_bold.nii*')}) - excluded)
    a.work.mkdir(parents=True, exist_ok=True)
    snap = a.work / (a.scope + '.json')
    if a.command == "snapshot":
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
        zeros = sum(compare_extension(rows, read(a.bids_root / rel)) for rel, rows in saved['events'].items())
        if zeros == 0:
            raise ValueError("validation did not exercise an actual zero choice")
        approvals = load_curation_approvals(ROOT / 'code/behavior_curation.tsv')
        for sub in saved['subjects']:
            failed, _ = audit_subject_session(a.bids_root, a.behavior_root, sub, '01', ['trust'], approvals=approvals)
            if failed:
                raise ValueError(f"check_events audit failed for sub-{sub}; inspect before advancing")
        report = dict(status='passed', subjects=saved['subjects'], runs=len(saved['events']), zero_choices=zeros,
            historical_columns_unchanged=True, imaging_stat_inventory_unchanged=True,
            bids_root=str(a.bids_root.resolve()), events_sha256={rel:sha256_file(a.bids_root/rel) for rel in saved['events']},
            converter_sha256=sha256_file(ROOT / 'code/convert_behavior.py'), generated_at=datetime.now(timezone.utc).isoformat())
        (a.work / (a.scope + '_passed.json')).write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
    else:
        gate = json.loads((a.work / 'cohort_passed.json').read_text())
        if gate['converter_sha256'] != sha256_file(ROOT / 'code/convert_behavior.py'):
            raise ValueError('converter changed after cohort validation')
        if gate['bids_root'] != str(a.bids_root.resolve()) or any(sha256_file(a.bids_root/rel)!=digest for rel,digest in gate['events_sha256'].items()):
            raise ValueError('cohort events changed after validation')
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
