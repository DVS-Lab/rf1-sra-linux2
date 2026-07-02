#!/usr/bin/env python3
"""Repair BIDS fieldmap IntendedFor metadata for RF1-SRA multi-echo BOLD."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline_utils import atomic_write_json, collect_intended_for_updates

DEFAULT_BIDS_ROOT = Path(__file__).resolve().parents[1] / "bids"


def apply_update(json_path: Path, intended_for: list[str]) -> None:
    data = json.loads(json_path.read_text())
    data["IntendedFor"] = intended_for
    data["Units"] = "Hz"
    data.pop("EchoTime1", None)
    data.pop("EchoTime2", None)
    atomic_write_json(json_path, data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bids-root",
        type=Path,
        default=DEFAULT_BIDS_ROOT,
        help="BIDS root to update. Defaults to the BIDS directory in this checkout.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without modifying JSON files.",
    )
    args = parser.parse_args()

    bids_root = args.bids_root.resolve()
    if not bids_root.is_dir():
        if args.dry_run:
            print(f"SKIP BIDS root not found: {bids_root}")
            print("Run prepdata before repairing IntendedFor metadata.")
            return 0
        raise FileNotFoundError(f"BIDS root not found: {bids_root}")

    updates = collect_intended_for_updates(bids_root)
    changed = 0
    skipped = 0
    for update in updates:
        rel = update.json_path.relative_to(bids_root)
        if update.reason:
            print(f"SKIP {rel}: {update.reason}")
            skipped += 1
            continue
        if not update.changed:
            print(f"OK   {rel}: IntendedFor already current")
            continue
        print(f"PLAN {rel}: {len(update.intended_for)} existing BOLD targets")
        for target in update.intended_for:
            print(f"     - {target}")
        if not args.dry_run:
            apply_update(update.json_path, update.intended_for)
            print(f"DONE {rel}")
        changed += 1

    mode = "would update" if args.dry_run else "updated"
    print(f"{mode} {changed} JSON file(s); skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
