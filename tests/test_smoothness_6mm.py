import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import nibabel as nib
import numpy as np
import pytest

from test_cohort_smoothness import setup, add_run, write_image
import measure_cohort_smoothness as baseline
import evaluate_smoothness_6mm as evaluation


@pytest.fixture
def prepared(setup, tmp_path):
    args, paths = setup
    assert baseline.plan(args) == 0
    assert baseline.run(args) == 0
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "measure_smoothness.sh").write_bytes(args.measure_script.read_bytes())
    (scripts / "project_config.sh").write_text("# test only\n")
    (scripts / "smooth_to_target.sh").write_text('''#!/bin/bash
set -euo pipefail
while [ "$#" -gt 0 ]; do
 case "$1" in
 --input) input="$2";; --mask) mask="$2";; --output) output="$2";; --qc-tsv) qc="$2";;
 esac
 shift 2
done
cp "$input" "$output"
printf 'input\\tmask\\tclassic_fwhm_x\\tclassic_fwhm_y\\tclassic_fwhm_z\\tclassic_fwhm_combined\\tacf_a\\tacf_b\\tacf_c\\tacf_effective_fwhm\\tafni_version\\n' > "$qc"
printf '%s\\t%s\\t6\\t6\\t6\\t%s\\t0.5\\t2\\t3\\t7\\ttest-only\\n' "$output" "$mask" "${TEST_FWHM:-6}" >> "$qc"
''')
    output = args.project / "derivatives/smoothness-evaluation-6mm-test"
    output.mkdir()
    options = SimpleNamespace(project=args.project, baseline=args.output, output=output,
                              sharedreward_code=scripts, jobs=2, threads=1)
    with patch.object(evaluation, "tools_contract", return_value={"test": "not real AFNI"}):
        yield options, paths


def test_plan_run_check_resume_preserves_inputs_and_qc(prepared):
    args, (_, bold, mask) = prepared
    protected = [bold, mask, args.project / "qc/run_qc.tsv"]
    hashes = [baseline.digest(p) for p in protected]
    assert evaluation.plan(args) == 0
    assert not (args.output / "runs").exists()
    assert evaluation.run(args) == 0
    row = evaluation.load_plan(args)["rows"][0]
    receipt = evaluation.result_path(args.output, row) / "receipt.json"
    mtime = receipt.stat().st_mtime_ns
    assert evaluation.run(args) == 0
    assert receipt.stat().st_mtime_ns == mtime
    assert evaluation.check(args) == 0
    assert hashes == [baseline.digest(p) for p in protected]
    assert (args.output / "figures/task-ugr_ses-01_before_after.png").is_file()
    result, = baseline.read_tsv(args.output / "run_results.tsv")
    assert result["imaging_qc_outlier"] == "TRUE"
    assert float(result["after_classic_fwhm_combined"]) == 6


def set_baseline_value(args, value):
    data = baseline.load_plan(SimpleNamespace(output=args.baseline))
    row = data["rows"][0]
    directory = args.baseline / "runs" / baseline.label(row)
    result = directory / "result.tsv"
    values, = baseline.read_tsv(result)
    values["classic_fwhm_combined"] = str(value)
    baseline.write_tsv(result, [values], tuple(values))
    receipt = json.loads((directory / "receipt.json").read_text())
    receipt["result_sha256"] = baseline.digest(result)
    baseline.atomic_json(directory / "receipt.json", receipt)


@pytest.mark.parametrize("value,held", [(5.4, False), (5.999, False), (6, True), (6.6, True), (7, True)])
def test_upper_tail_holds_without_excluding(prepared, value, held):
    args, _ = prepared
    set_baseline_value(args, value)
    assert evaluation.plan(args) == 0
    row = evaluation.load_plan(args)["rows"][0]
    assert (row["evaluation_action"] == "hold_at_or_above_target") == held
    assert evaluation.run(args) == 0
    assert evaluation.check(args) == int(held)
    results, = baseline.read_tsv(args.output / "run_results.tsv")
    if held:
        assert results["after_classic_fwhm_combined"] == ""
        assert not evaluation.result_path(args.output, row).exists()
    state = json.loads((args.output / "validation.json").read_text())
    assert state["technical_complete"] and not state["eligibility_changed"]


def test_outside_band_not_hidden_or_retried(prepared, monkeypatch):
    args, _ = prepared
    evaluation.plan(args)
    monkeypatch.setenv("TEST_FWHM", "7")
    assert evaluation.run(args) == 0
    monkeypatch.setenv("TEST_FWHM", "6")
    assert evaluation.run(args) == 0
    assert evaluation.check(args) == 1
    row, = baseline.read_tsv(args.output / "run_results.tsv")
    assert row["status"] == "outside_tolerance"
    assert float(row["after_classic_fwhm_combined"]) == 7
    assert (args.output / "figures/task-ugr_ses-01_before_after.png").is_file()


def test_corruption_never_overwritten(prepared):
    args, _ = prepared
    evaluation.plan(args)
    evaluation.run(args)
    assert evaluation.check(args) == 0
    plot = args.output / "figures/task-ugr_ses-01_before_after.png"
    original_plot = baseline.digest(plot)
    row = evaluation.load_plan(args)["rows"][0]
    image = evaluation.result_path(args.output, row) / evaluation.image_name(row)
    image.write_bytes(b"broken")
    assert evaluation.run(args) == 1
    assert image.read_bytes() == b"broken"
    assert evaluation.check(args) == 1
    assert baseline.digest(plot) != original_plot


def test_duplicate_coordinator_lock_stops_before_processing(prepared, monkeypatch):
    import fcntl
    import sys
    args, _ = prepared
    monkeypatch.setattr(evaluation, "LOCK_FDS", ())
    evaluation.plan(args)
    with (args.output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(sys, "argv", ["evaluate_smoothness_6mm.py", "run", "--project", str(args.project),
                                         "--baseline", str(args.baseline), "--output", str(args.output)])
        assert evaluation.main() == 1
    assert not (args.output / "runs").exists()
    evaluation.LOCK_FDS = ()


def test_missing_output_recoverable_and_input_change_stops(prepared):
    args, (_, bold, _) = prepared
    evaluation.plan(args)
    assert evaluation.check(args) == 1
    assert evaluation.run(args) == 0
    assert evaluation.check(args) == 0
    stat = bold.stat()
    content = bold.read_bytes()
    bold.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
    os.utime(bold, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert evaluation.run(args) == 1


def test_changed_wrapper_stops_plan(prepared):
    args, _ = prepared
    (args.sharedreward_code / "measure_smoothness.sh").write_text("changed")
    with pytest.raises(ValueError, match="wrapper differs"):
        evaluation.plan(args)


def test_failed_attempt_preserved_then_retried(prepared, monkeypatch):
    args, _ = prepared
    evaluation.plan(args)
    with patch.object(evaluation.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
        assert evaluation.run(args) == 1
    attempts = list((args.output / "attempts").iterdir())
    assert len(attempts) == 1
    assert evaluation.run(args) == 0
    assert attempts[0].is_dir()
    assert evaluation.check(args) == 0


def test_axis_tail_flag_does_not_exclude(prepared):
    args, _ = prepared
    evaluation.plan(args)
    row = evaluation.load_plan(args)["rows"][0]
    row["before"]["classic_fwhm_x"] = 7
    evaluation.upper_tail(args.output, [row])
    summary, = baseline.read_tsv(args.output / "upper_tail.tsv")
    assert summary["n_any_axis_ge_6"] == "1"
    assert summary["n_ge_6"] == "0"
    assert row["evaluation_action"] == "smooth"


def test_three_era_paired_plots_keep_held_and_failed_visible(prepared):
    import copy
    args, _ = prepared
    evaluation.plan(args)
    first = evaluation.load_plan(args)["rows"][0]
    rows = []
    for era, offset in (("E11", 0), ("XA30", .2), ("XA60", .7)):
        for i in range(6):
            row = copy.deepcopy(first)
            row.update(subject=str(10000 + len(rows)), software_era=era,
                       status="within_tolerance", after=copy.deepcopy(row["before"]))
            row["before"]["classic_fwhm_combined"] = 3 + offset + i * .1
            row["after"]["classic_fwhm_combined"] = 5.8 + i * .1
            row["before"]["acf_effective_fwhm"] = 5 + offset + i * .1
            row["after"]["acf_effective_fwhm"] = 7 + offset + i * .1
            rows.append(row)
    rows[-1].update(status="hold_at_or_above_target", after={})
    rows[-1]["before"]["classic_fwhm_combined"] = 6.9
    rows[-2].update(status="failed", after={})
    rows[-3]["after"]["classic_fwhm_combined"] = 7
    rows[-3]["status"] = "outside_tolerance"
    evaluation.report(args.output, rows)
    values = baseline.read_tsv(args.output / "paired_summary.tsv")
    xa60 = next(r for r in values if r["software_era"] == "XA60")
    assert (xa60["n_baseline"], xa60["n_paired"], xa60["n_held"], xa60["n_failed"], xa60["n_outside"]) == ("6", "4", "1", "1", "1")


def test_geometry_tr_and_nonfinite_rejected(prepared, tmp_path):
    args, (_, bold, mask) = prepared
    row = {"input_bold": str(bold), "input_mask": str(mask)}
    output = tmp_path / "output.nii.gz"
    write_image(output, (5, 6, 7, 9))
    with pytest.raises(ValueError, match="volume count"):
        evaluation.output_geometry(output, row)
    image = nib.load(bold)
    image.header.set_zooms((1, 1, 1, 2))
    nib.save(image, output)
    with pytest.raises(ValueError, match="TR"):
        evaluation.output_geometry(output, row)
    nib.save(nib.Nifti1Image(np.full((5, 6, 7, 10), np.nan), np.eye(4)), output)
    with pytest.raises(ValueError, match="Nonfinite"):
        evaluation.output_geometry(output, row)


def test_all_tasks_sessions_and_source_exclusions(setup, tmp_path):
    args, _ = setup
    for task in ("doors", "socialdoors", "sharedreward", "trust", "ugr"):
        for session in ("01", "02"):
            add_run(args.project, subject="10002", session=session, task=task)
    (args.excluded_source_root / "Smith-SRA-10001").mkdir()
    baseline.plan(args)
    baseline.run(args)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in evaluation.SCRIPTS:
        (scripts / name).write_bytes(args.measure_script.read_bytes())
    output = args.project / "derivatives/smoothness-evaluation-6mm-test"
    output.mkdir()
    options = SimpleNamespace(project=args.project, baseline=args.output, output=output, sharedreward_code=scripts)
    with patch.object(evaluation, "tools_contract", return_value={"test": "not real AFNI"}):
        evaluation.plan(options)
    rows = json.loads((output / "plan.json").read_text())["rows"]
    assert len(rows) == 11
    assert sum(r["evaluation_action"] == "smooth" for r in rows) == 10
    assert sum(r["evaluation_action"] == "source_excluded" for r in rows) == 1
