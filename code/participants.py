#!/usr/bin/env python3
"""Recover and maintain baseline participant metadata from saved HeuDiConv seqinfo."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid

from pipeline_utils import apply_umask_mode, read_subject_list

ROOT = Path(__file__).resolve().parents[1]
MISSING = {'', 'n/a', 'na', 'none', 'nan'}
REQUIRED = ('participant_id', 'age', 'sex')
PROVENANCE_KEY = 'RF1BaselineDemographics'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def age_years(raw):
    value = raw.strip()
    if value.lower() in MISSING:
        return 'n/a'
    # Match HeuDiConv's years/months interpretation, without silently stripping
    # unsupported DICOM units or deriving age from potentially shifted dates.
    match = re.fullmatch(r'(\d+(?:\.\d+)?)([YM]?)', value)
    if not match:
        raise ValueError('invalid or unsupported age encoding')
    age = Decimal(match[1])
    if match[2] == 'M':
        age = (age / 12).quantize(Decimal('0.01'))
    return format(age.normalize(), 'f')


def sex_code(raw):
    value = raw.strip()
    if value.lower() in MISSING or value.upper() == 'U':
        return 'n/a'
    if value.upper() not in {'M', 'F', 'O'}:
        raise ValueError('invalid sex encoding')
    return value.upper()


def read_tsv(path):
    data = path.read_bytes()
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')), delimiter='\t')
    fields = reader.fieldnames
    if not fields or len(fields) != len(set(fields)):
        raise ValueError('missing or duplicate column names')
    rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('malformed TSV row')
    return fields, rows, digest(data)


def source_row(path, subject):
    fields, rows, sha = read_tsv(path)
    if not {'patient_age', 'patient_sex'} <= set(fields) or not rows:
        raise ValueError('missing demographic columns or empty seqinfo')
    result = {'participant_id': 'sub-' + subject}
    missing = {}
    for field, source, normalizer in [('age', 'patient_age', age_years),
                                       ('sex', 'patient_sex', sex_code)]:
        values = [normalizer(row[source]) for row in rows]
        known = set(values) - {'n/a'}
        if len(known) > 1:
            raise ValueError('conflicting baseline ' + field + ' across series')
        result[field] = next(iter(known), 'n/a')
        missing[field + '_missing_series'] = values.count('n/a')
    return result, {'source': f'.heudiconv/{subject}/ses-01/info/dicominfo_ses-01.tsv',
                    'sha256': sha, 'series_rows': len(rows), **missing}


def exclusions(root):
    if not root.is_dir():
        raise ValueError('source-exclusions directory is unavailable')
    return {'sub-' + p.name.removeprefix('Smith-SRA-') for p in root.iterdir()
            if p.is_dir() and re.fullmatch(r'Smith-SRA-\d{5}', p.name)}


def scope(args, excluded):
    if args.subject:
        subjects = [args.subject.removeprefix('sub-')]
    elif args.sublist:
        subjects = read_subject_list(args.sublist)
    else:
        subjects = [p.name.removeprefix('sub-') for p in args.bids_root.glob('sub-*')
                    if p.is_dir()]
    if any(not re.fullmatch(r'\d{5}', sub) for sub in subjects):
        raise ValueError('invalid RF1 subject ID in requested scope')
    return sorted({s for s in subjects if 'sub-' + s not in excluded})


def read_existing(root):
    table = root / 'participants.tsv'
    if not table.exists():
        return list(REQUIRED), {}, {}
    fields, rows, _ = read_tsv(table)
    if not set(REQUIRED) <= set(fields):
        raise ValueError('existing participants.tsv lacks required columns')
    by_id = {}
    for row in rows:
        pid = row['participant_id']
        if not re.fullmatch(r'sub-\d{5}', pid) or pid in by_id:
            raise ValueError('existing participants.tsv has invalid or duplicate IDs')
        for name, normalizer in [('age', age_years), ('sex', sex_code)]:
            normalizer(row[name])
        by_id[pid] = row
    sidecar = root / 'participants.json'
    meta = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    if not isinstance(meta, dict):
        raise ValueError('participants.json must be an object')
    provenance = meta.get(PROVENANCE_KEY, {})
    if not isinstance(provenance, dict) or not isinstance(provenance.get('sources', {}), dict):
        raise ValueError('invalid existing participant provenance schema')
    return fields, by_id, meta


def table_bytes(fields, rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows[k] for k in sorted(rows))
    return out.getvalue().encode()


def atomic_write(path, data):
    if path.is_symlink():
        raise ValueError('refusing to replace a symlink')
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        apply_umask_mode(Path(temporary))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(root):
    # All RF1 participant writers use the same persistent inode. Do not unlink.
    with (root / '.participants.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def metadata(existing, sources, table_sha):
    result = dict(existing)
    result.update({
        'participant_id': {'Description': 'BIDS ID assigned by the RF1 conversion subject mapping.'},
        'age': {'Description': 'Scanner-recorded PatientAge from saved session-01 HeuDiConv '
                'seqinfo, in years at baseline MRI. Not derived from birth or acquisition dates. '
                'Not independently validated against research records; scanner rounding is retained.',
                'Units': 'years'},
        'sex': {'Description': 'Scanner-recorded PatientSex from saved session-01 HeuDiConv '
                'seqinfo; not a claim of self-reported gender.',
                'Levels': {'M': 'Male', 'F': 'Female', 'O': 'Other'}},
        PROVENANCE_KEY: {'reference_session': '01', 'source_type': 'HeuDiConv seqinfo DICOM demographics',
                        'missing_value': 'n/a', 'participants_sha256': table_sha, 'sources': sources}
    })
    return result


def eligible_ids(path, excluded):
    if path is None:
        return set()
    fields, rows, _ = read_tsv(path)
    needed = {'participant_id', 'structural_status', 'source_excluded', 'events_sha256'}
    if not needed <= set(fields):
        raise ValueError('invalid eligibility schema')
    return {r['participant_id'] for r in rows if r['structural_status'] == 'pass'
            and r['source_excluded'] == 'false' and r['events_sha256']
            and r['participant_id'] not in excluded}


def execute(args):
    root = args.bids_root
    if not root.is_dir():
        raise ValueError('BIDS root is unavailable')
    excluded = exclusions(args.exclusions_root)
    subjects = scope(args, excluded)
    if not subjects:
        raise ValueError('no non-source-excluded subjects in scope')
    report = {'schema_version': 1, 'command': args.command, 'applied': False,
              'reference_session': '01', 'requested_subjects': len(subjects),
              'source_excluded_subjects_omitted': len(excluded),
              'source_exclusion_ids_sha256': digest('\n'.join(sorted(excluded)).encode()),
              'issues': [], 'subjects': {}}
    with locked(root):
        fields, existing, old_meta = read_existing(root)
        if args.command == 'check' and not existing:
            raise ValueError('participants.tsv is missing or empty')
        output = {k: dict(v) for k, v in existing.items() if k not in excluded}
        sources = dict(old_meta.get(PROVENANCE_KEY, {}).get('sources', {}))
        sources = {k: v for k, v in sources.items() if k not in excluded}
        for sub in subjects:
            pid = 'sub-' + sub
            path = args.seqinfo_file or root / '.heudiconv' / sub / 'ses-01/info/dicominfo_ses-01.tsv'
            try:
                row, evidence = source_row(path, sub)
                sources[pid] = evidence
                report['subjects'][pid] = {**evidence, 'age_missing': row['age'] == 'n/a',
                                          'sex_missing': row['sex'] == 'n/a'}
                current = output.get(pid)
                if args.command == 'check' and current is None:
                    raise ValueError('participant row is missing')
                if current is None:
                    current = {k: 'n/a' for k in fields}
                    current['participant_id'] = pid
                for name, normalizer in [('age', age_years), ('sex', sex_code)]:
                    old = normalizer(current[name])
                    if old != row[name] and (old != 'n/a' or args.command == 'check'):
                        raise ValueError('existing ' + name + ' disagrees with baseline source')
                    current[name] = row[name]
                output[pid] = current
            except (ValueError, OSError, UnicodeError, csv.Error) as exc:
                # Never put source rows, ages, sex values, dates, or DICOM IDs in public logs.
                reason = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, UnicodeError) else type(exc).__name__
                report['issues'].append({'participant_id': pid, 'reason': reason})
        required = eligible_ids(args.eligibility, excluded)
        for pid in sorted(set(output) - set(sources)):
            report['issues'].append({'participant_id': pid,
                                     'reason': 'existing row has no baseline source provenance; run full build'})
        missing_required = sorted(required - set(output))
        report.update(exported_rows=len(output), eligible_participants=len(required),
                      eligible_missing_rows=missing_required,
                      eligible_missing_age=sum(age_years(output[k]['age']) == 'n/a' for k in required & set(output)),
                      eligible_missing_sex=sum(sex_code(output[k]['sex']) == 'n/a' for k in required & set(output)),
                      missing_age=sum(age_years(r['age']) == 'n/a' for r in output.values()),
                      missing_sex=sum(sex_code(r['sex']) == 'n/a' for r in output.values()))
        if missing_required:
            report['issues'].append({'reason': 'eligible participants are absent from export'})
        if args.eligibility:
            report['eligibility_sha256'] = digest(args.eligibility.read_bytes())
        if args.command == 'check':
            prov = old_meta.get(PROVENANCE_KEY, {})
            if (not {'participant_id', 'age', 'sex'} <= set(old_meta)
                    or prov.get('reference_session') != '01'
                    or prov.get('participants_sha256') != digest((root / 'participants.tsv').read_bytes())):
                report['issues'].append({'reason': 'missing or mismatched sidecar provenance'})
            if set(existing) & excluded:
                report['issues'].append({'reason': 'export contains source-excluded IDs'})
            for pid in report['subjects']:
                if prov.get('sources', {}).get(pid) != sources[pid]:
                    report['issues'].append({'participant_id': pid, 'reason': 'baseline source hash/provenance changed'})
        if not report['issues'] and args.command == 'build':
            data = table_bytes(fields, output)
            meta = metadata(old_meta, sources, digest(data))
            meta_data = (json.dumps(meta, indent=2, sort_keys=True) + '\n').encode()
            report['participants_sha256'] = digest(data)
            if args.apply:
                # Source files can be regenerated by prepdata. Refuse a changed
                # input between collection and installation rather than certifying it.
                for sub in subjects:
                    path = args.seqinfo_file or root / '.heudiconv' / sub / 'ses-01/info/dicominfo_ses-01.tsv'
                    if digest(path.read_bytes()) != sources['sub-' + sub]['sha256']:
                        raise ValueError('baseline source changed during export')
                backup = root / '.participants-backups' / uuid.uuid4().hex
                backup.mkdir(parents=True, mode=0o700)
                os.chmod(backup.parent, 0o700)
                for name in ('participants.tsv', 'participants.json'):
                    if (root / name).is_symlink():
                        raise ValueError('refusing to replace a symlink')
                    if (root / name).exists():
                        shutil.copy2(root / name, backup / name)
                        os.chmod(backup / name, 0o600)
                # The TSV digest in JSON detects interruption between the two
                # atomic replacements. The next check must pass before handoff.
                atomic_write(root / 'participants.json', meta_data)
                atomic_write(root / 'participants.tsv', data)
                report['applied'] = True
                report['backup'] = str(backup.relative_to(root))
        report['status'] = 'failed' if report['issues'] else 'passed'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'check'])
    parser.add_argument('--bids-root', type=Path, default=ROOT / 'bids')
    parser.add_argument('--exclusions-root', type=Path,
                        default=Path(os.environ.get('SOURCEDATA_EXCLUSIONS_ROOT',
                                     '/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions')))
    select = parser.add_mutually_exclusive_group()
    select.add_argument('--subject')
    select.add_argument('--sublist', type=Path)
    parser.add_argument('--seqinfo-file', type=Path, help='Staged session-01 metadata, only with --subject build.')
    parser.add_argument('--eligibility', type=Path, help='Also verify coverage of the Trust structural handoff.')
    parser.add_argument('--apply', action='store_true', help='Install the audited table; default build is a preview.')
    parser.add_argument('--report-json', type=Path)
    args = parser.parse_args(argv)
    if args.seqinfo_file and (not args.subject or args.command != 'build' or args.apply):
        parser.error('--seqinfo-file is only for a single-subject build preview')
    if args.apply and args.command != 'build':
        parser.error('--apply requires build')
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    report_path = args.report_json or ROOT / 'qc/participants' / (tag + '-' + args.command + '.json')
    try:
        report = execute(args)
    except (ValueError, OSError, UnicodeError, csv.Error, InvalidOperation) as exc:
        # Exception text from parsers/filesystems can disclose private paths/values.
        reason = str(exc) if type(exc) is ValueError else 'Could not validate input files/schema; inspect inputs privately.'
        report = {'status': 'failed', 'command': args.command, 'error_type': type(exc).__name__,
                  'issues': [{'reason': reason}]}
    report.update(script_sha256=digest(Path(__file__).read_bytes()),
                  created_utc=datetime.now(timezone.utc).isoformat())
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(report_path, (json.dumps(report, indent=2, sort_keys=True) + '\n').encode())
    print(f"Participants {args.command}: {report['status']}; rows={report.get('exported_rows', 0)}; "
          f"missing age={report.get('missing_age', 0)}; missing sex={report.get('missing_sex', 0)}")
    if 'eligible_participants' in report and args.eligibility:
        print(f"Eligible cohort: {report['eligible_participants']} participants; "
              f"missing rows={len(report['eligible_missing_rows'])}; "
              f"unknown age={report['eligible_missing_age']}; unknown sex={report['eligible_missing_sex']}")
    for issue in report['issues']:
        print(f"REVIEW {issue.get('participant_id', 'metadata')}: {issue['reason']}")
    print(f'Report: {report_path}')
    if report['status'] != 'passed':
        return 1
    if args.command == 'build' and not args.apply:
        print('DRY RUN: no participants table or sidecar installed. Add --apply.')
    else:
        print('CHECK PASSED: baseline metadata and requested demographic coverage validated.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
