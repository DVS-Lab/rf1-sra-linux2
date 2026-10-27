import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import handoff_fd_tsnr as handoff
from test_handoff_coverage95 import fixture, decide as old_decide


def inputs():
    plan, review, qc = fixture()
    for row in qc.values():
        row.update(fd_mean="0.1", tsnr="20", fd_mean_outlier="FALSE", tsnr_outlier="FALSE")
    previous = old_decide(plan, review, qc)
    thresholds = {(task, "01", metric): dict(upper_fence=0.4, lower_fence=10)
                  for task in handoff.old.TASKS for metric in ("fd_mean", "tsnr")}
    return plan, previous, qc, thresholds


def test_parallel_failures_and_good_ugr_fallback_task_session_isolation():
    plan, previous, qc, thresholds = inputs()
    qc[("11935", "01", "ugr", "1")].update(fd_mean="0.5", tsnr="5", brain_coverage_pct="94")
    qc[("11935", "01", "doors", "1")]["tsnr"] = "5"
    qc[("11935", "02", "socialdoors", "1")] = dict(fd_mean="100", tsnr="0", brain_coverage_pct="0")
    runs = handoff.decide(previous, qc, thresholds, {}, set())
    failed = next(r for r in runs if r["task"] == "ugr" and r["run"] == "1")
    assert failed["selection_reason"] == "coverage:exclude_below_95;fd_mean:high_fd_mean;tsnr:low_tsnr"
    selected = handoff.old.select(plan, runs)
    assert {(r["analysis"], r["level"], r["input_runs"]) for r in selected} == {
        ("ugr", "L1", "2"), ("socialdoors", "L1", "1")}
    changes = handoff.selection_changes(plan, previous, runs)
    assert next(r for r in changes if r["task"] == "ugr")["change"] == "run_subset_changed"
    assert next(r for r in changes if r["task"] == "doors")["change"] == "removed"


@pytest.mark.parametrize("metric,value,state", [
    ("fd_mean", "0.4", "eligible"), ("fd_mean", "0.40001", "excluded_run_qc"),
    ("tsnr", "10", "eligible"), ("tsnr", "9.999", "excluded_run_qc"),
    ("brain_coverage_pct", "95", "eligible"), ("brain_coverage_pct", "94.999", "excluded_run_qc"),
    ("fd_mean", "", "review_missing_or_invalid"), ("tsnr", "nan", "review_missing_or_invalid"),
    ("fd_mean", "-1", "review_missing_or_invalid"), ("tsnr", "inf", "review_missing_or_invalid"),
])
def test_boundaries_missing_and_invalid(metric, value, state):
    _, previous, qc, thresholds = inputs()
    key = ("11935", "01", "ugr", "1")
    qc[key][metric] = value
    runs = handoff.decide(previous, qc, thresholds, {}, set())
    assert next(r for r in runs if handoff.audit.key(r) == key)["selection_status"] == state


def test_prior_exclusions_never_rescued_and_new_holds_preserved():
    _, previous, qc, thresholds = inputs()
    previous[0].update(selection_status="held_existing_decision", selection_reason="settled")
    held = handoff.audit.key(previous[0])
    key = ("11935", "01", "ugr", "1")
    runs = handoff.decide(previous, qc, thresholds, {key: dict(reason="hold")}, set())
    assert next(r for r in runs if handoff.audit.key(r) == held)["selection_reason"] == "settled"
    assert next(r for r in runs if handoff.audit.key(r) == key)["selection_status"] == "held_existing_decision"
    runs = handoff.decide(previous, qc, thresholds, {}, {"11935"})
    assert all(r["selection_status"] == "held_existing_decision" for r in runs)


def test_tedana_and_aggregate_flags_do_not_exclude():
    plan, previous, qc, thresholds = inputs()
    for row in qc.values():
        row.update(tedana_outlier="TRUE", imaging_qc_outlier="TRUE", brain_coverage_outlier="TRUE")
    runs = handoff.decide(previous, qc, thresholds, {}, set())
    assert all(r["selection_status"] == "eligible" for r in runs)
    assert {r["level"] for r in handoff.old.select(plan, runs) if r["analysis"] == "ugr"} == {"L2"}


def canonical_fixture():
    policy = json.loads((Path(__file__).parents[1] / "qc/qc_policy.json").read_text())
    policy["task_map"] = {t: p for p, tasks in policy["paradigms"].items() for t in tasks}
    policy["metrics"] = {k: policy["metrics"][k] for k in ("fd_mean", "tsnr")}
    rows = [dict(subject=str(10000+i), session=ses, task=task, run="1", fd_mean=v, tsnr=100-v)
            for task in ("doors", "socialdoors", "ugr") for ses in ("01", "02")
            for i, v in enumerate(([1, 2, 3, 4, 50] if ses == "01" else [20, 21, 22, 23, 24]))]
    thresholds = handoff.canonical.compute_thresholds(rows, policy)
    for row in rows:
        for metric in policy["metrics"]:
            t = next(t for t in thresholds if (t["task"], t["session"], t["metric"]) == (row["task"], row["session"], metric))
            row[metric + "_outlier"] = row[metric] > t["upper_fence"] if metric == "fd_mean" else row[metric] < t["lower_fence"]
    return rows, thresholds, policy


def test_single_pass_canonical_fences_not_reestimated_after_exclusion():
    rows, saved, policy = canonical_fixture()
    lookup, _ = handoff.validated_thresholds(rows, saved, policy)
    assert lookup[("ugr", "01", "fd_mean")]["upper_fence"] == 7
    assert lookup[("ugr", "02", "fd_mean")]["upper_fence"] == 26
    rows[-1]["fd_mean_outlier"] = "TRUE"
    with pytest.raises(ValueError, match="flag disagrees"):
        handoff.validated_thresholds(rows, saved, policy)


@pytest.mark.parametrize("change", ["fence", "direction", "population", "duplicate", "pooled", "iterative"])
def test_rejects_stale_or_wrong_thresholds(change):
    rows, saved, policy = canonical_fixture()
    if change == "fence":
        saved[0]["upper_fence"] += 1
    elif change == "direction":
        saved[0]["outlier_direction"] = "lower"
    elif change == "population":
        saved[0]["n"] -= 1
    elif change == "duplicate":
        saved.append(saved[0])
    elif change == "pooled":
        policy["threshold_grouping"] = ["paradigm"]
    else:
        policy["threshold_passes"] = 2
    with pytest.raises(ValueError):
        handoff.validated_thresholds(rows, saved, policy)


def test_actual_published_canonical_tables_are_consistent():
    root = Path(__file__).parents[1]
    def read(name):
        with (root / "qc" / name).open() as stream:
            return list(csv.DictReader(stream, delimiter="\t"))
    lookup, _ = handoff.validated_thresholds(read("run_qc.tsv"), read("thresholds.tsv"),
                                           json.loads((root / "qc/qc_policy.json").read_text()))
    assert ("ugr", "01", "fd_mean") in lookup


def test_selected_products_verified_without_touching_excluded_outputs(monkeypatch):
    plan, previous, qc, thresholds = inputs()
    for job in plan["jobs"]:
        job["root"] = "/project"
        job["output"] = f"/project/derivatives/{handoff.finish.VARIANT}/{job['task']}/{job['run']}"
    qc[("11935", "01", "ugr", "1")]["fd_mean"] = "1"
    runs = handoff.decide(previous, qc, thresholds, {}, set())
    checked = []
    monkeypatch.setattr(handoff.l1, "verified_complete", lambda job: checked.append((job["task"], job["run"])))
    monkeypatch.setattr(handoff.finish, "verified_l2", lambda *a: pytest.fail("No pair should be selected"))
    monkeypatch.setattr(handoff.audit, "file_state", lambda path: "present")
    handoff.verify_selected(plan, runs)
    assert ("ugr", "1") not in checked and ("ugr", "2") in checked
    monkeypatch.setattr(handoff.audit, "file_state", lambda path: "missing")
    with pytest.raises(ValueError, match="Selected input missing"):
        handoff.verify_selected(plan, runs)


def historical_fixture(tmp_path):
    project = tmp_path
    previous_dir = project / "work/previous"
    previous_dir.mkdir(parents=True)
    finish_dir = project / "work/finish"
    finish_dir.mkdir()
    plan, previous, qc, _ = inputs()
    plan.update(variant=handoff.finish.VARIANT, qc_used_for_selection=False)
    plan_path = finish_dir / "plan.json"
    plan_path.write_text(json.dumps(plan))
    (finish_dir / "plan.sha256").write_text(handoff.audit.sha(plan_path))
    files, _ = handoff.old.render(plan, previous, {})
    for name, text in files.items():
        path = previous_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    record = dict(policy=handoff.old.POLICY, config=dict(finish_dir=str(finish_dir), project_root=str(project)),
                  outputs={name: handoff.audit.sha(previous_dir / name) for name in files},
                  sources=[handoff.l1.signature(plan_path)], source_exclusions=[])
    (previous_dir / "provenance.json").write_text(json.dumps(record))
    (previous_dir / "provenance.sha256").write_text(handoff.audit.sha(previous_dir / "provenance.json"))
    canonical_rows, thresholds, policy = canonical_fixture()
    for row in qc.values():
        row.update(fd_mean="50", tsnr="50", fd_mean_outlier="TRUE", tsnr_outlier="TRUE")
    canonical_rows.extend(qc.values())
    # Regenerate the fixture's canonical fences/flags with its extra subject.
    for row in canonical_rows:
        row.update(fd_mean=float(row["fd_mean"]), tsnr=float(row["tsnr"]))
    thresholds = handoff.canonical.compute_thresholds(canonical_rows, policy)
    for row in canonical_rows:
        for metric in policy["metrics"]:
            t = next(t for t in thresholds if (t["task"], t["session"], t["metric"]) == (row["task"], row["session"], metric))
            row[metric + "_outlier"] = row[metric] > t["upper_fence"] if metric == "fd_mean" else row[metric] < t["lower_fence"]
    (project / "qc").mkdir()
    fields = list(dict.fromkeys(k for row in canonical_rows for k in row))
    (project / "qc/run_qc.tsv").write_text(handoff.old.table(canonical_rows, fields))
    (project / "qc/thresholds.tsv").write_text(handoff.old.table(thresholds, list(thresholds[0])))
    (project / "qc/qc_policy.json").write_text(json.dumps(policy))
    (project / "qc/provenance.json").write_text(json.dumps(dict(inventory=dict(source_excluded_subjects=[]))))
    (project / "code").mkdir()
    (project / "code/task_availability_holds.tsv").write_text("subject\tsession\ttask\trun\treason\n")
    return SimpleNamespace(project=project, previous=previous_dir, output=project / "work/new",
                           katie_cohort=None, sophia_cohort=None, doors_cohort=None)


def test_build_check_integrity_and_no_overwrite(tmp_path, monkeypatch):
    args = historical_fixture(tmp_path)
    called = []
    monkeypatch.setattr(handoff, "verify_selected", lambda *a: called.append(True))
    cohort = tmp_path / "sophia.tsv"
    cohort.write_text("subject\n11935\n12345\n")
    args.sophia_cohort = cohort
    handoff.build(args)
    handoff.check(args)
    assert len(called) == 2
    assert json.loads((args.output / "summary.json").read_text())["policy"] == handoff.POLICY
    assert "12345" in (args.output / "paper_membership.tsv").read_text()
    with pytest.raises(ValueError, match="new output directory"):
        handoff.build(args)
    (args.output / "ugr/subjects.txt").write_text("tamper\n")
    with pytest.raises(ValueError, match="output changed"):
        handoff.check(args)


@pytest.mark.parametrize("target", ["prior_output", "plan", "qc", "holds"])
def test_changed_evidence_rejected(tmp_path, monkeypatch, target):
    args = historical_fixture(tmp_path)
    monkeypatch.setattr(handoff, "verify_selected", lambda *a: None)
    handoff.build(args)
    path = {"prior_output": args.previous / "ugr/subjects.txt",
            "plan": tmp_path / "work/finish/plan.json",
            "qc": tmp_path / "qc/run_qc.tsv", "holds": tmp_path / "code/task_availability_holds.tsv"}[target]
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="Frozen input"):
        handoff.check(args)


def test_missing_selected_product_fails_before_publishing(tmp_path, monkeypatch):
    args = historical_fixture(tmp_path)
    def fail(*args):
        raise ValueError("Incomplete selected output")
    monkeypatch.setattr(handoff, "verify_selected", fail)
    with pytest.raises(ValueError, match="Incomplete"):
        handoff.build(args)
    assert not args.output.exists()


@pytest.mark.parametrize("target", ["prior_output", "plan"])
def test_build_rejects_changed_historical_evidence(tmp_path, monkeypatch, target):
    args = historical_fixture(tmp_path)
    monkeypatch.setattr(handoff, "verify_selected", lambda *a: pytest.fail("Stop before product validation"))
    path = args.previous / "ugr/subjects.txt" if target == "prior_output" else tmp_path / "work/finish/plan.json"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="changed"):
        handoff.build(args)
    assert not args.output.exists()


def test_both_ugr_runs_fail_removes_only_that_task():
    plan, previous, qc, thresholds = inputs()
    for run in ("1", "2"):
        qc[("11935", "01", "ugr", run)]["fd_mean"] = "1"
    runs = handoff.decide(previous, qc, thresholds, {}, set())
    assert {r["analysis"] for r in handoff.old.select(plan, runs)} == {"doors", "socialdoors"}
