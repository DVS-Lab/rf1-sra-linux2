import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))
spec = importlib.util.spec_from_file_location("complete_11935_repair", CODE / "complete_11935_repair.py")
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def fs_fixture(tmp_path, subject_id='sub-11935_ses-01'):
    production = tmp_path / 'production'
    destination = production / 'work/repair/sub-11935-project'
    destination.mkdir(parents=True)
    source = production / 'derivatives/freesurfer' / subject_id
    for name in ['scripts/recon-all.done', 'mri/aparc+aseg.mgz', 'mri/brain.mgz',
                 *[f'surf/{hemi}.{surface}' for hemi in ('lh', 'rh')
                   for surface in ('white', 'pial', 'sphere.reg')]]:
        file = source / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(name)
    return production, destination, source


@pytest.mark.parametrize('subject_id', ['sub-11935', 'sub-11935_ses-01'])
def test_freesurfer_preserves_real_name_and_existing_bytes(tmp_path, subject_id):
    production, destination, source = fs_fixture(tmp_path, subject_id)
    before = repair.reviewed.signatures([source])
    target = repair.stage_freesurfer(production, destination, True)
    assert target.name == subject_id and target.is_dir() and not target.is_symlink()
    assert before == repair.reviewed.signatures([source])
    staged = repair.reviewed.signatures([target, destination / 'freesurfer-copy.json'])
    repair.stage_freesurfer(production, destination, True)
    repair.stage_freesurfer(production, destination, False)
    assert staged == repair.reviewed.signatures([target, destination / 'freesurfer-copy.json'])
    assert all((target / p.relative_to(source)).read_bytes() == p.read_bytes()
               for p in source.rglob('*') if p.is_file())


@pytest.mark.parametrize('damage', ['missing', 'ambiguous', 'running', 'source_changed', 'copy_changed'])
def test_freesurfer_refuses_incomplete_or_changed_anatomy(tmp_path, damage):
    production, destination, source = fs_fixture(tmp_path)
    if damage == 'missing':
        (source / 'surf/lh.white').unlink()
    elif damage == 'ambiguous':
        (source.parent / 'sub-11935').mkdir()
    elif damage == 'running':
        (source / 'scripts/IsRunning.lh+rh').touch()
    else:
        target = repair.stage_freesurfer(production, destination, True)
        bad = source if damage == 'source_changed' else target
        (bad / 'mri/brain.mgz').write_text('changed')
    with pytest.raises(ValueError):
        repair.stage_freesurfer(production, destination, True)


def test_freesurfer_file_link_becomes_independent_copy(tmp_path):
    production, destination, source = fs_fixture(tmp_path)
    link = source / 'mri/linked.mgz'
    link.symlink_to(source / 'mri/brain.mgz')
    target = repair.stage_freesurfer(production, destination, True)
    assert not (target / 'mri/linked.mgz').is_symlink()
    assert (target / 'mri/linked.mgz').read_bytes() == link.read_bytes()


def test_freesurfer_check_never_creates_missing_copy(tmp_path):
    production, destination, _ = fs_fixture(tmp_path)
    with pytest.raises(ValueError, match='receipt missing'):
        repair.stage_freesurfer(production, destination, False)
    assert not (destination / 'derivatives').exists()


def test_freesurfer_resumes_partial_copy_without_overwriting(tmp_path, monkeypatch):
    production, destination, source = fs_fixture(tmp_path)
    copy = repair.reviewed.copy_shared_file
    calls = []
    def interrupted(src, dst):
        calls.append(src)
        if len(calls) == 3:
            raise OSError('interrupted')
        copy(src, dst)
    monkeypatch.setattr(repair.reviewed, 'copy_shared_file', interrupted)
    with pytest.raises(OSError, match='interrupted'):
        repair.stage_freesurfer(production, destination, True)
    target = destination / 'derivatives/freesurfer' / source.name
    before = repair.reviewed.signatures([target])
    monkeypatch.setattr(repair.reviewed, 'copy_shared_file', copy)
    repair.stage_freesurfer(production, destination, True)
    after = repair.reviewed.signatures([target])
    assert all(after[k] == v for k, v in before.items())


@pytest.mark.parametrize("name,expected", [
    ("sub-11935_ses-01_task-doors_run-1.warpkit_done", True),
    ("sub-11935_ses-01_task-socialdoors_run-1_echo-1_part-mag_bold.nii.gz", True),
    ("sub-11935_ses-01_task-ugr_run-1_echo-1_part-mag_bold.nii.gz", False),
    ("sub-11935_ses-02_task-socialdoors_run-1_echo-1_part-mag_bold.nii.gz", False),
    ("sub-11935_ses-01_task-socialdoors_run-10_echo-1_part-mag_bold.nii.gz", False),
    ("sub-11936_ses-01_task-socialdoors_run-1_echo-1_part-mag_bold.nii.gz", False),
])
def test_exact_target_scope(name, expected):
    assert repair.target_file(name) is expected


def test_full_command_is_two_run_backport_not_cohort_upgrade(tmp_path):
    args = SimpleNamespace(image=tmp_path / "fmriprep-25.2.5.simg", templateflow=tmp_path / "tf",
                           licenses=tmp_path / "licenses", jobs=8)
    command = repair.fmriprep_command(args, tmp_path, "/installed/niworkflows/func/util.py")
    assert f"{tmp_path}/patch/util.py:/installed/niworkflows/func/util.py:ro" in command
    assert "--fs-no-resume" in command and "anatomy=/out/anatomy" in command
    assert command[command.index("--random-seed") + 1] == "20261021"
    assert command[command.index("--omp-nthreads") + 1] == "1"
    assert "--cifti-output" in command and "fsLR" in command
    assert "--bids-filter-file" in command
    assert repair.filter_spec()["bold"]["task"] == ["doors", "socialdoors"]
    assert repair.filter_spec()["sbref"]["run"] == "1"


def test_pruning_archives_only_unrelated_isolated_files(tmp_path, monkeypatch):
    func = tmp_path / "bids/sub-11935/ses-01/func"
    func.mkdir(parents=True)
    good = func / "sub-11935_ses-01_task-socialdoors_run-1_echo-1_part-mag_bold.nii.gz"
    other = func / "sub-11935_ses-01_task-ugr_run-1_echo-1_part-mag_bold.nii.gz"
    good.write_bytes(b"good")
    other.write_bytes(b"other")
    table = func.parent / "sub-11935_ses-01_scans.tsv"
    table.write_text(f"filename\tacq_time\nfunc/{good.name}\tshifted1\nfunc/{other.name}\tshifted2\n")
    monkeypatch.setattr(repair.reviewed, "validate_bids", lambda *a: None)
    repair.prune_conversion(tmp_path)
    assert good.read_bytes() == b"good"
    assert not other.exists()
    assert (tmp_path / "converted-not-promoted" / other.relative_to(tmp_path)).read_bytes() == b"other"
    assert "task-ugr" not in table.read_text()


def test_publishable_does_not_install_anatomy_or_other_runs(tmp_path):
    func = tmp_path / "derivatives/fmriprep/sub-11935/ses-01/func"
    func.mkdir(parents=True)
    good = func / "sub-11935_ses-01_task-doors_run-1_part-mag_desc-brain_mask.nii.gz"
    other = func / "sub-11935_ses-01_task-trust_run-1_part-mag_desc-brain_mask.nii.gz"
    good.write_bytes(b"new mask")
    other.write_bytes(b"preserve")
    fs = tmp_path / "derivatives/freesurfer/sub-11935/mri"
    fs.mkdir(parents=True)
    (fs / "brain.mgz").write_bytes(b"anatomy")
    files = repair.publishable_files(tmp_path)
    assert list(files) == [str(good.relative_to(tmp_path))]


def test_publishable_rejects_symlink(tmp_path):
    func = tmp_path / "bids/sub-11935/ses-01/func"
    func.mkdir(parents=True)
    source = tmp_path / "source"
    source.write_bytes(b"data")
    (func / "sub-11935_ses-01_task-doors_run-1_events.tsv").symlink_to(source)
    with pytest.raises(ValueError, match="symlinks"):
        repair.publishable_files(tmp_path)


def test_backport_is_exact_tested_source(tmp_path, monkeypatch):
    args = SimpleNamespace(image=tmp_path / "image", templateflow=tmp_path / "tf", licenses=tmp_path / "lic")
    args.image.write_bytes(b"container")
    source = "def init_enhance_and_skullstrip_bold_wf():\n    transform=('Affine', 0.1),\n    name='init_aff'\n"
    info = dict(module="/installed/util.py", source=source, fmriprep="25.2.5", niworkflows="1.14.4")
    monkeypatch.setattr(repair.subprocess, "check_output", lambda *a, **kw: json.dumps(info))
    with pytest.raises(ValueError, match="differs from paired tests"):
        repair.stage_patch(args, tmp_path)


def test_publishable_preserves_matched_derivative_fieldmap(tmp_path):
    folder = tmp_path / "derivatives/fmriprep/sub-11935/ses-01/fmap"
    folder.mkdir(parents=True)
    good = folder / "sub-11935_ses-01_acq-doors_run-1_fmapid-auto00000_desc-coeff_fieldmap.nii.gz"
    other = folder / "sub-11935_ses-01_acq-ugr_run-1_fmapid-auto00000_desc-coeff_fieldmap.nii.gz"
    good.write_bytes(b"matched fieldmap")
    other.write_bytes(b"unrelated")
    assert list(repair.publishable_files(tmp_path)) == [str(good.relative_to(tmp_path))]


def test_repair_metadata_is_idempotent_and_detects_different_patch(tmp_path):
    folder = tmp_path / "derivatives/fmriprep/sub-11935/ses-01/func"
    folder.mkdir(parents=True)
    file = folder / "sub-11935_ses-01_task-doors_run-1_part-mag_desc-coreg_boldref.json"
    file.write_text(json.dumps({"Sources": ["original source"]}))
    patch = dict(patched_sha256="patch1", image_sha256="container1")
    repair.annotate_derivatives(tmp_path, patch)
    before = file.stat().st_mtime_ns
    repair.annotate_derivatives(tmp_path, patch)
    assert file.stat().st_mtime_ns == before
    assert json.loads(file.read_text())["Sources"] == ["original source"]
    with pytest.raises(ValueError, match="provenance differs"):
        repair.annotate_derivatives(tmp_path, dict(patched_sha256="different", image_sha256="container1"))
