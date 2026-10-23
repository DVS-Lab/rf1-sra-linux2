#!/usr/bin/env python3
"""Pause exactly one logged cohort runner; retain successes and archive partials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

import benchmark_tedana_cohort as cohort
from audit_tedana import command_version
import restart_no_tedana_finish as restart


def find_runner(table, root, pid=None):
    if pid is not None:
        restart.session_members(table, pid, root, "benchmark_tedana_cohort.py", "--audit-root")
        return pid
    matches = []
    for candidate, row in table.items():
        argv = row["argv"]
        if (row["uid"] != os.getuid() or not argv or not Path(argv[0]).name.startswith("python")
                or not any(Path(a).name == "benchmark_tedana_cohort.py" for a in argv)
                or "run" not in argv or "--audit-root" not in argv):
            continue
        index = argv.index("--audit-root") + 1
        if index < len(argv) and Path(argv[index]).resolve() == root:
            matches.append(candidate)
    if len(matches) > 1:
        raise ValueError("Multiple matching cohort runners; inspect before pausing")
    return find_runner(table, root, matches[0]) if matches else None


def partial_jobs(project, root, manifest, command, version):
    partial, successes = [], 0
    for row in manifest["rows"]:
        for config in cohort.CONFIGS:
            job = cohort.job_for(project, root, command, row, config)
            path = job.output_dir
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise ValueError("Unexpected cohort output type: " + str(path))
            if (path / "cohort_success.json").exists():
                cohort.cached_success(job, version)
                successes += 1
            elif path.exists():
                partial.append(job)
    return partial, successes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--excluded-source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--tedana-command", type=Path, default=Path("/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/tedana"))
    parser.add_argument("--pid", type=int, help="Optional exact Python PID; otherwise find one matching runner")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        project, root = args.project_root.resolve(), args.audit_root.resolve()
        allowed = project / "derivatives/tedana-audit"
        if allowed not in root.parents or root.is_symlink():
            raise ValueError("Use the dedicated existing cohort audit root")
        table = restart.processes()
        pid = find_runner(table, root, args.pid)
        if pid is None:
            print("No matching Python cohort runner found; no signals or files changed. Promotion still checks all locks.")
            return 0
        manifest = cohort.load_manifest(args, project, root)
        if not args.apply:
            print(f"PREVIEW: stop only logged cohort PID {pid} and its isolated session.")
            print("Verified successes stay in place; in-flight/unreceipted attempts are archived, not reused.")
            print("No signals, files or analysis inputs changed. Add --apply to pause.")
            return 0
        restart.stop(pid, root, "benchmark_tedana_cohort.py", "--audit-root")
        version = command_version(args.tedana_command)
        if version != "26.0.3":
            raise ValueError("TEDANA 26.0.3 required")
        with cohort.exclusive(root):
            cohort.load_manifest(args, project, root)
            jobs, successes = partial_jobs(project, root, manifest, args.tedana_command.resolve(), version)
            archive = root / "failed-attempts" / ("pre-repair-pause-" + uuid.uuid4().hex)
            archive.mkdir(parents=True)
            moves = [{"source": str(j.output_dir), "destination": str(archive / j.config / j.run_key)} for j in jobs]
            cohort.write_json(archive / "pause.json", dict(state="planned", stopped_pid=pid,
                              preserved_successes=successes, moves=moves))
            for move in moves:
                destination = Path(move["destination"])
                destination.parent.mkdir(parents=True, exist_ok=True)
                Path(move["source"]).rename(destination)
            cohort.write_json(archive / "pause.json", dict(state="paused", stopped_pid=pid,
                              preserved_successes=successes, moves=moves))
            cohort.write_json(root / "validation.json", dict(validated=False, status="paused_for_11935_repair",
                              pause_receipt=str(archive / "pause.json")))
        print(f"PAUSED: preserved {successes} completed method/run outputs; archived {len(jobs)} partial attempts.")
        print("Resume the ordinary cohort runner after canonical promotion and manifest revision.")
        return 0
    except (ValueError, OSError, KeyError, IndexError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    os.umask(0)
    raise SystemExit(main())
