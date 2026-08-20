#!/usr/bin/env python3
"""Record provenance when one reviewed WarpKit fieldmap is reused for another run."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline_utils import atomic_write_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--source-json", required=True, type=Path)
    parser.add_argument("--target-json", required=True, type=Path)
    parser.add_argument("--source-fieldmap", required=True, type=Path)
    parser.add_argument("--target-fieldmap", required=True, type=Path)
    parser.add_argument("--provenance-json", required=True, type=Path)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    for path in (args.source_json, args.source_fieldmap, args.target_fieldmap):
        if not path.is_file():
            raise FileNotFoundError(path)

    source_sha256 = sha256_file(args.source_fieldmap)
    target_sha256 = sha256_file(args.target_fieldmap)
    if source_sha256 != target_sha256:
        raise ValueError("reused fieldmap does not match its recorded source")

    source_rel = relative(args.source_fieldmap, args.project_root)
    target_rel = relative(args.target_fieldmap, args.project_root)
    reuse = {
        "SourceFieldmap": source_rel,
        "SourceRun": args.source_run,
        "TargetRun": args.run,
        "Reason": args.reason,
    }
    metadata = json.loads(args.source_json.read_text())
    metadata.pop("IntendedFor", None)
    metadata["Description"] = (
        f"WarpKit fieldmap from {args.task} run {args.source_run}, reused for "
        f"{args.task} run {args.run} after a reviewed acquisition exception."
    )
    metadata["RF1SRAFieldmapReuse"] = reuse
    atomic_write_json(args.target_json, metadata)

    provenance = {
        "CreatedUTC": datetime.now(timezone.utc).isoformat(),
        "Subject": args.subject,
        "Session": args.session,
        "Task": args.task,
        "Run": args.run,
        "SourceRun": args.source_run,
        "Reason": args.reason,
        "SourceFieldmap": source_rel,
        "TargetFieldmap": target_rel,
        "FieldmapSHA256": source_sha256,
    }
    atomic_write_json(args.provenance_json, provenance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
