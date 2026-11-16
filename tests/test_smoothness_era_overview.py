import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import plot_smoothness_era_overview as report

SOURCE = report.ROOT / "qc/smoothness_evaluation_6mm/paired_summary.tsv"


def test_frozen_counts_and_paired_eras():
    rows = report.load_summary(SOURCE)
    classic = [r for r in rows if r["metric"] == "classic_fwhm_combined"]
    assert sum(r["n_paired"] for r in classic) == 2786
    assert sum(r["n_outside"] for r in classic) == 5
    assert {r["task"] for r in classic} == set(report.TASKS)
    wave2_xa30 = [r for r in classic if r["session"] == "02" and r["software_era"] == "XA30"]
    assert {r["n_subjects"] for r in wave2_xa30} == {1}


def test_gap_calculations_are_within_task_session_and_metric():
    gaps = report.era_gaps(report.load_summary(SOURCE))
    assert len(gaps) == 16
    row = next(r for r in gaps if (r["task"], r["session"], r["metric"]) == ("socialdoors", "01", "classic_fwhm_combined"))
    rows = [r for r in report.load_summary(SOURCE) if (r["task"], r["session"], r["metric"]) == ("socialdoors", "01", "classic_fwhm_combined")]
    before = max(r["before_median"] for r in rows) - min(r["before_median"] for r in rows)
    after = max(r["after_median"] for r in rows) - min(r["after_median"] for r in rows)
    assert row["before_era_median_range_mm"] == pytest.approx(before)
    assert row["range_reduction_pct"] == pytest.approx(100 * (1 - after / before))
    assert 90 < row["range_reduction_pct"] < 100


@pytest.mark.parametrize("mutation", ["duplicate", "quartile", "nan", "count", "unknown", "missing_metric"])
def test_bad_summary_rejected(tmp_path, mutation):
    with SOURCE.open() as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields, rows = reader.fieldnames, list(reader)
    row = next(r for r in rows if r["metric"] == "classic_fwhm_combined")
    if mutation == "duplicate":
        rows.append(row.copy())
    elif mutation == "quartile":
        row["before_q1"] = "20"
    elif mutation == "nan":
        row["after_median"] = "nan"
    elif mutation == "count":
        row["n_paired"] = "99999"
    elif mutation == "unknown":
        row["software_era"] = "new-era"
    else:
        rows.remove(row)
    path = tmp_path / "summary.tsv"
    with path.open("w") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        report.load_summary(path)


def test_build_keeps_all_sessions_metrics_and_source_hashes(tmp_path, monkeypatch):
    calls = []
    def fake_plot(rows, session, metric, output):
        calls.append((session, metric))
        return f"{session}-{metric}.png"
    monkeypatch.setattr(report, "plot", fake_plot)
    validation = SOURCE.parent / "validation.json"
    original = SOURCE.read_bytes()
    report.build(SOURCE, validation, tmp_path)
    assert set(calls) == {(s, m) for s in ("01", "02") for m in report.METRICS}
    provenance = json.loads((tmp_path / "provenance.json").read_text())
    assert provenance["summary_sha256"] == hashlib.sha256(original).hexdigest()
    assert provenance["bmall_retry_substituted"] is False
    assert provenance["exclusions_changed"] is False
    assert SOURCE.read_bytes() == original
    assert "2,786" in (tmp_path / "README.md").read_text()


def test_validation_mismatch_stops_plotting(tmp_path):
    validation = tmp_path / "validation.json"
    data = json.loads((SOURCE.parent / "validation.json").read_text())
    data["counts"]["outside_tolerance"] = 0
    validation.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="counts disagree"):
        report.build(SOURCE, validation, tmp_path / "out")
    assert not (tmp_path / "out").exists()
