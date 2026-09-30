#!/usr/bin/env python3
"""Reviewed 10668 task reassignment. Default: read-only plan, never implicit apply.

Raw DICOMs/behavior are never edited. Live apply archives the complete original
session and subject-level derivatives; a stage command serves fresh prepdata.
An interrupted transaction is refused, not silently restarted over its backups.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

import nibabel as nib
import numpy as np

from convert_behavior import convert_behavior, convert_source
from review_sharedreward_inventory import conversion_match

ROOT = Path(__file__).resolve().parents[1]
ID = "10668-sharedreward-v1"
SESSION = Path("sub-10668/ses-01")
PREFIX = "sub-10668_ses-01_"
OLD_A = PREFIX + "task-trust_run-2"
OLD_B = PREFIX + "task-sharedreward_run-1"
NEW_A = OLD_B
NEW_B = PREFIX + "task-sharedreward_run-2"
MARKER = ".rf1-10668-repair.json"
INVENTORY_SHA = "f4cd81016314c9cef0df705ed3f875741e02678f2f59cebb939d96b4bc42fac0"
SOURCE_HASHES = (
    "cc23b38f37104a22fb43b3d8ff1147ff0c7c8e6df9d2777a8f74b7862866deb7",
    "3f85c5f1d9c32a19fbd389f87c9bf2bfa0e8edfd10c24681cb9fb6dfbd087546",
)


class RepairError(ValueError):
    """Sanitized error safe for a shared run record."""


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise RepairError(message)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("x") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def tree_hashes(root):
    require(root.is_dir() and not root.is_symlink(), "Expected a real directory")
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Symlink in repair tree; inspect privately")
        if path.is_file():
            result[str(path.relative_to(root))] = sha(path)
    return result


def behavior_check(root):
    for run, expected in enumerate(SOURCE_HASHES, 1):
        path = root / "Scan-Card_Guessing_Game/logs/10668" / f"sub-10668_task-sharedreward_run-{run}_raw.csv"
        require(sha(path) == expected, f"Shared Reward attempt {run} source hash changed")
        data = convert_source("sharedreward", path)
        require(data.trial_count == 54 and not data.review_issues,
                f"Shared Reward attempt {run} failed conversion validation")


def renamed(value):
    # Simultaneous mapping: never apply run-1 -> run-2 to the newly recovered A.
    if isinstance(value, str):
        return re.sub(re.escape(OLD_A) + "|" + re.escape(OLD_B),
                      lambda m: {OLD_A: NEW_A, OLD_B: NEW_B}[m[0]], value)
    if isinstance(value, list):
        return [renamed(x) for x in value]
    if isinstance(value, dict):
        return {k: renamed(v) for k, v in value.items()}
    return value


def slice_timing(meta, img, label):
    """Validate run-local timing; return voxel-order times for diagnostics only."""
    if "SliceTiming" not in meta:
        return None
    values = meta["SliceTiming"]
    require(isinstance(values, list) and values and
            all(type(v) in (int, float) for v in values),
            f"Invalid SliceTiming numeric array: {label}")
    times = np.asarray(values, dtype=float)
    tr = meta["RepetitionTime"]
    require(np.all(np.isfinite(times)) and np.all(times >= 0) and np.all(times < tr),
            f"SliceTiming must be finite and within [0, TR): {label}")
    direction = meta.get("SliceEncodingDirection")
    header_axis = img.header.get_dim_info()[2]
    if direction is not None:
        require(direction in ("i", "j", "k", "i-", "j-", "k-"),
                f"Invalid SliceEncodingDirection: {label}")
        axis = "ijk".index(direction[0])
        require(header_axis is None or header_axis == axis,
                f"SliceEncodingDirection conflicts with NIfTI slice axis: {label}")
        evidence = "sidecar"
    elif header_axis is not None:
        axis, evidence = header_axis, "NIfTI"
    else:
        candidates = [i for i, size in enumerate(img.shape[:3]) if size == len(times)]
        require(len(candidates) == 1,
                f"Cannot uniquely validate SliceTiming slice count against image: {label}")
        axis, evidence = candidates[0], "unique matching dimension (axis not declared)"
    require(len(times) == img.shape[axis], f"SliceTiming slice count differs from image: {label}")
    if direction and direction.endswith("-"):
        times = times[::-1]
    return axis, evidence, times


def report_slice_timing(timings):
    for label, timing in zip(("original Trust-labeled run 2", "original Shared Reward run 1"), timings):
        if timing is None:
            print(f"SLICE TIMING {label}: unavailable; no timing synthesized")
        else:
            axis, evidence, times = timing
            print(f"SLICE TIMING {label}: n={len(times)} axis={'ijk'[axis]} ({evidence}); "
                  f"range_seconds=[{times.min():.9g}, {times.max():.9g}]")
    if all(t is not None for t in timings) and timings[0][0] == timings[1][0]:
        delta = np.abs(timings[0][2] - timings[1][2])
        print(f"SLICE TIMING cross-run max_abs_delta_seconds={delta.max():.9g}; "
              "diagnostic only, each acquisition retains its own timing")
    else:
        print("SLICE TIMING cross-run comparison unavailable; each acquisition retains its own metadata")


def validate_original(bids, inventory_path, behavior):
    require(sha(inventory_path) == INVENTORY_SHA, "Not the reviewed September 16 inventory")
    inventory = json.loads(inventory_path.read_text())
    behavior_check(behavior)
    session = bids / SESSION
    require(not (session / MARKER).exists(), "Session already has a repair receipt; use check")
    require(not list((session / "func").glob(NEW_B + "_*")), "Conflicting Shared Reward run-2 target")
    for task, run, expected in (("trust", "1", "8"), ("trust", "2", "11"), ("sharedreward", "1", "14")):
        path = session / "func" / f"{PREFIX}task-{task}_run-{run}_echo-1_part-mag_bold.json"
        status, matches, bad, _ = conversion_match(bids, "10668", run,
            json.loads(path.read_text()), inventory["series"], task=task)
        require(status == "PROVENANCE_UID_LINKED" and not bad and len(matches) == 1,
                f"Exact conversion provenance missing/conflicting for {task} run {run}")
        require(matches[0]["fields"].get("SeriesNumber") == [expected] and
                matches[0]["folders"] == ["10668"], "Unexpected reviewed source series")
    files = []
    shapes = []
    acquisition_metadata = []
    acquisition_timings = []
    for old, nvol, mag_series in ((OLD_A, 280, 11), (OLD_B, 255, 14)):
        group = sorted((session / "func").glob(old + "_*"))
        require(group, "Missing acquisition files")
        for part, number in (("mag", mag_series), ("phase", mag_series + 1)):
            for echo in range(1, 5):
                base = f"{old}_echo-{echo}_part-{part}_bold"
                imgpath = session / "func" / (base + ".nii.gz")
                meta = json.loads((session / "func" / (base + ".json")).read_text())
                if part == "mag" and echo == 1:
                    acquisition_metadata.append(meta)
                require(not any(k in meta for k in ("B0FieldSource", "B0FieldIdentifier")),
                        "Existing B0 identifier associations require explicit review before remapping")
                require(str(meta.get("SeriesNumber")) == str(number), "Unexpected echo source series")
                require(np.isclose(meta.get("RepetitionTime", 0), 1.615), "Unexpected TR")
                require(np.isclose(meta.get("EchoTime", 0), [0.0138, 0.03154, 0.04928, 0.06702][echo - 1]), "Unexpected TE")
                img = nib.load(imgpath)
                require(len(img.shape) == 4 and img.shape[3] == nvol, "Unexpected input volume count")
                require(img.header.get_xyzt_units()[1] == "sec" and
                        np.isclose(img.header.get_zooms()[3], 1.615), "Unexpected NIfTI time units/TR")
                timing = slice_timing(meta, img, base)
                if part == "mag" and echo == 1:
                    acquisition_timings.append(timing)
                shapes.append((img.shape[:3], img.affine))
        require(any(p.name.endswith("_sbref.nii.gz") for p in group), "SBRef missing")
        for path in group:
            require(path.is_file() and not path.is_symlink(), "Unexpected acquisition entry")
            require(re.search(r"_(bold|sbref)\.(nii\.gz|json)$|_events\.(tsv|json)$", path.name),
                    "Unrecognized acquisition companion; inspect before repair")
            if path.name.endswith("_sbref.json"):
                require(str(json.loads(path.read_text()).get("SeriesNumber")) == str(mag_series - 1),
                        "Unexpected SBRef series")
            if path.name.endswith(("_bold.json", "_sbref.json")):
                meta = json.loads(path.read_text())
                task, run = ("trust", "2") if old == OLD_A else ("sharedreward", "1")
                status, matches, bad, _ = conversion_match(bids, "10668", run, meta,
                    inventory["series"], task=task, output_stem=path.name[:-5])
                require(status == "PROVENANCE_UID_LINKED" and not bad and len(matches) == 1,
                        f"Companion source provenance failed: {path.name}")
                require(matches[0]["folders"] == ["10668"], "Companion source belongs to different folder")
            files.append(str(path.relative_to(session)))
    require(all(s == shapes[0][0] and np.allclose(a, shapes[0][1], atol=1e-5, rtol=0)
                for s, a in shapes), "Native image geometry differs; inspect before repair")
    report_slice_timing(acquisition_timings)
    for key in ("FlipAngle", "PhaseEncodingDirection", "EffectiveEchoSpacing",
                "TotalReadoutTime", "MultibandAccelerationFactor", "ParallelReductionFactorInPlane"):
        present = [key in m for m in acquisition_metadata]
        require(present[0] == present[1], f"Asymmetric acquisition metadata: {key}")
        if all(present):
            require(acquisition_metadata[0][key] == acquisition_metadata[1][key],
                    f"Acquisition parameter differs: {key}")
        print(f"PARAMETER {key}: {'equal' if all(present) else 'unavailable in both sidecars'}")
    require((session / f"{PREFIX}scans.tsv").is_file(), "Missing session scans.tsv")
    return files


def crop(source, destination):
    image = nib.load(source)
    data = image.dataobj.get_unscaled()[..., :255]
    header = image.header.copy()
    qform, qcode = image.get_qform(coded=True)
    sform, scode = image.get_sform(coded=True)
    out = image.__class__(data, image.affine, header)
    out.set_qform(qform, int(qcode))
    out.set_sform(sform, int(scode))
    out.header.set_slope_inter(image.dataobj.slope, image.dataobj.inter)
    nib.save(out, destination)
    check = nib.load(destination)
    require(np.array_equal(data, check.dataobj.get_unscaled()) and
            check.dataobj.slope == image.dataobj.slope and check.dataobj.inter == image.dataobj.inter,
            "Crop changed voxel values/scaling")


def build_stage(bids, staged_bids, files, behavior):
    original = bids / SESSION
    target = staged_bids / SESSION
    shutil.copytree(original, target, copy_function=shutil.copy2)
    for rel in files:
        (target / rel).unlink()
    # Fieldmaps are generated by WarpKit; regenerate all for this preserved session.
    if (target / "fmap").exists():
        shutil.rmtree(target / "fmap")
    for rel in files:
        source = original / rel
        if "_events." in source.name:
            continue  # Regenerate both event files from the reviewed source hashes.
        dest = target / renamed(rel)
        if source.name.endswith(".nii.gz"):
            if source.name.startswith(OLD_A + "_") and source.name.endswith("_bold.nii.gz"):
                crop(source, dest)
            else:
                shutil.copy2(source, dest)
        else:
            original_meta = json.loads(source.read_text())
            meta = renamed(original_meta)
            meta["TaskName"] = "sharedreward"
            meta["RF1SourceRepair"] = {"id": ID, "original_filename": source.name,
                                      "retained_volume_indices": [0, 254] if "_bold." in source.name else None,
                                      "scheduled_behavior_design_run": 1}
            write_json(dest, meta)
            saved = json.loads(dest.read_text())
            for key in ("SliceTiming", "SliceEncodingDirection"):
                require((key in saved) == (key in original_meta) and
                        saved.get(key) == original_meta.get(key),
                        f"Repair changed run-local {key}")
    scans = target / f"{PREFIX}scans.tsv"
    with scans.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields, rows = reader.fieldnames, list(reader)
    require(fields and "filename" in fields, "Invalid scans table")
    kept = []
    for row in rows:
        if row["filename"].startswith("fmap/"):
            continue
        row["filename"] = renamed(row["filename"])
        require((target / row["filename"]).is_file(), "Stale scans.tsv filename")
        kept.append(row)
    require(len({r["filename"] for r in kept}) == len(kept), "Duplicate scans entries after mapping")
    with scans.open("w", newline="") as f:
        writer = csv.DictWriter(f, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept)
    require(convert_behavior("10668", "01", ["sharedreward"], behavior, staged_bids,
                             overwrite=True) == 0, "Reviewed event conversion failed")
    write_json(target / MARKER, {"id": ID, "status": "bids_corrected_derivatives_require_rebuild",
                                "behavior_sha256": SOURCE_HASHES,
                                "original_session_sha256": tree_hashes(original)})
    check_session(target)
    return target


def check_session(session):
    marker = json.loads((session / MARKER).read_text())
    require(marker["id"] == ID, "Incorrect repair marker")
    require(not list((session / "func").glob(OLD_A + "_*")), "Stale Trust run-2 entry")
    for run, series in ((1, 11), (2, 14)):
        stem = f"{PREFIX}task-sharedreward_run-{run}"
        for part, number in (("mag", series), ("phase", series + 1)):
            for echo in range(1, 5):
                base = session / "func" / f"{stem}_echo-{echo}_part-{part}_bold"
                image = nib.load(str(base) + ".nii.gz")
                require(image.shape[3] == 255, "Corrected run length mismatch")
                meta = json.loads(Path(str(base) + ".json").read_text())
                require(str(meta["SeriesNumber"]) == str(number) and meta["TaskName"] == "sharedreward",
                        "Corrected metadata mismatch")
        require((session / "func" / (stem + "_events.tsv")).is_file(), "Missing corrected events")


def derivative_paths(project):
    paths = [project / "derivatives" / name / "sub-10668" for name in
             ("fmriprep", "warpkit", "tedana", "mriqc", "fsl/confounds_tedana")]
    paths += list((project / "derivatives/fmriprep").glob("sub-10668*.html"))
    paths += list((project / "derivatives/mriqc").glob("sub-10668*.html"))
    return [p for p in paths if p.exists()]


def check_products(project):
    """Check temporal alignment after the ordinary subject-level rebuild."""
    session = project / "bids" / SESSION
    check_session(session)
    for run in (1, 2):
        stem = f"{PREFIX}task-sharedreward_run-{run}"
        func = project / "derivatives/fmriprep" / SESSION / "func"
        images = [func / f"{stem}_echo-{e}_part-mag_desc-preproc_bold.nii.gz" for e in range(1, 5)]
        images.append(func / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz")
        tedana = project / "derivatives/tedana" / SESSION
        images.append(tedana / f"{stem}_desc-denoised_bold.nii.gz")
        for path in images:
            require(path.is_file() and nib.load(path).shape[3] == 255,
                    f"Rebuilt image missing/wrong length: {path.name}")
        tables = [(func / f"{stem}_part-mag_desc-confounds_timeseries.tsv", True),
                  (tedana / f"{stem}_desc-ICA_mixing.tsv", True),
                  (project / "derivatives/fsl/confounds_tedana/sub-10668" / f"{stem}_desc-TedanaPlusConfounds.tsv", False)]
        for path, has_header in tables:
            with path.open(newline="") as f:
                reader = csv.reader(f, delimiter="\t")
                if has_header:
                    next(reader, None)
                rows = list(reader)
            require(len(rows) == 255,
                    f"Rebuilt confound rows mismatch: {path.name} (expected 255, found {len(rows)}; header={has_header})")
            require(rows[0] and all(len(row) == len(rows[0]) for row in rows),
                    f"Empty/ragged confound matrix: {path.name}")
            print(f"ALIGNED {path.name}: {len(rows)} data rows; header={has_header}")
    for path in derivative_paths(project):
        if path.is_dir():
            require(not list(path.rglob(OLD_A + "_*")), "Stale Trust-run-2 derivative remains")
    print("CHECK PASSED: both corrected Shared Reward runs have 255-volume image/confound alignment.")


def apply_live(project, inventory, behavior, apply):
    bids = project / "bids"
    session = bids / SESSION
    archive = project / "derivatives/source_repairs" / ID
    receipt = archive / "receipt.json"
    if receipt.exists():
        state = json.loads(receipt.read_text())
        require(state.get("status") == "complete", "Interrupted repair: preserve archive and inspect receipt; do not delete/retry")
        check_session(session)
        for rel, digest in state["corrected_files"].items():
            require((session / rel).is_file() and sha(session / rel) == digest, "Corrected file changed since repair")
        require(tree_hashes(archive / "original_session") == state["original_files"], "Original backup changed")
        print("CHECK PASSED: repaired BIDS and original backup verified; downstream rebuild is separate.")
        return
    require(not archive.exists(), "Archive already exists without complete receipt; inspect privately")
    require(not session.is_symlink(), "Refusing symlink session")
    require(not (project / "logs/locks/fmriprep-sub-10668.lock").exists(), "fMRIPrep lock exists; stop processing before repair")
    files = validate_original(bids, inventory, behavior)
    originals = tree_hashes(session)
    paths = derivative_paths(project)
    require(all(not p.is_symlink() for p in paths), "Refusing symlink derivative root")
    archive_parent = project / "derivatives"
    require(archive_parent.is_dir(), "Derivative root is missing")
    require(all(p.stat().st_dev == archive_parent.stat().st_dev for p in [session, *paths]),
            "Cross-filesystem archive requires a separately reviewed copy/install procedure")
    print(f"Validated original BIDS and behavior. Acquisition companions: {len(files)}")
    print("Plan: Trust run 2 -> Shared Reward run 1 [0:255]; old Shared Reward run 1 -> run 2.")
    for path in paths:
        print(f"ARCHIVE {path.relative_to(project)}")
    print("Preserve FreeSurfer anatomy; rebuild WarpKit/MRIQC/fMRIPrep/TEDANA/confounds for sub-10668.")
    if not apply:
        print("DRY RUN: no files changed. Stop all subject processing before --apply.")
        return
    archive.mkdir(parents=True)
    state = {"id": ID, "status": "staging", "original_files": originals,
             "inventory_sha256": sha(inventory), "behavior_sha256": SOURCE_HASHES,
             "retired": []}
    write_json(receipt, state)
    staged = build_stage(bids, archive / "staged_bids", files, behavior)
    corrected = tree_hashes(staged)
    require(tree_hashes(session) == originals, "Live inputs changed during staging")
    shutil.copytree(bids / ".heudiconv/10668/ses-01", archive / "original_heudiconv")
    state.update(status="retiring_derivatives", corrected_files=corrected)
    write_json(receipt, state)
    for path in paths:
        dest = archive / "retired" / path.relative_to(project)
        dest.parent.mkdir(parents=True, exist_ok=True)
        require(not path.is_symlink(), "Refusing symlink derivative root")
        path.rename(dest)
        state["retired"].append(str(path.relative_to(project)))
        write_json(receipt, state)
    state["status"] = "installing"
    write_json(receipt, state)
    session.rename(archive / "original_session")
    staged.rename(session)
    require(tree_hashes(archive / "original_session") == originals, "Original backup verification failed")
    state["status"] = "complete"
    write_json(receipt, state)
    check_session(session)
    print("CHECK PASSED: BIDS repair installed; original session and old derivatives preserved.")
    print("REBUILD REQUIRED: do not use old QC/analysis manifests; regenerate downstream products.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("repair", "check", "stage", "check-products"))
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--behavior-root", type=Path, required=True)
    parser.add_argument("--bids-root", type=Path, help="Fresh staging BIDS only (stage command)")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-idle", action="store_true", help="Confirm no jobs/readers are using sub-10668")
    parser.add_argument("--exclusions-root", type=Path,
                        default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"))
    args = parser.parse_args()
    require(args.exclusions_root.is_dir(), "Authoritative source-exclusion directory unavailable")
    require(not (args.exclusions_root / "Smith-SRA-10668").exists(), "10668 is source-excluded; repair refused")
    if args.command == "check-products":
        check_products(args.project_root)
        return 0
    if args.command == "stage":
        require(args.bids_root and args.apply, "stage requires --bids-root and --apply")
        require(args.bids_root.resolve() != (args.project_root / "bids").resolve(), "stage refuses canonical BIDS")
        files = validate_original(args.bids_root, args.inventory, args.behavior_root)
        with tempfile.TemporaryDirectory(dir=args.bids_root.parent) as temp:
            staged = build_stage(args.bids_root, Path(temp), files, args.behavior_root)
            # This is disposable prepdata staging; raw sources remain untouched.
            shutil.rmtree(args.bids_root / SESSION)
            shutil.copytree(staged, args.bids_root / SESSION)
        print("CHECK PASSED: fresh prepdata stage uses reviewed 10668 mapping.")
    else:
        require(not args.apply or args.confirm_idle, "Live --apply requires --confirm-idle after stopping subject processing")
        if args.command == "check":
            require((args.project_root / "derivatives/source_repairs" / ID / "receipt.json").is_file(),
                    "Live repair receipt missing")
        apply_live(args.project_root, args.inventory, args.behavior_root,
                   args.apply and args.command == "repair")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Do not leak private DICOM metadata from parser/IO exception contents.
        print(f"ERROR: 10668 repair stopped ({type(exc).__name__}). No automatic recovery; inspect privately.", file=sys.stderr)
        if isinstance(exc, RepairError):
            print(str(exc), file=sys.stderr)
        sys.exit(1)
