#!/usr/bin/env python3
"""Fast-forward main after processing stops; back up identical published logs.

Fetch origin before using this helper. Untracked logs already published by
publish_run_logs.py can block Git's fast-forward. Only byte-identical incoming
timestamped run records may be moved aside. All copies remain in ignored work/.
Never resets, rebases, cleans, pushes, removes locks or overwrites local edits.
This standalone standard-library script can be executed from `git show` stdin.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

RECORD = re.compile(r"logs/records/\d{8}-\d{6}_[^/]+\.(?:md|txt)$")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def git(root, *args, data=None, check=True):
    result = subprocess.run(["git", "-C", str(root), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or "Git command failed")
    return result


def text(root, *args):
    return git(root, *args).stdout.decode().strip()


def files(root, ref):
    result = {}
    for entry in git(root, "ls-tree", "-r", "-z", ref).stdout.split(b"\0"):
        if entry:
            meta, name = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            result[os.fsdecode(name)] = (mode, kind, oid)
    return result


def safe(root, name):
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts, "unsafe relative path")
    p = root
    for part in relative.parts:
        p = p / part
        require(not p.is_symlink(), f"symlink forbidden: {p}")
    return p


def blob(root, path):
    require(path.is_file() and not path.is_symlink(), f"not a regular record: {path}")
    return git(root, "hash-object", "--stdin", data=path.read_bytes()).stdout.decode().strip()


def plan(root):
    require(text(root, "branch", "--show-current") == "main", "checkout must be on main")
    require(git(root, "diff", "--quiet", check=False).returncode == 0
            and git(root, "diff", "--cached", "--quiet", check=False).returncode == 0,
            "tracked/staged edits exist; preserve and review them before synchronization")
    head, target = text(root, "rev-parse", "HEAD"), text(root, "rev-parse", "origin/main^{commit}")
    require(git(root, "merge-base", "--is-ancestor", head, target, check=False).returncode == 0,
            "local main has divergent commits; no reset/rebase will be attempted")
    old, new = files(root, head), files(root, target)
    collisions = {}
    for name in sorted(set(new) - set(old)):
        p = safe(root, name)
        if not os.path.lexists(p):
            continue
        require(RECORD.fullmatch(name), f"untracked incoming-path collision is not a run record: {name}")
        mode, kind, oid = new[name]
        require(mode in ("100644", "100755") and kind == "blob", f"nonregular remote record: {name}")
        require(blob(root, p) == oid, f"local record differs from origin/main: {name}; nothing will be removed")
        collisions[name] = oid
    return {"head": head, "target": target, "records": collisions}


def sync(root, *, apply=False, processing_stopped=False):
    root = Path(root).resolve()
    require(text(root, "rev-parse", "--show-toplevel") == str(root), "--project must be the repository root")
    p = plan(root)
    print(f"main: {p['head'][:12]} -> origin/main: {p['target'][:12]}")
    print(f"Identical already-published untracked records: {len(p['records'])}")
    if not apply:
        print("PREVIEW ONLY. Apply only after processing using this checkout has stopped.")
        return None
    require(processing_stopped, "--apply requires --processing-stopped; do not update live/frozen pipeline code")
    archive = None
    receipt = {"state": "preparing", "plan": p}
    if p["records"]:
        folder = safe(root, "work/checkout-sync")
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
        archive.mkdir()
        for name, oid in p["records"].items():
            source, backup = safe(root, name), safe(archive, name)
            backup.parent.mkdir(parents=True, exist_ok=True)
            require(blob(root, source) == oid, f"record changed: {name}")
            shutil.copy2(source, backup)
            backup.chmod(0o666)
            require(blob(root, backup) == oid, f"backup verification failed: {name}")
        receipt["state"] = "backed-up"
        (archive / "sync.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"Verified log backups: {archive}")
    try:
        require(plan(root) == p, "checkout/remote/records changed during backup; stopped before fast-forward")
        for name, oid in p["records"].items():
            source = safe(root, name)
            require(blob(root, source) == oid, f"record changed: {name}")
            source.unlink()
        result = git(root, "merge", "--ff-only", p["target"])
        print(result.stdout.decode().strip())
        require(text(root, "rev-parse", "HEAD") == p["target"], "unexpected HEAD after fast-forward")
        for name, oid in p["records"].items():
            require(blob(root, safe(root, name)) == oid, f"tracked record differs after fast-forward: {name}")
        receipt["state"] = "synchronized"
    except BaseException as exc:
        # Recover records only into absent paths; never overwrite anything Git/user created.
        for name in p["records"]:
            target, backup = safe(root, name), safe(archive, name)
            if not os.path.lexists(target):
                target.parent.mkdir(parents=True, exist_ok=True)
                with backup.open("rb") as reader, target.open("xb") as writer:
                    shutil.copyfileobj(reader, writer)
                shutil.copystat(backup, target)
        receipt.update(state="stopped", error=str(exc))
        raise
    finally:
        if archive:
            (archive / "sync.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("SYNCHRONIZED: published logs now tracked locally; backups retained; no processing or lock files removed.")
    status = text(root, "status", "--short")
    print(status or "Working tree clean.")
    return archive


def main():
    os.umask(0o000)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--processing-stopped", action="store_true")
    args = parser.parse_args()
    try:
        sync(args.project, apply=args.apply, processing_stopped=args.processing_stopped)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
