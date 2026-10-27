"""Check the reviewed, Git-shared snapshot and its strict comparison subset."""
import csv
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1] / "qc/paired_difference/socialdoors-v1"


def rows(name):
    with (ROOT / name).open() as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_strict_snapshot_is_exact_numeric_qc_intersection():
    pairs = rows("diagnostic_pairs.tsv")
    strict = rows("strict_pairs.tsv")
    expected = []
    for row in pairs:
        assert row["session"] == "01"
        pass_qc = True
        for task in ("socialdoors", "doors"):
            assert 95 <= float(row[task + "_coverage_pct"]) <= 100
            assert float(row[task + "_tsnr"]) >= float(row[task + "_tsnr_fence"])
            pass_qc &= float(row[task + "_fd_mean"]) <= float(row[task + "_fd_mean_fence"])
        assert row["group"] == ("strict_pass" if pass_qc else "fd_tsnr_flagged")
        if pass_qc:
            expected.append(row)
    assert strict == expected
    assert len(pairs) == 540 and len(strict) == 484
    subjects = sorted({r["subject"] for r in strict})
    assert len(subjects) == 121
    assert (ROOT / "subjects_strict.txt").read_text().splitlines() == subjects
    for subject in {r["subject"] for r in pairs}:
        assert [r["contrast"] for r in pairs if r["subject"] == subject] == ["1", "2", "3", "4"]


def test_all_pairs_preserve_run_decisions_and_membership():
    runs = {(r["subject"], r["session"], r["task"], r["run"]): r for r in rows("run_membership.tsv")}
    pairs = rows("diagnostic_pairs.tsv")
    for row in pairs:
        for task in ("socialdoors", "doors"):
            run = runs[(row["subject"], "01", task, "1")]
            assert run["previous_selection_status"] == "eligible"
            assert run["diagnostic_included"] == "True"
            assert run["strict_selection_status"] in ("eligible", "excluded_run_qc")
            assert run["coverage_decision"] == "pass"
            assert run["qc_failure_reasons"] in ("", "fd_mean:high_fd_mean")
    members = rows("pair_membership.tsv")
    assert {r["subject"] for r in pairs} == {r["subject"] for r in members if r["diagnostic_pair"] == "True"}
    assert len({r["subject"] for r in pairs if r["group"] == "fd_tsnr_flagged"}) == 14


def test_report_statistics_reproduce_from_pair_metrics():
    pairs = {(r["subject"], r["contrast"]): r for r in rows("diagnostic_pairs.tsv")}
    metrics = rows("pair_metrics.tsv")
    assert len(metrics) == len(pairs)
    for row in metrics:
        pair = pairs[(row["subject"], row["contrast"])]
        for key in ("group", "flags", "session", "socialdoors_fd_mean", "doors_fd_mean", "socialdoors_tsnr", "doors_tsnr"):
            assert row[key] == pair[key]
        assert int(row["common_voxels"]) == 79801
    medians = {group: statistics.median(float(r["median_se"]) for r in metrics
                                      if r["contrast"] == "4" and r["group"] == group)
               for group in ("strict_pass", "fd_tsnr_flagged")}
    assert round(medians["strict_pass"], 2) == 93.98
    assert round(medians["fd_tsnr_flagged"], 2) == 125.90
    assert round(100 * (medians["fd_tsnr_flagged"] / medians["strict_pass"] - 1)) == 34
