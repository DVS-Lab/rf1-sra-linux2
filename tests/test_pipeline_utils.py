from __future__ import annotations

import json
import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
CODE_DIR = Path(__file__).resolve().parents[1] / "code"

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


def load_heuristic(name: str):
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), CODE_DIR / name)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_add_intended_for():
    spec = importlib.util.spec_from_file_location("add_intended_for", CODE_DIR / "addIntendedFor.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_gen_tedana_confounds():
    pytest.importorskip("pandas")
    spec = importlib.util.spec_from_file_location("gen_tedana_confounds", CODE_DIR / "genTedanaConfounds.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_make_repair_runlists():
    spec = importlib.util.spec_from_file_location("make_repair_runlists", CODE_DIR / "make_repair_runlists.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_read_subject_list_ignores_blank_lines_comments_and_prefixes(tmp_path: Path) -> None:
    sublist = tmp_path / "subjects.txt"
    sublist.write_text("\n# comment\nsub-10001\n10002  # inline\n\n")
    assert read_subject_list(sublist) == ["10001", "10002"]


def test_tedana_confound_sublist_filter_accepts_prefixed_and_plain_ids(tmp_path: Path) -> None:
    module = load_gen_tedana_confounds()
    sublist = tmp_path / "subjects.txt"
    sublist.write_text("sub-11923\n11924\n")
    assert module.subject_filter_from_sublist(sublist) == {"sub-11923", "sub-11924"}


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


def test_repair_runlists_report_missing_required_sources(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    scans = tmp_path / "Smith-SRA-10002" / "Smith-SRA-10002" / "scans" / "1-T1w" / "resources" / "DICOM" / "files"
    scans.mkdir(parents=True)
    (scans / "image.dcm").write_text("dicom")

    assert module.missing_required_sources(tmp_path, ["10001", "10002"]) == {"10001"}


def test_repair_runlists_accept_11891_nested_source_layout(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    scans = tmp_path / "11891" / "Smith-SRA-11891" / "Smith-SRA-11891" / "scans" / "1-T1w" / "resources" / "DICOM" / "files"
    scans.mkdir(parents=True)
    (scans / "image.dcm").write_text("dicom")

    assert module.source_has_dicoms(tmp_path, "11891")
    assert module.missing_required_sources(tmp_path, ["11891"]) == set()


def test_repair_runlists_report_excluded_sources(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    (tmp_path / "Smith-SRA-10001").mkdir()

    assert module.excluded_sources(tmp_path, ["10001", "10002"]) == {"10001"}
    assert module.excluded_sources(tmp_path / "missing", ["10001"]) == set()


@pytest.mark.parametrize("heuristic_name", ["heuristics_rf1.py", "heuristics_XA30.py"])
@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/scans/10-T1w/resources/DICOM/files/example.dcm", True),
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/scans/20-Trust/resources/DICOM/files/example.dcm", True),
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/scans/1-localizer/resources/DICOM/files/example.dcm", False),
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/scans/27-LOCALIZER/resources/DICOM/files/example.dcm", False),
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/scans/99-PhoenixZIPReport/resources/DICOM/files/example.dcm", False),
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/scans/99-pHoEnIxZiPrEpOrT/resources/DICOM/files/example.dcm", False),
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/scans/30-localizer_corrected_T1/resources/DICOM/files/example.dcm", True),
        ("/sourcedata/Smith-SRA-11922/Smith-SRA-11922/not-scans/1-localizer/resources/DICOM/files/example.dcm", True),
        ("/sourcedata/localizer_notes/Smith-SRA-11922/scans/10-T1w/resources/DICOM/files/example.dcm", True),
    ],
)
def test_heuristic_filter_files_skips_only_scanner_generated_scan_dirs(heuristic_name: str, filename: str, expected: bool) -> None:
    heuristic = load_heuristic(heuristic_name)
    assert heuristic.filter_files(filename) is expected


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


def test_intended_for_generation_ignores_non_warpkit_fmap_json(tmp_path: Path) -> None:
    bids = tmp_path / "bids"
    make_bids_run(bids, "sub-10001", "ses-01", "ugr", "1")
    fmap = bids / "sub-10001" / "ses-01" / "fmap"
    (fmap / "sub-10001_ses-01_acq-bold_magnitude.json").write_text("{}")
    (fmap / "sub-10001_ses-01_acq-ugr_run-1_magnitude.json").write_text("{}")
    (fmap / "sub-10001_ses-01_phasediff.json").write_text("{}")

    updates = collect_intended_for_updates(bids)

    assert [update.json_path.name for update in updates] == [
        "sub-10001_ses-01_acq-ugr_run-1_fieldmap.json"
    ]


def test_add_intended_for_accepts_sublist_filter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_add_intended_for()
    bids = tmp_path / "bids"
    make_bids_run(bids, "sub-10001", "ses-01", "ugr", "1")
    make_bids_run(bids, "sub-10002", "ses-01", "ugr", "1")
    sublist = tmp_path / "subjects.txt"
    sublist.write_text("10002\n")

    original_argv = sys.argv[:]
    sys.argv = ["addIntendedFor.py", "--bids-root", str(bids), "--sublist", str(sublist), "--dry-run"]
    try:
        assert module.main() == 0
    finally:
        sys.argv = original_argv

    captured = capsys.readouterr()
    assert "sub-10001" not in captured.out
    assert "sub-10002" in captured.out


def test_atomic_write_json_replaces_metadata(tmp_path: Path) -> None:
    path = tmp_path / "fieldmap.json"
    path.write_text('{"Units": "rad/s"}')
    atomic_write_json(path, {"Units": "Hz", "IntendedFor": ["ses-01/func/a.nii.gz"]})
    assert json.loads(path.read_text())["Units"] == "Hz"
    assert not list(tmp_path.glob("*.tmp"))


def test_shift_scans_tsv_accepts_mixed_iso_acq_times(tmp_path: Path) -> None:
    from shiftdates import shift_scans_tsv  # noqa: PLC0415

    scans_tsv = tmp_path / "sub-11982_ses-01_scans.tsv"
    scans_tsv.write_text(
        "filename\tacq_time\n"
        "anat/sub-11982_ses-01_T1w.nii.gz\t2026-06-12T17:51:05.123000\n"
        "func/sub-11982_ses-01_task-ugr_run-1_bold.nii.gz\t2026-06-12T17:51:05\n"
    )

    shifted = shift_scans_tsv(scans_tsv, months=1200)

    assert [row["acq_time"] for row in shifted] == [
        "1926-06-12T17:51:05.123000",
        "1926-06-12T17:51:05.000000",
    ]


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


def test_fmriprep_completion_accepts_extra_output_entities(tmp_path: Path) -> None:
    bids = tmp_path / "bids"
    deriv = tmp_path / "derivatives"
    make_bids_run(bids, "sub-10001", "ses-01", "ugr", "1")

    func = deriv / "fmriprep" / "sub-10001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (deriv / "fmriprep" / "sub-10001.html").write_text("html")
    (func / "sub-10001_ses-01_task-ugr_run-1_echo-1_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz").write_text("x")
    (func / "sub-10001_ses-01_task-ugr_run-1_desc-confounds_timeseries.tsv").write_text("x")
    fs_done = deriv / "freesurfer" / "sub-10001_ses-01" / "scripts" / "recon-all.done"
    fs_done.parent.mkdir(parents=True, exist_ok=True)
    fs_done.write_text("x")
    (func / "sub-10001_ses-01_task-ugr_run-1_space-fsLR_den-91k_bold.dtseries.nii").write_text("x")

    assert is_fmriprep_complete(bids, deriv, "10001")


def test_tedana_completion_checks_outputs(tmp_path: Path) -> None:
    deriv = tmp_path / "derivatives"
    expected = tedana_expected_outputs(deriv, "10001", "01", "ugr", "1")
    assert not is_tedana_complete(deriv, "10001", "01", "ugr", "1")
    for path in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    assert is_tedana_complete(deriv, "10001", "01", "ugr", "1")


def test_add_intended_for_dry_run_skips_missing_bids_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = load_add_intended_for()
    missing_bids = tmp_path / "missing-bids"
    original_argv = sys.argv[:]
    sys.argv = ["addIntendedFor.py", "--bids-root", str(missing_bids), "--dry-run"]
    try:
        assert module.main() == 0
    finally:
        sys.argv = original_argv

    captured = capsys.readouterr()
    assert "SKIP BIDS root not found" in captured.out
