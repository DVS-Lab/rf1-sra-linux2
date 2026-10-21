import os
import json
from pathlib import Path
import signal
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code'))
import restart_no_tedana_finish as restart


def table(private):
    def row(argv, ppid, sid=100):
        return dict(argv=argv, ppid=ppid, sid=sid, state='S', start='123', uid=os.getuid())
    return {100: row(['bash', 'code/run_logged.sh'], 1),
            101: row(['python', 'code/finish_no_tedana.py', 'run', '--private-dir', str(private)], 100),
            102: row(['film_gls'], 101),
            200: row(['tedana'], 1, 200)}


def test_isolates_session(tmp_path, monkeypatch):
    monkeypatch.setattr(restart.os, 'getsid', lambda _: 999)
    assert set(restart.session_members(table(tmp_path), 101, tmp_path)) == {100, 101, 102}


@pytest.mark.parametrize('problem', ['private', 'escape', 'owner', 'interactive', 'not_python'])
def test_refuses_unsafe_targets(tmp_path, monkeypatch, problem):
    monkeypatch.setattr(restart.os, 'getsid', lambda _: 100 if problem == 'interactive' else 999)
    rows = table(tmp_path)
    if problem == 'private':
        rows[101]['argv'][-1] += '/wrong'
    elif problem == 'escape':
        rows[102]['sid'] = 200
    elif problem == 'owner':
        rows[102]['uid'] += 1
    elif problem == 'not_python':
        rows[101]['argv'][0] = 'bash'
    with pytest.raises(ValueError):
        restart.session_members(rows, 101, tmp_path)


def test_pid_reuse_not_signaled(tmp_path, monkeypatch):
    rows = table(tmp_path)
    monkeypatch.setattr(restart, 'processes', lambda: rows)
    monkeypatch.setattr(restart.os, 'kill', lambda *args: pytest.fail('must not signal reused PID'))
    restart.send(101, dict(start='old'), signal.SIGTERM)


def test_stop_freezes_then_terminates_only_session(tmp_path, monkeypatch):
    rows = table(tmp_path)
    sent = []
    monkeypatch.setattr(restart.os, 'getsid', lambda _: 999)
    monkeypatch.setattr(restart, 'processes', lambda: {k: dict(v) for k, v in rows.items()})
    monkeypatch.setattr(restart.time, 'sleep', lambda _: None)
    def kill(pid, sig):
        sent.append((pid, sig))
        if sig == signal.SIGSTOP:
            rows[pid]['state'] = 'T'
        if sig == signal.SIGCONT:
            rows[pid]['state'] = 'Z'
    monkeypatch.setattr(restart.os, 'kill', kill)
    restart.stop(101, tmp_path)
    assert {pid for pid, _ in sent} == {100, 101, 102}
    assert [s for _, s in sent] == [signal.SIGSTOP]*3 + [signal.SIGTERM]*3 + [signal.SIGCONT]*3


def test_only_unmarked_nonreused_outputs_are_partial(tmp_path, monkeypatch):
    jobs = [dict(key=k, output=str(tmp_path / k)) for k in ('reused', 'complete', 'partial', 'absent')]
    for job in jobs[:-1]:
        Path(job['output']).mkdir()
    monkeypatch.setattr(restart.finish.l1, 'completion', lambda j: Path(j['output']) / 'success.json')
    (tmp_path / 'complete/success.json').touch()
    verified = []
    monkeypatch.setattr(restart.finish.l1, 'verified_complete', lambda j: verified.append(j['key']))
    plan = dict(jobs=jobs, reused_keys=['reused'], l2_jobs=[])
    assert restart.partial_outputs(plan) == [jobs[2]]
    assert verified == ['reused', 'complete']


def test_failed_success_verification_never_archived(tmp_path, monkeypatch):
    output = tmp_path / 'complete'
    output.mkdir()
    (output / 'success.json').touch()
    monkeypatch.setattr(restart.finish.l1, 'completion', lambda j: output / 'success.json')
    def fail(job):
        raise ValueError('changed successful output')
    monkeypatch.setattr(restart.finish.l1, 'verified_complete', fail)
    with pytest.raises(ValueError, match='changed successful'):
        restart.partial_outputs(dict(jobs=[dict(key='a', output=str(output))], reused_keys=[], l2_jobs=[]))
    assert output.exists()


@pytest.mark.parametrize('apply', [False, True])
def test_main_preserves_or_archives_partial_bytes(tmp_path, monkeypatch, apply):
    private = tmp_path / 'work/plan'
    private.mkdir(parents=True)
    variant = tmp_path / 'task/derivatives' / restart.finish.VARIANT
    output = variant / 'sub-1/partial.feat'
    output.mkdir(parents=True)
    (output / 'evidence.txt').write_text('keep these exact partial bytes')
    handoff = private / 'handoff_candidates.tsv'
    handoff.write_text('old handoff')
    job = dict(key='sub-1', root=str(tmp_path / 'task'), output=str(output))
    plan = dict(jobs=[job], reused_keys=[], l2_jobs=[])
    monkeypatch.setattr(restart, '__file__', str(tmp_path / 'code/restart_no_tedana_finish.py'))
    monkeypatch.setattr(restart.finish, 'load_plan', lambda _: plan)
    monkeypatch.setattr(restart.finish.l1, 'completion', lambda j: Path(j['output']) / 'success.json')
    monkeypatch.setattr(restart, 'processes', lambda: table(private))
    monkeypatch.setattr(restart.os, 'getsid', lambda _: 999)
    stopped = []
    monkeypatch.setattr(restart, 'stop', lambda *args: stopped.append(args))
    monkeypatch.setattr(sys, 'argv', ['restart', '--private-dir', str(private), '--pid', '101'] +
                        (['--apply'] if apply else []))
    restart.main()
    if apply:
        assert stopped == [(101, private)]
        assert not output.exists()
        saved = json.loads(next(private.glob('restart-*.json')).read_text())
        assert saved['status'] == 'complete'
        assert (Path(saved['moves'][0]['archive']) / 'evidence.txt').read_text() == 'keep these exact partial bytes'
        assert not handoff.exists()
        assert next(private.glob('handoff-before-restart-*.tsv')).read_text() == 'old handoff'
    else:
        assert not stopped
        assert (output / 'evidence.txt').is_file()
        assert handoff.is_file()
        assert not list(private.glob('restart-*.json'))
