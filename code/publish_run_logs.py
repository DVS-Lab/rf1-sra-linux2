#!/usr/bin/env python3
"""Append run records to remote main without changing this checkout or its index."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

RECORD = re.compile(r'\d{8}-\d{6}_[^/]+\.(?:md|txt)$')


def git(root, *args, data=None, env=None, check=True):
    result = subprocess.run(['git', '-C', str(root), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace').strip() or 'Git command failed')
    return result


def text(root, *args):
    return git(root, *args).stdout.decode().strip()


def tree_records(root, ref):
    result = {}
    for entry in git(root, 'ls-tree', '-r', '-z', ref, '--', 'logs/records/').stdout.split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        result[os.fsdecode(name)] = (mode, kind, oid)
    return result


def blob_id(data, algorithm):
    return hashlib.new(algorithm, b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def snapshot(root, base, remote):
    folder = root / 'logs/records'
    if folder.resolve() != folder:
        raise ValueError('logs/records cannot contain a directory symlink')
    algorithm = text(root, 'rev-parse', '--show-object-format')
    result = {}
    for path in sorted(folder.glob('*')):
        if not RECORD.fullmatch(path.name):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Refusing nonregular run record: {path.name}')
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(f'Run record still changing: {path.name}')
        name = str(path.relative_to(root))
        oid = blob_id(data, algorithm)
        old, current = base.get(name), remote.get(name)
        if current and current[0] in ('100644', '100755') and current[1:] == ('blob', oid):
            continue
        if old and old[1:] == ('blob', oid):
            # A stale local copy must not revert a newer remote record/deletion.
            continue
        if old:
            raise ValueError(f'Existing record edited locally; append-only upload refuses: {name}')
        if current:
            raise ValueError(f'Remote record has different content; refusing overwrite: {name}')
        result[name] = (oid, data)
    return result


def unchanged(root, head, records):
    if text(root, 'rev-parse', 'HEAD') != head:
        raise ValueError('Local HEAD changed during upload; retry after local Git operations finish')
    for name, (_, data) in records.items():
        path = root / name
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError(f'Run record changed during upload: {name}')


def publish(project, dry_run=False):
    root = Path(text(project, 'rev-parse', '--show-toplevel')).resolve()
    head = text(root, 'rev-parse', 'HEAD')
    private_ref = 'refs/rf1-log-upload/' + uuid.uuid4().hex
    os.umask(0o000)

    def fetch():
        git(root, 'fetch', '--no-tags', '--no-write-fetch-head', 'origin',
            f'refs/heads/main:{private_ref}')
        return text(root, 'rev-parse', private_ref)

    try:
        tip = fetch()
        base = tree_records(root, text(root, 'merge-base', head, tip))
        records = snapshot(root, base, tree_records(root, tip))
        if not records:
            print('ALREADY PUBLISHED: no new run records to upload; checkout unchanged')
            return
        print(f'New run records: {len(records)}', flush=True)
        for name in records:
            print(name)
        if dry_run:
            print('DRY RUN: no commit or push; checkout and index unchanged')
            return
        with tempfile.TemporaryDirectory(prefix='rf1-log-upload-') as temporary:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
            for attempt in range(3):
                remote = tree_records(root, tip)
                pending = {}
                for name, (oid, data) in records.items():
                    existing = remote.get(name)
                    if existing:
                        if existing[0] in ('100644', '100755') and existing[1:] == ('blob', oid):
                            continue
                        raise ValueError(f'Remote record collision; refusing overwrite: {name}')
                    pending[name] = (oid, data)
                if not pending:
                    print('ALREADY PUBLISHED by another upload; checkout unchanged')
                    return
                unchanged(root, head, records)
                git(root, 'read-tree', tip, env=env)
                for name, (oid, data) in pending.items():
                    actual = git(root, 'hash-object', '-w', '--stdin', data=data).stdout.decode().strip()
                    if actual != oid:
                        raise ValueError('Git blob checksum mismatch')
                    git(root, 'update-index', '--add', '--cacheinfo', '100644', oid, name, env=env)
                tree = git(root, 'write-tree', env=env).stdout.decode().strip()
                message = f'Publish {len(pending)} run records from Linux2 checkout {head[:12]}\n'
                commit = git(root, 'commit-tree', tree, '-p', tip, data=message.encode()).stdout.decode().strip()
                unchanged(root, head, records)
                pushed = git(root, 'push', 'origin', f'{commit}:refs/heads/main', check=False)
                if pushed.returncode == 0:
                    print(f'PUBLISHED {len(pending)} run records to origin/main at {commit[:12]}')
                    print('Local branch, tracked code, working files and index unchanged. No pull/rebase required.')
                    return
                previous, tip = tip, fetch()
                if tip == previous:
                    raise RuntimeError(pushed.stderr.decode(errors='replace').strip())
                print(f'Remote main advanced; retrying append-only upload ({attempt + 1}/3)', flush=True)
            raise RuntimeError('Remote main kept changing; run the same command again. No local files changed.')
    finally:
        git(root, 'update-ref', '-d', private_ref, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        publish(args.project, args.dry_run)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'STOPPED: {exc}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
