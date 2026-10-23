#!/usr/bin/env python3
"""Narrow, fail-closed promotion of reviewed 11935 ses-01 run-1 repairs.

API (all returned values are JSON serializable):
  plan(project, staged_project, archive_root, socdoors_root, cohort_root=None)
  apply_plan(plan, lock_fds=()) -> installed promotion receipt
  check(plan_or_receipt_or_receipt_path, allow_rebuilt=True) -> read-only summary
  production_guard(plan, lock_fds=()) -> context yielding held descriptor tuple

archive_root is a NEW transaction directory, not a shared archive container.
Stage must contain 11935-ready.json: validated=true, subject="11935",
session="01", tasks=["doors", "socialdoors"], files={project-relative: sha256}.
Only the two run-1 prefixes in the seven documented product families are accepted.
Every payload file must be listed except the ready receipt and optional session
scans TSV (which may also be listed). Non-payload workspace scaffolding is never
installed. Each family/task must be represented; the
ready receipt attests image/scientific validation, not this byte-level checker.
Whole-subject HTML, anatomy, FS, other runs and unrelated metadata are forbidden.

scans.tsv is synthesized from production plus staged affected rows; production
unrelated rows/columns are retained. New affected image rows must be provided.
No cohort manifest rewriting or scientific processing is performed. The frozen
manifest is archive-COPIED and its validation invalidated for the revise helper.
Receipt contract: state, plan, changed_keys (old UNION new run keys), staged_hashes,
source_original_inputs[project-relative]={archive_path, sha256}, cohort_manifest
{source, archive_path, sha256}, installs, moves, and requires_rebuild. Paths in
archive_path are absolute. Inputs outside the closure are COPIED, never removed.
Prepared/applying receipts must be recovered manually, never retried/overwritten.
Locks coordinate cooperating runners; stop other readers/writers before promotion.

CLI (all paths absolute; NEW_ARCHIVE must not exist):
  python3 code/promote_11935.py plan --project-root PROJECT \
      --staged-project PROJECT/work/REPAIR/sub11935-project \
      --archive-root NEW_ARCHIVE --socdoors-root SOCDOORS --cohort-root COHORT
  python3 code/promote_11935.py promote [same path flags] --approve-images
  python3 code/promote_11935.py check --archive-root NEW_ARCHIVE
The API apply_plan caller is responsible for human image approval; CLI enforces
the explicit flag. check allows downstream rebuilds; apply's initial stale gate
does not. source_original_inputs and cohort_manifest remain usable independently
of later cohort revision. No command launches models or changes eligibility/QC.
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import sys
from contextlib import contextmanager, ExitStack
import uuid


TASKS = ("doors", "socialdoors")
BASE = "sub-11935_ses-01_"
SESSION = "sub-11935/ses-01"
SCANS = f"bids/{SESSION}/{BASE}scans.tsv"
READY = "11935-ready.json"
KEY_RE = re.compile(r"sub-11935_ses-01_task-(doors|socialdoors)_run-1(?=[_.]|$)")
ACQ_RE = re.compile(r"sub-11935_ses-01_acq-(doors|socialdoors)_run-1(?=[_.]|$)")
RECOVERY = ("Manual recovery required: stop writers; preserve promotion.json, all "
            "archives and sibling temporaries; compare plan/hashes with live paths; "
            "restore or finish under review. Do not delete the receipt or retry promotion.")
_ACTIVE = {}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe(path):
    """Check every existing component without resolving away symlink evidence."""
    path = Path(path).absolute()
    require(".." not in path.parts, f"path traversal: {path}")
    for part in (*reversed(path.parents), path):
        require(not part.is_symlink(), f"symlink forbidden: {part}")
    return path


def relative(name):
    require(isinstance(name, str) and name and "\\" not in name, "invalid relative path")
    path = Path(name)
    require(not path.is_absolute() and path.as_posix() == name
            and not any(p in (".", "..") for p in path.parts), f"path escape: {name}")
    return path


def child(root, name):
    return safe(Path(root) / relative(name))


def sha256(path):
    path = safe(path)
    require(path.is_file(), f"missing regular file: {path}")
    require(stat.S_ISREG(path.stat().st_mode), f"not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files_under(root):
    root = safe(root)
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    require(root.is_dir(), f"not a directory: {root}")
    result = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            item = safe(Path(directory) / name)
            require(item.is_dir() or item.is_file(), f"special file forbidden: {item}")
        result.extend(Path(directory) / name for name in files)
    return sorted(result)


def product(name):
    """Return (family, task), using exact directories and entity boundaries."""
    path = relative(name)
    parent, filename = path.parent.as_posix(), path.name
    task = KEY_RE.match(filename)
    acq = ACQ_RE.match(filename)
    if parent == f"bids/{SESSION}/func" and task:
        return "bids_func", task[1]
    if parent == f"bids/{SESSION}/fmap" and acq:
        return "bids_fmap", acq[1]
    if parent == f"derivatives/warpkit/{SESSION}" and task:
        return "warpkit", task[1]
    if parent == f"derivatives/fmriprep/{SESSION}/func" and task:
        return "fmriprep", task[1]
    if parent == f"derivatives/fmriprep/{SESSION}/fmap" and acq:
        return "fmriprep_fmap", acq[1]
    if parent in (f"derivatives/fmriprep/{SESSION}/figures",
                  "derivatives/fmriprep/sub-11935/figures") and (task or acq):
        return "figures", (task or acq)[1]
    if parent in (f"derivatives/tedana/{SESSION}", f"derivatives/tedana/{SESSION}/figures") and task:
        return "tedana", task[1]
    if parent == "derivatives/fsl/confounds_tedana/sub-11935" and task:
        return "fsl_confounds", task[1]
    if parent in (f"derivatives/mriqc/{SESSION}/func", f"derivatives/mriqc/{SESSION}/figures", "derivatives/mriqc") and task:
        return "mriqc", task[1]
    return None


def canonical_files(project):
    roots = [f"bids/{SESSION}/func", f"bids/{SESSION}/fmap",
             f"derivatives/warpkit/{SESSION}", f"derivatives/fmriprep/{SESSION}/func",
             f"derivatives/fmriprep/{SESSION}/figures",
             f"derivatives/fmriprep/{SESSION}/fmap",
             "derivatives/fmriprep/sub-11935/figures", f"derivatives/tedana/{SESSION}",
             "derivatives/fsl/confounds_tedana/sub-11935",
             f"derivatives/mriqc/{SESSION}"]
    found = set()
    for name in roots:
        root = child(project, name)
        if not root.exists():
            continue
        # Inspect only matching branches, never descend through another run/tree.
        for path in root.iterdir():
            rel = path.relative_to(project).as_posix()
            if product(rel):
                require(not safe(path).is_dir(), f"expected flat product: {path}")
                found.add(rel)
            elif path.name == "figures" and name in (f"derivatives/tedana/{SESSION}", f"derivatives/mriqc/{SESSION}"):
                for item in safe(path).iterdir():
                    if product(item.relative_to(project).as_posix()):
                        require(safe(item).is_file(), f"expected flat figure: {item}")
                        found.add(item.relative_to(project).as_posix())
            elif path.name == "func" and name == f"derivatives/mriqc/{SESSION}":
                for item in safe(path).iterdir():
                    if product(item.relative_to(project).as_posix()):
                        found.add(item.relative_to(project).as_posix())
    mriqc = child(project, "derivatives/mriqc")
    if mriqc.exists():
        for path in mriqc.iterdir():
            if product(path.relative_to(project).as_posix()):
                found.add(path.relative_to(project).as_posix())
    return sorted(found)


def staged_files(staged, project):
    receipt = child(staged, READY)
    require(receipt.is_file(), f"missing required ready receipt: {receipt}")
    ready = json.loads(receipt.read_text())
    require(ready.get("validated") is True and ready.get("subject") == "11935"
            and ready.get("session") == "01" and isinstance(ready.get("tasks"), list)
            and sorted(ready["tasks"]) == list(TASKS), "invalid ready receipt identity/validation/tasks")
    hashes = ready.get("files")
    require(isinstance(hashes, dict) and hashes, "ready files must be a nonempty hash map")
    for name, digest in hashes.items():
        relative(name)
        require(product(name) or name == SCANS, f"extra/unapproved staged path: {name}")
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
                f"invalid sha256: {name}")
        require(sha256(child(staged, name)) == digest, f"staged hash mismatch: {name}")
    builder = child(staged, "repair.json")
    if builder.exists():
        metadata = json.loads(builder.read_text())
        require(metadata.get("production") == str(project) and metadata.get("state") == "ready",
                "invalid builder workspace receipt")
    require(not set(canonical_files(staged)) - set(hashes), "unlisted extra stage products")
    protected = ready.get("inputs", {})
    require(isinstance(protected, dict), "invalid ready protected inputs")
    for name, expected in protected.items():
        path = safe(name)
        require(project in path.parents, "protected input escapes project")
        if expected is None:
            require(not path.exists(), f"protected input appeared: {path}")
        else:
            require(isinstance(expected, list) and len(expected) == 2, "invalid protected signature")
            info = path.stat()
            require([info.st_size, info.st_mtime_ns] == expected, f"protected input changed: {path}")
    families = {"bids_func", "bids_fmap", "warpkit", "fmriprep", "tedana", "fsl_confounds", "mriqc"}
    for task in TASKS:
        require(families <= {kind[0] for name in hashes
                            if (kind := product(name)) and kind[1] == task},
                f"missing staged product families for {task}")
    return hashes, sha256(receipt), protected


def read_scans(path):
    if not safe(path).exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        columns = reader.fieldnames
        require(columns and "filename" in columns and len(set(columns)) == len(columns),
                f"invalid scans columns: {path}")
        rows = list(reader)
    seen = set()
    for row in rows:
        require(None not in row and None not in row.values(), f"ragged scans row: {path}")
        relative(row["filename"])
        require(row["filename"] not in seen, f"duplicate scans row: {path}")
        seen.add(row["filename"])
    return columns, rows


def affected_scan(row):
    return row["filename"].startswith("func/") and bool(KEY_RE.match(row["filename"][5:]))


def merge_scans(project, staged, hashes):
    old, new = child(project, SCANS), child(staged, SCANS)
    if not old.exists() and not new.exists():
        return None
    columns, rows = read_scans(old)
    added_columns, additions = read_scans(new)
    additions = [row for row in additions if affected_scan(row)]
    require(additions, "staged scans.tsv needs replacement rows for affected images")
    expected = {Path(name).relative_to(f"bids/{SESSION}").as_posix()
                for name in hashes if product(name) and product(name)[0] == "bids_func"
                and name.endswith((".nii", ".nii.gz"))}
    require({row["filename"] for row in additions} == expected,
            "staged affected scans rows differ from staged images")
    columns += [column for column in added_columns if column not in columns]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, delimiter="\t", lineterminator="\n",
                            restval="n/a")
    writer.writeheader()
    writer.writerows([row for row in rows if not affected_scan(row)] + additions)
    return {"content": output.getvalue(), "old_sha256": sha256(old) if old.exists() else None,
            "staged_sha256": sha256(new)}


def external_outputs(root):
    files, directories, rebuild, l3 = set(), set(), set(), []
    for variant in ("fsl", "fsl-no-tedana-age55"):
        base = child(root, f"derivatives/{variant}")
        subject = base / SESSION
        if safe(subject).exists():
            for path in subject.iterdir():
                # Entity boundaries prevent run-10/task-doorsExtra/session-02 matches.
                l1 = re.match(r"L1_(?:sub-11935_)?task-(?:socialdoors|doors|Faces|Doors)_ses-01_", path.name)
                l2 = re.match(r"L2_(?:sub-11935_)?task-socialdoors_ses-01_", path.name)
                ts = re.match(r"ts_task-(?:socialdoors|doors|Faces|Doors)_ses-01_", path.name)
                if not (l1 or l2 or ts):
                    continue
                if (l1 or ts) and not re.search(r"_run-1(?=[_.]|$)", path.name):
                    continue
                rel = path.relative_to(root).as_posix()
                rebuild.add(rel)
                if safe(path).is_dir():
                    directories.add(rel)
                files.update(p.relative_to(root).as_posix() for p in files_under(path))
        ev_session = child(root, f"derivatives/{variant}/EVfiles/{SESSION}")
        if ev_session.exists():
            for folder in ev_session.iterdir():
                if folder.name not in ("doors", "socialdoors", "Doors", "Faces"):
                    continue
                safe(folder)
                # Task folders contain run-specific EV subdirectories; preserve other runs.
                for item in folder.iterdir():
                    if item.name == "run-1" or re.search(r"(?:^|_)run-1(?=[_.]|$)", item.name):
                        rel = item.relative_to(root).as_posix()
                        rebuild.add(rel)
                        if safe(item).is_dir():
                            directories.add(rel)
                        files.update(p.relative_to(root).as_posix() for p in files_under(item))
        if base.exists():
            for item in base.iterdir():
                if item.name.startswith("L3"):
                    l3.append(str(safe(item)))
    return sorted(files), sorted(directories), sorted(rebuild), sorted(l3)


def plan(project, staged_project, archive_root, socdoors_root, cohort_root=None):
    """Inventory and hash only; never create locks, receipts, or directories."""
    project, staged, archive, socdoors = map(safe, (project, staged_project, archive_root, socdoors_root))
    cohort = safe(cohort_root) if cohort_root is not None else None
    for root in (project, staged, socdoors, *([cohort] if cohort else [])):
        require(root.is_dir(), f"missing root: {root}")
    require(project != socdoors, "project and socdoors roots must be distinct")
    for root in (project, socdoors, *([cohort] if cohort else [])):
        require(staged != root and staged not in root.parents,
                "staging must not contain production/cohort")
        if root in staged.parents:
            require(root == project and project / "work" in staged.parents,
                    "nested staging is permitted only under project/work")
    require(not archive.exists(), f"archive exists; {RECOVERY}")
    require(archive != staged and archive not in staged.parents and staged not in archive.parents,
            "archive/staging overlap")
    for root in (project, socdoors, *([cohort] if cohort else [])):
        require(archive != root and archive not in root.parents, "archive would contain a live root")
    for root in (project, socdoors):
        if root in archive.parents:
            first = archive.relative_to(root).parts
            require(first[0] not in ("bids", "logs") and not (
                len(first) > 1 and first[0] == "derivatives" and first[1] in
                ("fmriprep", "mriqc", "tedana", "warpkit", "fsl", "fsl-no-tedana-age55", "freesurfer")),
                "archive overlaps managed production trees")
    if cohort:
        require(cohort not in archive.parents, "archive must not be inside cohort root")
    hashes, ready_hash, protected = staged_files(staged, project)
    scans = merge_scans(project, staged, hashes)
    canonical = canonical_files(project)
    if scans and child(project, SCANS).exists():
        canonical.append(SCANS)
    installs = []
    for name, digest in sorted(hashes.items()):
        if name != SCANS:
            child(project, name)
            installs.append({"relpath": name, "sha256": digest, "source": str(child(staged, name))})
    if scans:
        installs.append({"relpath": SCANS, "sha256": hashlib.sha256(scans["content"].encode()).hexdigest(),
                         "content": scans["content"]})
    external, directories, rebuild, l3 = external_outputs(socdoors)
    moves = []
    for label, root, names in (("project", project, canonical), ("socdoors", socdoors, external)):
        for name in sorted(set(names)):
            moves.append({"root": label, "relpath": name, "source": str(child(root, name)),
                          "archive_path": str(child(archive, f"{label}/{name}")),
                          "sha256": sha256(child(root, name))})
    changed = {match[0] for name in canonical + list(hashes)
               if (match := KEY_RE.match(Path(name).name))}
    inputs, manifest_info = {}, None
    if cohort:
        manifest = child(cohort, "manifest.json")
        data = json.loads(manifest.read_text())
        require(data.get("project_root") == str(project) and isinstance(data.get("rows"), list),
                "cohort manifest project/rows mismatch")
        existing = {entry["relpath"]: entry for entry in moves if entry["root"] == "project"}
        for row in data["rows"]:
            key = row.get("run_key", "")
            if not KEY_RE.fullmatch(key):
                continue
            changed.add(key)
            require(isinstance(row.get("inputs"), dict), "affected cohort row lacks input map")
            for name in row["inputs"]:
                source = child(project, name)
                digest = sha256(source)
                destination = existing[name]["archive_path"] if name in existing else str(child(archive, f"original_inputs/{name}"))
                inputs[name] = {"archive_path": destination, "sha256": digest}
        manifest_info = {"source": str(manifest), "sha256": sha256(manifest),
                         "archive_path": str(child(archive, "cohort/manifest.json"))}
        safe(cohort / "validation.json")
    # Include all retired BIDS input bytes even when there is no old Doors cohort row.
    for entry in moves:
        if entry["root"] == "project" and entry["relpath"].startswith("bids/"):
            inputs[entry["relpath"]] = {k: entry[k] for k in ("archive_path", "sha256")}
    return {"schema": 1, "project": str(project), "staged_project": str(staged),
            "archive_root": str(archive), "socdoors_root": str(socdoors),
            "cohort_root": str(cohort) if cohort else None, "ready_sha256": ready_hash,
            "staged_hashes": dict(sorted(hashes.items())), "scans_merge": scans,
            "protected_signatures": protected,
            "installs": installs, "moves": moves, "remove_directories": directories,
            "source_original_inputs": inputs, "cohort_manifest": manifest_info,
            "changed_keys": sorted(changed), "requires_rebuild": rebuild,
            "activation_rebuild": [name for name in rebuild if "_type-act_" in name],
            "other_analysis_requires_rebuild": [name for name in rebuild
                                                if "_type-act_" not in name and "/EVfiles/" not in name],
            "stale_l3_report": {"paths": l3, "action": "review/rebuild affected L3; never auto-run"},
            "post_apply": "revise frozen cohort manifest and revalidate; preserve exclusions, holds and QC"}


def sync_directory(path):
    fd = os.open(safe(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mkdir_durable(path):
    path = safe(path)
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for folder in reversed(missing):
        folder.mkdir()
        sync_directory(folder.parent)


def write_json(path, data):
    path = safe(path)
    temporary = safe(path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp"))
    with temporary.open("x") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def copy_verified(source, destination, digest):
    source, destination = safe(source), safe(destination)
    require(not destination.exists(), f"refusing archive/temp overwrite: {destination}")
    mkdir_durable(destination.parent)
    require(sha256(source) == digest, f"source changed: {source}")
    with source.open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())
    shutil.copystat(source, destination)
    require(sha256(destination) == digest and sha256(source) == digest, f"copy hash mismatch: {source}")
    sync_directory(destination.parent)


def lock_paths(p):
    paths = [child(p["project"], "logs/locks/.11935-repair.lock"),
             child(p["project"], ".11935-repair.lock"),  # Legacy revision-helper guard.
             child(p["socdoors_root"], "derivatives/fsl/.runner.lock"),
             child(p["socdoors_root"], "derivatives/fsl-no-tedana-age55/.runner.lock")]
    if p["cohort_root"]:
        paths.append(child(p["cohort_root"], ".cohort.lock"))
    return sorted(paths)


@contextmanager
def production_guard(p, lock_fds=()):
    """Acquire all locks; borrow caller-owned flock FDs by inode, without unlocking.

    Holds the same mkdir lock as fmriprep.sh, preventing it from starting mid-apply.
    An existing mkdir lock is ALWAYS refused, including unknown host/dead PID.
    """
    key = (p["project"], p["cohort_root"], p["socdoors_root"])
    if key in _ACTIVE:
        require(set(_ACTIVE[key]) <= set(lock_fds), "nested guard requires its held lock_fds")
        yield _ACTIVE[key]
        return
    borrowed = {}
    for value in lock_fds:
        fd = value if isinstance(value, int) else value.fileno()
        info = os.fstat(fd)
        borrowed[(info.st_dev, info.st_ino)] = fd
    subject_lock = child(p["project"], "logs/locks/fmriprep-sub-11935.lock")
    require(not subject_lock.exists(), f"fMRIPrep subject lock exists (host/PID not assumed stale): {subject_lock}")
    with ExitStack() as stack:
        held = []
        for path in lock_paths(p):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                info = path.stat()
                fd = borrowed.get((info.st_dev, info.st_ino))
            else:
                fd = None
            if fd is not None:
                # A separate open description must conflict with the borrowed lock.
                with path.open("a+") as probe:
                    try:
                        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        fcntl.flock(probe, fcntl.LOCK_UN)
                        raise ValueError(f"borrowed descriptor is not locked: {path}")
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                handle = stack.enter_context(path.open("a+"))
                fd = handle.fileno()
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ValueError(f"production lock busy: {path}") from exc
            held.append(fd)
        subject_lock.parent.mkdir(parents=True, exist_ok=True)
        try:
            subject_lock.mkdir()
        except FileExistsError as exc:
            raise ValueError(f"fMRIPrep subject lock appeared: {subject_lock}") from exc
        try:
            (subject_lock / "pid").write_text(str(os.getpid()) + "\n")
            (subject_lock / "host").write_text(socket.gethostname() + "\n")
            _ACTIVE[key] = tuple(held)
            yield tuple(held)
        finally:
            _ACTIVE.pop(key, None)
            for name in ("pid", "host"):
                safe(subject_lock / name).unlink(missing_ok=True)
            subject_lock.rmdir()


def fresh_plan(p):
    return plan(*(p[name] for name in ("project", "staged_project", "archive_root", "socdoors_root")),
                cohort_root=p["cohort_root"])


def verify_receipt(receipt, *, allow_rebuilt=True):
    p = receipt["plan"]
    require(receipt.get("state") == "installed", RECOVERY)
    require(p.get("schema") == 1, "unsupported promotion receipt schema")
    for name in ("installs", "staged_hashes", "changed_keys"):
        require(receipt.get(name) == p[name], f"receipt/plan {name} mismatch")
    expected = {entry["relpath"]: entry["sha256"] for entry in p["installs"]}
    actual = set(canonical_files(Path(p["project"])))
    require(actual == set(expected) - {SCANS}, "canonical closure differs from installed plan")
    for name, digest in expected.items():
        require(sha256(child(p["project"], name)) == digest, f"installed hash mismatch: {name}")
    for entry in p["moves"]:
        require(sha256(entry["archive_path"]) == entry["sha256"], "retired archive hash mismatch")
        if ((entry["root"] == "socdoors" and not allow_rebuilt)
                or (entry["root"] == "project" and entry["relpath"] not in expected)):
            require(not safe(entry["source"]).exists(), f"stale output reappeared: {entry['source']}")
    for item in p["source_original_inputs"].values():
        require(sha256(item["archive_path"]) == item["sha256"], "original input archive hash mismatch")
    if p["cohort_manifest"]:
        item = p["cohort_manifest"]
        require(sha256(item["archive_path"]) == item["sha256"], "manifest archive hash mismatch")
    if not allow_rebuilt:
        for name in p["remove_directories"]:
            require(not child(p["socdoors_root"], name).exists(), "stale analysis directory remains")
        require(not external_outputs(Path(p["socdoors_root"]))[0], "new stale downstream outputs present")
    return {"state": "installed", "verified": True, "changed_keys": p["changed_keys"],
            "requires_rebuild": p["requires_rebuild"], "stale_l3_report": p["stale_l3_report"]}


def check(value, *, allow_rebuilt=True):
    """Read-only installed-byte verification; not scientific/cohort validation."""
    if isinstance(value, (str, Path)):
        value = json.loads(safe(value).read_text())
    if "state" not in value:
        receipt = child(value["archive_root"], "promotion.json")
        require(receipt.exists(), f"promotion receipt missing: {receipt}")
        state = json.loads(receipt.read_text())
        require(state.get("plan") == value, "receipt does not match supplied plan")
        value = state
    return verify_receipt(value, allow_rebuilt=allow_rebuilt)


def apply_plan(p, lock_fds=()):
    """Apply only an unchanged plan, under guards. Never resume an existing archive."""
    require(not safe(p["archive_root"]).exists(), f"archive exists; {RECOVERY}")
    with production_guard(p, lock_fds=lock_fds):
        require(fresh_plan(p) == p, "plan changed; regenerate and review before applying")
        archive = safe(p["archive_root"])
        mkdir_durable(archive.parent)
        archive.mkdir(exist_ok=False)
        sync_directory(archive.parent)
        receipt_path = archive / "promotion.json"
        token = uuid.uuid4().hex
        temporaries = {entry["relpath"]: str(child(p["project"], entry["relpath"]).with_name(
            "." + Path(entry["relpath"]).name + ".11935-repair-" + token + ".tmp")) for entry in p["installs"]}
        receipt = {"state": "prepared", "plan": p, "staged_hashes": p["staged_hashes"],
                   "changed_keys": p["changed_keys"], "source_original_inputs": p["source_original_inputs"],
                   "cohort_manifest": p["cohort_manifest"], "installs": p["installs"], "moves": p["moves"],
                   "requires_rebuild": p["requires_rebuild"], "temporaries": temporaries,
                   "recovery": RECOVERY}
        write_json(receipt_path, receipt)
        try:
            if p["cohort_root"]:
                validation = child(p["cohort_root"], "validation.json")
                if validation.exists():
                    copy_verified(validation, archive / "cohort/validation.json", sha256(validation))
                write_json(validation, {"validated": False, "status": "11935-promotion",
                                        "changed_keys": p["changed_keys"], "promotion_receipt": str(receipt_path)})
            for entry in p["installs"]:
                target = safe(temporaries[entry["relpath"]])
                if "content" in entry:
                    mkdir_durable(target.parent)
                    with target.open("xb") as handle:
                        handle.write(entry["content"].encode())
                        handle.flush()
                        os.fsync(handle.fileno())
                    require(sha256(target) == entry["sha256"], "merged scans hash mismatch")
                    sync_directory(target.parent)
                else:
                    copy_verified(entry["source"], target, entry["sha256"])
            # Back up and hash everything before the first canonical unlink.
            for entry in p["moves"]:
                copy_verified(entry["source"], entry["archive_path"], entry["sha256"])
            destinations = {entry["archive_path"] for entry in p["moves"]}
            for name, item in p["source_original_inputs"].items():
                if item["archive_path"] not in destinations:
                    copy_verified(child(p["project"], name), item["archive_path"], item["sha256"])
            if p["cohort_manifest"]:
                item = p["cohort_manifest"]
                copy_verified(item["source"], item["archive_path"], item["sha256"])
            receipt["state"] = "applying"
            write_json(receipt_path, receipt)
            for entry in p["moves"]:
                source = safe(entry["source"])
                require(sha256(source) == entry["sha256"], f"live source changed: {source}")
                source.unlink()
                sync_directory(source.parent)
            for name in sorted(p["remove_directories"], key=len, reverse=True):
                folder = child(p["socdoors_root"], name)
                for directory, _, _ in os.walk(folder, topdown=False):
                    safe(directory).rmdir()
                sync_directory(folder.parent)
            for entry in p["installs"]:
                target = child(p["project"], entry["relpath"])
                temporary = safe(temporaries[entry["relpath"]])
                require(sha256(temporary) == entry["sha256"], "temporary changed before installation")
                require(not target.exists(), f"refusing unexpected canonical overwrite: {target}")
                # link is an atomic, no-clobber install on the destination filesystem.
                os.link(temporary, target)
                temporary.unlink()
                sync_directory(target.parent)
            candidate = dict(receipt, state="installed")
            verify_receipt(candidate, allow_rebuilt=False)
            write_json(receipt_path, candidate)
            return candidate
        except BaseException as exc:
            receipt["error"] = f"{type(exc).__name__}: {exc}"
            try:
                write_json(receipt_path, receipt)
            except Exception:
                pass
            raise RuntimeError(f"promotion NOT installed: {exc}. {RECOVERY}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "promote", "check"))
    parser.add_argument("--project", "--project-root", dest="project", type=Path)
    parser.add_argument("--staged-project", type=Path)
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--socdoors-root", type=Path)
    parser.add_argument("--cohort-root", type=Path)
    parser.add_argument("--receipt", type=Path, help="check an existing promotion.json")
    parser.add_argument("--approve-images", action="store_true", help="attest reviewed staged images")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            require(args.receipt or args.archive_root, "check requires --receipt or --archive-root")
            result = check(args.receipt or args.archive_root / "promotion.json")
        else:
            require(all((args.project, args.staged_project, args.archive_root, args.socdoors_root)),
                    "requires --project, --staged-project, --archive-root, --socdoors-root")
            if args.command == "promote":
                require(args.approve_images, "promote requires --approve-images")
            p = plan(args.project, args.staged_project, args.archive_root, args.socdoors_root, args.cohort_root)
            result = apply_plan(p) if args.command == "promote" else p
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
