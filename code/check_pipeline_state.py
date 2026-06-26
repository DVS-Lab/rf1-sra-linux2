#!/usr/bin/env python3
"""Repository-local validation checks used by shell wrappers."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_utils import (
    ensure_safe_child_path,
    fmriprep_expected_outputs,
    is_fmriprep_complete,
    is_tedana_complete,
    missing_paths,
    tedana_expected_outputs,
    warpkit_required_inputs,
)


def print_missing(paths: list[Path]) -> None:
    for path in paths:
        print(f"MISSING {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    safe = subparsers.add_parser("safe-child")
    safe.add_argument("root", type=Path)
    safe.add_argument("target", type=Path)

    warpkit = subparsers.add_parser("warpkit-inputs")
    warpkit.add_argument("func_dir", type=Path)
    warpkit.add_argument("subject")
    warpkit.add_argument("session")
    warpkit.add_argument("task")
    warpkit.add_argument("run")

    fprep = subparsers.add_parser("fmriprep-complete")
    fprep.add_argument("bids_root", type=Path)
    fprep.add_argument("derivatives_root", type=Path)
    fprep.add_argument("subject")
    fprep.add_argument("--list", action="store_true")

    tedana = subparsers.add_parser("tedana-complete")
    tedana.add_argument("derivatives_root", type=Path)
    tedana.add_argument("subject")
    tedana.add_argument("session")
    tedana.add_argument("task")
    tedana.add_argument("run")
    tedana.add_argument("--list", action="store_true")

    args = parser.parse_args()
    if args.command == "safe-child":
        ensure_safe_child_path(args.root, args.target)
        print(args.target.resolve())
        return 0

    if args.command == "warpkit-inputs":
        required = warpkit_required_inputs(
            args.func_dir, args.subject, args.session, args.task, args.run
        )
        missing = missing_paths(required)
        if missing:
            print_missing(missing)
            return 1
        return 0

    if args.command == "fmriprep-complete":
        expected = fmriprep_expected_outputs(args.bids_root, args.derivatives_root, args.subject)
        if args.list:
            for path in expected:
                print(path)
        if is_fmriprep_complete(args.bids_root, args.derivatives_root, args.subject):
            return 0
        print_missing(missing_paths(expected))
        return 1

    if args.command == "tedana-complete":
        expected = tedana_expected_outputs(
            args.derivatives_root, args.subject, args.session, args.task, args.run
        )
        if args.list:
            for path in expected:
                print(path)
        if is_tedana_complete(args.derivatives_root, args.subject, args.session, args.task, args.run):
            return 0
        print_missing(missing_paths(expected))
        return 1

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
