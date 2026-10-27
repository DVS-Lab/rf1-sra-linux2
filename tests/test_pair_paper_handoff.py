import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import pair_paper_handoff as pair
from test_handoff_fd_tsnr import historical_fixture


def fixture():
    tables, decisions = {}, []
    for task, subjects in (("socialdoors", ("10001", "10002")), ("doors", ("10002", "10003"))):
        rows = []
        for sub in subjects:
            decisions.append(dict(subject=sub, session="01", task=task, run="1", selection_status="eligible", selection_reason=""))
            for contrast in range(1, 5):
                rows.append(dict(subject=sub, session="01", analysis=task, level="L1", input_runs="1", contrast=str(contrast),
                                 **{f: f"/{sub}/{task}/{contrast}/{f}" for f in ("cope", "varcope", "mask", "dof", "feat_dir")}))
        tables[task] = pair.source.old.table(rows, list(rows[0]))
    return tables, decisions


def test_pair_intersection_order_paths_and_reasons():
    tables, decisions = fixture()
    files, counts, n = pair.pair_tables(tables, decisions)
    assert counts == dict(socialdoors=2, doors=2) and n == 1
    assert files["socialdoors/subjects.txt"] == files["doors/subjects.txt"] == "10002\n"
    _, rows = pair.parse(files["paired_socialdoors/selected_pairs.tsv"])
    assert len(rows) == 4
    assert rows[0]["socialdoors_cope"] == "/10002/socialdoors/1/cope"
    assert rows[0]["doors_cope"] == "/10002/doors/1/cope"
    assert "doors:no_selected_input" in files["paired_membership.tsv"]
    assert "socialdoors:no_selected_input" in files["paired_membership.tsv"]


@pytest.mark.parametrize("problem", ["session", "L2", "duplicate", "contrast", "held"])
def test_reject_invalid_pair_inputs(problem):
    tables, decisions = fixture()
    fields, rows = pair.parse(tables["socialdoors"])
    if problem == "session":
        rows[0]["session"] = "02"
    elif problem == "L2":
        rows[0]["level"] = "L2"
    elif problem == "duplicate":
        rows.append(rows[0])
    elif problem == "contrast":
        rows.pop()
    else:
        decisions[0]["selection_status"] = "held_existing_decision"
    tables["socialdoors"] = pair.source.old.table(rows, fields)
    with pytest.raises(ValueError):
        pair.pair_tables(tables, decisions)


def test_empty_intersection_is_valid_and_keeps_table_headers():
    tables, decisions = fixture()
    tables["doors"] = tables["doors"].replace("10002", "10004")
    for r in decisions:
        if r["task"] == "doors" and r["subject"] == "10002":
            r["subject"] = "10004"
    files, _, n = pair.pair_tables(tables, decisions)
    assert n == 0 and files["paired_socialdoors/subjects.txt"] == ""
    assert len(files["paired_socialdoors/selected_pairs.tsv"].splitlines()) == 1


def test_build_check_ugr_identical_source_and_tampering(tmp_path, monkeypatch):
    source_args = historical_fixture(tmp_path)
    monkeypatch.setattr(pair.source, "verify_selected", lambda *a: None)
    pair.source.build(source_args)
    args = SimpleNamespace(previous=source_args.output, output=tmp_path / "work/paired")
    pair.build(args)
    pair.check(args)
    for name in ("ugr/selected_inputs.tsv", "ugr/subjects.txt", "run_decisions.tsv"):
        assert (args.output / name).read_bytes() == (args.previous / name).read_bytes()
    assert json.loads((args.output / "summary.json").read_text())["policy"] == pair.POLICY
    with pytest.raises(ValueError, match="new output"):
        pair.build(args)
    (args.output / "doors/subjects.txt").write_text("99999\n")
    with pytest.raises(ValueError, match="Paired output changed"):
        pair.check(args)


def test_changed_source_fail_closed_no_output(tmp_path, monkeypatch):
    source_args = historical_fixture(tmp_path)
    monkeypatch.setattr(pair.source, "verify_selected", lambda *a: None)
    pair.source.build(source_args)
    (source_args.output / "ugr/subjects.txt").write_text("99999\n")
    args = SimpleNamespace(previous=source_args.output, output=tmp_path / "work/paired")
    with pytest.raises(ValueError, match="Replacement output changed"):
        pair.build(args)
    assert not args.output.exists()
