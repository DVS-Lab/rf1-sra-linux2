#!/usr/bin/env python3
"""Audit, repair, and verify post-fMRIPrep volumetric BOLD geometry.

Only non-echo, 4D, MNI152NLin6Asym ``desc-preproc_bold`` NIfTIs under
``derivatives/fmriprep`` are in scope. The repair command consumes a frozen
audit report, preserves each original, resamples through the pinned fMRIPrep
container, validates the result, and atomically replaces the canonical
fMRIPrep path. Pristine BIDS data are never read as repair targets or written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TARGET_SPACE = "MNI152NLin6Asym"
TARGET_SUFFIX = "_desc-preproc_bold.nii.gz"
DEFAULT_AFFINE_ATOL = 1e-5
ENTITY_RE = re.compile(r"(?:^|_)(sub|ses|task|run)-([^_]+)")


def imaging_modules():
    """Import imaging dependencies only when image access is requested."""
    try:
        import nibabel as nib  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "nibabel and numpy are required. On Linux2 use "
            "/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/python."
        ) from exc
    return nib, np


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_target_bold(path: Path) -> bool:
    name = path.name
    return (
        path.parent.name == "func"
        and name.endswith(TARGET_SUFFIX)
        and f"_space-{TARGET_SPACE}" in name
        and "_echo-" not in name
    )


def discover_target_bolds(fmriprep_root: Path) -> list[Path]:
    return sorted(
        path
        for path in fmriprep_root.rglob(f"*{TARGET_SUFFIX}")
        if path.is_file() and is_target_bold(path)
    )


def parse_entities(path: Path) -> dict[str, str]:
    return {key: value for key, value in ENTITY_RE.findall(path.name)}


def ensure_standard_fmriprep_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.name != "fmriprep" or resolved.parent.name != "derivatives":
        raise ValueError(
            "Refusing nonstandard repair root; expected .../derivatives/fmriprep, "
            f"got {resolved}"
        )
    if "bids" in {part.lower() for part in resolved.parts}:
        raise ValueError(f"Refusing a repair root inside BIDS: {resolved}")
    return resolved


def safe_relative(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Path is outside {resolved_root}: {resolved_path}") from exc
    if not relative.parts:
        raise ValueError(f"Expected a child of {resolved_root}, got the root itself")
    return relative


def refuse_bids_path(project_root: Path, path: Path) -> None:
    bids_root = (project_root / "bids").resolve()
    resolved = path.resolve()
    if resolved == bids_root or bids_root in resolved.parents:
        raise ValueError(f"Refusing to write under pristine BIDS: {resolved}")


def fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class Geometry:
    spatial_shape: tuple[int, int, int]
    full_shape: tuple[int, ...]
    n_volumes: int
    zooms: tuple[float, float, float]
    temporal_spacing: float
    affine: tuple[tuple[float, ...], ...]
    orientation: str
    qform_code: int
    sform_code: int
    qform: tuple[tuple[float, ...], ...]
    sform: tuple[tuple[float, ...], ...]


@dataclass
class ImageRecord:
    relative_path: str
    subject: str
    session: str
    task: str
    run: str
    size_bytes: int
    mtime_ns: int
    geometry: Geometry | None
    status: str = "unclassified"
    reason: str = ""
    xform_status: str = "unchecked"
    xform_reason: str = ""
    sha256: str = ""


def inspect_geometry(path: Path) -> Geometry:
    nib, np = imaging_modules()
    image = nib.load(str(path), mmap=True)
    shape = tuple(int(value) for value in image.shape)
    if len(shape) != 4:
        raise ValueError(f"expected a 4D BOLD image, found shape {shape}")
    affine_array = np.asarray(image.affine, dtype=float)
    if affine_array.shape != (4, 4) or not np.isfinite(affine_array).all():
        raise ValueError("effective affine is not a finite 4x4 matrix")
    all_zooms = tuple(float(value) for value in image.header.get_zooms())
    zooms = all_zooms[:3]
    if len(zooms) != 3 or any(not np.isfinite(value) or value <= 0 for value in zooms):
        raise ValueError(f"invalid spatial zooms: {zooms}")
    temporal_spacing = all_zooms[3]
    if not np.isfinite(temporal_spacing) or temporal_spacing <= 0:
        raise ValueError(f"invalid temporal spacing: {temporal_spacing}")
    orientation = "".join(value or "?" for value in nib.aff2axcodes(affine_array))
    qform_code = int(image.header["qform_code"])
    sform_code = int(image.header["sform_code"])
    qform = np.asarray(image.get_qform(), dtype=float)
    sform = np.asarray(image.get_sform(), dtype=float)
    return Geometry(
        spatial_shape=shape[:3],
        full_shape=shape,
        n_volumes=shape[3],
        zooms=zooms,
        temporal_spacing=temporal_spacing,
        affine=tuple(tuple(float(value) for value in row) for row in affine_array),
        orientation=orientation,
        qform_code=qform_code,
        sform_code=sform_code,
        qform=tuple(tuple(float(value) for value in row) for row in qform),
        sform=tuple(tuple(float(value) for value in row) for row in sform),
    )


def geometries_match(left: Geometry, right: Geometry, affine_atol: float) -> bool:
    _, np = imaging_modules()
    return left.spatial_shape == right.spatial_shape and bool(
        np.allclose(left.affine, right.affine, rtol=0.0, atol=affine_atol)
    )


def xform_metadata_match(
    left: Geometry, right: Geometry, affine_atol: float
) -> bool:
    """Require the modal qform/sform matrices and their NIfTI intent codes."""
    _, np = imaging_modules()
    return (
        left.qform_code == right.qform_code
        and left.sform_code == right.sform_code
        and bool(
            np.allclose(left.qform, right.qform, rtol=0.0, atol=affine_atol)
        )
        and bool(
            np.allclose(left.sform, right.sform, rtol=0.0, atol=affine_atol)
        )
    )


def modal_cluster(
    records: Sequence[ImageRecord], affine_atol: float
) -> tuple[list[ImageRecord], list[list[ImageRecord]]]:
    clusters: list[list[ImageRecord]] = []
    for record in records:
        if record.geometry is None:
            continue
        for cluster in clusters:
            representative = cluster[0]
            assert representative.geometry is not None
            if geometries_match(record.geometry, representative.geometry, affine_atol):
                cluster.append(record)
                break
        else:
            clusters.append([record])
    if not clusters:
        raise ValueError("no valid 4D image grids were available to define a mode")
    clusters.sort(key=lambda cluster: (-len(cluster), cluster[0].relative_path))
    if len(clusters) > 1 and len(clusters[0]) == len(clusters[1]):
        raise ValueError(
            "grid mode is tied; refusing to choose a repair target without review"
        )
    return clusters[0], clusters


def inspect_inventory(fmriprep_root: Path, affine_atol: float) -> dict[str, Any]:
    paths = discover_target_bolds(fmriprep_root)
    if not paths:
        raise ValueError(
            f"no non-echo {TARGET_SPACE} volumetric preprocessed BOLD files found "
            f"under {fmriprep_root}"
        )

    records: list[ImageRecord] = []
    for path in paths:
        entities = parse_entities(path)
        relative = safe_relative(fmriprep_root, path)
        file_stat = path.stat()
        record = ImageRecord(
            relative_path=str(relative),
            subject=entities.get("sub", ""),
            session=entities.get("ses", ""),
            task=entities.get("task", ""),
            run=entities.get("run", ""),
            size_bytes=file_stat.st_size,
            mtime_ns=file_stat.st_mtime_ns,
            geometry=None,
        )
        try:
            record.geometry = inspect_geometry(path)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - preserve per-file imaging diagnostics.
            record.status = "invalid"
            record.reason = str(exc)
        records.append(record)

    modal_records, clusters = modal_cluster(records, affine_atol)
    modal_reference = modal_records[0]
    assert modal_reference.geometry is not None
    for record in records:
        if record.geometry is None:
            continue
        if geometries_match(record.geometry, modal_reference.geometry, affine_atol):
            record.status = "modal"
            if xform_metadata_match(
                record.geometry, modal_reference.geometry, affine_atol
            ):
                record.xform_status = "modal"
            else:
                record.xform_status = "mismatch"
                record.xform_reason = (
                    "qform/sform matrix and/or intent code differs from modal metadata"
                )
        else:
            record.status = "outlier"
            record.xform_status = "not_applicable"
            record.reason = (
                "spatial shape and/or effective affine differs from modal grid"
            )

    outliers = [record for record in records if record.status == "outlier"]
    invalid = [record for record in records if record.status == "invalid"]
    modal = [record for record in records if record.status == "modal"]
    xform_mismatches = [
        record for record in records if record.xform_status == "mismatch"
    ]

    # Hash only repair inputs and the modal witness. Reading every 4D image in a
    # large cohort would turn this header audit into an unnecessary data scan.
    modal_reference.sha256 = sha256_file(fmriprep_root / modal_reference.relative_path)
    for record in outliers:
        record.sha256 = sha256_file(fmriprep_root / record.relative_path)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "target": {
            "space": TARGET_SPACE,
            "suffix": TARGET_SUFFIX,
            "echo_policy": "exclude filenames containing _echo-",
            "dimensionality": "4D volumetric NIfTI only",
        },
        "fmriprep_root": str(fmriprep_root),
        "affine_atol": affine_atol,
        "summary": {
            "candidate_count": len(records),
            "modal_count": len(modal),
            "outlier_count": len(outliers),
            "invalid_count": len(invalid),
            "grid_count": len(clusters),
            "xform_metadata_mismatch_count": len(xform_mismatches),
        },
        "modal_grid": asdict(modal_reference.geometry),
        "modal_reference": {
            "relative_path": modal_reference.relative_path,
            "sha256": modal_reference.sha256,
        },
        "files": [record_to_dict(record) for record in records],
    }


def record_to_dict(record: ImageRecord) -> dict[str, Any]:
    result = asdict(record)
    if record.geometry is not None:
        result["geometry"] = asdict(record.geometry)
    return result


def geometry_from_dict(data: dict[str, Any]) -> Geometry:
    affine = tuple(
        tuple(float(value) for value in row) for row in data["affine"]
    )
    return Geometry(
        spatial_shape=tuple(int(value) for value in data["spatial_shape"]),
        full_shape=tuple(int(value) for value in data["full_shape"]),
        n_volumes=int(data["n_volumes"]),
        zooms=tuple(float(value) for value in data["zooms"]),
        temporal_spacing=float(data["temporal_spacing"]),
        affine=affine,
        orientation=str(data["orientation"]),
        qform_code=int(data["qform_code"]),
        sform_code=int(data["sform_code"]),
        # Schema-1 audit reports written before transform-metadata validation
        # did not retain these matrices. fMRIPrep's modal qform and sform both
        # encode the effective affine, so the frozen affine is the safe fallback.
        qform=tuple(
            tuple(float(value) for value in row)
            for row in data.get("qform", affine)
        ),
        sform=tuple(
            tuple(float(value) for value in row)
            for row in data.get("sform", affine)
        ),
    )


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def write_audit_tsv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "status",
        "xform_status",
        "subject",
        "session",
        "task",
        "run",
        "relative_path",
        "spatial_shape",
        "n_volumes",
        "zooms",
        "orientation",
        "affine",
        "sha256",
        "reason",
        "xform_reason",
    ]
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for record in report["files"]:
            geometry = record.get("geometry") or {}
            writer.writerow(
                {
                    "status": record["status"],
                    "xform_status": record.get("xform_status", "unchecked"),
                    "subject": record["subject"],
                    "session": record["session"],
                    "task": record["task"],
                    "run": record["run"],
                    "relative_path": record["relative_path"],
                    "spatial_shape": json.dumps(geometry.get("spatial_shape", [])),
                    "n_volumes": geometry.get("n_volumes", ""),
                    "zooms": json.dumps(geometry.get("zooms", [])),
                    "orientation": geometry.get("orientation", ""),
                    "affine": json.dumps(geometry.get("affine", [])),
                    "sha256": record.get("sha256", ""),
                    "reason": record.get("reason", ""),
                    "xform_reason": record.get("xform_reason", ""),
                }
            )
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def report_paths(prefix: Path) -> tuple[Path, Path]:
    if prefix.suffix in {".json", ".tsv"}:
        prefix = prefix.with_suffix("")
    return Path(f"{prefix}.json"), Path(f"{prefix}.tsv")


def print_audit_summary(
    report: dict[str, Any], json_path: Path, tsv_path: Path
) -> None:
    summary = report["summary"]
    grid = report["modal_grid"]
    print(f"Audited: {summary['candidate_count']} file(s)")
    print(
        "Modal grid: "
        f"shape={tuple(grid['spatial_shape'])} zooms={tuple(grid['zooms'])} "
        f"orientation={grid['orientation']} ({summary['modal_count']} file(s))"
    )
    print(f"Modal affine: {json.dumps(grid['affine'])}")
    print(f"Outliers: {summary['outlier_count']}")
    print(
        "qform/sform metadata mismatches: "
        f"{summary.get('xform_metadata_mismatch_count', 0)}"
    )
    print(f"Invalid: {summary['invalid_count']}")
    for record in report["files"]:
        if record["status"] in {"outlier", "invalid"}:
            print(
                f"{record['status'].upper()} sub-{record['subject']} "
                f"ses-{record['session']} task-{record['task']} run-{record['run']}: "
                f"{record['relative_path']} ({record['reason']})"
            )
        elif record.get("xform_status") == "mismatch":
            print(
                f"XFORM MISMATCH sub-{record['subject']} "
                f"ses-{record['session']} task-{record['task']} run-{record['run']}: "
                f"{record['relative_path']} ({record['xform_reason']})"
            )
    print(f"JSON report: {json_path}")
    print(f"TSV report: {tsv_path}")
    print(
        "AUDIT COMPLETE: "
        f"{summary['candidate_count']} file(s), {summary['outlier_count']} outlier(s), "
        f"{summary['invalid_count']} invalid file(s), "
        f"{summary.get('xform_metadata_mismatch_count', 0)} xform metadata mismatch(es)."
    )


def load_audit(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text())
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported audit schema {report.get('schema_version')}; expected {SCHEMA_VERSION}"
        )
    required = {"fmriprep_root", "modal_grid", "modal_reference", "files", "summary"}
    missing = sorted(required - report.keys())
    if missing:
        raise ValueError(f"audit report lacks required keys: {', '.join(missing)}")
    return report


def default_repair_roots(report: dict[str, Any], audit_json: Path) -> tuple[Path, Path]:
    fmriprep_root = ensure_standard_fmriprep_root(Path(report["fmriprep_root"]))
    project_root = fmriprep_root.parent.parent
    audit_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", audit_json.stem)
    base = project_root / "derivatives" / "fmriprep_geometry"
    return base / "originals" / audit_id, base / "repairs" / audit_id


def copy_original(source: Path, backup: Path, expected_sha256: str) -> None:
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        if sha256_file(backup) != expected_sha256:
            raise ValueError(f"existing backup checksum mismatch: {backup}")
        return
    with tempfile.NamedTemporaryFile(
        dir=backup.parent, prefix=f".{backup.name}.", suffix=".nii.gz", delete=False
    ) as handle:
        temp_path = Path(handle.name)
    try:
        shutil.copy2(source, temp_path)
        if sha256_file(temp_path) != expected_sha256:
            raise ValueError(f"backup checksum mismatch after copying {source}")
        fsync_file(temp_path)
        os.replace(temp_path, backup)
        fsync_directory(backup.parent)
    finally:
        temp_path.unlink(missing_ok=True)


def write_reference_image(path: Path, geometry: Geometry) -> None:
    nib, np = imaging_modules()
    path.parent.mkdir(parents=True, exist_ok=True)
    image = nib.Nifti1Image(
        np.zeros(geometry.spatial_shape, dtype=np.uint8), np.asarray(geometry.affine)
    )
    image.set_qform(np.asarray(geometry.affine), code=max(geometry.qform_code, 1))
    image.set_sform(np.asarray(geometry.affine), code=max(geometry.sform_code, 1))
    nib.save(image, str(path))


def normalize_xform_metadata(
    path: Path, target_geometry: Geometry, affine_atol: float
) -> dict[str, Any]:
    """Atomically copy the modal qform/sform matrices and intent codes.

    ANTs correctly resamples onto the reference lattice but writes generic
    scanner-anatomical transform codes. Rewriting through nibabel changes only
    the derivative file; the caller validates geometry, timing, and voxel data
    before the canonical path is replaced.
    """
    nib, np = imaging_modules()
    before = inspect_geometry(path)
    if xform_metadata_match(before, target_geometry, affine_atol):
        return {"changed": False, "before": asdict(before), "after": asdict(before)}

    image = nib.load(str(path), mmap=True)
    header = image.header.copy()
    corrected = nib.Nifti1Image(
        image.dataobj, np.asarray(target_geometry.affine, dtype=float), header
    )
    corrected.set_qform(
        np.asarray(target_geometry.qform, dtype=float),
        code=target_geometry.qform_code,
    )
    corrected.set_sform(
        np.asarray(target_geometry.sform, dtype=float),
        code=target_geometry.sform_code,
    )

    mode = stat.S_IMODE(path.stat().st_mode)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.xform-metadata.",
        suffix=".nii.gz",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
    try:
        nib.save(corrected, str(temp_path))
        os.chmod(temp_path, mode)
        fsync_file(temp_path)
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        temp_path.unlink(missing_ok=True)

    after = inspect_geometry(path)
    if not xform_metadata_match(after, target_geometry, affine_atol):
        raise ValueError(f"failed to normalize qform/sform metadata: {path}")
    return {"changed": True, "before": asdict(before), "after": asdict(after)}


def write_identity_transform(path: Path) -> None:
    path.write_text(
        "#Insight Transform File V1.0\n"
        "#Transform 0\n"
        "Transform: AffineTransform_double_3_3\n"
        "Parameters: 1 0 0 0 1 0 0 0 1 0 0 0\n"
        "FixedParameters: 0 0 0\n"
    )


def ants_command(
    apptainer: str,
    image: Path,
    project_root: Path,
    source: Path,
    reference: Path,
    identity_transform: Path,
    output: Path,
) -> list[str]:
    return [
        apptainer,
        "exec",
        "--cleanenv",
        "--bind",
        f"{project_root}:{project_root}",
        str(image),
        "antsApplyTransforms",
        "--dimensionality",
        "3",
        "--input-image-type",
        "3",
        "--float",
        "1",
        "--input",
        str(source),
        "--reference-image",
        str(reference),
        "--output",
        str(output),
        "--interpolation",
        "LanczosWindowedSinc",
        "--transform",
        str(identity_transform),
    ]


def validate_resampled(
    path: Path, source_geometry: Geometry, target_geometry: Geometry, affine_atol: float
) -> dict[str, Any]:
    _, np = imaging_modules()
    geometry = inspect_geometry(path)
    if not geometries_match(geometry, target_geometry, affine_atol):
        raise ValueError(f"resampled output does not match modal grid: {path}")
    if not xform_metadata_match(geometry, target_geometry, affine_atol):
        raise ValueError(
            f"resampled output qform/sform metadata does not match modal grid: {path}"
        )
    if geometry.n_volumes != source_geometry.n_volumes:
        raise ValueError(
            f"volume count changed from {source_geometry.n_volumes} to {geometry.n_volumes}: {path}"
        )
    if abs(geometry.temporal_spacing - source_geometry.temporal_spacing) > 1e-6:
        raise ValueError(
            "temporal spacing changed from "
            f"{source_geometry.temporal_spacing} to {geometry.temporal_spacing}: {path}"
        )
    nib, _ = imaging_modules()
    image = nib.load(str(path), mmap=True)
    nonzero = False
    for volume_index in range(geometry.n_volumes):
        volume = np.asanyarray(image.dataobj[..., volume_index])
        if not np.isfinite(volume).all():
            raise ValueError(
                f"non-finite values in output volume {volume_index}: {path}"
            )
        if not nonzero and np.any(volume != 0):
            nonzero = True
    if not nonzero:
        raise ValueError(f"resampled output contains only zeros: {path}")
    return {"geometry": asdict(geometry), "sha256": sha256_file(path)}


def outlier_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [record for record in report["files"] if record["status"] == "outlier"]


def invalid_records(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [record for record in report["files"] if record["status"] == "invalid"]


def per_file_provenance_path(provenance_root: Path, relative: Path) -> Path:
    name = relative.name.removesuffix(".nii.gz") + "_geometry-repair.json"
    return provenance_root / "files" / relative.parent / name


def existing_repair_state(
    canonical: Path,
    backup: Path,
    provenance_path: Path,
    record: dict[str, Any],
    target_geometry: Geometry,
    affine_atol: float,
    audit_sha256: str,
) -> str:
    expected_original = record["sha256"]
    current_sha = sha256_file(canonical)
    if current_sha == expected_original:
        if backup.exists() and sha256_file(backup) != expected_original:
            raise ValueError(f"backup checksum mismatch: {backup}")
        return "pending"
    if not backup.exists() or sha256_file(backup) != expected_original:
        raise ValueError(
            f"canonical file changed since audit and no verified original backup exists: {canonical}"
        )
    current_geometry = inspect_geometry(canonical)
    if not geometries_match(current_geometry, target_geometry, affine_atol):
        raise ValueError(
            f"changed canonical file still has a nonmodal grid: {canonical}"
        )
    if current_geometry.n_volumes != int(record["geometry"]["n_volumes"]):
        raise ValueError(
            f"changed canonical file has an unexpected volume count: {canonical}"
        )
    if not provenance_path.exists():
        raise ValueError(f"repaired file lacks provenance: {provenance_path}")
    provenance = json.loads(provenance_path.read_text())
    if provenance.get("audit_sha256") != audit_sha256:
        raise ValueError(
            f"repair provenance does not match the frozen audit: {canonical}"
        )
    if provenance.get("corrected_sha256") != current_sha:
        raise ValueError(
            f"repaired-file checksum does not match provenance: {canonical}"
        )
    if not xform_metadata_match(current_geometry, target_geometry, affine_atol):
        return "metadata_pending"
    return "complete"


def preflight_repair(
    report: dict[str, Any], audit_json: Path, backup_root: Path, provenance_root: Path
) -> list[tuple[dict[str, Any], Path, Path, Path, str]]:
    if invalid_records(report):
        raise ValueError(
            "audit contains invalid images; resolve them before geometry repair"
        )
    fmriprep_root = ensure_standard_fmriprep_root(Path(report["fmriprep_root"]))
    target_geometry = geometry_from_dict(report["modal_grid"])
    affine_atol = float(report["affine_atol"])
    audit_sha256 = sha256_file(audit_json)
    audited_by_path = {record["relative_path"]: record for record in report["files"]}
    current_paths = discover_target_bolds(fmriprep_root)
    current_relative = {
        str(safe_relative(fmriprep_root, path)) for path in current_paths
    }
    audited_relative = set(audited_by_path)
    if current_relative != audited_relative:
        added = sorted(current_relative - audited_relative)
        removed = sorted(audited_relative - current_relative)
        raise ValueError(
            "fMRIPrep inventory changed since audit; run a new audit before repair "
            f"(added={added[:5]}, removed={removed[:5]})"
        )
    for relative, record in audited_by_path.items():
        if record["status"] != "modal":
            continue
        current_geometry = inspect_geometry(fmriprep_root / relative)
        if not geometries_match(current_geometry, target_geometry, affine_atol):
            raise ValueError(
                f"a modal file changed grid since audit; run a new audit: {relative}"
            )
    reference = fmriprep_root / report["modal_reference"]["relative_path"]
    if sha256_file(reference) != report["modal_reference"]["sha256"]:
        raise ValueError(f"modal reference changed since audit: {reference}")

    plan = []
    for record in outlier_records(report):
        relative = Path(record["relative_path"])
        canonical = fmriprep_root / relative
        safe_relative(fmriprep_root, canonical)
        if not canonical.is_file():
            raise ValueError(f"audited outlier is missing: {canonical}")
        backup = backup_root / relative
        provenance = per_file_provenance_path(provenance_root, relative)
        state = existing_repair_state(
            canonical,
            backup,
            provenance,
            record,
            target_geometry,
            affine_atol,
            audit_sha256,
        )
        plan.append((record, canonical, backup, provenance, state))
    return plan


def run_repair(args: argparse.Namespace) -> int:
    audit_json = args.audit_json.expanduser().resolve()
    report = load_audit(audit_json)
    default_backup, default_provenance = default_repair_roots(report, audit_json)
    backup_root = (args.backup_root or default_backup).expanduser().resolve()
    provenance_root = (
        (args.provenance_root or default_provenance).expanduser().resolve()
    )
    fmriprep_root = ensure_standard_fmriprep_root(Path(report["fmriprep_root"]))
    project_root = fmriprep_root.parent.parent
    for root in (backup_root, provenance_root):
        safe_relative(project_root, root)
        refuse_bids_path(project_root, root)
        if root == fmriprep_root or fmriprep_root in root.parents:
            raise ValueError(
                f"backup/provenance root cannot be inside fMRIPrep outputs: {root}"
            )

    plan = preflight_repair(report, audit_json, backup_root, provenance_root)
    pending = [item for item in plan if item[-1] in {"pending", "metadata_pending"}]
    complete = [item for item in plan if item[-1] == "complete"]
    print(f"Audit outliers: {len(plan)}")
    print(f"Pending repair: {len(pending)}")
    print(f"Already repaired and verified: {len(complete)}")
    print(f"Original backup root: {backup_root}")
    print(f"Provenance root: {provenance_root}")
    for record, canonical, _, _, state in plan:
        print(f"{state.upper()} sub-{record['subject']}: {canonical}")
    if not args.apply:
        print(
            "DRY RUN: no files were copied, resampled, or replaced. Add --apply after review."
        )
        return 0
    if not pending:
        print(
            "REPAIR COMPLETE: all audited outliers were already repaired and verified."
        )
        return 0

    apptainer = (
        args.apptainer or os.environ.get("APPTAINER") or shutil.which("apptainer")
    )
    if not apptainer:
        raise ValueError(
            "Apptainer executable not found; set APPTAINER or use --apptainer"
        )
    image = args.image.expanduser().resolve()
    if not image.is_file():
        raise ValueError(f"fMRIPrep image not found: {image}")

    target_geometry = geometry_from_dict(report["modal_grid"])
    affine_atol = float(report["affine_atol"])
    provenance_root.mkdir(parents=True, exist_ok=True)
    reference_image = provenance_root / "modal_grid_reference.nii.gz"
    # The suffix controls ITK transform reader selection. This is Insight text,
    # so using .mat would incorrectly invoke MatlabTransformIO.
    identity_transform = provenance_root / "identity_3d.txt"
    write_reference_image(reference_image, target_geometry)
    write_identity_transform(identity_transform)

    tool_info = {
        "apptainer": subprocess.run(
            [apptainer, "--version"], check=True, text=True, capture_output=True
        ).stdout.strip(),
        "image": str(image),
        "image_sha256": sha256_file(image),
        "image_size_bytes": image.stat().st_size,
        "image_mtime_ns": image.stat().st_mtime_ns,
    }
    completed_count = len(complete)
    audit_sha256 = sha256_file(audit_json)
    for record, canonical, backup, provenance_path, state in plan:
        if state == "complete":
            continue
        source_geometry = (
            inspect_geometry(canonical)
            if state == "metadata_pending"
            else geometry_from_dict(record["geometry"])
        )
        copy_original(canonical, backup, record["sha256"])
        canonical.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=canonical.parent,
            prefix=f".{canonical.name}.geometry-repair.",
            suffix=".nii.gz",
        )
        os.close(fd)
        temp_output = Path(temp_name)
        temp_output.unlink(missing_ok=True)
        command: list[str]
        try:
            if state == "metadata_pending":
                command = [
                    "nibabel",
                    "copy-modal-qform-sform",
                    str(canonical),
                ]
                print(f"NORMALIZE XFORMS: {canonical}")
                shutil.copy2(canonical, temp_output)
            else:
                command = ants_command(
                    apptainer,
                    image,
                    project_root,
                    backup,
                    reference_image,
                    identity_transform,
                    temp_output,
                )
                print("RUN:", " ".join(command))
                subprocess.run(command, check=True)
            xform_normalization = normalize_xform_metadata(
                temp_output, target_geometry, affine_atol
            )
            validation = validate_resampled(
                temp_output, source_geometry, target_geometry, affine_atol
            )
            os.chmod(temp_output, stat.S_IMODE(canonical.stat().st_mode))
            if state == "metadata_pending":
                provenance = json.loads(provenance_path.read_text())
                provenance["pre_xform_normalization_sha256"] = sha256_file(canonical)
                provenance["xform_metadata_normalization"] = {
                    "normalized_at": utc_now(),
                    "method": "nibabel qform/sform copy from frozen modal grid",
                    **xform_normalization,
                }
            else:
                provenance = {
                    "schema_version": SCHEMA_VERSION,
                    "audit_json": str(audit_json),
                    "audit_sha256": audit_sha256,
                    "canonical_path": str(canonical),
                    "backup_path": str(backup),
                    "original_sha256": record["sha256"],
                    "original_geometry": record["geometry"],
                    "modal_grid": report["modal_grid"],
                    "interpolation": "LanczosWindowedSinc",
                    "transform": "identity physical-space affine",
                    "command": command,
                    "tool": tool_info,
                    "xform_metadata_normalization": xform_normalization,
                }
            provenance.update(
                {
                    "state": "prepared",
                    "prepared_at": utc_now(),
                    "corrected_sha256": validation["sha256"],
                    "corrected_geometry": validation["geometry"],
                }
            )
            atomic_write_json(provenance_path, provenance)
            fsync_file(temp_output)
            os.replace(temp_output, canonical)
            fsync_directory(canonical.parent)
            provenance["state"] = "complete"
            provenance["completed_at"] = utc_now()
            atomic_write_json(provenance_path, provenance)
            completed_count += 1
            print(f"REPAIRED {canonical}")
        finally:
            temp_output.unlink(missing_ok=True)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "completed_at": utc_now(),
        "audit_json": str(audit_json),
        "audit_sha256": audit_sha256,
        "fmriprep_root": str(fmriprep_root),
        "backup_root": str(backup_root),
        "provenance_root": str(provenance_root),
        "outlier_count": len(plan),
        "completed_count": completed_count,
        "tool": tool_info,
    }
    atomic_write_json(provenance_root / "repair-manifest.json", manifest)
    print(f"Repair manifest: {provenance_root / 'repair-manifest.json'}")
    print(
        f"REPAIR COMPLETE: {completed_count}/{len(plan)} audited outlier(s) verified."
    )
    return 0


def run_verify(args: argparse.Namespace) -> int:
    audit_json = args.audit_json.expanduser().resolve()
    report = load_audit(audit_json)
    default_backup, default_provenance = default_repair_roots(report, audit_json)
    backup_root = (args.backup_root or default_backup).expanduser().resolve()
    provenance_root = (
        (args.provenance_root or default_provenance).expanduser().resolve()
    )
    plan = preflight_repair(report, audit_json, backup_root, provenance_root)
    incomplete = [item for item in plan if item[-1] != "complete"]
    if incomplete:
        for _, canonical, _, _, state in incomplete:
            print(f"CHECK FAILED: {state} geometry repair: {canonical}")
        return 1

    fmriprep_root = ensure_standard_fmriprep_root(Path(report["fmriprep_root"]))
    current = inspect_inventory(fmriprep_root, float(report["affine_atol"]))
    summary = current["summary"]
    if (
        summary["outlier_count"]
        or summary["invalid_count"]
        or summary.get("xform_metadata_mismatch_count", 0)
    ):
        for record in current["files"]:
            if record["status"] != "modal":
                print(f"CHECK FAILED: {record['status']}: {record['relative_path']}")
            elif record.get("xform_status") == "mismatch":
                print(
                    "CHECK FAILED: xform metadata mismatch: "
                    f"{record['relative_path']}"
                )
        return 1
    print(
        "CHECK PASSED: "
        f"{summary['candidate_count']} non-echo {TARGET_SPACE} BOLD file(s) share the "
        f"modal grid and qform/sform metadata; {len(plan)} repaired original(s) "
        "and provenance record(s) verified."
    )
    return 0


def run_audit(args: argparse.Namespace) -> int:
    fmriprep_root = ensure_standard_fmriprep_root(args.fmriprep_root)
    report = inspect_inventory(fmriprep_root, args.affine_atol)
    prefix = args.report_prefix
    if prefix is None:
        project_root = fmriprep_root.parent.parent
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = project_root / "logs" / "geometry" / f"fmriprep-geometry-{stamp}"
    json_path, tsv_path = report_paths(prefix.expanduser().resolve())
    project_root = fmriprep_root.parent.parent
    refuse_bids_path(project_root, json_path)
    refuse_bids_path(project_root, tsv_path)
    if any(fmriprep_root in path.parents for path in (json_path, tsv_path)):
        raise ValueError(
            "refusing to write audit reports inside canonical fMRIPrep outputs"
        )
    existing_reports = [path for path in (json_path, tsv_path) if path.exists()]
    if existing_reports:
        raise ValueError(
            "refusing to replace a frozen audit report: "
            + ", ".join(str(path) for path in existing_reports)
        )
    atomic_write_json(json_path, report)
    write_audit_tsv(tsv_path, report)
    print_audit_summary(report, json_path, tsv_path)
    summary = report["summary"]
    if summary["invalid_count"]:
        return 2
    if args.fail_on_outliers and (
        summary["outlier_count"]
        or summary.get("xform_metadata_mismatch_count", 0)
    ):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser(
        "audit", help="Read headers and write a cohort geometry report"
    )
    audit.add_argument(
        "--fmriprep-root",
        type=Path,
        default=project_root / "derivatives" / "fmriprep",
    )
    audit.add_argument("--report-prefix", type=Path)
    audit.add_argument("--affine-atol", type=float, default=DEFAULT_AFFINE_ATOL)
    audit.add_argument("--fail-on-outliers", action="store_true")
    audit.set_defaults(func=run_audit)

    repair = subparsers.add_parser(
        "repair", help="Plan or apply repairs from a frozen audit"
    )
    repair.add_argument("--audit-json", type=Path, required=True)
    repair.add_argument("--backup-root", type=Path)
    repair.add_argument("--provenance-root", type=Path)
    repair.add_argument(
        "--image",
        type=Path,
        default=Path("/ZPOOL/data/tools/fmriprep-25.2.5.simg"),
    )
    repair.add_argument("--apptainer")
    repair.add_argument(
        "--apply",
        action="store_true",
        help="Copy originals, resample, validate, and atomically replace canonical files",
    )
    repair.set_defaults(func=run_repair)

    verify = subparsers.add_parser(
        "verify",
        help="Verify canonical grids, preserved originals, and repair provenance",
    )
    verify.add_argument("--audit-json", type=Path, required=True)
    verify.add_argument("--backup-root", type=Path)
    verify.add_argument("--provenance-root", type=Path)
    verify.set_defaults(func=run_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "affine_atol", DEFAULT_AFFINE_ATOL) <= 0:
        parser.error("--affine-atol must be positive")
    try:
        return int(args.func(args))
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
