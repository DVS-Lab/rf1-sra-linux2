import csv
import io
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import refresh_task_handoff as handoff
from test_task_availability import setup, populate, put


def row(**changes):
    return dict(subject="10001", session="01", task="ugr", run="1", roster_gate="member",
                existing_hold="", existing_decision="not_recorded", decision_reason="",
                technical_status="inputs_present_aligned", missing_inputs="", input_findings="",
                **changes)


def test_qc_does_not_decide_eligibility():
    r = row()
    for status in ("outlier", "incomplete", "pass", ""):
        r.update(recorded_qc_status=status, task_session_qc_status=status)
        assert handoff.disposition(r) == ("ready", "")


@pytest.mark.parametrize("field,value", [("existing_hold", "reviewed hold"),
    ("existing_decision", "exclude"), ("existing_decision", "review"),
    ("existing_decision", "unavailable"), ("roster_gate", "blocked")])
def test_settled_blocks_override_present_files_and_qc(field, value):
    r = row()
    r[field] = value
    assert handoff.disposition(r)[0] == "held"
    exported = handoff.manifests([r])
    assert len(list(csv.DictReader(io.StringIO(exported["ugr/L1-ready.tsv"]), delimiter="\t"))) == 0
    assert "10001\t01\t1" in exported["ugr/L1-held.tsv"]


def test_include_does_not_override_technical_failure():
    r = row()
    r.update(existing_decision="include", technical_status="needs_review", input_findings="bad_alignment")
    assert handoff.disposition(r) == ("missing", "bad_alignment")


def test_reject_omitted_expected_run_and_wildcards(tmp_path):
    rows = [row()]
    second = dict(rows[0], run="2", technical_status="needs_review")
    rows.append(second)
    put(tmp_path / "raw-ugr-ready.tsv", "subject\tsession\trun\n10001\t01\t1\n")
    put(tmp_path / "raw-ugr-missing.tsv", "subject\tsession\trun\treason\n")
    with pytest.raises(ValueError, match="omitted"):
        handoff.validate_builder_tables(tmp_path, rows)
    put(tmp_path / "raw-ugr-missing.tsv", "subject\tsession\trun\treason\n10001\t01\t*\tmissing\n")
    with pytest.raises(ValueError):
        handoff.validate_builder_tables(tmp_path, rows)


def test_build_check_no_snapshot_overwrite_and_tamper_detection(tmp_path, monkeypatch):
    args = setup(tmp_path)
    populate(args)
    output = args.project_root / "work/handoff"
    # Run the real upstream audit/check; fake only task builders in this unit test.
    original_run = handoff.run_private
    def run(command, log):
        if "audit_task_availability.py" in command[1]:
            return original_run(command, log)
        task = "socialdoors" if "--tasks" in command else "ugr"
        ready = Path(command[command.index("--output") + 1])
        missing = Path(command[command.index("--missing-output") + 1])
        if task == "ugr":
            ready.write_text("subject\tsession\trun\n12018\t01\t1\n")
            missing.write_text("subject\tsession\trun\treason\n12018\t01\t2\tevents,BOLD,confounds\n")
        else:
            ready.write_text("subject\tsession\ttask\trun\n")
            missing.write_text("subject\tsession\ttask\trun\tmissing\n12018\t01\tsocialdoors\t1\tevents,BOLD,confounds\n")
        log.write_text("synthetic builder\n")
    real_repos = os.environ.get("RF1_HANDOFF_TEST_REPOS")
    if not real_repos:
        monkeypatch.setattr(handoff, "run_private", run)
    for name, root in (("ugr", args.ugr_root), ("socdoors", args.socdoors_root)):
        builder = root / "code/build_L1_manifest.py"
        put(builder, "# synthetic test builder\n")
        if real_repos:
            shutil.copyfile(Path(real_repos) / f"rf1-sra-{name}-handoff/code/build_L1_manifest.py", builder)
        put(root / "logs/runlists/L1-ready.tsv", "subject\tsession\ttask\trun\n")
    handoff.build(args, output)
    handoff.check(output)
    assert "12018\t01\t1" in (output / "ugr/L1-ready.tsv").read_text()
    assert (args.ugr_root / "logs/runlists/L1-ready.tsv").read_text() == "subject\tsession\ttask\trun\n"
    with pytest.raises(ValueError, match="new private"):
        handoff.build(args, output)
    (output / "ugr/L1-ready.tsv").write_text("changed\n")
    with pytest.raises(ValueError, match="hash"):
        handoff.check(output)
