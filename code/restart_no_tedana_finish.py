#!/usr/bin/env python3
"""Stop one isolated follow-up runner and archive only unverified partial outputs."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import signal
import time

import finish_no_tedana as finish


def processes():
    result = {}
    for folder in Path('/proc').glob('[0-9]*'):
        try:
            fields = (folder / 'stat').read_text().rsplit(')', 1)[1].split()
            result[int(folder.name)] = dict(
                state=fields[0], ppid=int(fields[1]), sid=int(fields[3]),
                start=fields[19], uid=folder.stat().st_uid,
                argv=(folder / 'cmdline').read_bytes().decode().rstrip('\0').split('\0'))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    return result


def session_members(table, pid, private):
    row = table[pid]
    argv = row['argv']
    if (row['uid'] != os.getuid() or not Path(argv[0]).name.startswith('python')
            or not any(Path(a).name == 'finish_no_tedana.py' for a in argv)
            or 'run' not in argv or '--private-dir' not in argv
            or Path(argv[argv.index('--private-dir') + 1]).resolve() != private):
        raise ValueError('PID is not the requested Python follow-up runner')
    sid = row['sid']
    leader = table.get(sid, {})
    if sid == os.getsid(0) or not any('run_logged.sh' in a for a in leader.get('argv', [])):
        raise ValueError('Runner is not in a separate run_logged session; refusing signals')
    members = {p: r for p, r in table.items() if r['sid'] == sid and r['state'] != 'Z'}
    if any(r['uid'] != os.getuid() for r in members.values()):
        raise ValueError('Session contains another user')
    descendants = {pid}
    while True:
        expanded = descendants | {p for p, r in table.items() if r['ppid'] in descendants}
        if expanded == descendants:
            break
        descendants = expanded
    if any(table[p]['sid'] != sid for p in descendants):
        raise ValueError('FEAT child escaped the session; inspect before stopping')
    return members


def send(pid, row, sig):
    current = processes().get(pid)
    if current and current['start'] == row['start']:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass


def stop(pid, private):
    original = processes()[pid]
    frozen = {}
    try:
        for _ in range(10):
            table = processes()
            if table.get(pid, {}).get('start') != original['start']:
                raise ValueError('Runner exited or PID changed; no restart performed')
            members = session_members(table, pid, private)
            for p, row in members.items():
                send(p, row, signal.SIGSTOP)
                frozen[p] = row
            time.sleep(0.1)
            after = session_members(processes(), pid, private)
            if all(r['state'] in {'T', 't'} for r in after.values()) and set(after) <= set(frozen):
                break
        else:
            raise ValueError('Could not quiesce the session; no termination performed')
        for p, row in frozen.items():
            send(p, row, signal.SIGTERM)
    finally:
        for p, row in frozen.items():
            send(p, row, signal.SIGCONT)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        live = [p for p, r in processes().items() if r['sid'] == original['sid'] and r['state'] != 'Z']
        if not live:
            return
        time.sleep(1)
    raise ValueError('Some session processes remain; no outputs archived. Inspect before retrying')


def partial_outputs(plan):
    jobs = {j['key']: j for j in plan['jobs']}
    partial = []
    for stage, selected in [('l1', plan['jobs']), ('l2', plan['l2_jobs'])]:
        for job in selected:
            output = Path(job['output'])
            reused = job['key'] in plan['reused_keys']
            marker = (finish.l1.completion(job) if stage == 'l1'
                      else output / 'no_tedana_l2_success.json')
            if reused or marker.exists():
                # A recorded success that fails verification is NOT disposable partial work.
                if stage == 'l1':
                    finish.l1.verified_complete(job)
                else:
                    finish.verified_l2(job, jobs)
            elif output.exists():
                if output.is_symlink() or not output.is_dir():
                    raise ValueError('Unexpected partial output type: ' + str(output))
                partial.append(job)
    return partial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', required=True, type=Path)
    parser.add_argument('--pid', required=True, type=int)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    private = args.private_dir.resolve()
    root = Path(__file__).resolve().parents[1]
    if root / 'work' not in private.parents:
        parser.error('private-dir must be under this repository work/')
    plan = finish.load_plan(private)
    members = session_members(processes(), args.pid, private)
    print(f'Isolated runner PID {args.pid}; {len(members)} session processes.', flush=True)
    if not args.apply:
        print('PREVIEW: no signals or changes. Apply stops this session, verifies successes, and archives partials.')
        return
    stop(args.pid, private)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    with ExitStack() as stack:
        for task_root in sorted({j['root'] for j in plan['jobs']}):
            handle = stack.enter_context((Path(task_root) / 'derivatives' / finish.VARIANT / '.runner.lock').open('a'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = finish.load_plan(private)
        partial = partial_outputs(plan)
        moves = []
        for job in partial:
            output = Path(job['output'])
            target = Path(job['root']) / 'derivatives' / finish.VARIANT / 'restart-archives' / stamp / job['key'] / output.name
            moves.append(dict(source=str(output), archive=str(target)))
        record = private / f'restart-{stamp}.json'
        finish.l1.write_json(record, dict(status='planned', moves=moves, stopped_pid=args.pid))
        for move in moves:
            target = Path(move['archive'])
            target.parent.mkdir(parents=True, exist_ok=True)
            Path(move['source']).rename(target)
        handoff = private / 'handoff_candidates.tsv'
        if moves and handoff.exists():
            handoff.rename(private / f'handoff-before-restart-{stamp}.tsv')
        finish.l1.write_json(record, dict(status='complete', moves=moves, stopped_pid=args.pid))
    print(f'RESTART READY: {len(moves)} partial directories archived; verified successes preserved.')
    print('Resume the SAME private plan with finish_no_tedana.py run --jobs 20.')


if __name__ == '__main__':
    main()
