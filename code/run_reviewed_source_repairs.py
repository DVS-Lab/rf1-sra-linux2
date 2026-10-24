#!/usr/bin/env python3
"""Build approved 10964/11935 repairs in isolation; never promote production files."""
from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import traceback

import nibabel as nib

from convert_behavior import convert_source, resolve_sources
from reviewed_behavior_sources import wave2_source

ROOT = Path(__file__).resolve().parents[1]
SPECS = {"10964": "02", "11935": "01"}
BASELINE_10964 = Path("bids/.heudiconv/10964/ses-01/info/dicominfo_ses-01.tsv")


class RepairError(ValueError):
    """Message contains only allowlisted diagnostics suitable for the run log."""


def require(ok, message):
    if not ok:
        raise RepairError(message)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def signatures(paths):
    result = {}
    for root in paths:
        if not root.exists():
            result[str(root)] = None
            continue
        for path in ([root] if root.is_file() else sorted(root.rglob("*"))):
            if path.is_file():
                stat = path.stat()
                result[str(path)] = [stat.st_size, stat.st_mtime_ns]
    return result


def tracked_code_paths(root):
    output = subprocess.check_output(
        ["git", "-C", str(root.parent), "ls-files", "--cached", "-z", "--", root.name])
    paths = sorted({str(Path(os.fsdecode(p)).relative_to(root.name))
                    for p in output.split(b"\0") if p})
    require(bool(paths), "No Git-tracked pipeline code found")
    return paths


def code_hashes(root, paths):
    result = {}
    for name in paths:
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts,
                "Invalid path in code snapshot")
        path = root / relative
        require(path.resolve().is_relative_to(root.resolve()), "Code path escapes snapshot root")
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def copy_code_snapshot(root, destination, paths):
    destination.mkdir(parents=True, exist_ok=False)
    for name in paths:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copy_shared_file(root / name, target)


def copy_shared_file(source, destination):
    """Copy bytes, not source ACLs/modes, into a new lab-shared file."""
    with source.open("rb") as reader, destination.open("xb") as writer:
        shutil.copyfileobj(reader, writer)
    destination.chmod(0o777 if source.stat().st_mode & 0o111 else 0o666)


def copy_shared_tree(source, destination):
    """Do not inherit restrictive directory metadata or link back to originals."""
    require(not source.is_symlink(), "Refusing a directory symlink in the repair copy")
    destination.mkdir(parents=True, exist_ok=False)
    destination.chmod(0o777)
    for entry in sorted(source.iterdir()):
        if entry.name == "__pycache__":
            continue
        target = destination / entry.name
        if entry.is_dir():
            copy_shared_tree(entry, target)
        else:
            require(stat.S_ISREG(entry.stat().st_mode), "Repair copy contains a nonregular file")
            copy_shared_file(entry, target)


def protected_paths(project, subject):
    return [project / "bids" / f"sub-{subject}",
            *[project / "derivatives" / name / f"sub-{subject}" for name in
              ("fmriprep", "tedana", "warpkit", "mriqc", "freesurfer", "fsl/confounds_tedana")],
            project / "code/behavior_curation.tsv", project / "qc/run_disposition.tsv",
            *([project / BASELINE_10964] if subject == "10964" else [])]


def baseline_preflight(project, subject):
    if subject != "10964":
        return
    from participants import source_row, read_existing, age_years, sex_code
    source = project / BASELINE_10964
    require(source.is_file(), "10964 baseline HeuDiConv demographics missing; stop before conversion")
    expected, _ = source_row(source, subject)
    _, rows, _ = read_existing(project / "bids")
    current = rows.get("sub-10964")
    require(current is not None, "10964 baseline participants row missing")
    for field, normalize in (("age", age_years), ("sex", sex_code)):
        require(normalize(current[field]) == expected[field],
                f"10964 baseline {field} disagrees with canonical participants table")
    print("BASELINE PASSED 10964: HeuDiConv demographics match canonical participants row", flush=True)


def behavior_preflight(root, subject):
    session = SPECS[subject]
    for task in ("doors", "socialdoors"):
        if subject == "10964":
            wave2_source(root, task)
            baseline = resolve_sources(root, subject, "01", task, [1])[1]
            require(baseline.status == "available" and "ses-1_" in baseline.path.name,
                    "10964 baseline source is not the preserved historical source")
        source = resolve_sources(root, subject, session, task, [1])[1]
        require(source.status == "available", f"{subject} {task}: source unresolved")
        converted = convert_source(task, source.path)
        require(converted.trial_count == 40 and not converted.review_issues,
                f"{subject} {task}: behavioral validation failed")
    print(f"BEHAVIOR PASSED {subject}: complete reviewed Faces/Doors sources", flush=True)


def timing_matches(acquisitions, triggers, tolerance=5):
    """Compare relative cross-clock offsets, never assume clocks are identical."""
    grouped = {task: sorted([r for r in acquisitions if r["task"] == task],
                            key=lambda r: r["time"]) for task in ("doors", "socialdoors", "ugr")}
    matches = []
    for doors, faces, ugr in itertools.product(grouped["doors"], grouped["socialdoors"],
                                              itertools.combinations(grouped["ugr"], 2)):
        chosen = [doors, faces, *ugr]
        offsets = [(datetime.fromisoformat(t) - datetime.fromisoformat(r["time"])).total_seconds()
                   for t, r in zip(triggers, chosen)]
        if max(offsets) - min(offsets) <= tolerance and max(abs(v) for v in offsets) < 86400:
            matches.append({"series": [r["series"] for r in chosen], "offset_seconds": offsets})
    return matches


def timestamp_check(source_root, behavior, private):
    import pydicom
    scanroot = source_root / "Smith-SRA-10964-2/Smith-SRA-10964-2/scans"
    require(scanroot.is_dir(), "10964 wave-2 DICOM source directory missing")
    acquisitions = []
    for directory in sorted(scanroot.iterdir()):
        files = sorted(directory.rglob("*.dcm"))
        if not files:
            continue
        ds = pydicom.dcmread(files[0], stop_before_pixels=True, specific_tags=[
            "SeriesDescription", "SeriesNumber", "SeriesDate", "SeriesTime", "ImageType"])
        desc = str(getattr(ds, "SeriesDescription", ""))
        if "SBRef" in desc or "_Pha" in desc or "P" in getattr(ds, "ImageType", []):
            continue
        task = next((task for text, task in [("SocialDoors_doors", "doors"),
                    ("SocialDoors_face", "socialdoors"), ("UGR", "ugr")] if text in desc), None)
        if task is None:
            continue
        # This reviewed XA60 export has one DICOM per echo-volume.
        expected = 960 if task == "ugr" else 872
        if len(files) != expected:
            continue
        value = str(getattr(ds, "SeriesDate", "")) + str(getattr(ds, "SeriesTime", ""))
        fmt = "%Y%m%d%H%M%S.%f" if "." in value else "%Y%m%d%H%M%S"
        acquisitions.append({"task": task, "series": int(ds.SeriesNumber),
                             "time": datetime.strptime(value, fmt).isoformat(), "dicoms": len(files)})
    triggers, starts = [], {}
    for task, path in [
        ("doors", behavior / "Scan-Social_Doors/data/10964/sub-10964_ses-01_task-socialReward_doorsA3_desc-runtiming.jsonl"),
        ("socialdoors", behavior / "Scan-Social_Doors/data/10964/sub-10964_ses-01_task-socialReward_facesA3_desc-runtiming.jsonl"),
        ("ugr1", behavior / "Scan-Lets_Make_A_Deal/logs/10964/sub-10964_ses-02_task-ultimatum_run-01_desc-runtiming.jsonl"),
        ("ugr2", behavior / "Scan-Lets_Make_A_Deal/logs/10964/sub-10964_ses-02_task-ultimatum_run-02_desc-runtiming.jsonl")]:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        completed = [r for r in rows if r.get("RunStatus") == "completed"]
        require(len(completed) == 1, f"10964 {task}: expected one completed runtime record")
        # DICOM uses scanner local time; compare offsets to behavioral local wall time.
        trigger = datetime.fromisoformat(completed[0]["ScannerTriggerReceivedDateTime"])
        require(trigger.utcoffset() is not None, "Runtime timezone missing")
        triggers.append(trigger.replace(tzinfo=None).isoformat())
        starts[task] = [r["ScannerTriggerReceivedDateTime"] for r in rows if r.get("RunStatus") == "started"]
    matches = timing_matches(acquisitions, triggers)
    evidence = {"acquisitions": acquisitions, "completed_triggers": triggers,
                "all_starts": starts, "matches": matches, "tolerance_seconds": 5}
    write_json(private / "10964-timing-private.json", evidence)
    require(len(matches) == 1, "10964 timestamp match not unique; inspect private timing report before conversion")
    print("TIMING PASSED 10964: one four-run match with consistent cross-clock offsets", flush=True)
    print("Matched series (Doors, Faces, UGR1, UGR2): " + str(matches[0]["series"]), flush=True)
    return matches[0]


def validate_bids(project, subject, timing=None):
    session = SPECS[subject]
    func = project / f"bids/sub-{subject}/ses-{session}/func"
    expected = {("doors", 1): 218, ("socialdoors", 1): 218}
    if subject == "10964":
        expected.update({("ugr", 1): 240, ("ugr", 2): 240})
        require(timing is not None, "10964 timing evidence missing")
        numbers = dict(zip(expected, timing["series"]))
    else:
        numbers = {("doors", 1): 29, ("socialdoors", 1): 25}
    for (task, run), length in expected.items():
        stem = f"sub-{subject}_ses-{session}_task-{task}_run-{run}"
        for echo in range(1, 5):
            for part, offset in (("mag", 0), ("phase", 1)):
                path = func / f"{stem}_echo-{echo}_part-{part}_bold.nii.gz"
                image = nib.load(path)
                meta = json.loads(path.with_name(path.name[:-7] + ".json").read_text())
                require(len(image.shape) == 4 and image.shape[3] == length,
                        f"{stem} {part} echo {echo}: wrong length")
                require(int(meta["SeriesNumber"]) == numbers[(task, run)] + offset,
                        f"{stem}: source series differs from approved mapping")
        refs = list(func.glob(stem + "*_sbref.json"))
        require(bool(refs), f"{stem}: reference missing")
        for path in refs:
            require(int(json.loads(path.read_text())["SeriesNumber"]) == numbers[(task, run)] - 2,
                    f"{stem}: reference is not from its own acquisition")
    print(f"BIDS MAPPING PASSED {subject}: reviewed echoes, volumes, source series and references", flush=True)


def validate_mriqc(project, subject):
    session = SPECS[subject]
    func = project / f"bids/sub-{subject}/ses-{session}/func"
    inputs = list(func.glob("*_echo-2_part-mag_bold.nii.gz"))
    require(bool(inputs), "No target-session inputs for MRIQC check")
    for image in inputs:
        path = project / f"derivatives/mriqc/sub-{subject}/ses-{session}/func" / (image.name[:-7] + ".json")
        require(path.is_file() and isinstance(json.loads(path.read_text()), dict),
                f"MRIQC output missing or invalid for {image.name}")
    print(f"MRIQC PASSED {subject} ses-{session}: {len(inputs)} acquired runs", flush=True)


def initialize(project, destination, subject):
    require(destination.is_relative_to(project / "work"), "Repair destination must be inside ignored work")
    require(not destination.exists(), "New repair project must not already exist")
    baseline_preflight(project, subject)
    code = code_hashes(project / "code", tracked_code_paths(project / "code"))
    receipt = {"subject": subject, "production": str(project), "code": code,
               "protected": signatures(protected_paths(project, subject)), "state": "initializing"}
    destination.mkdir(parents=True)
    write_json(destination / "repair.json", receipt)
    print("Initializing isolated code copy (lab-shared permissions)", flush=True)
    copy_code_snapshot(project / "code", destination / "code", code)
    bids = destination / "bids"
    bids.mkdir()
    for name in ("dataset_description.json", "participants.tsv", "participants.json", ".bidsignore"):
        source = project / "bids" / name
        if source.is_file():
            copy_shared_file(source, bids / name)
    if subject == "10964":
        metadata = destination / BASELINE_10964
        metadata.parent.mkdir(parents=True)
        copy_shared_file(project / BASELINE_10964, metadata)
        source = project / "bids/sub-10964/ses-01/anat"
        require(source.is_dir() and bool(list(source.glob("*_T1w.nii.gz"))), "10964 baseline anatomy missing")
        print("Copying preserved baseline anatomy into isolated repair", flush=True)
        copy_shared_tree(source, bids / "sub-10964/ses-01/anat")
    fs = project / "derivatives/freesurfer" / f"sub-{subject}"
    if (fs / "scripts/recon-all.done").is_file() and (fs / "mri/aparc+aseg.mgz").is_file():
        # Independent copies, not symlinks/hardlinks: FreeSurfer may write on resume.
        print(f"Copying completed FreeSurfer anatomy for {subject}", flush=True)
        copy_shared_tree(fs, destination / "derivatives/freesurfer" / f"sub-{subject}")
        print(f"Copied completed FreeSurfer anatomy for {subject}; original unchanged", flush=True)
    (destination / "subject.txt").write_text(subject + "\n")
    receipt["state"] = "ready"
    write_json(destination / "repair.json", receipt)
    return receipt


def run(args):
    project, private = args.project_root.resolve(), args.private_dir.resolve()
    require(private.is_relative_to(project / "work"), "Private directory must be under production work/")
    require(not private.is_symlink(), "Private directory must not be a symlink")
    subject = args.subject
    require(args.exclusions_root.is_dir(), "Source-exclusion root unavailable")
    require(not (args.exclusions_root / f"Smith-SRA-{subject}").exists(), "Subject is source-excluded")
    behavior_preflight(args.behavior_root, subject)
    baseline_preflight(project, subject)
    print(f"ISOLATED REPAIR {subject}; production, exclusions, QC and paper handoff remain unchanged", flush=True)
    if args.command == "plan":
        code = code_hashes(project / "code", tracked_code_paths(project / "code"))
        print(f"CODE PASSED: {len(code)} tracked pipeline files readable; untracked logs ignored", flush=True)
        if subject == "10964":
            private.mkdir(parents=True, exist_ok=True)
            timestamp_check(args.source_root, args.behavior_root, private)
        print("Stages: timestamp linkage (10964), prepdata, mapping/events checks, WarpKit, IntendedFor, MRIQC, fMRIPrep, geometry, TEDANA, confounds.")
        print("No production promotion or task-level L1/L2 rerun is performed.")
        return
    private.mkdir(parents=True, exist_ok=True)
    with (private / f"{subject}.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        destination = private / f"sub-{subject}-project"
        require(not destination.is_symlink(), "Repair project cannot be a symlink")
        path = destination / "repair.json"
        require(args.command != "check" or path.is_file(), "No repair exists to check")
        receipt = json.loads(path.read_text()) if path.exists() else initialize(project, destination, subject)
        validation = destination / "validated.json"
        previous = json.loads(validation.read_text()) if validation.exists() else {}
        write_json(validation, {"validated": False, "status": "checking_or_building"})
        require(receipt["state"] == "ready" and receipt["subject"] == subject and receipt["production"] == str(project),
                "Interrupted or mismatched initialization; inspect preserved workspace")
        require(receipt["code"] == code_hashes(project / "code", tracked_code_paths(project / "code"))
                == code_hashes(destination / "code", receipt["code"]),
                "Repair code changed; use a new isolated workspace")
        require(receipt["protected"] == signatures(protected_paths(project, subject)), "Production inputs changed since repair initialization")
        if subject == "10964":
            require(hashlib.sha256((destination / BASELINE_10964).read_bytes()).digest()
                    == hashlib.sha256((project / BASELINE_10964).read_bytes()).digest(),
                    "Isolated baseline demographics changed; do not regenerate baseline age from wave 2")
        if previous.get("validated"):
            require(previous["outputs"] == signatures([destination / "bids", destination / "derivatives"]),
                    "Previously validated repaired products changed; inspect without overwriting")
        timing = timestamp_check(args.source_root, args.behavior_root, private) if subject == "10964" else None
        env = {**os.environ, "BEHAVIOR_ROOT": str(args.behavior_root.resolve()),
               "SOURCEDATA_ROOT": str(args.source_root.resolve()),
               "SOURCEDATA_EXCLUSIONS_ROOT": str(args.exclusions_root.resolve()),
               "SCRATCH_ROOT": str(destination / "scratch"),
               "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
               "PYTHONUNBUFFERED": "1", "FMRIPREP_NPROCS": str(args.jobs),
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "NUMEXPR_NUM_THREADS": "1", "FSLSUB_PARALLEL": "1",
               "FMRIPREP_MEM_MB": "32000", "FMRIPREP_OMP_NTHREADS": "2",
               "MRIQC_NPROCS": "4", "MRIQC_OMP_NTHREADS": "2", "MRIQC_MEM_GB": "16"}
        py = sys.executable
        sublist = str(destination / "subject.txt")
        session = SPECS[subject]
        def execute(command):
            for name in ("code", "bids", "derivatives", "scratch"):
                require(not (destination / name).is_symlink(), "Repair storage root cannot be a symlink")
            print("COMMAND: " + " ".join(map(str, command)), flush=True)
            subprocess.run(list(map(str, command)), cwd=destination, env=env, check=True, pass_fds=(lock.fileno(),))
        def checked_step(name, command, check):
            marker = destination / "stages" / f"{name}.json"
            if args.command == "build" and not marker.exists():
                execute(command)
                check() if callable(check) else execute(check)
                write_json(marker, {"passed": True})
            else:
                check() if callable(check) else execute(check)
        target = destination / f"bids/sub-{subject}/ses-{session}"
        if args.command == "build" and not target.exists():
            execute(["bash", "code/prepdata.sh", subject, session])
        validate_bids(destination, subject, timing)
        execute([py, "code/check_events.py", "--subject", subject, "--session", session,
                 "--behavior-root", args.behavior_root, "--quiet-ok"])
        checked_step("warpkit", ["bash", "code/run_warpkit.sh", "--sublist", sublist, "--jobs", "2"],
                     ["bash", "code/check_warpkit.sh", "--sublist", sublist])
        if args.command == "build":
            execute([py, "code/addIntendedFor.py", "--sublist", sublist])
        checked_step("mriqc", ["bash", "code/mriqc.sh", subject, session],
                     lambda: validate_mriqc(destination, subject))
        checked_step("fmriprep", ["bash", "code/fmriprep.sh", subject],
                     ["bash", "code/check_fmriprep.sh", "--sublist", sublist])
        geometry = destination / "logs/geometry/repaired"
        execute([py, "code/fmriprep_geometry.py", "audit", "--report-prefix", geometry])
        execute([py, "code/fmriprep_geometry.py", "verify", "--audit-json", str(geometry) + ".json"])
        checked_step("tedana", ["bash", "code/run_tedana.sh", "--sublist", sublist, "--session", session, "--jobs", "1"],
                     ["bash", "code/check_tedana.sh", "--sublist", sublist, "--session", session])
        if args.command == "build":
            execute([py, "code/genTedanaConfounds.py", "--sublist", sublist, "--session", session, "--preserve-existing"])
        execute([py, "code/genTedanaConfounds.py", "--sublist", sublist, "--session", session, "--check"])
        require(receipt["protected"] == signatures(protected_paths(project, subject)), "Production files changed during repair; do not promote")
        write_json(destination / "validated.json", {"validated": True, "production_modified": False,
                   "subject": subject, "session": session, "l1_l2_rebuilt": False,
                   "outputs": signatures([destination / "bids", destination / "derivatives"])})
        print(f"CHECK PASSED: isolated {subject} repair complete through confounds; production promotion and downstream rebuild remain separate.", flush=True)


def main():
    # Lab policy applies to this process and all pipeline children, not originals.
    os.umask(0o000)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "build", "check"))
    parser.add_argument("--subject", choices=tuple(SPECS), required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--behavior-root", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra/stimuli"))
    parser.add_argument("--source-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"))
    parser.add_argument("--exclusions-root", type=Path, default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    require(1 <= args.jobs <= 16, "Use 1-16 fMRIPrep CPUs for this isolated repair")
    try:
        run(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, RepairError):
            print(f"ERROR: {exc}", file=sys.stderr)
        else:
            private = args.private_dir.resolve()
            if private.is_relative_to(args.project_root.resolve() / "work"):
                private.mkdir(parents=True, exist_ok=True)
                (private / f"{args.subject}-error-private.txt").write_text(traceback.format_exc())
            print(f"ERROR: {type(exc).__name__}; inspect private repair error record", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
