from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import handoff_coverage95 as handoff


def fixture():
    jobs, review, qc = [], [], []
    for task, run in (("ugr", "1"), ("ugr", "2"), ("socialdoors", "1"), ("doors", "1")):
        key = dict(subject="11935", session="01", task=task, run=run)
        jobs.append(dict(key, key=f"sub-11935_ses-01_task-{task}_run-{run}",
                         output=f"/isolated/{task}/{run}"))
        review.append(dict(key, roster_gate="member", existing_hold="", existing_decision="not_recorded",
                           rerun_status="reused_verified"))
        qc.append(dict(key, brain_coverage_pct="99.5", brain_coverage_outlier="TRUE",
                       fd_mean_outlier="TRUE", tedana_outlier="TRUE"))
    plan = dict(jobs=jobs, l2_jobs=[dict(subject="11935", task="ugr", ncopes=17, output="/isolated/ugr/l2"),
                                  dict(subject="11935", task="socialdoors", ncopes=4, output="/isolated/social/l2")])
    return plan, review, handoff.audit.indexed(qc)


def decide(plan, review, qc, holds=None, excluded=None, decisions=None):
    return handoff.decide_runs(plan, review, qc, holds or {}, excluded or set(), decisions or {})


@pytest.mark.parametrize("value,expected", [
    (94.9999, "exclude_below_95"), (95, "pass"), (100, "pass"),
    ("", "review_missing_or_invalid"), (None, "review_missing_or_invalid"),
    ("nan", "review_missing_or_invalid"), ("inf", "review_missing_or_invalid"),
    (-1, "review_missing_or_invalid"), (101, "review_missing_or_invalid")])
def test_boundary_and_missing(value, expected):
    assert handoff.coverage(value) == expected


def test_preserves_good_runs_independent_tasks_and_descriptive_flags():
    plan, review, qc = fixture()
    qc[("11935", "01", "ugr", "1")]["brain_coverage_pct"] = "86"
    qc[("11935", "01", "socialdoors", "1")]["brain_coverage_pct"] = "78"
    # Session 02 must not affect baseline selection.
    qc[("11935", "02", "ugr", "2")] = dict(brain_coverage_pct="20")
    rows = handoff.select(plan, decide(plan, review, qc))
    assert {(r["analysis"], r["level"], r["input_runs"]) for r in rows} == {
        ("ugr", "L1", "2"), ("doors", "L1", "1")}
    assert len(rows) == 21


def test_both_runs_choose_one_l2_per_contrast_not_two_l1s():
    plan, review, qc = fixture()
    rows = handoff.select(plan, decide(plan, review, qc))
    ugr = [r for r in rows if r["analysis"] == "ugr"]
    assert len(ugr) == 17 and {r["level"] for r in ugr} == {"L2"}
    assert len({(r["subject"], r["analysis"], r["contrast"]) for r in rows}) == len(rows)
    assert not any(r["analysis"] == "socialdoors_doors_mean" for r in rows)
    plan["l2_jobs"] = []
    with pytest.raises(ValueError, match="Missing/duplicate"):
        handoff.select(plan, decide(plan, review, qc))


def test_holds_and_exclusions_cannot_be_overridden_by_include():
    plan, review, qc = fixture()
    key = ("11935", "01", "ugr", "1")
    review[0]["existing_decision"] = "exclude"
    rows = decide(plan, review, qc, decisions={key: dict(decision="include")})
    assert rows[0]["subject"] == "11935"
    assert next(r for r in rows if handoff.audit.key(r) == key)["selection_status"] == "held_existing_decision"
    rows = decide(plan, review, qc, excluded={"11935"})
    assert {r["selection_status"] for r in rows} == {"held_existing_decision"}
    rows = decide(plan, review, qc, holds={("11935", "01", "doors", "1"): dict(reason="settled")})
    assert next(r for r in rows if r["task"] == "doors")["selection_status"] == "held_existing_decision"


def test_missing_metric_never_passes_and_missing_plan_not_resurrected():
    plan, review, qc = fixture()
    del qc[("11935", "01", "ugr", "1")]
    plan["jobs"] = [j for j in plan["jobs"] if j["task"] != "doors"]
    rows = decide(plan, review, qc)
    assert next(r for r in rows if r["task"] == "ugr" and r["run"] == "1")["selection_status"] == "review_missing_or_invalid"
    assert next(r for r in rows if r["task"] == "doors")["selection_status"] == "not_in_verified_plan"


def test_cohort_counts_are_unique_subjects_and_preserve_nonselected_members():
    plan, review, qc = fixture()
    rows = decide(plan, review, qc)
    files, counts = handoff.render(plan, rows, {"sophia": ("ugr", {"11935", "12345"}, Path("approved.tsv"))})
    paper = next(c for c in counts if c["scope"] == "sophia")
    assert (paper["starting_n"], paper["selected_n"], paper["not_selected_n"]) == (2, 1, 1)
    assert "absent_from_frozen_age55_review" in files["paper_membership.tsv"]
    assert files["papers/sophia/subjects.txt"] == "11935\n"
    assert next(c for c in counts if c["scope"] == "imaging")["final_paper_n"].startswith("not_established")
    empty = decide(plan, review, qc, excluded={"11935"})
    files, counts = handoff.render(plan, empty, {})
    assert len(files["ugr/selected_inputs.tsv"].splitlines()) == 1
    assert all(c["selected_n"] == 0 for c in counts)


def test_cohort_schema_and_duplicates(tmp_path):
    p = tmp_path / "cohort.tsv"
    p.write_text("participant_id\nsub-11935\n")
    assert handoff.cohort_ids(p) == {"11935"}
    p.write_text("participant_id\nsub-11935\n11935\n")
    with pytest.raises(ValueError, match="duplicate"):
        handoff.cohort_ids(p)
    p.write_text("subject\tparticipant_id\n11935\tsub-11935\n")
    with pytest.raises(ValueError, match="exactly one"):
        handoff.cohort_ids(p)


def test_snapshot_check_recomputes_and_detects_tampering(tmp_path, monkeypatch):
    plan, review, qc = fixture()
    files, counts = handoff.render(plan, decide(plan, review, qc), {})
    source = tmp_path / "source.txt"
    source.write_text("frozen")
    signatures = [handoff.l1.signature(source)]
    monkeypatch.setattr(handoff, "inputs", lambda config: (files, counts, signatures, []))
    args = SimpleNamespace(private_dir=tmp_path / "new", finish_dir=tmp_path / "finish", project_root=tmp_path,
                           dispositions=None, katie_cohort=None, sophia_cohort=None, doors_cohort=None)
    handoff.build(args)
    handoff.check(args)
    with pytest.raises(ValueError, match="never overwrite"):
        handoff.build(args)
    (args.private_dir / "ugr/subjects.txt").write_text("99999\n")
    with pytest.raises(ValueError, match="output changed"):
        handoff.check(args)
    source.write_text("changed")
    with pytest.raises(ValueError, match="Frozen input"):
        handoff.check(args)


def test_invalid_session_and_duplicate_qc_rejected():
    plan, review, qc = fixture()
    review[0]["session"] = "02"
    with pytest.raises(ValueError):
        decide(plan, review, qc)
    with pytest.raises(ValueError, match="duplicate"):
        handoff.audit.indexed([dict(subject="11935", session="01", task="ugr", run="1")] * 2)


def test_input_loading_checks_outputs_and_live_source_exclusions(tmp_path, monkeypatch):
    plan, review, qc = fixture()
    finish_dir = tmp_path / "work/finish"
    finish_dir.mkdir(parents=True)
    (tmp_path / "qc").mkdir()
    (tmp_path / "code").mkdir()
    qc_path = tmp_path / "qc/run_qc.tsv"
    qc_path.write_text(handoff.table(list(qc.values()), list(next(iter(qc.values())))))
    (tmp_path / "code/task_availability_holds.tsv").write_text("subject\tsession\ttask\trun\treason\n")
    (finish_dir / "run_review.tsv").write_text(handoff.table(review, list(review[0])))
    (finish_dir / "plan.json").write_text("{}")
    (finish_dir / "plan.sha256").write_text("test")
    exclusions = tmp_path / "excluded"
    (exclusions / "Smith-SRA-11935").mkdir(parents=True)
    plan.update(parent_dir=str(tmp_path / "parent"), sources=[handoff.l1.signature(qc_path)])
    monkeypatch.setattr(handoff.finish, "load_plan", lambda p: plan)
    monkeypatch.setattr(handoff.l1, "load_plan", lambda p: dict(exclusions_root=str(exclusions)))
    called = []
    monkeypatch.setattr(handoff, "verify_products", lambda p: called.append(p))
    config = dict(finish_dir=str(finish_dir), project_root=str(tmp_path))
    files, counts, sources, excluded = handoff.inputs(config)
    assert called and excluded == ["11935"]
    assert all(c["selected_n"] == 0 for c in counts)
    assert "source_or_roster_exclusion" in files["run_decisions.tsv"]
    def incomplete(plan):
        raise ValueError("Incomplete L2")
    monkeypatch.setattr(handoff, "verify_products", incomplete)
    with pytest.raises(ValueError, match="Incomplete L2"):
        handoff.inputs(config)
