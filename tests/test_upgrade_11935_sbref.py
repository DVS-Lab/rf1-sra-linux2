import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
import upgrade_11935_sbref as upgrade
import run_reviewed_source_repairs as reviewed

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    project = tmp_path / 'production'
    dest = project / 'work/final/sub-11935-project'
    (dest / 'code').mkdir(parents=True)
    (dest / 'code' / upgrade.NAME).write_bytes(subprocess.check_output(
        ['git', 'show', 'bd3ff07d:code/' + upgrade.NAME], cwd=ROOT))
    code = reviewed.code_hashes(dest / 'code', [upgrade.NAME])
    receipt = dict(state='ready', subject='11935', production=str(project), code=code,
                   completion_runner_sha256=upgrade.FS_RUNNER_SHA,
                   protected=reviewed.signatures(reviewed.protected_paths(project, '11935')))
    reviewed.write_json(dest / 'repair.json', receipt)
    reviewed.write_json(dest / 'completion-stages/fmriprep.json', dict(passed=True))
    for name in ('bids/reference.nii.gz', 'derivatives/freesurfer/surf/white',
                 'derivatives/warpkit/field.nii.gz', 'derivatives/mriqc/iqms.json',
                 'functional-cache/completed.txt', 'logs/geometry/11935-repaired.json'):
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'keep')
    func = dest / 'derivatives/fmriprep/sub-11935/ses-01/func'
    for task in ('doors', 'socialdoors'):
        stem = f'sub-11935_ses-01_task-{task}_run-1'
        reviewed.write_json(func / f'{stem}_part-mag_desc-coreg_boldref.json', dict(Sources=[
            'bids:raw:sub-11935/ses-01/func/sub-11935_ses-01_task-doors_run-1_echo-1_sbref.nii.gz',
            f'bids::sub-11935/ses-01/fmap/sub-11935_ses-01_acq-{task}_run-1_fmapid-auto00001_desc-coeff_fieldmap.nii.gz']))
        (func / f'{stem}_bold.nii.gz').write_bytes(b'original pixels')
    return project, dest


def test_backup_upgrade_and_idempotence(tmp_path):
    project, dest = fixture(tmp_path)
    folders = [dest / n for n in ('bids', 'derivatives', 'completion-stages', 'functional-cache', 'logs')]
    before = reviewed.signatures(folders)
    upgrade.upgrade(project, dest)
    assert not (dest / 'sbref-task-recovery-v1').exists()
    upgrade.upgrade(project, dest, True)
    assert reviewed.signatures(folders) == before
    receipt = json.loads((dest / 'repair.json').read_text())
    assert receipt['completion_runner_sha256'] == upgrade.RUNNER_SHA
    assert receipt['code'] == reviewed.code_hashes(dest / 'code', receipt['code'])
    assert receipt['sbref_task_recovery']['task'] == 'socialdoors'
    assert any('task-doors' in p for p in receipt['sbref_task_recovery']['preserved_files'])
    backup = dest / 'sbref-task-recovery-v1/fmriprep'
    assert upgrade.file_hashes(backup) == upgrade.file_hashes(dest / 'derivatives/fmriprep')
    after = reviewed.signatures([dest])
    upgrade.upgrade(project, dest, True)
    assert reviewed.signatures([dest]) == after


@pytest.mark.parametrize('damage', ['ready', 'tedana', 'code', 'wrong_reference'])
def test_refuses_unreviewed_state(tmp_path, damage):
    project, dest = fixture(tmp_path)
    if damage == 'ready':
        (dest / '11935-ready.json').write_text('{}')
    elif damage == 'tedana':
        (dest / 'completion-stages/tedana.json').write_text('{}')
    elif damage == 'code':
        (dest / 'code' / upgrade.NAME).write_text('changed')
    else:
        file = next((dest / 'derivatives/fmriprep').rglob('*task-socialdoors*json'))
        file.write_text(file.read_text().replace('task-doors', 'task-other'))
    with pytest.raises(ValueError):
        upgrade.upgrade(project, dest, True)
    assert not (dest / 'sbref-task-recovery-v1').exists()


def test_backup_tampering_rejected(tmp_path):
    project, dest = fixture(tmp_path)
    upgrade.upgrade(project, dest, True)
    next((dest / 'sbref-task-recovery-v1/fmriprep').rglob('*.nii.gz')).write_bytes(b'changed')
    with pytest.raises(ValueError, match='Backup changed'):
        upgrade.upgrade(project, dest, True)
