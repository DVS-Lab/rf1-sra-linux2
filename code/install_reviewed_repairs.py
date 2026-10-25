#!/usr/bin/env python3
"""Install only the validated 10964/02 and 11935/01 functional repairs.

The completed cohort experiment is immutable. Original inputs needed by its
affected rows are copied into the transaction archive, with a lineage map.
Never restart the old experiment against the changed production input paths.
No processing, QC refresh, eligibility edits, or automatic rollback is done.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys
import uuid

import promote_11935 as common

SPECS = {"10964": ("02", {("doors", "1"), ("socialdoors", "1"), ("ugr", "1"), ("ugr", "2")}),
         "11935": ("01", {("doors", "1"), ("socialdoors", "1")})}
FAMILIES = {"bids_func", "bids_fmap", "warpkit", "fmriprep", "tedana", "confounds", "mriqc"}
require = common.require
sha = common.sha256
child = common.child


def read(path):
    return json.loads(common.safe(path).read_text())


def stamp(path):
    s = common.safe(path).stat()
    return [s.st_size, s.st_mtime_ns]


def tree(root):
    return {str(p): stamp(p) for p in common.files_under(root)}


def safe_leaf(path):
    """Permit a link only at the leaf; never traverse a symlink parent."""
    path = Path(path).absolute()
    require(".." not in path.parts, "archive entry path traversal")
    common.safe(path.parent)
    return path


def archive_entries(root):
    """Inventory retired FEAT entries without following file or directory links."""
    root = common.safe(root)
    if root.is_file():
        return [root]
    require(root.is_dir(), f"retired output missing: {root}")
    result = []
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs) + files:
            p = safe_leaf(Path(folder) / name)
            mode = p.lstat().st_mode
            if stat.S_ISLNK(mode):
                result.append(p)
                if name in dirs:
                    dirs.remove(name)
            elif stat.S_ISREG(mode):
                result.append(p)
            else:
                require(stat.S_ISDIR(mode), f"special file in retired output: {p}")
    return sorted(result)


def original_signature(path):
    path = safe_leaf(path)
    if path.is_symlink():
        return {"symlink": os.readlink(path)}
    return {"sha256": sha(path)}


def original_location(archive, relative):
    return safe_leaf(archive / common.relative(relative))


def verify_original(path, item):
    expected = {"symlink": item["symlink"]} if "symlink" in item else {"sha256": item["sha256"]}
    require(original_signature(path) == expected, f"original file/link mismatch: {path}")


def archive_original(source, destination, item):
    verify_original(source, item)
    if "symlink" in item:
        common.mkdir_durable(destination.parent)
        # symlink() refuses an existing entry, including an existing dangling link.
        os.symlink(item["symlink"], destination)
        common.sync_directory(destination.parent)
        verify_original(destination, item)
        verify_original(source, item)
    else:
        copy_shared(source, destination, item["sha256"])


def validated_stage_tree(stage):
    """Match the original validator's stat receipt, including FS surface links."""
    result = {}
    fs = stage / "derivatives/freesurfer"
    for root in (stage / "bids", stage / "derivatives"):
        common.safe(root)
        for p in sorted(root.rglob("*")):
            if p.is_file():
                if fs in p.parents:
                    s = p.stat()  # Read-only, exactly as the staged validator did.
                    result[str(p)] = [s.st_size, s.st_mtime_ns]
                else:
                    result[str(p)] = stamp(p)
    return result


def freesurfer_snapshot(project):
    """Preserve anatomy and link topology without following directory symlinks."""
    result = {}
    root = common.safe(project / "derivatives/freesurfer")
    if not root.exists():
        return result
    for folder in sorted(root.iterdir()):
        if not re.fullmatch(r"sub-(10964|11935)(?:_ses-\d+)?", folder.name):
            continue
        for p in [folder, *sorted(folder.rglob("*"))] if not folder.is_symlink() else [folder]:
            if p.is_symlink():
                s = p.lstat()
                result[str(p)] = {"link": os.readlink(p), "size": s.st_size, "mtime_ns": s.st_mtime_ns}
            elif p.is_file():
                result[str(p)] = stamp(p)
    return result


def match(name, subject, acquisition=False):
    session, runs = SPECS[subject]
    kind = "acq" if acquisition else "task"
    m = re.match(rf"sub-{subject}_ses-{session}_{kind}-([a-z]+)_run-(\d+)(?=[_.]|$)", name)
    return (m[1], m[2]) if m and (m[1], m[2]) in runs else None


def product(name, subject):
    path = common.relative(name)
    session = SPECS[subject][0]
    base = f"sub-{subject}/ses-{session}"
    parent = path.parent.as_posix()
    task, acq = match(path.name, subject), match(path.name, subject, True)
    allowed = [(f"bids/{base}/func", "bids_func", task),
               (f"bids/{base}/fmap", "bids_fmap", acq),
               (f"derivatives/warpkit/{base}", "warpkit", task),
               (f"derivatives/fmriprep/{base}/func", "fmriprep", task),
               (f"derivatives/fmriprep/{base}/fmap", "fmap", acq),
               (f"derivatives/fsl/confounds_tedana/sub-{subject}", "confounds", task)]
    for folder in (f"derivatives/fmriprep/{base}/figures", f"derivatives/fmriprep/sub-{subject}/figures"):
        allowed.append((folder, "figures", task or acq))
    for folder in (f"derivatives/tedana/{base}", f"derivatives/tedana/{base}/figures"):
        allowed.append((folder, "tedana", task))
    for folder in ("derivatives/mriqc", f"derivatives/mriqc/{base}/func", f"derivatives/mriqc/{base}/figures"):
        allowed.append((folder, "mriqc", task))
    return next(((family, run) for folder, family, run in allowed if folder == parent and run), None)


def subject_files(project, subject):
    names = set()
    for base in ("bids", "derivatives/warpkit", "derivatives/fmriprep", "derivatives/tedana",
                 "derivatives/mriqc", "derivatives/fsl/confounds_tedana"):
        names.update(p.relative_to(project).as_posix() for p in common.files_under(project / base / f"sub-{subject}"))
    for base in ("derivatives/mriqc", "derivatives/fmriprep"):
        root = project / base
        if root.exists():
            names.update(p.relative_to(project).as_posix() for p in root.glob(f"sub-{subject}*.html") if common.safe(p).is_file())
    return sorted(names)


def scans_name(subject):
    session = SPECS[subject][0]
    return f"bids/sub-{subject}/ses-{session}/sub-{subject}_ses-{session}_scans.tsv"


def merge_scans(project, stage, subject, names):
    name = scans_name(subject)
    old_cols, old = common.read_scans(project / name)
    new_cols, new = common.read_scans(stage / name)
    def affected(row):
        return row["filename"].startswith("func/") and match(Path(row["filename"]).name, subject)
    new = [r for r in new if affected(r)]
    images = {"func/" + Path(n).name for n in names if product(n, subject)[0] == "bids_func" and n.endswith((".nii", ".nii.gz"))}
    require(images and {r["filename"] for r in new} == images, f"{subject}: scans rows do not match staged images")
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=old_cols + [c for c in new_cols if c not in old_cols],
                            delimiter="\t", lineterminator="\n", restval="n/a")
    writer.writeheader()
    writer.writerows([r for r in old if not affected(r)] + new)
    return out.getvalue()


def staged_payload(project, stage, subject):
    require(read(stage / "repair.json").get("production") == str(project), "stage production root mismatch")
    if subject == "11935":
        hashes, _, _ = common.staged_files(stage, project)
        hashes = {n: h for n, h in hashes.items() if n != scans_name(subject)}
    else:
        ready = read(stage / "validated.json")
        require(ready.get("validated") is True and ready.get("subject") == subject and ready.get("session") == "02",
                "10964 final validation receipt missing or invalid")
        outputs = ready["outputs"]
        require(isinstance(outputs, dict) and outputs, "empty validation outputs")
        actual = validated_stage_tree(stage)
        require(actual == outputs, "10964 staged outputs differ from final validation")
        for name, expected in read(stage / "repair.json")["protected"].items():
            path = Path(name).absolute()
            require(".." not in path.parts, "protected path traversal")
            require(project in path.parents, "protected path escapes production")
            if project / "derivatives/freesurfer" in path.parents:
                common.safe(project / "derivatives/freesurfer")
            else:
                common.safe(path)
            require((not path.exists()) if expected is None else [path.stat().st_size, path.stat().st_mtime_ns] == expected,
                    f"10964 production input changed: {path}")
        hashes = {n: sha(stage / n) for n in subject_files(stage, subject) if product(n, subject)}
    require(set(hashes) == {n for n in subject_files(stage, subject) if product(n, subject)}, "unlisted staged products")
    for run in SPECS[subject][1]:
        require(FAMILIES <= {product(n, subject)[0] for n in hashes if product(n, subject)[1] == run},
                f"missing staged product family: {subject} {run}")
    return hashes


def downstream(root, subject, tasks):
    """Retire only affected session/task L1/L2, EV and extracted timeseries."""
    session, runs = SPECS[subject]
    items = set()
    for variant in ("fsl", "fsl-no-tedana-age55"):
        folder = root / f"derivatives/{variant}/sub-{subject}/ses-{session}"
        if folder.exists():
            for p in folder.iterdir():
                m = re.match(rf"(?:L[12]_(?:sub-{subject}_)?|ts_)task-(\w+)_ses-{session}_", p.name)
                if not m or m[1] not in tasks:
                    continue
                run = re.search(r"_run-(\d+)(?=[_.]|$)", p.name)
                if p.name.startswith("L2_") or (run and (m[1], run[1]) in runs):
                    items.add(str(common.safe(p)))
        for task in tasks:
            folder = root / f"derivatives/{variant}/EVfiles/sub-{subject}/ses-{session}/{task}"
            if folder.exists():
                for p in folder.iterdir():
                    m = re.search(r"(?:^|_)run-(\d+)(?=[_.]|$)", p.name)
                    if m and (task, m[1]) in runs:
                        items.add(str(common.safe(p)))
    return sorted(items)


def protected(project, payload):
    result = {}
    for subject in SPECS:
        for name in subject_files(project, subject):
            if name not in payload:
                result[str(project / name)] = stamp(project / name)
    # Preserve every QC table/plot and curation/hold/exclusion source, plus demographics.
    for root in (project / "qc", project / "code"):
        for p in common.files_under(root):
            if root.name == "qc" or p.suffix in (".tsv", ".csv", ".txt", ".json"):
                result[str(p)] = stamp(p)
    for name in ("bids/participants.tsv", "bids/participants.json", "bids/dataset_description.json"):
        p = project / name
        result[str(p)] = stamp(p) if p.exists() else None
    return result


def plan(project, stages, archive, socdoors, ugr, cohort):
    project, archive, socdoors, ugr, cohort = map(common.safe, (project, archive, socdoors, ugr, cohort))
    stages = {s: common.safe(p) for s, p in stages.items()}
    require(set(stages) == set(SPECS), "both exact repair stages required")
    require(not archive.exists(), "archive already exists; use check, never overwrite/retry a partial transaction")
    require(project / "work" in archive.parents and cohort not in archive.parents, "archive must be under project/work outside cohort")
    for stage in stages.values():
        require(project / "work" in stage.parents and stage not in archive.parents and archive not in stage.parents and stage != archive,
                "unsafe stage/archive overlap")
    require(socdoors.is_dir() and ugr.is_dir(), "downstream repository missing")
    require(project != socdoors and project != ugr and socdoors != ugr, "repository roots must be distinct")
    manifest, validation = read(cohort / "manifest.json"), read(cohort / "validation.json")
    require(manifest["project_root"] == str(project), "cohort production root mismatch")
    require(validation.get("validated") is True and validation.get("failures") == 0
            and validation.get("summary_rows") == validation.get("expected_jobs") == 3 * len(manifest["rows"])
            and validation.get("manifest_sha256") == sha(cohort / "manifest.json"), "completed cohort validation missing/mismatched")
    installs, originals, affected = {}, {}, []
    for subject, stage in stages.items():
        print(f"Checking validated stage and hashing {subject} payload...", flush=True)
        hashes = staged_payload(project, stage, subject)
        for n, digest in hashes.items():
            installs[n] = {"source": str(stage / n), "sha256": digest}
        n = scans_name(subject)
        content = merge_scans(project, stage, subject, hashes)
        installs[n] = {"content": content, "sha256": hashlib.sha256(content.encode()).hexdigest()}
        for n in subject_files(project, subject):
            if product(n, subject) or n == scans_name(subject):
                originals[str(project / n)] = {"archive": f"originals/project/{n}", "sha256": sha(project / n)}
    # Existing cohort inputs are immutable scientific provenance, even when not replaced.
    lineage = {}
    for row in manifest["rows"]:
        if not any(match(row["run_key"], s) for s in SPECS):
            continue
        affected.append(row["run_key"])
        for n, expected in row["inputs"].items():
            p = child(project, n)
            require(stamp(p) == [expected["size"], expected["mtime_ns"]], f"cohort input already changed: {n}")
            digest = sha(p)
            require("sha256" not in expected or expected["sha256"] == digest, f"cohort input hash mismatch: {n}")
            lineage[n] = {"archive": f"originals/project/{n}", "sha256": digest, "original_signature": expected}
            originals[str(p)] = {"archive": lineage[n]["archive"], "sha256": digest}
    retired = []
    for root, subject, tasks in ((socdoors, "11935", {"doors", "socialdoors"}),
                                 (socdoors, "10964", {"doors", "socialdoors"}), (ugr, "10964", {"ugr"})):
        retired.extend(downstream(root, subject, tasks))
    # Include historical Faces/Doors aliases covered by the established 11935 installer.
    old_files, old_dirs, rebuild, _ = common.external_outputs(socdoors, file_walker=archive_entries)
    retired.extend(str(socdoors / n) for n in rebuild)
    retire_files = set(str(p) for n in retired for p in archive_entries(n))
    retire_files.update(str(socdoors / n) for n in old_files)
    for n in retire_files:
        p = Path(n)
        root, label = (socdoors, "socdoors") if socdoors in p.parents else (ugr, "ugr")
        originals[n] = {"archive": f"originals/{label}/{p.relative_to(root)}", **original_signature(p)}
    retire_dirs = sorted({n for n in retired if Path(n).is_dir()} | {str(socdoors / n) for n in old_dirs})
    payload = set(installs) | {str(Path(n).relative_to(project)) for n in originals if project in Path(n).parents
                             and any(product(str(Path(n).relative_to(project)), s) for s in SPECS)}
    return {"schema": 1, "project": str(project), "stages": {s: str(p) for s, p in stages.items()},
            "archive": str(archive), "socdoors": str(socdoors), "ugr": str(ugr), "cohort": str(cohort),
            "installs": installs, "originals": originals,
            "remove": sorted({str(project / n) for n in payload if (project / n).exists()} | retire_files),
            "retire_dirs": retire_dirs, "downstream_requires_rebuild": sorted(set(retired)),
            "protected": protected(project, payload), "freesurfer": freesurfer_snapshot(project), "cohort_tree": tree(cohort),
            "cohort_lineage": lineage, "cohort_affected_keys": sorted(affected)}


@contextmanager
def guards(project, stages, socdoors, ugr, cohort):
    paths = [cohort / ".cohort.lock", project / ".reviewed-install.lock", project / ".11935-repair.lock"]
    paths += [project / f"logs/locks/.{s}-repair.lock" for s in SPECS]
    for root in (socdoors, ugr):
        paths += [root / f"derivatives/{v}/.runner.lock" for v in ("fsl", "fsl-no-tedana-age55")]
    # Both stage builders use a subject lock in their parent workspace.
    paths += [p.parent / f"{s}.lock" for s, p in stages.items()]
    paths += [stages["11935"].parent / ".stage.lock"]
    with ExitStack() as stack:
        for p in sorted(set(paths)):
            common.safe(p).parent.mkdir(parents=True, exist_ok=True)
            h = stack.enter_context(p.open("a+"))
            fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dirs = []
        try:
            for subject in SPECS:
                p = common.safe(project / f"logs/locks/fmriprep-sub-{subject}.lock")
                p.mkdir()  # Existing lock, even apparently stale, is never removed.
                dirs.append(p)
                (p / "pid").write_text(str(os.getpid()) + "\n")
                (p / "host").write_text(socket.gethostname() + "\n")
            yield
        finally:
            for p in reversed(dirs):
                (p / "pid").unlink(missing_ok=True)
                (p / "host").unlink(missing_ok=True)
                p.rmdir()


def check(receipt):
    require(receipt["state"] == "installed", "partial installation: preserve archive and inspect; do not retry")
    p = receipt["plan"]
    project, archive = Path(p["project"]), Path(p["archive"])
    for name, item in p["installs"].items():
        require(sha(child(project, name)) == item["sha256"], f"installed bytes differ: {name}")
    for subject in SPECS:
        actual = {n for n in subject_files(project, subject) if product(n, subject)}
        require(actual == {n for n in p["installs"] if product(n, subject)}, f"unexpected/stale product for {subject}")
    for item in p["originals"].values():
        verify_original(original_location(archive, item["archive"]), item)
    for name in p["remove"]:
        if not (project in Path(name).parents and str(Path(name).relative_to(project)) in p["installs"]):
            require(not os.path.lexists(name), f"stale product still present: {name}")
    for name, expected in p["protected"].items():
        require((not Path(name).exists()) if expected is None else stamp(name) == expected, f"protected file changed: {name}")
    require(tree(Path(p["cohort"])) == p["cohort_tree"], "completed cohort experiment changed")
    require(freesurfer_snapshot(project) == p["freesurfer"], "FreeSurfer anatomy or links changed")
    print("CHECK PASSED: both repairs installed; staged payload hashes match; originals archived.")
    print("CHECK PASSED: completed cohort experiment, baseline data, QC tables and settled decisions unchanged.")
    print(f"Retired downstream entries needing a separate rebuild: {len(p['downstream_requires_rebuild'])}")
    print("Historical cohort results retain original-input lineage; no cohort restart or processing performed.")


def install(p):
    archive, project = Path(p["archive"]), Path(p["project"])
    archive.mkdir(exist_ok=False)
    receipt = {"state": "preparing", "plan": p}
    record = archive / "installation.json"
    common.write_json(record, receipt)
    try:
        print("Copying and hash-verifying all originals and replacement files before any live changes...", flush=True)
        for name, item in p["originals"].items():
            archive_original(name, original_location(archive, item["archive"]), item)
        for filename in ("manifest.json", "validation.json"):
            source = Path(p["cohort"]) / filename
            copy_shared(source, archive / "historical-cohort" / filename, sha(source))
        common.write_json(archive / "historical-cohort/input-lineage.json", {
            "note": "Completed experiment uses PRE-REPAIR inputs. Resolve affected original paths through this map; do not resume the original runner against changed production.",
            "original_project": p["project"], "archive_root": str(archive), "inputs": p["cohort_lineage"],
            "affected_run_keys": p["cohort_affected_keys"]})
        temp = {}
        for name, item in p["installs"].items():
            target = child(project, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name("." + target.name + ".reviewed-" + uuid.uuid4().hex)
            if "source" in item:
                copy_shared(item["source"], tmp, item["sha256"])
            else:
                with tmp.open("xb") as out:
                    out.write(item["content"].encode())
                    out.flush()
                    os.fsync(out.fileno())
            tmp.chmod(0o666)
            require(sha(tmp) == item["sha256"], "replacement hash mismatch")
            temp[name] = str(tmp)
        receipt.update(state="applying", temporaries=temp)
        common.write_json(record, receipt)
        for name in p["remove"]:
            verify_original(name, p["originals"][name])
            Path(name).unlink()
            common.sync_directory(Path(name).parent)
        for name in sorted(p["retire_dirs"], key=len, reverse=True):
            if Path(name).exists():
                for directory, _, _ in os.walk(name, topdown=False):
                    common.safe(directory).rmdir()
        for name, tmp in temp.items():
            target = child(project, name)
            os.link(tmp, target)  # Atomic no-clobber installation; never overwrite a new writer.
            Path(tmp).unlink()
            common.sync_directory(target.parent)
        candidate = dict(receipt, state="installed")
        check(candidate)
        common.write_json(record, candidate)
        return candidate
    except BaseException as exc:
        receipt["error"] = str(exc)
        common.write_json(record, receipt)
        raise RuntimeError(f"Installation incomplete. Preserve {archive}; do not delete or retry. {exc}") from exc


def copy_shared(source, destination, digest):
    common.copy_verified(source, destination, digest)
    Path(destination).chmod(0o666)


def main():
    os.umask(0o000)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "install", "check"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--approve-images", action="store_true")
    args = parser.parse_args()
    project, archive = common.safe(args.project), common.safe(args.archive)
    stages = {"10964": project / "work/reviewed-source-repairs-v3/sub-10964-project",
              "11935": project / "work/11935-final-repair-v1/sub-11935-project"}
    socdoors, ugr = project.parent / "rf1-sra-socdoors", project.parent / "rf1-sra-ugr"
    cohort = project / "derivatives/tedana-audit/cohort-pca-v1"
    try:
        with guards(project, stages, socdoors, ugr, cohort):
            if args.command == "check":
                check(read(archive / "installation.json"))
            else:
                require(args.command != "install" or args.approve_images, "installation requires --approve-images")
                p = plan(project, stages, archive, socdoors, ugr, cohort)
                print(f"Validated replacement files: {len(p['installs'])}; original files to preserve: {len(p['originals'])}")
                for s in SPECS:
                    print(f"INSTALL sub-{s} ses-{SPECS[s][0]}: {len(SPECS[s][1])} functional runs only")
                if args.command == "install":
                    install(p)
                else:
                    print("PLAN ONLY: no imaging, cohort, QC or decision files changed.")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
