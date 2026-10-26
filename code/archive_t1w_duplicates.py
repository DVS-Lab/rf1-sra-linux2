#!/usr/bin/env python3
"""Archive only the two T1w compression duplicates verified on 2026-10-26."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import uuid

from reconcile_tubric_qa import digest


EXPECTED = {
    "11982": "97860a68869432b0d804e5d87c684ee5b59a956663bb69bec20d3a047170da52",
    "12038": "1ac9496099e917726a636e2e71e0cc26e778df9e07ef450d39f5b6fcdd675e74",
}
ARCHIVE = "work/t1w-compression-duplicates-20261026"


def save_receipt(path, value):
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def paths(project, subject):
    relative = Path(f"sub-{subject}/ses-01/anat/sub-{subject}_ses-01_T1w.nii")
    return (project / "bids" / relative,
            project / "bids" / (str(relative) + ".gz"),
            project / ARCHIVE / "originals" / relative)


def regular(path, root):
    if path.is_symlink() or not path.is_file() or root.resolve() not in path.resolve().parents:
        raise ValueError(f"Expected regular file inside {root}: {path}")


def inspect(project, receipt=None, complete=False):
    records = []
    for subject, expected in EXPECTED.items():
        source, compressed, archived = paths(project, subject)
        if source.exists() and archived.exists():
            raise ValueError(f"Both source and archive exist for {subject}; refusing to overwrite")
        if complete and source.exists():
            raise ValueError(f"Uncompressed duplicate remains in BIDS: {source}")
        current = source if source.exists() else archived
        if current == archived and receipt is None:
            raise ValueError("Archive exists without a receipt; inspect before continuing")
        regular(current, project / ("bids" if current == source else ARCHIVE))
        regular(compressed, project / "bids")
        plain_content = digest(current)
        compressed_content = digest(compressed, compressed=True)
        if plain_content != compressed_content or plain_content["sha256"] != expected:
            raise ValueError(f"Content differs from reviewed identical pair: {subject}")
        compressed_file = digest(compressed)
        if receipt and compressed_file != receipt["pairs"][subject]["compressed_file"]:
            raise ValueError(f"Retained compressed file changed: {subject}")
        records.append((subject, {"source": str(source), "retained": str(compressed),
                                 "archive": str(archived), "content": plain_content,
                                 "compressed_file": compressed_file}))
    return dict(records)


def execute(project, mode):
    project = project.resolve()
    archive = project / ARCHIVE
    if archive.is_symlink() or project not in archive.resolve().parents:
        raise ValueError("Archive must be an ordinary directory inside the project")
    receipt_path = archive / "receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    if receipt and (receipt.get("schema_version") != 1 or receipt.get("project") != str(project)
                    or set(receipt.get("pairs", {})) != set(EXPECTED)):
        raise ValueError("Unexpected archive receipt")
    if mode == "check":
        if not receipt or receipt.get("status") != "complete":
            raise ValueError("No completed archive receipt")
        inspect(project, receipt, complete=True)
        print("CHECK PASSED: both duplicates archived; retained .nii.gz bytes unchanged.")
        print(f"Receipt: {receipt_path}")
        return

    records = inspect(project, receipt)
    for subject, record in records.items():
        print(f"VERIFIED {subject}: {record['content']['uncompressed_bytes']} bytes; "
              f"SHA256={record['content']['sha256']}")
        print(f"ARCHIVE {record['source']} -> {record['archive']}")
    if mode == "preview":
        print("DRY RUN: no files changed.")
        return

    archive.mkdir(parents=True, exist_ok=True)
    with (archive / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Refuse stale simultaneous launchers; the same command can resume a partial archive.
        current_receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
        if current_receipt != receipt:
            raise ValueError("Receipt changed while acquiring lock; rerun")
        records = inspect(project, receipt)
        if receipt is None:
            receipt = {"schema_version": 1, "project": str(project), "status": "prepared",
                       "created_utc": datetime.now(timezone.utc).isoformat(), "pairs": records}
            save_receipt(receipt_path, receipt)
        for subject in EXPECTED:
            source, _, destination = paths(project, subject)
            if source.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.parent.resolve() != destination.parent or destination.exists():
                    raise ValueError("Unsafe or occupied archive destination")
                # Same-filesystem rename preserves the original bytes, permissions and timestamps.
                if source.stat().st_dev != destination.parent.stat().st_dev:
                    raise ValueError("Archive is on another filesystem; refusing to copy/delete")
                source.rename(destination)
        inspect(project, receipt, complete=True)
        receipt["status"] = "complete"
        save_receipt(receipt_path, receipt)
    print("COMPLETE: two uncompressed duplicates archived outside BIDS.")
    print("No .nii.gz, JSON sidecars, derivatives, QC tables or exclusion decisions modified.")
    print("Existing QA reports remain historical snapshots; check --inputs will detect this cleanup.")
    print(f"Receipt: {receipt_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preview", "apply", "check"))
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        execute(args.project, args.mode)
        return 0
    except (OSError, ValueError, KeyError, EOFError) as exc:
        print(f"ERROR: {exc}; no automatic deletion or rollback. Preserve the archive and receipt.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
