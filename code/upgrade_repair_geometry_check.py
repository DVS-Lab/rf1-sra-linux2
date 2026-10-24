#!/usr/bin/env python3
"""Upgrade only two orchestration files in a frozen, inactive repair workspace."""
from contextlib import ExitStack
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path

import run_reviewed_source_repairs as reviewed

VERSIONS = {
    "run_reviewed_source_repairs.py": (
        "706dfe120dc8e5643fde1d0491b362c88e81b75041c4920c2c8e7c2dec884fda",
        "ae78f6b8e841e0bc8b8f20f4c5486625ba459d9c537650d5784f7268ccac85a6"),
    "complete_11935_repair.py": (
        "6432d3944af0dbd2444f4ae57d2753902229e1f55ce90fead0f431a3cdaea380",
        "e133776407da30180982d9822c51e82792f95b01eb4ff79914511f69fed7f79b"),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    reviewed.require(path.is_file() and not path.is_symlink(), f"Expected regular file: {path.name}")
    return path.read_bytes()


def replace(path, data):
    temporary = path.with_name(path.name + ".geometry-upgrade.tmp")
    with temporary.open("xb") as handle:
        handle.write(data)
    temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o666)
    os.replace(temporary, path)


def upgrade(project, destination, apply=False):
    project, destination = project.resolve(), destination.absolute()
    reviewed.require(destination.resolve() == destination and destination.is_relative_to(project / "work"),
                     "Workspace must be a real directory under production work/")
    reviewed.require(destination.is_dir(), "Repair workspace not initialized; do not recreate completed work")
    reviewed.require((destination / "code").resolve() == destination / "code",
                     "Staged code directory cannot contain a symlink")
    subject = destination.name.removeprefix("sub-").removesuffix("-project")
    reviewed.require(subject in reviewed.SPECS, "Unexpected repair subject")
    with ExitStack() as stack:
        for name in (f"{subject}.lock", ".stage.lock"):
            lock = stack.enter_context((destination.parent / name).open("a+"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        backup = destination / "geometry-check-upgrade-v1"
        reviewed.require(backup.resolve() == backup, "Upgrade backup cannot be a symlink")
        receipt_path = destination / "repair.json"
        current_bytes = regular(receipt_path)
        current = json.loads(current_bytes)
        journal = backup / "journal.json"
        if backup.exists():
            reviewed.require(journal.is_file(), "Incomplete upgrade backup; inspect before continuing")
            saved = json.loads(regular(journal))
            original_bytes = regular(backup / "repair.json")
            reviewed.require(sha(original_bytes) == saved["original_receipt_sha256"], "Upgrade backup receipt changed")
        else:
            original_bytes = current_bytes
            saved = None
        original = json.loads(original_bytes)
        reviewed.require(original["state"] == "ready" and original["subject"] == subject
                         and original["production"] == str(project), "Mismatched repair receipt")
        reviewed.require("production_code" not in original, "Unexpected previous code migration")
        reviewed.require(original["code"] == reviewed.code_hashes(project / "code", reviewed.tracked_code_paths(project / "code")),
                         "Production checkout differs from frozen receipt; do not pull/reset or bypass this check")
        reviewed.require(original["protected"] == reviewed.signatures(reviewed.protected_paths(project, subject)),
                         "Protected production inputs changed")
        payloads = {}
        for name, (old, new) in VERSIONS.items():
            reviewed.require(original["code"].get(name) == old, "Unrecognized frozen orchestration version")
            payloads[name] = regular(Path(__file__).parent / name)
            reviewed.require(sha(payloads[name]) == new, "Upgrade bundle checksum mismatch")
        actual = reviewed.code_hashes(destination / "code", original["code"])
        for name, digest in actual.items():
            permitted = VERSIONS[name] if saved and name in VERSIONS else (original["code"][name],)
            reviewed.require(digest in permitted, f"Unexpected staged code change: {name}")
        preserved_paths = [destination / "bids", destination / "derivatives", destination / "stages",
                           destination / "completion-stages", destination / "logs/geometry"]
        products = reviewed.signatures(preserved_paths)
        if saved:
            reviewed.require(saved["products"] == products, "Products changed during orchestration upgrade")
        updated = json.loads(original_bytes)
        updated["production_code"] = original["code"]
        updated["code"] = {**original["code"], **{k: v[1] for k, v in VERSIONS.items()}}
        if "completion_runner_sha256" in original:
            reviewed.require(original["completion_runner_sha256"] in VERSIONS["complete_11935_repair.py"],
                             "Unrecognized completion runner")
            updated["completion_runner_sha256"] = VERSIONS["complete_11935_repair.py"][1]
        updated["geometry_check_upgrade"] = "geometry-check-upgrade-v1/journal.json"
        reviewed.require(current in (original, updated), "Receipt changed outside this upgrade")
        if saved and current == updated and all(actual[k] == v[1] for k, v in VERSIONS.items()):
            print(f"ALREADY UPGRADED {subject}: frozen processing and completed products preserved")
            return
        print(f"UPGRADE {subject}: geometry orchestration only; no processing or production writes")
        if not apply:
            print("DRY RUN: add --apply to back up and upgrade the two frozen orchestration files")
            return
        if not saved:
            backup.mkdir()
            for name in VERSIONS:
                (backup / name).write_bytes(regular(destination / "code" / name))
            (backup / "repair.json").write_bytes(original_bytes)
            reviewed.write_json(journal, dict(original_receipt_sha256=sha(original_bytes),
                                             replacements=VERSIONS, products=products))
        for name, payload in payloads.items():
            if sha(regular(destination / "code" / name)) != VERSIONS[name][1]:
                replace(destination / "code" / name, payload)
        reviewed.write_json(receipt_path, updated)
        reviewed.require(products == reviewed.signatures(preserved_paths), "Products changed during upgrade")
        print(f"UPGRADED {subject}: original code/receipt backed up; completed outputs and stage markers unchanged")


def main():
    os.umask(0o000)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        upgrade(args.project_root, args.workspace, args.apply)
    except (OSError, ValueError) as exc:
        print(f"STOPPED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
