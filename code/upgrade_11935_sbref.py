#!/usr/bin/env python3
"""Back up the isolated SBRef failure and enable Social Doors-only recovery."""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path

import run_reviewed_source_repairs as reviewed
from run_11935_initialization import sha as file_sha
from upgrade_repair_geometry_check import regular, replace, sha, FS_RUNNER_SHA

RUNNER_SHA = "e0d5e1da2032edae4ebcdb1053dd3ab3e1cfb5331ae3cef61a20d9d6be6442e9"
NAME = "complete_11935_repair.py"


def file_hashes(root):
    result = {}
    for path in sorted(root.rglob("*")):
        reviewed.require(not path.is_symlink(), "Backup source contains a symlink")
        if path.is_file():
            result[str(path.relative_to(root))] = file_sha(path)
    return result


def preserved_files(destination):
    files = {}
    for relative in ("bids", "anatomy", "derivatives/freesurfer", "derivatives/warpkit",
                     "derivatives/mriqc"):
        for name, digest in file_hashes(destination / relative).items():
            files[f"{relative}/{name}"] = digest
    root = destination / "derivatives/fmriprep"
    for path in root.rglob("*"):
        # The final runner adds repair provenance to JSONs, but must never
        # modify completed Doors images/transforms or precomputed anatomy.
        if path.is_file() and path.suffix != ".json" and (
                "task-doors_" in path.name or "acq-doors_" in path.name or "anat" in path.parts):
            files[str(path.relative_to(destination))] = file_sha(path)
    return files


def upgrade(project, destination, apply=False):
    project, destination = project.resolve(), destination.absolute()
    reviewed.require(destination.resolve() == destination and destination.is_relative_to(project / "work")
                     and destination.name == "sub-11935-project", "Expected real isolated 11935 workspace")
    reviewed.require((destination / "code").resolve() == destination / "code", "Code directory cannot be a symlink")
    payload = regular(Path(__file__).parent / NAME)
    reviewed.require(sha(payload) == RUNNER_SHA, "SBRef upgrade bundle mismatch")
    with ExitStack() as stack:
        for name in ("11935.lock", ".stage.lock"):
            lock = stack.enter_context((destination.parent / name).open("a+"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt_path = destination / "repair.json"
        current_bytes = regular(receipt_path)
        current = json.loads(current_bytes)
        backup = destination / "sbref-task-recovery-v1"
        reviewed.require(backup.resolve() == backup, "Backup cannot be a symlink")
        original_bytes = regular(backup / "repair.json") if backup.exists() else current_bytes
        original = json.loads(original_bytes)
        reviewed.require(original.get("subject") == "11935" and original.get("state") == "ready"
                         and original.get("production") == str(project), "Invalid original receipt")
        reviewed.require(original["code"].get(NAME) == original.get("completion_runner_sha256") == FS_RUNNER_SHA,
                         "Unrecognized old runner; do not bypass frozen-code checks")
        reviewed.require(original["protected"] == reviewed.signatures(reviewed.protected_paths(project, "11935")),
                         "Protected production inputs changed")
        actual = reviewed.code_hashes(destination / "code", original["code"])
        for name, digest in actual.items():
            allowed = (FS_RUNNER_SHA, RUNNER_SHA) if name == NAME and backup.exists() else (original["code"][name],)
            reviewed.require(digest in allowed, f"Unexpected frozen code change: {name}")
        if current.get("sbref_task_recovery"):
            reviewed.require(current["completion_runner_sha256"] == actual[NAME] == RUNNER_SHA,
                             "Incomplete code migration")
            saved = json.loads(regular(backup / "manifest.json"))
            reviewed.require(file_hashes(backup / "fmriprep") == saved["files"], "Backup changed")
            expected = json.loads(original_bytes)
            expected["code"][NAME] = expected["completion_runner_sha256"] = RUNNER_SHA
            expected["sbref_task_recovery"] = saved["recovery"]
            reviewed.require(current == expected, "Receipt changed outside SBRef upgrade")
            print("ALREADY UPGRADED: resume only pending SBRef recovery stages")
            return
        reviewed.require(current == original, "Receipt changed outside SBRef upgrade")
        reviewed.require(not (destination / "11935-ready.json").exists(), "Validated repair exists; inspect before upgrading")
        reviewed.require((destination / "completion-stages/fmriprep.json").is_file(), "Original fMRIPrep must be complete")
        reviewed.require(not (destination / "completion-stages/tedana.json").exists()
                         and not any((destination / "derivatives/tedana").rglob("*metrics.tsv")),
                         "TEDANA products already exist; inspect lineage before recovery")
        func = destination / "derivatives/fmriprep/sub-11935/ses-01/func"
        for task in ("doors", "socialdoors"):
            path = func / f"sub-11935_ses-01_task-{task}_run-1_part-mag_desc-coreg_boldref.json"
            sources = json.loads(regular(path))["Sources"]
            expected = "bids:raw:sub-11935/ses-01/func/sub-11935_ses-01_task-doors_run-1_echo-1_sbref.nii.gz"
            reviewed.require([s for s in sources if s.startswith("bids:raw:")] == [expected]
                             and any(f"acq-{task}_run-1_" in s and "desc-coeff_fieldmap" in s for s in sources),
                             "Source-reference pattern differs from reviewed failure")
        print("CONFIRMED: both references used Doors SBRef; fieldmaps remain task-matched")
        print("PLAN: preserve original derivatives/cache; resume Social Doors functional processing only")
        print("No conversion, anatomy, FreeSurfer, WarpKit, MRIQC, production or cohort TEDANA rerun")
        if not apply:
            print("DRY RUN: no changes; --apply backs up and enables targeted recovery")
            return
        source = destination / "derivatives/fmriprep"
        print("Hashing completed products and preparing verified backup; no processing rerun", flush=True)
        before = file_hashes(source)
        kept = preserved_files(destination)
        if not backup.exists():
            backup.mkdir()
            (backup / "repair.json").write_bytes(original_bytes)
            (backup / NAME).write_bytes(regular(destination / "code" / NAME))
        for name, digest in before.items():
            target = backup / "fmriprep" / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                reviewed.copy_shared_file(source / name, target)
            reviewed.require(file_sha(target) == digest, "Backup differs; stop without overwriting")
        reviewed.require(file_hashes(source) == file_hashes(backup / "fmriprep") == before,
                         "Functional products changed during backup")
        recovery = dict(task="socialdoors", backup="sbref-task-recovery-v1/manifest.json", preserved_files=kept)
        reviewed.write_json(backup / "manifest.json", dict(files=before, recovery=recovery))
        updated = json.loads(original_bytes)
        updated["code"][NAME] = updated["completion_runner_sha256"] = RUNNER_SHA
        updated["sbref_task_recovery"] = recovery
        replace(destination / "code" / NAME, payload)
        reviewed.write_json(receipt_path, updated)
        print("UPGRADED: original outputs backed up; no processing started; old stage receipts retained")


def main():
    os.umask(0)
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
