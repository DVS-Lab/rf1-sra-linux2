from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
spec = importlib.util.spec_from_file_location(
    "fmriprep_geometry", CODE_DIR / "fmriprep_geometry.py"
)
assert spec is not None and spec.loader is not None
geometry = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = geometry
spec.loader.exec_module(geometry)

nib = pytest.importorskip("nibabel")
np = pytest.importorskip("numpy")


def save_bold(
    root: Path,
    subject: str,
    task: str,
    run: str,
    affine,
    *,
    echo: str | None = None,
    shape: tuple[int, int, int, int] = (3, 4, 5, 2),
) -> Path:
    func = root / f"sub-{subject}" / "ses-01" / "func"
    func.mkdir(parents=True, exist_ok=True)
    echo_entity = f"_echo-{echo}_part-mag" if echo else ""
    path = (
        func / f"sub-{subject}_ses-01_task-{task}_run-{run}{echo_entity}"
        "_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
    )
    data = np.arange(np.prod(shape), dtype=np.float32).reshape(shape) + 1
    image = nib.Nifti1Image(data, affine)
    image.set_qform(affine, code=1)
    image.set_sform(affine, code=1)
    nib.save(image, path)
    return path


def make_standard_root(tmp_path: Path) -> Path:
    root = tmp_path / "project" / "derivatives" / "fmriprep"
    root.mkdir(parents=True)
    return root


def test_audit_finds_every_non_echo_sub_12013_outlier(tmp_path: Path) -> None:
    root = make_standard_root(tmp_path)
    modal_affine = np.diag([2.0, 2.0, 2.0, 1.0])
    outlier_affine = modal_affine.copy()
    outlier_affine[0, 3] = 1.0

    for subject, task, run in [
        ("11001", "doors", "1"),
        ("11002", "ugr", "1"),
        ("11003", "trust", "1"),
        ("11004", "sharedreward", "2"),
    ]:
        save_bold(root, subject, task, run, modal_affine)

    expected_12013 = {
        ("doors", "1"),
        ("sharedreward", "2"),
        ("ugr", "1"),
    }
    for task, run in sorted(expected_12013):
        save_bold(root, "12013", task, run, outlier_affine)

    # Echo-level outputs are intentionally outside the geometry-repair scope.
    save_bold(root, "12013", "ugr", "1", outlier_affine, echo="1")

    report = geometry.inspect_inventory(root, geometry.DEFAULT_AFFINE_ATOL)

    assert report["summary"] == {
        "candidate_count": 7,
        "modal_count": 4,
        "outlier_count": 3,
        "invalid_count": 0,
        "grid_count": 2,
    }
    outliers = [row for row in report["files"] if row["status"] == "outlier"]
    assert {row["subject"] for row in outliers} == {"12013"}
    assert {(row["task"], row["run"]) for row in outliers} == expected_12013
    assert all(row["sha256"] for row in outliers)
    assert "echo-1" not in "\n".join(row["relative_path"] for row in report["files"])


def test_audit_reports_invalid_3d_bold_without_using_it_as_mode(tmp_path: Path) -> None:
    root = make_standard_root(tmp_path)
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    save_bold(root, "11001", "doors", "1", affine)
    save_bold(root, "11002", "doors", "1", affine)
    save_bold(root, "12013", "doors", "1", affine, shape=(3, 4, 5))

    report = geometry.inspect_inventory(root, geometry.DEFAULT_AFFINE_ATOL)

    assert report["summary"]["modal_count"] == 2
    assert report["summary"]["invalid_count"] == 1
    invalid = next(row for row in report["files"] if row["status"] == "invalid")
    assert invalid["subject"] == "12013"
    assert "expected a 4D BOLD image" in invalid["reason"]


def test_dry_run_preflights_without_writing_backup_or_provenance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_standard_root(tmp_path)
    modal_affine = np.diag([2.0, 2.0, 2.0, 1.0])
    outlier_affine = modal_affine.copy()
    outlier_affine[1, 3] = 1.0
    save_bold(root, "11001", "doors", "1", modal_affine)
    save_bold(root, "11002", "doors", "1", modal_affine)
    save_bold(root, "12013", "doors", "1", outlier_affine)
    report = geometry.inspect_inventory(root, geometry.DEFAULT_AFFINE_ATOL)
    audit_json = tmp_path / "project" / "logs" / "geometry" / "audit.json"
    geometry.atomic_write_json(audit_json, report)

    args = argparse.Namespace(
        audit_json=audit_json,
        backup_root=None,
        provenance_root=None,
        image=tmp_path / "missing.simg",
        apptainer=None,
        apply=False,
    )
    assert geometry.run_repair(args) == 0

    backup_root, provenance_root = geometry.default_repair_roots(report, audit_json)
    assert not backup_root.exists()
    assert not provenance_root.exists()
    assert "DRY RUN" in capsys.readouterr().out


def test_ants_command_uses_4d_timeseries_mode_and_identity_transform(
    tmp_path: Path,
) -> None:
    command = geometry.ants_command(
        "apptainer",
        tmp_path / "fmriprep.simg",
        tmp_path / "project",
        tmp_path / "original.nii.gz",
        tmp_path / "reference.nii.gz",
        tmp_path / "identity.mat",
        tmp_path / "corrected.nii.gz",
    )

    assert command[command.index("--input-image-type") + 1] == "3"
    assert command[command.index("--dimensionality") + 1] == "3"
    assert command[command.index("--interpolation") + 1] == "LanczosWindowedSinc"
    assert command[command.index("--transform") + 1].endswith("identity.mat")


def test_apply_preserves_original_replaces_canonical_and_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_standard_root(tmp_path)
    modal_affine = np.diag([2.0, 2.0, 2.0, 1.0])
    outlier_affine = modal_affine.copy()
    outlier_affine[2, 3] = 1.0
    save_bold(root, "11001", "doors", "1", modal_affine)
    save_bold(root, "11002", "doors", "1", modal_affine)
    outlier = save_bold(root, "12013", "doors", "1", outlier_affine)
    original_sha = geometry.sha256_file(outlier)
    report = geometry.inspect_inventory(root, geometry.DEFAULT_AFFINE_ATOL)
    audit_json = tmp_path / "project" / "logs" / "geometry" / "audit.json"
    geometry.atomic_write_json(audit_json, report)
    image = tmp_path / "project" / "fmriprep.simg"
    image.write_text("synthetic container witness")

    real_run = subprocess.run

    def fake_run(command, *args, **kwargs):
        if command == ["fake-apptainer", "--version"]:
            return subprocess.CompletedProcess(
                command, 0, stdout="apptainer fake\n", stderr=""
            )
        if "antsApplyTransforms" in command:
            source = Path(command[command.index("--input") + 1])
            reference = Path(command[command.index("--reference-image") + 1])
            output = Path(command[command.index("--output") + 1])
            source_image = nib.load(source)
            reference_image = nib.load(reference)
            corrected = nib.Nifti1Image(
                np.asanyarray(source_image.dataobj), reference_image.affine
            )
            corrected.set_qform(reference_image.affine, code=1)
            corrected.set_sform(reference_image.affine, code=1)
            nib.save(corrected, output)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(geometry.subprocess, "run", fake_run)
    args = argparse.Namespace(
        audit_json=audit_json,
        backup_root=None,
        provenance_root=None,
        image=image,
        apptainer="fake-apptainer",
        apply=True,
    )

    assert geometry.run_repair(args) == 0
    backup_root, provenance_root = geometry.default_repair_roots(report, audit_json)
    relative = outlier.relative_to(root)
    backup = backup_root / relative
    provenance_path = geometry.per_file_provenance_path(provenance_root, relative)
    assert geometry.sha256_file(backup) == original_sha
    assert geometry.sha256_file(outlier) != original_sha
    assert geometry.geometries_match(
        geometry.inspect_geometry(outlier),
        geometry.geometry_from_dict(report["modal_grid"]),
        geometry.DEFAULT_AFFINE_ATOL,
    )
    provenance = json.loads(provenance_path.read_text())
    assert provenance["state"] == "complete"
    assert provenance["original_sha256"] == original_sha
    assert provenance["corrected_sha256"] == geometry.sha256_file(outlier)

    verify_args = argparse.Namespace(
        audit_json=audit_json,
        backup_root=None,
        provenance_root=None,
    )
    assert geometry.run_verify(verify_args) == 0


def test_repair_root_guard_rejects_bids_and_nonstandard_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nonstandard repair root"):
        geometry.ensure_standard_fmriprep_root(tmp_path / "derivatives" / "other")
    with pytest.raises(ValueError, match="inside BIDS"):
        geometry.ensure_standard_fmriprep_root(
            tmp_path / "bids" / "derivatives" / "fmriprep"
        )
