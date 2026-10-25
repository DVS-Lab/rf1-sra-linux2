from pathlib import Path
import csv
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import measure_cohort_smoothness as smooth


def write_image(path, shape, affine=None, mask=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.ones(shape, dtype=np.float32) if mask else np.random.default_rng(42).normal(size=shape).astype(np.float32)
    nib.save(nib.Nifti1Image(data, np.eye(4) if affine is None else affine), path)


def add_run(project, subject="10001", session="01", task="ugr", run="1", era="XA60"):
    stem = f"sub-{subject}_ses-{session}_task-{task}_run-{run}"
    raw = project / f"bids/sub-{subject}/ses-{session}/func/{stem}_echo-2_part-mag_bold.nii.gz"
    write_image(raw, (5, 6, 7, 10))
    raw.with_name(raw.name.replace(".nii.gz", ".json")).write_text(json.dumps({"SoftwareVersions": era}))
    folder = project / f"derivatives/fmriprep/sub-{subject}/ses-{session}/func"
    bold = folder / f"{stem}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
    mask = bold.with_name(bold.name.replace("desc-preproc_bold", "desc-brain_mask"))
    write_image(bold, (5, 6, 7, 10))
    write_image(mask, (5, 6, 7), mask=True)
    return raw, bold, mask


@pytest.fixture
def setup(tmp_path):
    project = tmp_path / "project"
    excluded = tmp_path / "excluded"
    excluded.mkdir()
    (project / "qc").mkdir(parents=True)
    (project / "qc/run_qc.tsv").write_text("subject\tsession\ttask\trun\tqc_status\timaging_qc_outlier\n"
                                          "10001\t01\tugr\t1\tincomplete\tTRUE\n")
    raw, bold, mask = add_run(project)
    output = project / "work/measurement"
    output.mkdir(parents=True)
    wrapper = tmp_path / "measure_smoothness.sh"
    # Exercise real shell invocation/atomic results, without pretending to test AFNI numerics.
    wrapper.write_text('''#!/bin/bash
# -ShowMeClassicFWHM -detrend -acf NULL
while [ "$#" -gt 0 ]; do
 case "$1" in
 --input) input="$2";; --mask) mask="$2";; --output-tsv) output="$2";; --work-dir) work="$2";;
 esac
 shift 2
done
printf 'input\\tmask\\tclassic_fwhm_x\\tclassic_fwhm_y\\tclassic_fwhm_z\\tclassic_fwhm_combined\\tacf_a\\tacf_b\\tacf_c\\tacf_effective_fwhm\\tafni_version\\n' > "$output"
printf '%s\\t%s\\t3\\t4\\t5\\t4\\t0.5\\t2\\t3\\t5\\ttest-only\\n' "$input" "$mask" >> "$output"
''')
    args = SimpleNamespace(project=project, output=output, excluded_source_root=excluded,
                           measure_script=wrapper, jobs=2, threads=1)
    with patch.object(smooth, "tools_contract", return_value={"test": "not real AFNI"}):
        yield args, (raw, bold, mask)


def test_inventory_never_filters_qc_flags_or_session(setup):
    args, _ = setup
    add_run(args.project, session="02", task="doors")
    rows = smooth.inventory(args.project, args.excluded_source_root)
    assert len(rows) == 2
    assert all(row["status"] == "ready" for row in rows)
    assert rows[0]["imaging_qc_outlier"] == "TRUE"
    assert rows[1]["qc_status"] == "absent"


def test_source_exclusion_is_accounted_not_reinstated(setup):
    args, _ = setup
    (args.excluded_source_root / "Smith-SRA-10001").mkdir()
    row, = smooth.inventory(args.project, args.excluded_source_root)
    assert row["status"] == "source_excluded"


def test_missing_mask_not_silently_dropped(setup):
    args, (_, _, mask) = setup
    mask.unlink()
    row, = smooth.inventory(args.project, args.excluded_source_root)
    assert row["status"] == "unavailable"
    assert "mask" in row["reason"]


def test_duplicate_preproc_not_chosen_arbitrarily(setup):
    args, (_, bold, _) = setup
    bold.with_name(bold.name.replace("_desc-", "_res-2_desc-")).write_bytes(bold.read_bytes())
    row, = smooth.inventory(args.project, args.excluded_source_root)
    assert row["status"] == "unavailable"
    assert "found 2" in row["reason"]


def test_ignores_echo_phase_other_space_and_archive(setup):
    args, (_, bold, _) = setup
    for name in (bold.name.replace("_part-mag", "_echo-1_part-mag"),
                 bold.name.replace("_part-mag", "_part-phase"),
                 bold.name.replace("MNI152NLin6Asym", "MNI152NLin2009cAsym")):
        bold.with_name(name).write_bytes(bold.read_bytes())
    add_run(args.project / "work/archive", subject="99999")
    row, = smooth.inventory(args.project, args.excluded_source_root)
    assert row["status"] == "ready"


def test_missing_source_root_fails(setup):
    args, _ = setup
    args.excluded_source_root.rmdir()
    with pytest.raises(ValueError, match="Source-exclusion"):
        smooth.inventory(args.project, args.excluded_source_root)


def test_geometry_rejects_misalignment_and_empty_mask(setup):
    _, (_, bold, mask) = setup
    assert smooth.geometry(str(bold), str(mask))["shape"][-1] == 10
    write_image(mask, (5, 6, 7), affine=np.diag([2, 2, 2, 1]), mask=True)
    with pytest.raises(ValueError, match="geometry"):
        smooth.geometry(str(bold), str(mask))
    nib.save(nib.Nifti1Image(np.zeros((5, 6, 7)), np.eye(4)), mask)
    with pytest.raises(ValueError, match="Mask empty"):
        smooth.geometry(str(bold), str(mask))


def test_plan_run_restart_and_check(setup):
    args, (_, bold, _) = setup
    before = smooth.digest(bold)
    assert smooth.plan(args) == 0
    assert smooth.run(args) == 0
    row = smooth.load_plan(args)["rows"][0]
    destination = args.output / "runs" / smooth.label(row)
    modified = (destination / "result.tsv").stat().st_mtime_ns
    assert smooth.run(args) == 0
    assert (destination / "result.tsv").stat().st_mtime_ns == modified
    assert smooth.report(args) == 0
    assert smooth.digest(bold) == before
    assert (args.output / "figures/task-ugr_ses-01.png").is_file()
    assert smooth.read_tsv(args.output / "run_metrics.tsv")[0]["imaging_qc_outlier"] == "TRUE"


def test_live_input_or_qc_change_stops_resume(setup):
    args, (_, bold, _) = setup
    smooth.plan(args)
    original = bold.stat()
    os.utime(bold, ns=(original.st_atime_ns, original.st_mtime_ns + 100))
    with pytest.raises(ValueError, match="Live inputs"):
        smooth.run(args)
    os.utime(bold, ns=(original.st_atime_ns, original.st_mtime_ns))
    with (args.project / "qc/run_qc.tsv").open("a") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="QC inventory"):
        smooth.run(args)


def test_corrupt_result_is_preserved_and_rejected(setup):
    args, _ = setup
    smooth.plan(args)
    smooth.run(args)
    row = smooth.load_plan(args)["rows"][0]
    result = args.output / "runs" / smooth.label(row) / "result.tsv"
    result.write_text("corrupt\n")
    assert smooth.run(args) == 1
    assert result.read_text() == "corrupt\n"
    assert smooth.report(args) == 1


def test_unavailable_rows_fail_final_completeness(setup):
    args, (_, _, mask) = setup
    mask.unlink()
    smooth.plan(args)
    assert smooth.run(args) == 0
    assert smooth.report(args) == 1
    assert smooth.read_tsv(args.output / "summary.tsv")[0]["n_missing"] == "1"


def test_numeric_result_rejects_nan(setup):
    args, _ = setup
    smooth.plan(args)
    smooth.run(args)
    row = smooth.load_plan(args)["rows"][0]
    path = args.output / "runs" / smooth.label(row) / "result.tsv"
    records = smooth.read_tsv(path)
    records[0]["classic_fwhm_combined"] = "nan"
    smooth.write_tsv(path, records, list(records[0]))
    with pytest.raises(ValueError, match="Nonfinite"):
        smooth.read_result(path, row)


def test_failure_preserves_attempt_and_retries(setup):
    args, _ = setup
    smooth.plan(args)
    with patch.object(smooth.subprocess, "run", return_value=SimpleNamespace(returncode=2)):
        assert smooth.run(args) == 1
    assert list((args.output / "attempts").glob("*/command.log"))
    assert not list((args.output / "runs").iterdir())
    assert smooth.run(args) == 0


def test_new_input_requires_new_plan(setup):
    args, _ = setup
    smooth.plan(args)
    add_run(args.project, subject="10002")
    with pytest.raises(ValueError, match="Live inputs"):
        smooth.run(args)


def test_report_keeps_tasks_and_sessions_separate(setup):
    args, _ = setup
    add_run(args.project, task="socialdoors")
    add_run(args.project, session="02")
    smooth.plan(args)
    smooth.run(args)
    smooth.report(args)
    rows = smooth.read_tsv(args.output / "summary.tsv")
    assert {(r["task"], r["session"]) for r in rows} == {("ugr", "01"), ("ugr", "02"), ("socialdoors", "01")}
    assert all(r["n_runs"] == "1" for r in rows)
