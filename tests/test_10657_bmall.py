import copy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import test_cohort_smoothness as cohort_fixtures
import test_smoothness_6mm as evaluation_fixtures
import evaluate_smoothness_6mm as evaluation
import measure_cohort_smoothness as baseline
import retry_10657_bmall as retry

setup = cohort_fixtures.setup
prepared = evaluation_fixtures.prepared
add_run = cohort_fixtures.add_run


@pytest.fixture
def batch(prepared, monkeypatch, tmp_path):
    options, _ = prepared
    # Exercise real frozen-plan validation and old-result verification with synthetic images.
    for task, run in retry.TARGETS:
        add_run(options.project, subject="10657", task=task, run=run)
    bargs = SimpleNamespace(project=options.project, output=options.project / "work/cohort-smoothness-v1",
                            excluded_source_root=tmp_path / "excluded",
                            measure_script=options.sharedreward_code / "measure_smoothness.sh",
                            jobs=2, threads=1)
    bargs.output.mkdir()
    (bargs.output / ".lock").touch()
    baseline.plan(bargs)
    baseline.run(bargs)
    options.baseline = bargs.output
    options.output = options.project / "derivatives/smoothness-evaluation-6mm-v1"
    options.output.mkdir()
    (options.output / ".lock").touch()
    evaluation.plan(options)
    monkeypatch.setenv("TEST_FWHM", "5.3")
    evaluation.run(options)
    (options.output / "validation.json").write_text('{"technical_complete": true}')
    output = options.project / "derivatives/smoothness-10657-bmall-v1"
    output.mkdir()
    args = SimpleNamespace(project=options.project, output=output, command="run")
    real_run = retry.subprocess.run
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "3dBlurToFWHM":
            assert "-bmall" in cmd and "-quiet" not in cmd
            assert "/derivatives/fmriprep/" in cmd[cmd.index("-input") + 1]
            shutil.copyfile(cmd[cmd.index("-input") + 1], cmd[cmd.index("-prefix") + 1])
            kwargs["stdout"].write("synthetic controller: reached target\n")
            return SimpleNamespace(returncode=0)
        result = real_run(cmd, **kwargs)
        table = Path(cmd[cmd.index("--output-tsv") + 1])
        rows = baseline.read_tsv(table)
        rows[0]["classic_fwhm_combined"] = "5.9"
        baseline.write_tsv(table, rows, tuple(rows[0]))
        return result

    with patch.object(retry.subprocess, "run", side_effect=fake_run):
        yield args, calls


def test_only_five_runs_no_promotion_resume_and_check(batch):
    args, calls = batch
    source = args.project / "derivatives/smoothness-evaluation-6mm-v1"
    protected = {p: baseline.digest(p) for p in source.rglob("*") if p.is_file()}
    assert retry.run(args) == 0
    assert len(calls) == 10
    assert retry.run(args) == 0
    args.command = "check"
    assert retry.run(args) == 0
    assert len(calls) == 10
    assert all(baseline.digest(p) == d for p, d in protected.items())
    results = baseline.read_tsv(args.output / "comparison.tsv")
    assert len(results) == 5
    assert {r["subject"] for r in results} == {"10657"}
    assert next(r for r in results if r["task"] == "sharedreward")["settled_note"].startswith("Shared Reward run 1 excluded")
    state = json.loads((args.output / "validation.json").read_text())
    assert state["technical_complete"] and not state["eligibility_changed"] and not state["production_promoted"]


def test_selection_rejects_missing_duplicates_and_parked():
    rows = [dict(subject="10657", session="01", task=t, run=r, evaluation_action="smooth")
            for t, r in retry.TARGETS]
    assert len(retry.select_rows({"rows": rows + [dict(rows[0], session="02")]})) == 5
    for invalid in (rows[:-1], rows + [rows[0]], [dict(rows[0], evaluation_action="source_excluded"), *rows[1:]]):
        with pytest.raises(ValueError):
            retry.select_rows({"rows": invalid})


def test_completed_retry_corruption_is_not_overwritten(batch):
    args, calls = batch
    retry.run(args)
    image = next((args.output / "runs").glob("*/*.nii.gz"))
    image.write_bytes(b"corrupt")
    assert retry.run(args) == 1
    assert image.read_bytes() == b"corrupt" and len(calls) == 10


def test_changed_source_is_rejected(batch):
    args, _ = batch
    retry.run(args)
    plan = json.loads((args.output / "plan.json").read_text())
    Path(plan["rows"][0]["input_bold"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="Original input changed"):
        retry.run(args)


def test_changed_retry_wrapper_is_rejected(batch):
    args, _ = batch
    retry.run(args)
    (args.output / "code/measure_smoothness.sh").write_text("changed")
    with pytest.raises(ValueError, match="wrapper changed"):
        retry.run(args)


def test_failure_preserves_attempt_and_resumes(batch):
    args, _ = batch
    with patch.object(retry.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
        assert retry.run(args) == 1
    attempts = list((args.output / "attempts").iterdir())
    assert len(attempts) == 5
    assert retry.run(args) == 0
    assert all(p.exists() for p in attempts)


def test_outside_band_is_review_not_processing_failure(batch):
    args, calls = batch
    original = retry.execute
    def outside(*params):
        status, values = original(*params)
        values = copy.deepcopy(values)
        values["classic_fwhm_combined"] = "5.3"
        return status, values
    with patch.object(retry, "execute", side_effect=outside):
        assert retry.run(args) == 2
    state = json.loads((args.output / "validation.json").read_text())
    assert state["technical_complete"] and state["outside_tolerance"] == 5


def test_lock_prevents_launch(batch, monkeypatch):
    import fcntl
    import sys
    args, calls = batch
    lockpath = args.project / "derivatives/smoothness-evaluation-6mm-v1/.lock"
    with lockpath.open("r") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(sys, "argv", ["retry_10657_bmall.py", "run", "--project", str(args.project)])
        assert retry.main() == 1
    assert not calls
