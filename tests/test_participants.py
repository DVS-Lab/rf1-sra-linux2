"""Participant recovery must preserve baseline, provenance, and shared writes."""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
import participants as p


def write_tsv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='') as h:
        writer = csv.DictWriter(h, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


class ParticipantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bids = self.root / 'bids'
        self.bids.mkdir()
        self.excluded = self.root / 'exclusions'
        self.excluded.mkdir()

    def args(self, **kw):
        values = dict(command='build', bids_root=self.bids, exclusions_root=self.excluded,
                      subject=None, sublist=None, seqinfo_file=None, eligibility=None, apply=False)
        values.update(kw)
        return SimpleNamespace(**values)

    def source(self, subject='10001', age='042Y', sex='F', session='01'):
        (self.bids / ('sub-' + subject) / ('ses-' + session)).mkdir(parents=True, exist_ok=True)
        path = self.bids / '.heudiconv' / subject / ('ses-' + session) / 'info' / ('dicominfo_ses-' + session + '.tsv')
        write_tsv(path, ['patient_age', 'patient_sex', 'patient_id'],
                  [{'patient_age': age, 'patient_sex': sex, 'patient_id': 'PRIVATE_REGISTRATION'}])
        return path

    def test_age_sex_encoding(self):
        for raw, expected in [('042Y', '42'), ('42', '42'), ('018M', '1.5'), ('001M', '0.08'),
                              ('000Y', '0'), ('None', 'n/a'), ('', 'n/a')]:
            self.assertEqual(p.age_years(raw), expected)
        for bad in ['042D', '-1', 'inf', '03Q', 'patient_age']:
            with self.assertRaises(ValueError):
                p.age_years(bad)
        self.assertEqual(p.sex_code('f'), 'F')
        self.assertEqual(p.sex_code('U'), 'n/a')
        with self.assertRaises(ValueError):
            p.sex_code('PRIVATE NAME')

    def test_dry_run_then_apply_check_and_baseline(self):
        self.source()
        self.source(age='044Y', session='02')
        report = p.execute(self.args())
        self.assertEqual(report['status'], 'passed')
        self.assertFalse((self.bids / 'participants.tsv').exists())
        self.assertNotIn('PRIVATE_REGISTRATION', json.dumps(report))
        p.execute(self.args(apply=True))
        row = p.read_existing(self.bids)[1]['sub-10001']
        self.assertEqual(row['age'], '42')
        self.assertEqual(p.execute(self.args(command='check'))['status'], 'passed')

    def test_conflicts_report_without_values_or_writes(self):
        path = self.source()
        with path.open('a') as h:
            h.write('051Y\tF\tPRIVATE_REGISTRATION\n')
        report = p.execute(self.args(apply=True))
        self.assertEqual(report['status'], 'failed')
        self.assertIn('conflicting baseline age', report['issues'][0]['reason'])
        self.assertNotIn('051', json.dumps(report))
        self.assertFalse((self.bids / 'participants.tsv').exists())

    def test_missing_source_is_not_placeholder_metadata(self):
        (self.bids / 'sub-10001').mkdir()
        report = p.execute(self.args(apply=True))
        self.assertEqual(report['status'], 'failed')
        self.assertFalse((self.bids / 'participants.tsv').exists())

    def test_genuine_missing_values_and_partial_series_missingness(self):
        path = self.source(age='', sex='')
        p.execute(self.args(apply=True))
        self.assertEqual(p.read_existing(self.bids)[1]['sub-10001']['age'], 'n/a')
        with path.open('a') as h:
            h.write('042Y\tF\tPRIVATE_REGISTRATION\n')
        report = p.execute(self.args(apply=True))
        self.assertEqual(report['missing_age'], 0)
        self.assertEqual(report['subjects']['sub-10001']['age_missing_series'], 1)

    def test_existing_conflict_stops_and_preserves_bytes(self):
        self.source()
        p.execute(self.args(apply=True))
        before = (self.bids / 'participants.tsv').read_bytes()
        self.source(age='043Y')
        report = p.execute(self.args(apply=True))
        self.assertEqual(report['status'], 'failed')
        self.assertEqual((self.bids / 'participants.tsv').read_bytes(), before)

    def test_preserve_extra_columns_other_subjects_and_backup(self):
        self.source()
        p.execute(self.args(apply=True))
        fields, rows, _ = p.read_existing(self.bids)
        fields.append('study_group')
        rows['sub-10001']['study_group'] = 'existing'
        write_tsv(self.bids / 'participants.tsv', fields, rows.values())
        before = (self.bids / 'participants.tsv').read_bytes()
        self.source(subject='10002')
        report = p.execute(self.args(subject='10002', apply=True))
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(p.read_existing(self.bids)[1]['sub-10001']['study_group'], 'existing')
        backup = self.bids / report['backup'] / 'participants.tsv'
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_exclusions_are_not_qa_and_must_exist(self):
        self.source()
        self.source(subject='10002')
        (self.excluded / 'Smith-SRA-10002').mkdir()
        report = p.execute(self.args(apply=True))
        self.assertEqual(report['exported_rows'], 1)
        self.assertEqual(set(p.read_existing(self.bids)[1]), {'sub-10001'})
        with self.assertRaises(ValueError):
            p.execute(self.args(exclusions_root=self.root / 'absent'))

    def test_eligible_coverage_checks_all_participants(self):
        self.source()
        path = self.root / 'eligibility.tsv'
        write_tsv(path, ['participant_id', 'structural_status', 'source_excluded', 'events_sha256'], [
            dict(participant_id='sub-10002', structural_status='pass', source_excluded='false', events_sha256='hash')])
        report = p.execute(self.args(apply=True, eligibility=path))
        self.assertEqual(report['eligible_missing_rows'], ['sub-10002'])
        self.assertEqual(report['status'], 'failed')
        self.assertFalse((self.bids / 'participants.tsv').exists())

    def test_checker_detects_table_and_source_drift(self):
        source = self.source()
        p.execute(self.args(apply=True))
        with source.open('a') as h:
            h.write('042Y\tF\tPRIVATE_REGISTRATION\n')
        self.assertEqual(p.execute(self.args(command='check'))['status'], 'failed')
        p.execute(self.args(apply=True))
        with (self.bids / 'participants.tsv').open('a') as h:
            h.write('sub-10002\t40\tM\n')
        self.assertEqual(p.execute(self.args(command='check'))['status'], 'failed')

    def test_new_subject_preview_uses_staging_then_installed_source(self):
        stage = self.root / 'stage.tsv'
        write_tsv(stage, ['patient_age', 'patient_sex'], [dict(patient_age='040Y', patient_sex='M')])
        report = p.execute(self.args(subject='10001', seqinfo_file=stage))
        self.assertEqual(report['status'], 'passed')
        self.assertFalse((self.bids / 'participants.tsv').exists())

    def test_public_reports_do_not_print_private_invalid_values(self):
        self.source(age='PRIVATE_BAD_AGE')
        report_path = self.root / 'report.json'
        cmd = [sys.executable, str(Path(p.__file__)), 'build', '--bids-root', str(self.bids),
               '--exclusions-root', str(self.excluded), '--report-json', str(report_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        text = result.stdout + result.stderr + report_path.read_text()
        self.assertNotIn('PRIVATE_', text)

    def test_shared_permissions_follow_umask(self):
        self.source()
        previous = os.umask(0o002)
        try:
            p.execute(self.args(apply=True))
        finally:
            os.umask(previous)
        self.assertEqual((self.bids / 'participants.tsv').stat().st_mode & 0o777, 0o664)

    def test_parallel_subject_updates_do_not_lose_rows(self):
        self.source()
        self.source(subject='10002')
        commands = []
        for sub in ['10001', '10002']:
            commands.append([sys.executable, str(Path(p.__file__)), 'build', '--apply', '--subject', sub,
                             '--bids-root', str(self.bids), '--exclusions-root', str(self.excluded),
                             '--report-json', str(self.root / (sub + '.json'))])
        processes = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for cmd in commands]
        for proc in processes:
            stdout, stderr = proc.communicate(timeout=30)
            self.assertEqual(proc.returncode, 0, stdout + stderr)
        self.assertEqual(set(p.read_existing(self.bids)[1]), {'sub-10001', 'sub-10002'})
        self.assertEqual(p.execute(self.args(command='check'))['status'], 'passed')


if __name__ == '__main__':
    unittest.main()
