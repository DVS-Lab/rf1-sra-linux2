import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
import upgrade_repair_geometry_check as upgrade
import run_reviewed_source_repairs as reviewed

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path, monkeypatch, subject='10964'):
    production = tmp_path / 'production'
    code = production / 'code'
    code.mkdir(parents=True)
    bundle = tmp_path / 'geometry-v1-bundle'
    bundle.mkdir()
    monkeypatch.setattr(upgrade, '__file__', str(bundle / 'upgrade_repair_geometry_check.py'))
    for name, (old, new) in upgrade.VERSIONS.items():
        data = subprocess.check_output(['git', 'show', 'ad061b5f:code/' + name], cwd=ROOT)
        assert upgrade.sha(data) == old
        payload = subprocess.check_output(['git', 'show', 'f1ea354b:code/' + name], cwd=ROOT)
        assert upgrade.sha(payload) == new
        (bundle / name).write_bytes(payload)
        (code / name).write_bytes(data)
    (code / 'unchanged.py').write_text('# immutable processing code\n')
    monkeypatch.setattr(reviewed, 'tracked_code_paths', lambda root: sorted(p.name for p in root.iterdir()))
    destination = production / 'work/repair' / f'sub-{subject}-project'
    (destination / 'code').mkdir(parents=True)
    for path in code.iterdir():
        (destination / 'code' / path.name).write_bytes(path.read_bytes())
    receipt = dict(state='ready', subject=subject, production=str(production),
                   code=reviewed.code_hashes(code, reviewed.tracked_code_paths(code)),
                   protected=reviewed.signatures(reviewed.protected_paths(production, subject)))
    if subject == '11935':
        receipt['completion_runner_sha256'] = upgrade.VERSIONS['complete_11935_repair.py'][0]
    reviewed.write_json(destination / 'repair.json', receipt)
    for name in ('bids/example.nii.gz', 'derivatives/output.nii.gz', 'stages/fmriprep.json', 'logs/geometry/repaired.json'):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('untouched')
    return production, destination, receipt


@pytest.mark.parametrize('subject', ['10964', '11935'])
def test_upgrade_only_orchestration_and_idempotent(tmp_path, monkeypatch, subject):
    production, destination, receipt = fixture(tmp_path, monkeypatch, subject)
    original = reviewed.signatures([production / 'code', destination / 'bids', destination / 'derivatives', destination / 'stages', destination / 'logs'])
    upgrade.upgrade(production, destination)
    assert json.loads((destination / 'repair.json').read_text()) == receipt
    assert not (destination / 'geometry-check-upgrade-v1').exists()
    upgrade.upgrade(production, destination, True)
    assert reviewed.signatures([production / 'code', destination / 'bids', destination / 'derivatives', destination / 'stages', destination / 'logs']) == original
    updated = json.loads((destination / 'repair.json').read_text())
    assert updated['production_code'] == receipt['code']
    assert updated['code'] == reviewed.code_hashes(destination / 'code', updated['code'])
    if subject == '11935':
        assert updated['completion_runner_sha256'] == upgrade.VERSIONS['complete_11935_repair.py'][1]
    before = reviewed.signatures([destination])
    upgrade.upgrade(production, destination, True)
    assert reviewed.signatures([destination]) == before


@pytest.mark.parametrize('damage', ['processing', 'production', 'receipt', 'active'])
def test_refuse_unrelated_changes_or_active_runner(tmp_path, monkeypatch, damage):
    production, destination, receipt = fixture(tmp_path, monkeypatch)
    if damage == 'processing':
        (destination / 'code/unchanged.py').write_text('changed')
    elif damage == 'production':
        (production / 'code/unchanged.py').write_text('changed')
    elif damage == 'receipt':
        receipt['state'] = 'initializing'
        reviewed.write_json(destination / 'repair.json', receipt)
    else:
        lock = (destination.parent / '10964.lock').open('a+')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    before = reviewed.signatures([destination])
    try:
        with pytest.raises((ValueError, BlockingIOError)):
            upgrade.upgrade(production, destination, True)
    finally:
        if damage == 'active':
            lock.close()
    assert reviewed.signatures([destination]) == before


def test_resume_interrupted_upgrade(tmp_path, monkeypatch):
    production, destination, _ = fixture(tmp_path, monkeypatch)
    real_replace = upgrade.replace
    calls = []
    def interrupt(path, data):
        calls.append(path)
        if len(calls) == 2:
            raise OSError('interrupted')
        real_replace(path, data)
    monkeypatch.setattr(upgrade, 'replace', interrupt)
    with pytest.raises(OSError, match='interrupted'):
        upgrade.upgrade(production, destination, True)
    monkeypatch.setattr(upgrade, 'replace', real_replace)
    upgrade.upgrade(production, destination, True)
    updated = json.loads((destination / 'repair.json').read_text())
    assert updated['code'] == reviewed.code_hashes(destination / 'code', updated['code'])


def test_refuse_code_directory_link_to_production(tmp_path, monkeypatch):
    production, destination, _ = fixture(tmp_path, monkeypatch)
    (destination / 'code').rename(destination / 'old-code')
    (destination / 'code').symlink_to(production / 'code', target_is_directory=True)
    before = reviewed.signatures([production / 'code'])
    with pytest.raises(ValueError, match='symlink'):
        upgrade.upgrade(production, destination, True)
    assert reviewed.signatures([production / 'code']) == before


def test_upgrade_actual_older_11935_snapshot(tmp_path, monkeypatch):
    production, destination, receipt = fixture(tmp_path, monkeypatch, '11935')
    for name, (old, new) in upgrade.OLDER_11935_CODE.items():
        data = subprocess.check_output(['git', 'show', 'ca4323cd:code/' + name], cwd=ROOT)
        assert upgrade.sha(data) == old
        (destination / 'code' / name).write_bytes(data)
        receipt['code'][name] = old
        newer = subprocess.check_output(['git', 'show', '591d29d7:code/' + name], cwd=ROOT)
        assert upgrade.sha(newer) == new
        (production / 'code' / name).write_bytes(newer)
    reviewed.write_json(destination / 'repair.json', receipt)
    before = reviewed.signatures([destination / 'bids', destination / 'derivatives', destination / 'stages'])
    upgrade.upgrade(production, destination, True)
    updated = json.loads((destination / 'repair.json').read_text())
    assert updated['code'] == reviewed.code_hashes(destination / 'code', updated['code'])
    assert updated['production_code'] == reviewed.code_hashes(production / 'code', updated['production_code'])
    assert updated['code']['run_11935_initialization.py'] == upgrade.OLDER_11935_CODE['run_11935_initialization.py'][0]
    assert reviewed.signatures([destination / 'bids', destination / 'derivatives', destination / 'stages']) == before
    upgrade.upgrade(production, destination, True)


@pytest.mark.parametrize('damage', ['unrecognized_hash', 'extra_file', 'wrong_subject'])
def test_older_snapshot_exception_is_narrow(damage):
    frozen = {k: v[0] for k, v in upgrade.OLDER_11935_CODE.items()}
    current = {k: v[1] for k, v in upgrade.OLDER_11935_CODE.items()}
    subject = '11935'
    if damage == 'unrecognized_hash':
        current['run_11935_initialization.py'] = 'unexpected'
    elif damage == 'extra_file':
        current['fmriprep.sh'] = 'unexpected'
    else:
        subject = '10964'
    with pytest.raises(ValueError, match='differs'):
        upgrade.validate_production_code(subject, frozen, current)


def test_freesurfer_upgrade_preserves_other_code_and_products(tmp_path, monkeypatch):
    production, destination, _ = fixture(tmp_path, monkeypatch, '11935')
    upgrade.upgrade(production, destination, True)
    monkeypatch.setattr(upgrade, '__file__', str(ROOT / 'code/upgrade_repair_geometry_check.py'))
    real_check_output = subprocess.check_output
    monkeypatch.setattr(upgrade.subprocess, 'check_output',
                        lambda command: real_check_output(['git', 'show', command[-1]], cwd=ROOT))
    before = reviewed.signatures([destination / 'bids', destination / 'derivatives', destination / 'stages', production / 'code'])
    upgrade.upgrade_freesurfer(production, destination, True)
    receipt = json.loads((destination / 'repair.json').read_text())
    assert receipt['code'] == reviewed.code_hashes(destination / 'code', receipt['code'])
    assert receipt['completion_runner_sha256'] == upgrade.FS_RUNNER_SHA
    assert reviewed.signatures([destination / 'bids', destination / 'derivatives', destination / 'stages', production / 'code']) == before
    staged = reviewed.signatures([destination])
    upgrade.upgrade_freesurfer(production, destination, True)
    assert reviewed.signatures([destination]) == staged


def test_geometry_upgrade_with_new_bundle_uses_verified_historical_payload(tmp_path, monkeypatch):
    production, destination, _ = fixture(tmp_path, monkeypatch, '11935')
    monkeypatch.setattr(upgrade, '__file__', str(ROOT / 'code/upgrade_repair_geometry_check.py'))
    real_check_output = subprocess.check_output
    def git_blob(command):
        assert command == ['git', '-C', str(production), 'show',
                           'f1ea354b:code/complete_11935_repair.py']
        return real_check_output(['git', 'show', command[-1]], cwd=ROOT)
    monkeypatch.setattr(upgrade.subprocess, 'check_output', git_blob)
    upgrade.upgrade(production, destination, True)
    receipt = json.loads((destination / 'repair.json').read_text())
    assert receipt['completion_runner_sha256'] == upgrade.VERSIONS['complete_11935_repair.py'][1]
