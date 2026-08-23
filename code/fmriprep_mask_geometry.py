#!/usr/bin/env python3
"""Audit and repair fMRIPrep brain masks against canonical MNI BOLD grids."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import stat
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import fmriprep_geometry as bold_geometry


SCHEMA_VERSION = 1
REPORT_TYPE = "fmriprep_bold_brain_mask_geometry"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def companion_mask(bold: Path) -> Path:
    if not bold.name.endswith(bold_geometry.TARGET_SUFFIX):
        raise ValueError(f"not a canonical target BOLD: {bold}")
    return bold.with_name(
        bold.name.removesuffix(bold_geometry.TARGET_SUFFIX)
        + "_desc-brain_mask.nii.gz"
    )


def inspect_mask(path: Path) -> dict[str, Any]:
    nib, np = bold_geometry.imaging_modules()
    image = nib.load(str(path), mmap=True)
    shape = tuple(int(value) for value in image.shape)
    if len(shape) != 3:
        raise ValueError(f"expected a 3D brain mask, found shape {shape}")
    affine = np.asarray(image.affine, dtype=float)
    if affine.shape != (4, 4) or not np.isfinite(affine).all():
        raise ValueError("effective affine is not a finite 4x4 matrix")
    qform = np.asarray(image.get_qform(), dtype=float)
    sform = np.asarray(image.get_sform(), dtype=float)
    zooms = tuple(float(value) for value in image.header.get_zooms()[:3])
    return {
        "spatial_shape": shape,
        "zooms": zooms,
        "affine": affine.tolist(),
        "qform_code": int(image.header["qform_code"]),
        "sform_code": int(image.header["sform_code"]),
        "qform": qform.tolist(),
        "sform": sform.tolist(),
    }


def mask_grid_matches_bold(
    mask_info: dict[str, Any], bold_info: bold_geometry.Geometry, affine_atol: float
) -> bool:
    _, np = bold_geometry.imaging_modules()
    return (
        tuple(mask_info["spatial_shape"]) == bold_info.spatial_shape
        and np.allclose(
            mask_info["affine"], bold_info.affine, rtol=0.0, atol=affine_atol
        )
    )


def mask_xforms_match_bold(
    mask_info: dict[str, Any], bold_info: bold_geometry.Geometry, affine_atol: float
) -> bool:
    _, np = bold_geometry.imaging_modules()
    return (
        int(mask_info["qform_code"]) == bold_info.qform_code
        and int(mask_info["sform_code"]) == bold_info.sform_code
        and np.allclose(
            mask_info["qform"], bold_info.qform, rtol=0.0, atol=affine_atol
        )
        and np.allclose(
            mask_info["sform"], bold_info.sform, rtol=0.0, atol=affine_atol
        )
    )


def mask_matches_bold(
    mask_info: dict[str, Any], bold_info: bold_geometry.Geometry, affine_atol: float
) -> bool:
    return mask_grid_matches_bold(
        mask_info, bold_info, affine_atol
    ) and mask_xforms_match_bold(mask_info, bold_info, affine_atol)


def inspect_inventory(fmriprep_root: Path, affine_atol: float) -> dict[str, Any]:
    fmriprep_root = bold_geometry.ensure_standard_fmriprep_root(fmriprep_root)
    bolds = bold_geometry.discover_target_bolds(fmriprep_root)
    if not bolds:
        raise ValueError(f"no canonical MNI BOLD files found: {fmriprep_root}")
    records = []
    for bold in bolds:
        relative_bold = bold_geometry.safe_relative(fmriprep_root, bold)
        mask = companion_mask(bold)
        relative_mask = bold_geometry.safe_relative(fmriprep_root, mask)
        entities = bold_geometry.parse_entities(bold)
        record: dict[str, Any] = {
            "subject": entities.get("sub", ""),
            "session": entities.get("ses", ""),
            "task": entities.get("task", ""),
            "run": entities.get("run", ""),
            "bold_relative_path": str(relative_bold),
            "mask_relative_path": str(relative_mask),
            "status": "unchecked",
            "reason": "",
            "repair_type": "",
            "bold_geometry": None,
            "mask_geometry": None,
            "bold_sha256": "",
            "mask_sha256": "",
        }
        if not mask.is_file():
            record["status"] = "missing"
            record["reason"] = "companion brain mask does not exist"
            records.append(record)
            continue
        try:
            bold_info = bold_geometry.inspect_geometry(bold)
            mask_info = inspect_mask(mask)
            record["bold_geometry"] = asdict(bold_info)
            record["mask_geometry"] = mask_info
            if not mask_grid_matches_bold(mask_info, bold_info, affine_atol):
                record["status"] = "mismatch"
                record["repair_type"] = "nearest_neighbor_resample"
                record["reason"] = "mask spatial grid differs from BOLD"
            elif not mask_xforms_match_bold(mask_info, bold_info, affine_atol):
                record["status"] = "mismatch"
                record["repair_type"] = "metadata_only"
                record["reason"] = "mask qform/sform metadata differs from BOLD"
            else:
                record["status"] = "match"
            if record["status"] == "mismatch":
                record["bold_sha256"] = bold_geometry.sha256_file(bold)
                record["mask_sha256"] = bold_geometry.sha256_file(mask)
        except Exception as error:  # preserve per-file diagnostic in the audit
            record["status"] = "invalid"
            record["reason"] = str(error)
        records.append(record)
    counts = {
        status: sum(record["status"] == status for record in records)
        for status in ("match", "mismatch", "missing", "invalid")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "generated_at": utc_now(),
        "fmriprep_root": str(fmriprep_root),
        "affine_atol": affine_atol,
        "summary": {"candidate_count": len(records), **counts},
        "files": records,
    }


def report_paths(prefix: Path) -> tuple[Path, Path]:
    return prefix.with_suffix(".json"), prefix.with_suffix(".tsv")


def write_tsv(path: Path, report: dict[str, Any]) -> None:
    fields = (
        "status",
        "subject",
        "session",
        "task",
        "run",
        "bold_relative_path",
        "mask_relative_path",
        "bold_shape",
        "mask_shape",
        "repair_type",
        "reason",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for record in report["files"]:
            writer.writerow(
                {
                    **{field: record.get(field, "") for field in fields},
                    "bold_shape": "x".join(
                        str(value)
                        for value in (record.get("bold_geometry") or {}).get(
                            "spatial_shape", []
                        )
                    ),
                    "mask_shape": "x".join(
                        str(value)
                        for value in (record.get("mask_geometry") or {}).get(
                            "spatial_shape", []
                        )
                    ),
                }
            )


def load_audit(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text())
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported companion-mask audit schema")
    if report.get("report_type") != REPORT_TYPE:
        raise ValueError("not a fMRIPrep BOLD/brain-mask audit")
    return report


def default_roots(report: dict[str, Any], audit_json: Path) -> tuple[Path, Path]:
    root = bold_geometry.ensure_standard_fmriprep_root(Path(report["fmriprep_root"]))
    project_root = root.parent.parent
    audit_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", audit_json.stem)
    base = project_root / "derivatives" / "fmriprep_geometry"
    return base / "mask_originals" / audit_id, base / "mask_repairs" / audit_id


def provenance_path(provenance_root: Path, relative: Path) -> Path:
    name = relative.name.removesuffix(".nii.gz") + "_mask-geometry-repair.json"
    return provenance_root / "files" / relative.parent / name


def current_state(
    record: dict[str, Any], root: Path, backup_root: Path, provenance_root: Path,
    audit_sha256: str, affine_atol: float
) -> tuple[Path, Path, Path, Path, str]:
    bold = root / record["bold_relative_path"]
    mask = root / record["mask_relative_path"]
    relative_mask = Path(record["mask_relative_path"])
    backup = backup_root / relative_mask
    provenance = provenance_path(provenance_root, relative_mask)
    if bold_geometry.sha256_file(bold) != record["bold_sha256"]:
        raise ValueError(f"audited BOLD changed; run a new audit: {bold}")
    current_sha = bold_geometry.sha256_file(mask)
    if current_sha == record["mask_sha256"]:
        if backup.exists() and bold_geometry.sha256_file(backup) != current_sha:
            raise ValueError(f"existing mask backup checksum mismatch: {backup}")
        return bold, mask, backup, provenance, "pending"
    if not backup.is_file() or bold_geometry.sha256_file(backup) != record["mask_sha256"]:
        raise ValueError(f"changed mask lacks its verified original backup: {mask}")
    if not provenance.is_file():
        raise ValueError(f"changed mask lacks repair provenance: {provenance}")
    metadata = json.loads(provenance.read_text())
    if metadata.get("audit_sha256") != audit_sha256:
        raise ValueError(f"mask provenance does not match audit: {mask}")
    if metadata.get("corrected_sha256") != current_sha:
        raise ValueError(f"mask checksum does not match provenance: {mask}")
    bold_info = bold_geometry.inspect_geometry(bold)
    if not mask_matches_bold(inspect_mask(mask), bold_info, affine_atol):
        raise ValueError(f"changed mask still does not match BOLD: {mask}")
    return bold, mask, backup, provenance, "complete"


def preflight(
    report: dict[str, Any], audit_json: Path, backup_root: Path, provenance_root: Path
) -> list[tuple[dict[str, Any], Path, Path, Path, Path, str]]:
    root = bold_geometry.ensure_standard_fmriprep_root(Path(report["fmriprep_root"]))
    current = {
        str(bold_geometry.safe_relative(root, path))
        for path in bold_geometry.discover_target_bolds(root)
    }
    audited = {record["bold_relative_path"] for record in report["files"]}
    if current != audited:
        raise ValueError("fMRIPrep BOLD inventory changed; run a new mask audit")
    blockers = [
        record for record in report["files"]
        if record["status"] in {"missing", "invalid"}
    ]
    if blockers:
        raise ValueError(
            f"mask audit contains {len(blockers)} missing/invalid companion(s)"
        )
    affine_atol = float(report["affine_atol"])
    audit_sha = bold_geometry.sha256_file(audit_json)
    plan = []
    for record in report["files"]:
        bold = root / record["bold_relative_path"]
        mask = root / record["mask_relative_path"]
        if record["status"] == "match":
            if not mask_matches_bold(
                inspect_mask(mask), bold_geometry.inspect_geometry(bold), affine_atol
            ):
                raise ValueError(f"previously matching mask changed: {mask}")
            continue
        if record["status"] != "mismatch":
            raise ValueError(f"unrecognized audit status: {record['status']}")
        bold, mask, backup, provenance, state = current_state(
            record, root, backup_root, provenance_root, audit_sha, affine_atol
        )
        plan.append((record, bold, mask, backup, provenance, state))
    return plan


def resample_mask(source: Path, bold: Path, output: Path) -> dict[str, Any]:
    nib, np = bold_geometry.imaging_modules()
    try:
        from nibabel.processing import resample_from_to
    except ImportError as error:
        raise RuntimeError(f"nibabel.processing/scipy is required: {error}") from error
    source_image = nib.load(str(source), mmap=True)
    bold_image = nib.load(str(bold), mmap=True)
    target = (bold_image.shape[:3], bold_image.affine)
    resampled = resample_from_to(
        source_image, target, order=0, mode="constant", cval=0.0
    )
    data = (np.asanyarray(resampled.dataobj) > 0).astype(np.uint8)
    if not np.any(data):
        raise ValueError(f"resampled brain mask is empty: {source}")
    header = source_image.header.copy()
    header.set_data_dtype(np.uint8)
    corrected = nib.Nifti1Image(data, bold_image.affine, header)
    corrected.set_qform(
        bold_image.get_qform(), code=int(bold_image.header["qform_code"])
    )
    corrected.set_sform(
        bold_image.get_sform(), code=int(bold_image.header["sform_code"])
    )
    nib.save(corrected, str(output))
    if not mask_matches_bold(
        inspect_mask(output), bold_geometry.inspect_geometry(bold),
        bold_geometry.DEFAULT_AFFINE_ATOL,
    ):
        raise ValueError(f"corrected mask does not exactly match BOLD: {output}")
    return {
        "method": "nibabel.processing.resample_from_to",
        "interpolation_order": 0,
        "binary_threshold": ">0",
        "nonzero_voxels": int(np.count_nonzero(data)),
    }


def normalize_mask_metadata(source: Path, bold: Path, output: Path) -> dict[str, Any]:
    nib, np = bold_geometry.imaging_modules()
    source_image = nib.load(str(source), mmap=True)
    bold_image = nib.load(str(bold), mmap=True)
    source_data = np.asanyarray(source_image.dataobj)
    header = source_image.header.copy()
    corrected = nib.Nifti1Image(source_data, bold_image.affine, header)
    corrected.set_qform(
        bold_image.get_qform(), code=int(bold_image.header["qform_code"])
    )
    corrected.set_sform(
        bold_image.get_sform(), code=int(bold_image.header["sform_code"])
    )
    nib.save(corrected, str(output))
    if not mask_matches_bold(
        inspect_mask(output), bold_geometry.inspect_geometry(bold),
        bold_geometry.DEFAULT_AFFINE_ATOL,
    ):
        raise ValueError(f"metadata-normalized mask does not match BOLD: {output}")
    if not np.array_equal(np.asanyarray(nib.load(str(output)).dataobj), source_data):
        raise ValueError(f"metadata normalization changed mask voxels: {source}")
    return {
        "method": "nibabel qform/sform copy from corresponding BOLD",
        "interpolation_order": None,
        "voxel_data_equal": True,
        "nonzero_voxels": int(np.count_nonzero(source_data)),
    }


def run_audit(args: argparse.Namespace) -> int:
    root = bold_geometry.ensure_standard_fmriprep_root(args.fmriprep_root)
    report = inspect_inventory(root, args.affine_atol)
    prefix = args.report_prefix
    if prefix is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = root.parent.parent / "logs/geometry" / f"fmriprep-mask-{stamp}"
    json_path, tsv_path = report_paths(prefix.expanduser().resolve())
    if json_path.exists() or tsv_path.exists():
        raise ValueError("refusing to replace a frozen companion-mask audit")
    bold_geometry.atomic_write_json(json_path, report)
    write_tsv(tsv_path, report)
    summary = report["summary"]
    print(f"BOLD/mask pairs: {summary['candidate_count']}")
    for status in ("match", "mismatch", "missing", "invalid"):
        print(f"{status.title()}: {summary[status]}")
    for record in report["files"]:
        if record["status"] != "match":
            print(
                f"{record['status'].upper()} sub-{record['subject']} "
                f"ses-{record['session']} task-{record['task']} "
                f"run-{record['run']}: {record['reason']}"
            )
    print(f"JSON report: {json_path}")
    print(f"TSV report: {tsv_path}")
    problems = summary["mismatch"] + summary["missing"] + summary["invalid"]
    if args.fail_on_mismatch and problems:
        return 1
    return 2 if summary["missing"] or summary["invalid"] else 0


def run_repair(args: argparse.Namespace) -> int:
    audit_json = args.audit_json.expanduser().resolve()
    report = load_audit(audit_json)
    defaults = default_roots(report, audit_json)
    backup_root = (args.backup_root or defaults[0]).expanduser().resolve()
    provenance_root = (args.provenance_root or defaults[1]).expanduser().resolve()
    root = bold_geometry.ensure_standard_fmriprep_root(Path(report["fmriprep_root"]))
    project_root = root.parent.parent
    for target in (backup_root, provenance_root):
        bold_geometry.safe_relative(project_root, target)
        bold_geometry.refuse_bids_path(project_root, target)
        if target == root or root in target.parents:
            raise ValueError(f"backup/provenance cannot be inside fMRIPrep: {target}")
    plan = preflight(report, audit_json, backup_root, provenance_root)
    pending = [item for item in plan if item[-1] == "pending"]
    complete = [item for item in plan if item[-1] == "complete"]
    print(f"Audited mismatches: {len(plan)}")
    print(f"Pending mask repairs: {len(pending)}")
    print(f"Already repaired and verified: {len(complete)}")
    for record, _, mask, _, _, state in plan:
        print(f"{state.upper()} sub-{record['subject']}: {mask}")
    if not args.apply:
        print("DRY RUN: no masks were copied, resampled, or replaced.")
        return 0
    audit_sha = bold_geometry.sha256_file(audit_json)
    completed_count = len(complete)
    for record, bold, mask, backup, provenance, state in plan:
        if state == "complete":
            continue
        bold_geometry.copy_original(mask, backup, record["mask_sha256"])
        descriptor, temporary_name = tempfile.mkstemp(
            dir=mask.parent,
            prefix=f".{mask.name}.mask-geometry-repair.",
            suffix=".nii.gz",
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            if record["repair_type"] == "nearest_neighbor_resample":
                details = resample_mask(backup, bold, temporary)
            elif record["repair_type"] == "metadata_only":
                details = normalize_mask_metadata(backup, bold, temporary)
            else:
                raise ValueError(
                    f"unrecognized mask repair type: {record['repair_type']}"
                )
            os.chmod(temporary, stat.S_IMODE(mask.stat().st_mode))
            corrected_sha = bold_geometry.sha256_file(temporary)
            metadata = {
                "schema_version": SCHEMA_VERSION,
                "state": "prepared",
                "prepared_at": utc_now(),
                "audit_json": str(audit_json),
                "audit_sha256": audit_sha,
                "bold_path": str(bold),
                "bold_sha256": record["bold_sha256"],
                "canonical_mask_path": str(mask),
                "backup_path": str(backup),
                "original_sha256": record["mask_sha256"],
                "corrected_sha256": corrected_sha,
                "original_geometry": record["mask_geometry"],
                "corrected_geometry": inspect_mask(temporary),
                **details,
            }
            bold_geometry.atomic_write_json(provenance, metadata)
            bold_geometry.fsync_file(temporary)
            os.replace(temporary, mask)
            bold_geometry.fsync_directory(mask.parent)
            metadata["state"] = "complete"
            metadata["completed_at"] = utc_now()
            bold_geometry.atomic_write_json(provenance, metadata)
            completed_count += 1
            print(f"REPAIRED MASK {mask}")
        finally:
            temporary.unlink(missing_ok=True)
    final = inspect_inventory(root, float(report["affine_atol"]))
    summary = final["summary"]
    if summary["mismatch"] or summary["missing"] or summary["invalid"]:
        raise ValueError(f"post-repair companion-mask audit failed: {summary}")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "completed_at": utc_now(),
        "audit_json": str(audit_json),
        "audit_sha256": audit_sha,
        "fmriprep_root": str(root),
        "backup_root": str(backup_root),
        "provenance_root": str(provenance_root),
        "mismatch_count": len(plan),
        "completed_count": completed_count,
    }
    bold_geometry.atomic_write_json(
        provenance_root / "mask-repair-manifest.json", manifest
    )
    print(
        f"CHECK PASSED: all {summary['candidate_count']} canonical BOLD/brain-mask "
        "pairs have identical spatial grids and qform/sform metadata."
    )
    return 0


def run_verify(args: argparse.Namespace) -> int:
    audit_json = args.audit_json.expanduser().resolve()
    report = load_audit(audit_json)
    defaults = default_roots(report, audit_json)
    plan = preflight(
        report,
        audit_json,
        (args.backup_root or defaults[0]).expanduser().resolve(),
        (args.provenance_root or defaults[1]).expanduser().resolve(),
    )
    incomplete = [item for item in plan if item[-1] != "complete"]
    if incomplete:
        for _, _, mask, _, _, state in incomplete:
            print(f"CHECK FAILED: {state}: {mask}")
        return 1
    current = inspect_inventory(
        Path(report["fmriprep_root"]), float(report["affine_atol"])
    )
    summary = current["summary"]
    if summary["mismatch"] or summary["missing"] or summary["invalid"]:
        return 1
    print(
        f"CHECK PASSED: all {summary['candidate_count']} canonical BOLD/brain-mask "
        f"pairs match; {len(plan)} repaired mask(s) and provenance verified."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit")
    audit.add_argument(
        "--fmriprep-root", type=Path,
        default=project_root / "derivatives/fmriprep"
    )
    audit.add_argument("--report-prefix", type=Path)
    audit.add_argument(
        "--affine-atol", type=float, default=bold_geometry.DEFAULT_AFFINE_ATOL
    )
    audit.add_argument("--fail-on-mismatch", action="store_true")
    audit.set_defaults(func=run_audit)
    for name, function in (("repair", run_repair), ("verify", run_verify)):
        command = subparsers.add_parser(name)
        command.add_argument("--audit-json", type=Path, required=True)
        command.add_argument("--backup-root", type=Path)
        command.add_argument("--provenance-root", type=Path)
        if name == "repair":
            command.add_argument("--apply", action="store_true")
        command.set_defaults(func=function)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "affine_atol", bold_geometry.DEFAULT_AFFINE_ATOL) <= 0:
        parser.error("--affine-atol must be positive")
    try:
        return int(args.func(args))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
