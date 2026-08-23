from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
spec = importlib.util.spec_from_file_location(
    "fmriprep_mask_geometry", CODE_DIR / "fmriprep_mask_geometry.py"
)
assert spec is not None and spec.loader is not None
mask_geometry = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mask_geometry
spec.loader.exec_module(mask_geometry)

nib = pytest.importorskip("nibabel")
np = pytest.importorskip("numpy")
pytest.importorskip("scipy")


def standard_root(tmp_path: Path) -> Path:
    root = tmp_path / "project/derivatives/fmriprep"
    root.mkdir(parents=True)
    return root


def save_pair(root: Path, subject: str, mask_affine, mask_shape=(4, 5, 6)):
    func = root / f"sub-{subject}/ses-01/func"
    func.mkdir(parents=True)
    stem = f"sub-{subject}_ses-01_task-sharedreward_run-1_part-mag_space-MNI152NLin6Asym"
    bold = func / f"{stem}_desc-preproc_bold.nii.gz"
    mask = func / f"{stem}_desc-brain_mask.nii.gz"
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    bold_image = nib.Nifti1Image(
        np.ones((4, 5, 6, 3), dtype=np.float32), affine
    )
    bold_image.set_qform(affine, code=4)
    bold_image.set_sform(affine, code=4)
    nib.save(bold_image, bold)
    mask_image = nib.Nifti1Image(
        np.ones(mask_shape, dtype=np.uint8), mask_affine
    )
    mask_image.set_qform(mask_affine, code=4)
    mask_image.set_sform(mask_affine, code=4)
    nib.save(mask_image, mask)
    return bold, mask


def test_audit_and_repair_companion_mask_is_restartable(tmp_path: Path) -> None:
    root = standard_root(tmp_path)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    save_pair(root, "100", affine)
    _, mismatch = save_pair(root, "12013", affine, mask_shape=(3, 4, 5))
    original_sha = mask_geometry.bold_geometry.sha256_file(mismatch)

    report = mask_geometry.inspect_inventory(
        root, mask_geometry.bold_geometry.DEFAULT_AFFINE_ATOL
    )
    assert report["summary"] == {
        "candidate_count": 2,
        "match": 1,
        "mismatch": 1,
        "missing": 0,
        "invalid": 0,
    }
    mismatch_record = next(
        record for record in report["files"] if record["status"] == "mismatch"
    )
    assert mismatch_record["repair_type"] == "nearest_neighbor_resample"
    audit_json = tmp_path / "project/logs/geometry/masks.json"
    mask_geometry.bold_geometry.atomic_write_json(audit_json, report)
    args = argparse.Namespace(
        audit_json=audit_json,
        backup_root=None,
        provenance_root=None,
        apply=False,
    )
    assert mask_geometry.run_repair(args) == 0
    assert mask_geometry.bold_geometry.sha256_file(mismatch) == original_sha

    args.apply = True
    assert mask_geometry.run_repair(args) == 0
    corrected = mask_geometry.inspect_inventory(
        root, mask_geometry.bold_geometry.DEFAULT_AFFINE_ATOL
    )
    assert corrected["summary"]["mismatch"] == 0
    backup_root, provenance_root = mask_geometry.default_roots(report, audit_json)
    relative = mismatch.relative_to(root)
    backup = backup_root / relative
    provenance = mask_geometry.provenance_path(provenance_root, relative)
    assert mask_geometry.bold_geometry.sha256_file(backup) == original_sha
    metadata = json.loads(provenance.read_text())
    assert metadata["state"] == "complete"
    assert metadata["interpolation_order"] == 0
    data = np.asanyarray(nib.load(mismatch).dataobj)
    assert set(np.unique(data)).issubset({0, 1})

    # A restart verifies the corrected mask and performs no second interpolation.
    assert mask_geometry.run_repair(args) == 0
    verify = argparse.Namespace(
        audit_json=audit_json,
        backup_root=None,
        provenance_root=None,
    )
    assert mask_geometry.run_verify(verify) == 0


def test_xform_only_mismatch_preserves_mask_voxels(tmp_path: Path) -> None:
    root = standard_root(tmp_path)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    _, mask = save_pair(root, "100", affine)
    image = nib.load(mask)
    legacy = nib.Nifti1Image(
        np.asanyarray(image.dataobj), image.affine, image.header.copy()
    )
    legacy.set_qform(image.affine, code=1)
    legacy.set_sform(image.affine, code=1)
    nib.save(legacy, mask)
    expected = np.asanyarray(nib.load(mask).dataobj).copy()
    report = mask_geometry.inspect_inventory(
        root, mask_geometry.bold_geometry.DEFAULT_AFFINE_ATOL
    )
    record = report["files"][0]
    assert record["status"] == "mismatch"
    assert record["repair_type"] == "metadata_only"
    audit_json = tmp_path / "project/logs/geometry/xform.json"
    mask_geometry.bold_geometry.atomic_write_json(audit_json, report)
    args = argparse.Namespace(
        audit_json=audit_json,
        backup_root=None,
        provenance_root=None,
        apply=True,
    )
    assert mask_geometry.run_repair(args) == 0
    assert np.array_equal(np.asanyarray(nib.load(mask).dataobj), expected)
    _, provenance_root = mask_geometry.default_roots(report, audit_json)
    provenance = mask_geometry.provenance_path(
        provenance_root, mask.relative_to(root)
    )
    metadata = json.loads(provenance.read_text())
    assert metadata["voxel_data_equal"] is True
    assert metadata["interpolation_order"] is None


def test_missing_companion_mask_blocks_repair(tmp_path: Path) -> None:
    root = standard_root(tmp_path)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    _, mask = save_pair(root, "100", affine)
    mask.unlink()
    report = mask_geometry.inspect_inventory(
        root, mask_geometry.bold_geometry.DEFAULT_AFFINE_ATOL
    )
    assert report["summary"]["missing"] == 1
    audit_json = tmp_path / "project/logs/geometry/missing.json"
    mask_geometry.bold_geometry.atomic_write_json(audit_json, report)
    args = argparse.Namespace(
        audit_json=audit_json,
        backup_root=None,
        provenance_root=None,
        apply=False,
    )
    with pytest.raises(ValueError, match="missing/invalid"):
        mask_geometry.run_repair(args)
