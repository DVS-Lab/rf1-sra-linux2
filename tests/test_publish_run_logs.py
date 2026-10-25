from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
import publish_run_logs as upload

LOG = 'logs/records/20261024-201433_pixel-check.md'


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.PIPE).decode().strip()


def write(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)


def commit(root, name, data):
    write(root, name, data)
    git(root, 'add', name)
    git(root, 'commit', '-m', name)


@pytest.fixture
def repos(tmp_path):
    remote, writer, linux = [tmp_path / name for name in ('remote.git', 'writer', 'linux')]
    remote.mkdir()
    git(remote, 'init', '--bare', '--initial-branch=main')
    git(tmp_path, 'clone', str(remote), str(writer))
    for root in (writer,):
        git(root, 'config', 'user.name', 'Test')
        git(root, 'config', 'user.email', 'test@example.invalid')
    commit(writer, 'code.py', 'frozen code\n')
    commit(writer, 'logs/records/20260101-000000_old.md', 'old record\n')
    git(writer, 'push', 'origin', 'main')
    git(tmp_path, 'clone', str(remote), str(linux))
    git(linux, 'config', 'user.name', 'Test')
    git(linux, 'config', 'user.email', 'test@example.invalid')
    return remote, writer, linux


def state(root):
    return (git(root, 'rev-parse', 'HEAD'), (root / '.git/index').read_bytes(),
            {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
             for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts})


@pytest.mark.parametrize('committed', [False, True])
def test_divergent_main_upload_keeps_checkout_and_staged_work(repos, committed):
    remote, writer, linux = repos
    commit(writer, 'code.py', 'new remote code\n')
    git(writer, 'push', 'origin', 'main')
    if committed:
        commit(linux, LOG, 'complete record\n')
    else:
        write(linux, LOG, 'complete record\n')
    write(linux, 'code.py', 'unrelated local edit\n')
    git(linux, 'add', 'code.py')
    write(linux, 'private.txt', 'do not publish\n')
    before = state(linux)
    upload.publish(linux)
    assert state(linux) == before
    assert git(remote, 'show', 'main:' + LOG) == 'complete record'
    assert git(remote, 'show', 'main:code.py') == 'new remote code'
    assert 'private.txt' not in git(remote, 'ls-tree', '-r', '--name-only', 'main')
    assert git(linux, 'for-each-ref', 'refs/rf1-log-upload') == ''
    tip = git(remote, 'rev-parse', 'main')
    upload.publish(linux)
    assert git(remote, 'rev-parse', 'main') == tip
    assert state(linux) == before


def test_dry_run_does_not_publish(repos):
    remote, _, linux = repos
    write(linux, LOG, 'record')
    before, tip = state(linux), git(remote, 'rev-parse', 'main')
    upload.publish(linux, True)
    assert state(linux) == before and git(remote, 'rev-parse', 'main') == tip


def test_collision_refuses_all_logs(repos):
    remote, writer, linux = repos
    commit(writer, LOG, 'remote record')
    git(writer, 'push', 'origin', 'main')
    write(linux, LOG, 'different record')
    write(linux, 'logs/records/20261024-210000_another.md', 'new record')
    tip = git(remote, 'rev-parse', 'main')
    with pytest.raises(ValueError, match='refusing overwrite'):
        upload.publish(linux)
    assert git(remote, 'rev-parse', 'main') == tip


def test_old_local_record_does_not_revert_remote_edit(repos):
    remote, writer, linux = repos
    commit(writer, 'logs/records/20260101-000000_old.md', 'corrected remote')
    git(writer, 'push', 'origin', 'main')
    write(linux, LOG, 'new record')
    upload.publish(linux)
    assert git(remote, 'show', 'main:logs/records/20260101-000000_old.md') == 'corrected remote'


def test_local_edit_of_existing_record_requires_review(repos):
    _, _, linux = repos
    write(linux, 'logs/records/20260101-000000_old.md', 'changed locally')
    with pytest.raises(ValueError, match='edited locally'):
        upload.publish(linux)


def test_retry_preserves_concurrent_code_push(repos, monkeypatch):
    remote, writer, linux = repos
    write(linux, LOG, 'record')
    before = state(linux)
    original, raced = upload.git, []
    def racing(root, *args, **kwargs):
        if args[0] == 'push' and not raced:
            raced.append(True)
            commit(writer, 'code.py', 'concurrent update')
            git(writer, 'push', 'origin', 'main')
        return original(root, *args, **kwargs)
    monkeypatch.setattr(upload, 'git', racing)
    upload.publish(linux)
    assert git(remote, 'show', 'main:code.py') == 'concurrent update'
    assert git(remote, 'show', 'main:' + LOG) == 'record'
    assert state(linux) == before


def test_symlink_record_refused(repos):
    _, _, linux = repos
    path = linux / LOG
    path.symlink_to(linux / 'code.py')
    with pytest.raises(ValueError, match='nonregular'):
        upload.publish(linux)
