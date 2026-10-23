#!/usr/bin/env python3
"""Rebase only the reviewed 11935/session-01 SocialDoors + Doors repair.

plan_revision(project, audit_root, changed_keys, archive_root, *,
              excluded_source_root=DEFAULT_EXCLUSIONS) is read-only.
apply_revision(plan, *, promotion_receipt) rechecks the plan under .cohort.lock.
No TEDANA jobs are launched. Interrupted operations require manual recovery;
neither an existing archive nor an in-progress marker is ever reused.

Accepts promote_11935.py's installed promotion.json: plan.schema=1,
plan.project, plan.archive_root, plan.cohort_root, changed_keys, installs,
source_original_inputs[project-relative]={archive_path (absolute), sha256},
and cohort_manifest={source, archive_path, sha256}. Duplicated receipt fields
must agree with plan. Every frozen target input must be covered; archive bytes
are hashed and sizes/mtimes compared with frozen signatures. Current target
input hashes must match installs (or unchanged archived originals). No scientific
QC threshold is imposed here. The caller supplies the reviewed promotion receipt.

Post-promotion CLI (substitute absolute paths):
  python code/revise_tedana_cohort.py plan --project-root PROJECT \
      --audit-root AUDIT --promotion-receipt PROMOTION_ARCHIVE/promotion.json
  python code/revise_tedana_cohort.py apply --project-root PROJECT \
      --audit-root AUDIT --promotion-receipt PROMOTION_ARCHIVE/promotion.json
Both accept --archive-root and --excluded-source-root. Default revision archive:
AUDIT/revisions/PROMOTION_ARCHIVE_DIRECTORY_NAME. Plan prints JSON without writes;
apply acquires project/.11935-repair.lock, AUDIT/.cohort.lock, then the same
logs/locks/fmriprep-sub-11935.lock mkdir guard as the promoter. Busy/stale locks
are refused, never cleared. The existing runner has no subject filter: it queues
the whole manifest and skips only jobs with intact, matching success receipts.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import socket
import sys

import benchmark_tedana_cohort as cohort


APPROVED_KEYS = frozenset({
    "sub-11935_ses-01_task-socialdoors_run-1",
    "sub-11935_ses-01_task-doors_run-1",
})
DOORS_KEY = "sub-11935_ses-01_task-doors_run-1"
DEFAULT_EXCLUSIONS = Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions")
MARKER = ".revision-in-progress.json"
RETIRED_FILES = ("manifest.json", "validation.json", "component_summary.tsv",
                 "check_failures.tsv", "status.tsv")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(data):
    return json.loads(data, object_pairs_hook=_pairs)


def _path(value, within=None):
    path = Path(value)
    _require(".." not in path.parts, f"path escape: {path}")
    path = Path(os.path.abspath(path))
    if within is not None:
        _require(path != within and within in path.parents, f"path escapes root: {path}")
    for part in [*reversed(path.parents), path]:
        _require(not part.is_symlink(), f"symlink refused: {part}")
    return path


def _relative(root, name):
    _require(isinstance(name, str) and not Path(name).is_absolute(), "relative path required")
    return _path(root / name, root)


def _tree(path):
    """Snapshot only retirement candidates; reject links and special files."""
    _path(path)
    if not path.exists():
        return None
    paths = [path, *sorted(path.rglob("*"))] if path.is_dir() else [path]
    result = {}
    for entry in paths:
        _path(entry)
        info = entry.stat()
        _require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode),
                 f"special file refused: {entry}")
        result[str(entry.relative_to(path))] = {
            "directory": entry.is_dir(), "size": info.st_size,
            "mtime_ns": info.st_mtime_ns, "inode": info.st_ino, "device": info.st_dev,
            **({"sha256": cohort.sha256(entry)} if entry.is_file()
               and not entry.name.endswith(".nii.gz") else {}),
        }
    return result


def _inputs(project, row):
    _require(isinstance(row.get("inputs"), dict) and row["inputs"], "empty input inventory")
    for name in row["inputs"]:
        _require(_relative(project, name).is_file(), f"missing input: {name}")
    for name in row.get("echo_files", "").split(";"):
        if name:
            _require(name in row["inputs"], "echo file absent from input inventory")
    for field in ("fmriprep_mask", "fmriprep_confounds"):
        if field in row:
            _require(row[field] in row["inputs"], f"{field} absent from input inventory")


def plan_revision(project, audit_root, changed_keys, archive_root, *,
                  excluded_source_root=DEFAULT_EXCLUSIONS):
    """Return a serializable, read-only plan; the exact approved pair is required.

    Archive must be a new directory, outside canonical BIDS/fMRIPrep and active
    benchmark/log trees. Doors may be newly acquired, but must have 218 volumes.
    Existing unrelated rows retain exactly the same JSON values.
    """
    keys = list(changed_keys)
    _require(len(keys) == 2 and set(keys) == APPROVED_KEYS, "changed_keys must equal approved allowlist")
    project, root = _path(project), _path(audit_root)
    allowed = _path(project / "derivatives/tedana-audit")
    _require(allowed in root.parents, "audit_root must be a dedicated TEDANA audit directory")
    archive = _path(archive_root)
    excluded_root = _path(excluded_source_root)
    _require(root.is_dir(), "audit root missing")
    _require(not _path(root / MARKER).exists(),
             "interrupted revision: inspect marker/archive; manual recovery required, do not retry")
    _require(not archive.exists(), "archive already exists; manual recovery required, do not retry")
    for protected in (root, project / "bids", project / "derivatives/fmriprep"):
        _require(archive != protected and archive not in protected.parents,
                 "archive overlaps active root")
    for protected in (project / "bids", project / "derivatives/fmriprep",
                      root / "benchmark", root / "logs", excluded_root):
        _require(archive != protected and protected not in archive.parents,
                 "archive overlaps active inputs/outputs")
    manifest_path = _path(root / "manifest.json")
    raw = manifest_path.read_bytes()
    manifest = _json(raw)
    _require(manifest.get("schema") == 1 and manifest.get("project_root") == str(project)
             and manifest.get("configs") == list(cohort.CONFIGS) and manifest.get("rows"),
             "invalid or incompatible old manifest")
    _require(manifest.get("blocked") == [], "blocked manifest is not eligible for revision")
    old_rows = manifest["rows"]
    old = {row["run_key"]: row for row in old_rows}
    _require(len(old) == len(old_rows), "duplicate old roster keys")
    _require(bool(set(old) & APPROVED_KEYS), "at least one approved key must exist in old manifest")
    found, excluded = cohort.inventory(project, excluded_root)
    live = {key.prefix: (key, paths) for key, paths in found.items()}
    _require(set(live) - APPROVED_KEYS == set(old) - APPROVED_KEYS
             and APPROVED_KEYS <= set(live), "unrelated roster changed or approved target missing")
    _require(sorted(excluded) == manifest["source_excluded"], "source exclusions changed")
    for row in old_rows:
        _inputs(project, row)
        if row["run_key"] not in APPROVED_KEYS:
            _require(cohort.current_signatures(project, row) == row["inputs"],
                     f"unrelated inputs changed: {row['run_key']}")
    refreshed = {}
    for name in sorted(APPROVED_KEYS):
        key, paths = live[name]
        for path in paths:
            _path(path, project)
        # inspect_run constructs these paths itself; check links before it reads.
        for base in (project / "bids", project / "derivatives/fmriprep"):
            directory = _path(base / f"sub-{key.subject}/ses-{key.session}/func", project)
            if directory.exists():
                for entry in directory.rglob("*"):
                    _path(entry, project)
        row = cohort.inspect_run(project, key, paths)
        _require(row["run_key"] == name and all(row[field] == getattr(key, field)
                 for field in ("subject", "session", "task", "run")), "refreshed key mismatch")
        _inputs(project, row)
        _require(cohort.current_signatures(project, row) == row["inputs"], "target inputs changed")
        refreshed[name] = row
    if DOORS_KEY not in old:
        _require(refreshed[DOORS_KEY]["number_of_original_volumes"] == 218,
                 "new Doors row must have 218 original volumes")
    _require(any(old[name] != refreshed[name] for name in set(old) & APPROVED_KEYS),
             "no existing target repair detected")
    candidates = [root / name for name in RETIRED_FILES]
    for name in sorted(APPROVED_KEYS):
        for config in cohort.CONFIGS:
            job = cohort.job_for(project, root, Path("tedana"), old.get(name, refreshed[name]), config)
            path = _path(job.output_dir, root)
            _require((root / "benchmark") in path.parents, "job output outside benchmark tree")
            _require(not path.exists() or path.is_dir(), "job output is not a directory")
            candidates.append(path)
    _require(len(set(candidates)) == len(candidates), "overlapping retirement paths")
    for path in candidates:
        _require(not any(path in other.parents for other in candidates), "nested retirement paths")
    moves = []
    for path in candidates:
        _require(archive != path and path not in archive.parents, "archive overlaps retirement path")
        snapshot = _tree(path)
        moves.append({"relative_path": str(path.relative_to(root)), "snapshot": snapshot})
    return {"schema": 1, "project": str(project), "audit_root": str(root),
            "archive_root": str(archive), "excluded_source_root": str(excluded_root),
            "changed_keys": sorted(APPROVED_KEYS), "old_manifest_sha256": _digest(raw),
            "refreshed_rows": refreshed, "moves": moves}


def _receipt(plan, receipt_path, old):
    path = _path(receipt_path)
    raw = path.read_bytes()
    receipt = _json(raw)
    promotion = receipt.get("plan", {})
    _require(receipt.get("state") == "installed" and promotion.get("schema") == 1,
             "installed canonical repair promotion receipt required")
    _require(promotion.get("project") == plan["project"]
             and promotion.get("cohort_root") == plan["audit_root"]
             and receipt.get("changed_keys") == promotion.get("changed_keys") == plan["changed_keys"],
             "promotion receipt project/cohort/allowlist mismatch")
    archive = _path(promotion["archive_root"])
    _require(Path(promotion["archive_root"]).is_absolute() and archive.is_dir()
             and path == archive / "promotion.json", "invalid promotion archive/receipt path")
    revision_archive = Path(plan["archive_root"])
    _require(archive != revision_archive and revision_archive not in archive.parents,
             "old input archive overlaps revision destination")
    manifest_info = receipt.get("cohort_manifest")
    _require(isinstance(manifest_info, dict) and manifest_info == promotion.get("cohort_manifest")
             and manifest_info.get("source") == str(Path(plan["audit_root"]) / "manifest.json")
             and manifest_info.get("sha256") == plan["old_manifest_sha256"],
             "promotion receipt old manifest mismatch")
    saved_manifest = _path(manifest_info["archive_path"], archive)
    _require(cohort.sha256(saved_manifest) == plan["old_manifest_sha256"], "promotion archived manifest hash mismatch")
    expected = {name: sig for row in old["rows"] if row["run_key"] in APPROVED_KEYS
                for name, sig in row["inputs"].items()}
    coverage = receipt.get("source_original_inputs", {})
    _require(coverage == promotion.get("source_original_inputs"), "promotion original input maps disagree")
    _require(set(expected) <= set(coverage), "old input archive coverage incomplete")
    used = set()
    project = Path(plan["project"])
    for name, frozen in expected.items():
        record = coverage[name]
        _require(Path(record["archive_path"]).is_absolute(), "absolute old archive path required")
        saved = _path(record["archive_path"], archive)
        _require(saved not in used and saved != _relative(project, name), "old input archive aliases live input")
        used.add(saved)
        _require(saved.is_file(), f"old archived input missing: {name}")
        info = saved.stat()
        _require(info.st_size == frozen["size"] and info.st_mtime_ns == frozen["mtime_ns"],
                 f"old archived input signature mismatch: {name}")
        digest = cohort.sha256(saved)
        _require(digest == record["sha256"] and ("sha256" not in frozen or digest == frozen["sha256"]),
                 f"old archived input hash mismatch: {name}")
        _require(saved.stat().st_ino != (project / name).stat().st_ino
                 or saved.stat().st_dev != (project / name).stat().st_dev,
                 "old archive hardlinks live input")
    installs = receipt.get("installs")
    _require(isinstance(installs, list) and installs == promotion.get("installs"),
             "promotion install maps disagree")
    installed = {entry["relpath"]: entry["sha256"] for entry in installs}
    _require(len(installed) == len(installs), "duplicate promotion installs")
    for row in plan["refreshed_rows"].values():
        for name in row["inputs"]:
            expected_hash = installed.get(name, coverage.get(name, {}).get("sha256"))
            _require(expected_hash is not None and cohort.sha256(_relative(project, name)) == expected_hash,
                     f"promotion current input hash mismatch or missing coverage: {name}")
    return {"promotion_receipt": str(path), "promotion_receipt_sha256": _digest(raw),
            "old_input_archive": str(archive)}


def _manifest_bytes(raw, rows, provenance):
    manifest = _json(raw)
    existing = {row["run_key"] for row in manifest["rows"]}
    unrelated = [row for row in manifest["rows"] if row["run_key"] not in rows]
    manifest["rows"] = [rows.get(row["run_key"], row) for row in manifest["rows"]]
    manifest["rows"].extend(rows[key] for key in sorted(set(rows) - existing))
    manifest["revision_provenance"] = provenance
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    _require([row for row in _json(encoded)["rows"] if row["run_key"] not in rows] == unrelated,
             "unrelated row changed during serialization")
    return encoded


def _write_new(path, data):
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _sync(directory):
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _mkdir(directory):
    """Persist newly created ancestors before any archived file is moved."""
    missing = []
    current = directory
    while not current.exists():
        missing.append(current)
        current = current.parent
    for path in reversed(missing):
        path.mkdir()
        _sync(path.parent)


@contextmanager
def _flock(path):
    path = _path(path)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        _require(stat.S_ISREG(os.fstat(fd).st_mode), "invalid cohort lock file")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"another cohort command or production repair is active: {path}") from exc
        yield
    finally:
        os.close(fd)


@contextmanager
def _locked(project, root):
    subject = _path(project / "logs/locks/fmriprep-sub-11935.lock")
    _require(not subject.exists(), "fMRIPrep subject lock exists; stop production writer before revision")
    with ExitStack() as stack:
        # Same ordering as promote_11935.lock_paths, restricted to our two flocks.
        for path in sorted([project / ".11935-repair.lock", root / ".cohort.lock"]):
            stack.enter_context(_flock(path))
        subject.parent.mkdir(parents=True, exist_ok=True)
        try:
            subject.mkdir()
        except FileExistsError as exc:
            raise ValueError("fMRIPrep subject lock appeared; no revision performed") from exc
        try:
            _write_new(subject / "pid", (str(os.getpid()) + "\n").encode())
            _write_new(subject / "host", (socket.gethostname() + "\n").encode())
            yield
        finally:
            for name in ("pid", "host"):
                _path(subject / name).unlink(missing_ok=True)
            subject.rmdir()


def apply_revision(plan, *, promotion_receipt):
    """Archive, then atomically install schema-1 manifest; return provenance.

    Any existing archive/marker is an explicit manual-recovery error, including
    a second call after success. The lock is held through all verification and
    installation. Only existing target attempts are retired. The cohort runner
    still schedules all rows, skipping unrelated jobs only with valid receipts.
    """
    root = _path(plan["audit_root"])
    with _locked(_path(plan["project"]), root):
        _require(plan.get("schema") == 1, "incompatible revision plan")
        fresh = plan_revision(plan["project"], root, plan["changed_keys"], plan["archive_root"],
                              excluded_source_root=plan["excluded_source_root"])
        _require(fresh == plan, "old manifest/inputs/outputs changed or plan mismatch; re-plan required")
        raw = (root / "manifest.json").read_bytes()
        old = _json(raw)
        provenance = _receipt(plan, promotion_receipt, old)
        archive = Path(plan["archive_root"])
        provenance.update({"schema": 1, "changed_keys": plan["changed_keys"],
                           "old_manifest_sha256": plan["old_manifest_sha256"],
                           "old_manifest": str(archive / "retired/manifest.json"),
                           "revision_archive": str(archive)})
        updated = _manifest_bytes(raw, plan["refreshed_rows"], provenance)
        # All retirements must be atomic renames, never copy/delete fallbacks.
        parent = archive.parent
        while not parent.exists():
            parent = parent.parent
        _require(parent.stat().st_dev == root.stat().st_dev,
                 "cross-filesystem revision archive refused")
        for move in plan["moves"]:
            if move["snapshot"] is not None:
                source = _relative(root, move["relative_path"])
                _require(source.stat().st_dev == parent.stat().st_dev, "cross-filesystem retirement refused")
        marker = root / MARKER
        journal = {"status": "in_progress", "plan": plan, "provenance": provenance,
                   "recovery": "Do not retry or delete archives; inspect retired paths and staged manifest manually."}
        _write_new(marker, (json.dumps(journal, indent=2, sort_keys=True) + "\n").encode())
        _sync(root)
        _mkdir(archive)
        _sync(archive.parent)
        _write_new(archive / "journal.json", marker.read_bytes())
        _write_new(archive / "new-manifest.json", updated)
        _sync(archive)
        for move in plan["moves"]:
            source = _relative(root, move["relative_path"])
            _require(_tree(source) == move["snapshot"], "retirement candidate changed; manual recovery required")
            if move["snapshot"] is None:
                continue
            destination = archive / "retired" / move["relative_path"]
            _mkdir(destination.parent)
            source.rename(destination)
            _sync(source.parent)
            _sync(destination.parent)
        # Recheck inputs/roster after archival, before the new manifest is visible.
        found, excluded = cohort.inventory(Path(plan["project"]), Path(plan["excluded_source_root"]))
        new = _json(updated)
        _require({key.prefix for key in found} == {row["run_key"] for row in new["rows"]}
                 and sorted(excluded) == new["source_excluded"], "roster changed during revision; manual recovery required")
        for row in new["rows"]:
            _inputs(Path(plan["project"]), row)
            _require(cohort.current_signatures(Path(plan["project"]), row) == row["inputs"],
                     "inputs changed during revision; manual recovery required")
        _require(not (root / "manifest.json").exists(), "manifest unexpectedly recreated; manual recovery required")
        (archive / "new-manifest.json").rename(root / "manifest.json")
        _sync(archive)
        _sync(root)
        _write_new(archive / "complete.json", (json.dumps({"status": "complete",
                   "manifest_sha256": _digest(updated), **provenance}, sort_keys=True) + "\n").encode())
        _sync(archive)
        marker.unlink()
        _sync(root)
        return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--audit-root", required=True, type=Path)
    parser.add_argument("--promotion-receipt", required=True, type=Path)
    parser.add_argument("--archive-root", type=Path,
                        help="new revision directory; default: AUDIT/revisions/PROMOTION_DIRECTORY")
    parser.add_argument("--excluded-source-root", type=Path, default=DEFAULT_EXCLUSIONS)
    args = parser.parse_args(argv)
    try:
        receipt_path = _path(args.promotion_receipt)
        archive = args.archive_root or args.audit_root / "revisions" / receipt_path.parent.name
        planned = plan_revision(args.project_root, args.audit_root, sorted(APPROVED_KEYS), archive,
                                excluded_source_root=args.excluded_source_root)
        if args.command == "apply":
            result = apply_revision(planned, promotion_receipt=receipt_path)
        else:
            # CLI planning validates receipt coverage, still without creating locks.
            old = _json((Path(planned["audit_root"]) / "manifest.json").read_bytes())
            _receipt(planned, receipt_path, old)
            result = planned
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
