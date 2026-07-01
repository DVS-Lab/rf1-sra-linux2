from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from pipeline_utils import (  # noqa: E402
    atomic_write_json,
    choose_heuristic,
    collect_intended_for_updates,
    ensure_safe_child_path,
    fmriprep_expected_outputs,
    is_fmriprep_complete,
    is_tedana_complete,
    missing_paths,
    read_subject_list,
    runs_for_task,
    tasks_for_session,
    tedana_expected_outputs,
    warpkit_required_inputs,
)


def test_read_subject_list_ignores_blank_lines_comments_and_prefixes(tmp_path: Path) -> None:
    sublist = tmp_path / "subjects.txt"
    sublist.write_text("\n# comment\nsub-10001\n10002  # inline\n\n")
    assert read_subject_list(sublist) == ["10001", "10002"]


def test_session_task_and_run_selection() -> None:
    assert tasks_for_session("01") == ("ugr", "trust", "sharedreward", "doors", "socialdoors")
    assert tasks_for_session("02") == ("ugr", "doors", "socialdoors")
    assert runs_for_task("doors") == ("1",)
    assert runs_for_task("ugr") == ("1", "2")


def test_scanner_heuristic_selection_preserves_current_cutoff() -> None:
    assert choose_heuristic("01", date(2025, 3, 4)) == "heuristics_rf1.py"
    assert choose_heuristic("01", date(2025, 3, 5)) == "heuristics_XA30.py"
    assert choose_heuristic("01", date(2026, 1, 1), subject="11433") == "heuristics_rf1.py"
    assert choose_heuristic("02", date(2024, 1, 1)) == "heuristics_XA30.py"


def make_bids_run(root: Path, sub: str, ses: str, task: str, run: str, echoes: int = 4) -> None:
    func = root / sub / ses / "func"
    fmap = root / sub / ses / "fmap"
    func.mkdir(parents=True)
    fmap.mkdir(parents=True)
    for echo in range(1, echoes + 1):
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-mag_bold.nii.gz").write_text("nii")
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-phase_bold.nii.gz").write_text("nii")
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-phase_bold.json").write_text('{"EchoTime": 0.01}')
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-mag_bold.json").write_text('{"EchoTime": 0.01}')
    (fmap / f"{sub}_{ses}_acq-{task}_run-{run}_fieldmap.json").write_text(
        json.dumps({"TaskName": task, "IntendedFor": ["missing.nii.gz"]})
    )


def test_intended_for_generation_filters_missing_runs(tmp_path: Path) -> None:
    bids = tmp_path / "bids with spaces"
    make_bids_run(bids, "sub-10001", "ses-01", "ugr", "1")
    make_bids_run(bids, "sub-10001", "ses-02", "doors", "1", echoes=3)

    updates = collect_intended_for_updates(bids)
    ses1 = [u for u in updates if "ses-01" in u.json_path.as_posix()][0]
    ses2 = [u for u in updates if "ses-02" in u.json_path.as_posix()][0]

    assert len(ses1.intended_for) == 4
    assert all(Path(target).name.endswith("_part-mag_bold.nii.gz") for target in ses1.intended_for)
    assert len(ses2.intended_for) == 3


def test_atomic_write_json_replaces_metadata(tmp_path: Path) -> None:
    path = tmp_path / "fieldmap.json"
    path.write_text('{"Units": "rad/s"}')
    atomic_write_json(path, {"Units": "Hz", "IntendedFor": ["ses-01/func/a.nii.gz"]})
    assert json.loads(path.read_text())["Units"] == "Hz"
    assert not list(tmp_path.glob("*.tmp"))


def test_safe_child_path_refuses_root_and_outside(tmp_path: Path) -> None:
    root = tmp_path / "bids"
    root.mkdir()
    child = root / "sub-1"
    child.write_text("x")
    assert ensure_safe_child_path(root, child) == child.resolve()
    with pytest.raises(ValueError):
        ensure_safe_child_path(root, root)
    with pytest.raises(ValueError):
        ensure_safe_child_path(root, tmp_path / "outside")


def test_warpkit_manifest_detects_missing_echo(tmp_path: Path) -> None:
    func = tmp_path / "func"
    func.mkdir()
    required = warpkit_required_inputs(func, "10001", "01", "ugr", "1")
    for path in required[:-1]:
        path.write_text("x")
    assert missing_paths(required) == [required[-1]]


def test_fmriprep_completion_checks_expected_outputs(tmp_path: Path) -> None:
    bids = tmp_path / "bids"
    deriv = tmp_path / "derivatives"
    make_bids_run(bids, "sub-10001", "ses-01", "ugr", "1")
    expected = fmriprep_expected_outputs(bids, deriv, "10001")
    assert not is_fmriprep_complete(bids, deriv, "10001")
    for path in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    assert not is_fmriprep_complete(bids, deriv, "10001")
    fs_done = deriv / "freesurfer" / "sub-10001_ses-01" / "scripts" / "recon-all.done"
    fs_done.parent.mkdir(parents=True, exist_ok=True)
    fs_done.write_text("x")
    assert not is_fmriprep_complete(bids, deriv, "10001")
    cifti = (
        deriv
        / "fmriprep"
        / "sub-10001"
        / "ses-01"
        / "func"
        / "sub-10001_ses-01_task-ugr_run-1_space-fsLR_den-91k_bold.dtseries.nii"
    )
    cifti.write_text("x")
    assert is_fmriprep_complete(bids, deriv, "10001")


def test_tedana_completion_checks_outputs(tmp_path: Path) -> None:
    deriv = tmp_path / "derivatives"
    expected = tedana_expected_outputs(deriv, "10001", "01", "ugr", "1")
    assert not is_tedana_complete(deriv, "10001", "01", "ugr", "1")
    for path in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    assert is_tedana_complete(deriv, "10001", "01", "ugr", "1")
