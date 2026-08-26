from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
CODE_DIR = Path(__file__).resolve().parents[1] / "code"

from pipeline_utils import (  # noqa: E402
    apply_umask_mode,
    atomic_write_json,
    choose_heuristic,
    collect_intended_for_updates,
    ensure_safe_child_path,
    fmriprep_expected_outputs,
    is_fmriprep_complete,
    is_tedana_complete,
    load_warpkit_reuse,
    missing_paths,
    read_subject_list,
    runs_for_task,
    subject_t1w_inputs,
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


def test_tempfile_mode_is_replaced_with_mode_allowed_by_umask(tmp_path: Path) -> None:
    path = tmp_path / "private.tmp"
    path.write_text("test")
    path.chmod(0o600)
    previous = os.umask(0o002)
    try:
        apply_umask_mode(path)
    finally:
        os.umask(previous)
    assert path.stat().st_mode & 0o777 == 0o664


def test_shell_subject_reader_skips_source_exclusions_unless_overridden(tmp_path: Path) -> None:
    sublist = tmp_path / "subjects.txt"
    sublist.write_text("10001\n10002\n")
    exclusions = tmp_path / "exclusions"
    (exclusions / "Smith-SRA-10002").mkdir(parents=True)
    command = (
        f'source "{CODE_DIR / "pipeline_common.sh"}"; '
        f'SCRIPT_DIR="{CODE_DIR}"; '
        f'rf1_read_subjects "{sublist}"'
    )
    env = os.environ | {"SOURCEDATA_EXCLUSIONS_ROOT": str(exclusions)}

    filtered = subprocess.run(
        ["bash", "-c", command], env=env, text=True, capture_output=True, check=True
    )
    assert filtered.stdout == "10001\n"
    assert "SKIP source-excluded sub-10002" in filtered.stderr

    included = subprocess.run(
        ["bash", "-c", command],
        env=env | {"RF1_INCLUDE_SOURCE_EXCLUDED": "1"},
        text=True,
        capture_output=True,
        check=True,
    )
    assert included.stdout == "10001\n10002\n"
    assert included.stderr == ""


def test_tedana_command_has_shared_default_and_environment_override() -> None:
    command = (
        f'source "{CODE_DIR / "pipeline_common.sh"}"; '
        "rf1_load_config; "
        "printf '%s\\n' \"$TEDANA_CMD\""
    )
    expected = "/ZPOOL/data/tools/anaconda/tug87422/envs/tedana-26.0.3/bin/tedana\n"

    default = subprocess.run(
        ["bash", "-c", command], text=True, capture_output=True, check=True
    )
    assert default.stdout == expected

    overridden = subprocess.run(
        ["bash", "-c", command],
        env=os.environ | {"TEDANA_CMD": "/tmp/test-tedana"},
        text=True,
        capture_output=True,
        check=True,
    )
    assert overridden.stdout == "/tmp/test-tedana\n"


def test_warpkit_reuse_manifest_and_shell_lookup(tmp_path: Path) -> None:
    manifest = tmp_path / "warpkit_reuse.tsv"
    manifest.write_text(
        "subject\tsession\ttask\trun\tsource_run\treason\n"
        "10929\t01\tugr\t2\t1\tincomplete_phase_acquisition\n"
    )
    specs = load_warpkit_reuse(manifest)
    assert specs[("10929", "01", "ugr", "2")].source_run == "1"

    command = (
        f'source "{CODE_DIR / "pipeline_common.sh"}"; '
        f'SCRIPT_DIR="{CODE_DIR}"; '
        f'WARPKIT_REUSE_FILE="{manifest}"; '
        'rf1_warpkit_reuse_spec 10929 01 ugr 2'
    )
    result = subprocess.run(
        ["bash", "-c", command], text=True, capture_output=True, check=True
    )
    assert result.stdout == "1\tincomplete_phase_acquisition\n"


def test_warpkit_reuse_manifest_rejects_same_source_and_target(tmp_path: Path) -> None:
    manifest = tmp_path / "warpkit_reuse.tsv"
    manifest.write_text(
        "subject\tsession\ttask\trun\tsource_run\treason\n"
        "10929\t01\tugr\t2\t2\tincomplete_phase_acquisition\n"
    )
    with pytest.raises(ValueError, match="source equals target"):
        load_warpkit_reuse(manifest)


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


def test_repair_runlists_accept_12018_malformed_source_layout(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    scans = (
        tmp_path
        / "Smith-SRA-12018"
        / "Smith-SRA-"
        / "scans"
        / "1-T1w"
        / "resources"
        / "DICOM"
        / "files"
    )
    scans.mkdir(parents=True)
    (scans / "image.dcm").write_text("dicom")

    assert module.source_has_dicoms(tmp_path, "12018")
    assert module.missing_required_sources(tmp_path, ["12018"]) == set()


def test_repair_runlists_report_excluded_sources(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    (tmp_path / "Smith-SRA-10001").mkdir()

    assert module.excluded_sources(tmp_path, ["10001", "10002"]) == {"10001"}
    assert module.excluded_sources(tmp_path / "missing", ["10001"]) == set()


def test_repair_runlists_issue_tsv_uses_unix_line_endings(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    output = tmp_path / "missing-paths.tsv"
    issue = module.Issue(
        subject="10001",
        stage="mriqc",
        session="01",
        task="",
        run="",
        path="/tmp/output.json",
        message="MRIQC JSON missing",
    )

    module.write_issues(output, [issue])

    contents = output.read_bytes()
    assert b"\r\n" not in contents
    assert contents.endswith(b"MRIQC JSON missing\n")


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
    func.mkdir(parents=True, exist_ok=True)
    fmap.mkdir(parents=True, exist_ok=True)
    for echo in range(1, echoes + 1):
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-mag_bold.nii.gz").write_text("nii")
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-phase_bold.nii.gz").write_text("nii")
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-phase_bold.json").write_text('{"EchoTime": 0.01}')
        (func / f"{sub}_{ses}_task-{task}_run-{run}_echo-{echo}_part-mag_bold.json").write_text('{"EchoTime": 0.01}')
    (fmap / f"{sub}_{ses}_acq-{task}_run-{run}_fieldmap.json").write_text(
        json.dumps({"TaskName": task, "IntendedFor": ["missing.nii.gz"]})
    )


def test_repair_audit_accepts_completed_reviewed_warpkit_reuse(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    project = tmp_path / "project"
    bids = project / "bids"
    make_bids_run(bids, "sub-10929", "ses-01", "ugr", "1")
    make_bids_run(bids, "sub-10929", "ses-01", "ugr", "2")
    func = bids / "sub-10929" / "ses-01" / "func"
    fmap = bids / "sub-10929" / "ses-01" / "fmap"
    outdir = project / "derivatives" / "warpkit" / "sub-10929" / "ses-01"
    outdir.mkdir(parents=True)

    for echo in range(1, 5):
        (func / f"sub-10929_ses-01_task-ugr_run-2_echo-{echo}_part-phase_bold.nii.gz").unlink()
        (func / f"sub-10929_ses-01_task-ugr_run-2_echo-{echo}_part-phase_bold.json").unlink()

    for run in ("1", "2"):
        stem = f"sub-10929_ses-01_task-ugr_run-{run}"
        (outdir / f"{stem}.warpkit_done").write_text("done")
        (fmap / f"sub-10929_ses-01_acq-ugr_run-{run}_fieldmap.nii.gz").write_text("nii")
        (fmap / f"sub-10929_ses-01_acq-ugr_run-{run}_magnitude.nii.gz").write_text("nii")
        (fmap / f"sub-10929_ses-01_acq-ugr_run-{run}_magnitude.json").write_text("{}")
    (outdir / "sub-10929_ses-01_task-ugr_run-2_fieldmap-reuse.json").write_text("{}")

    manifest = tmp_path / "warpkit_reuse.tsv"
    manifest.write_text(
        "subject\tsession\ttask\trun\tsource_run\treason\n"
        "10929\t01\tugr\t2\t1\tincomplete_phase_acquisition\n"
    )
    issues = []
    needs_repair = module.add_warpkit_issues(
        issues, project, ["10929"], load_warpkit_reuse(manifest)
    )

    assert needs_repair == set()
    assert issues == []


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


def test_record_warpkit_reuse_preserves_source_and_writes_provenance(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    source_fieldmap = project / "bids/source_fieldmap.nii.gz"
    target_fieldmap = project / "bids/target_fieldmap.nii.gz"
    source_json = project / "bids/source_fieldmap.json"
    target_json = project / "bids/target_fieldmap.json"
    provenance = project / "derivatives/target_fieldmap-reuse.json"
    source_fieldmap.parent.mkdir(parents=True)
    provenance.parent.mkdir(parents=True)
    source_fieldmap.write_bytes(b"fieldmap")
    target_fieldmap.write_bytes(b"fieldmap")
    source_json.write_text(
        json.dumps({"Units": "Hz", "IntendedFor": ["ses-01/func/run-1.nii.gz"]})
    )

    subprocess.run(
        [
            sys.executable,
            str(CODE_DIR / "record_warpkit_reuse.py"),
            "--project-root",
            str(project),
            "--source-json",
            str(source_json),
            "--target-json",
            str(target_json),
            "--source-fieldmap",
            str(source_fieldmap),
            "--target-fieldmap",
            str(target_fieldmap),
            "--provenance-json",
            str(provenance),
            "--subject",
            "10929",
            "--session",
            "01",
            "--task",
            "ugr",
            "--run",
            "2",
            "--source-run",
            "1",
            "--reason",
            "incomplete_phase_acquisition",
        ],
        check=True,
    )

    metadata = json.loads(target_json.read_text())
    assert metadata["Units"] == "Hz"
    assert "IntendedFor" not in metadata
    assert metadata["RF1SRAFieldmapReuse"]["SourceRun"] == "1"
    assert metadata["RF1SRAFieldmapReuse"]["TargetRun"] == "2"
    recorded = json.loads(provenance.read_text())
    assert recorded["Reason"] == "incomplete_phase_acquisition"
    assert recorded["SourceFieldmap"] == "bids/source_fieldmap.nii.gz"


def test_subject_t1w_inputs_accepts_session_and_subject_anat(tmp_path: Path) -> None:
    bids = tmp_path / "bids"
    session_t1w = bids / "sub-10001" / "ses-01" / "anat" / "sub-10001_ses-01_T1w.nii.gz"
    subject_t1w = bids / "sub-10002" / "anat" / "sub-10002_T1w.nii.gz"
    session_t1w.parent.mkdir(parents=True)
    subject_t1w.parent.mkdir(parents=True)
    session_t1w.write_text("nii")
    subject_t1w.write_text("nii")

    assert subject_t1w_inputs(bids, "10001") == [session_t1w]
    assert subject_t1w_inputs(bids, "10002") == [subject_t1w]
    assert subject_t1w_inputs(bids, "10003") == []


def test_repair_runlists_report_missing_t1w_as_bids_issue(tmp_path: Path) -> None:
    module = load_make_repair_runlists()
    project_root = tmp_path / "project"
    session = project_root / "bids" / "sub-10001" / "ses-01"
    func = session / "func"
    func.mkdir(parents=True)
    (session / "sub-10001_ses-01_scans.tsv").write_text("filename\tacq_time\n")
    (func / "sub-10001_ses-01_task-ugr_run-1_bold.nii.gz").write_text("nii")
    issues = []

    needs_repair = module.add_bids_issues(issues, project_root, tmp_path / "source", ["10001"])

    assert needs_repair == {"10001"}
    assert any(issue.message == "no BIDS T1w input available for fMRIPrep/FreeSurfer" for issue in issues)


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
