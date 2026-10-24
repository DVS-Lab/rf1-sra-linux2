from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import pytest


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))

import build_scanner_era_qc as scanner_qc  # noqa: E402


def write_tsv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def make_inputs(project: Path) -> tuple[Path, Path]:
    run_rows: list[dict[str, object]] = []
    tasks = {
        "sharedreward": "sharedreward",
        "trust": "trust",
        "ugr": "ugr",
        "socialdoors": "socialdoors",
    }
    for paradigm_index, (paradigm, task) in enumerate(tasks.items(), start=1):
        for era_index, era in enumerate(scanner_qc.ERAS, start=1):
            subject = f"{10000 + paradigm_index * 10 + era_index}"
            prefix = f"sub-{subject}_ses-01_task-{task}_run-1_echo-2_part-mag_bold"
            directory = project / "bids" / f"sub-{subject}" / "ses-01" / "func"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{prefix}.nii.gz").touch()
            (directory / f"{prefix}.json").write_text(
                json.dumps({"SoftwareVersions": f"syngo MR {era}"})
            )
            mriqc = project / "derivatives/mriqc" / f"sub-{subject}" / "ses-01/func" / f"{prefix}.json"
            mriqc.parent.mkdir(parents=True)
            mriqc.write_text(json.dumps({"fwhm_avg": era_index + 1, "fwhm_x": era_index,
                "fwhm_y": era_index + 1, "fwhm_z": era_index + 2,
                "spacing_x": 2, "spacing_y": 2, "spacing_z": 3,
                "provenance": {"version": "24.0.2"}}))
            run_rows.append(
                {
                    "subject": subject,
                    "session": "01",
                    "paradigm": paradigm,
                    "task": task,
                    "run": "1",
                    "tsnr": 20 + era_index,
                    "fd_mean": 0.1 * era_index,
                    "tedana_rejected_components": 10 + era_index,
                    "brain_coverage_pct": 100 - era_index,
                    "tsnr_outlier": "FALSE",
                    "fd_mean_outlier": "FALSE",
                    "tedana_outlier": "FALSE",
                    "brain_coverage_outlier": "FALSE",
                    "imaging_qc_outlier": "FALSE",
                    "qc_status": "pass",
                    "mriqc_json": mriqc.relative_to(project).as_posix(),
                    "bids_bold": (directory / f"{prefix}.nii.gz")
                    .relative_to(project)
                    .as_posix(),
                }
            )
    run_columns = list(run_rows[0])
    run_qc = project / "qc" / "run_qc.tsv"
    write_tsv(run_qc, run_rows, run_columns)

    threshold_rows = []
    for paradigm in scanner_qc.PARADIGMS:
        for metric in scanner_qc.METRICS:
            lower = metric in {"tsnr", "brain_coverage_pct"}
            threshold_rows.append(
                {
                    "paradigm": paradigm,
                    "task": paradigm,
                    "session": "01",
                    "metric": metric,
                    "outlier_direction": "lower" if lower else "upper",
                    "lower_fence": 5 if lower else "",
                    "upper_fence": "" if lower else 50,
                }
            )
    threshold_columns = list(threshold_rows[0])
    thresholds = project / "qc" / "thresholds.tsv"
    write_tsv(thresholds, threshold_rows, threshold_columns)
    return run_qc, thresholds


def args(project: Path, run_qc: Path, thresholds: Path, **kwargs) -> argparse.Namespace:
    return argparse.Namespace(
        project_root=project,
        run_qc=run_qc,
        thresholds=thresholds,
        output_dir=project / "qc" / "scanner_era",
        overwrite=kwargs.get("overwrite", False),
        dry_run=kwargs.get("dry_run", False),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("syngo MR E11", "E11"),
        ("XA30", "XA30"),
        ("syngo MR XA60", "XA60"),
        ("unknown release", "unknown"),
    ],
)
def test_software_era(value: str, expected: str) -> None:
    assert scanner_qc.software_era(value) == expected


def test_summary_reports_e11_deltas() -> None:
    rows = []
    for era, value in (("E11", 10.0), ("XA30", 15.0), ("XA60", 20.0)):
        rows.append(
            {
                "paradigm": "trust",
                "subject": "10001",
                "task": "trust",
                "session": "01",
                "software_era": era,
                "tsnr": value,
                "tsnr_outlier": False,
            }
        )
    thresholds = {
        (paradigm, "01", metric): {"direction": "lower", "fence": 1.0}
        for paradigm in scanner_qc.PARADIGMS
        for metric in scanner_qc.METRICS
    }
    summary = scanner_qc.summarize(rows, thresholds)
    lookup = {
        row["software_era"]: row
        for row in summary
        if row["paradigm"] == "trust" and row["metric"] == "tsnr"
    }
    assert lookup["E11"]["median_delta_from_e11"] == 0
    assert lookup["XA30"]["median_delta_from_e11"] == 5
    assert lookup["XA30"]["median_pct_delta_from_e11"] == 50
    assert lookup["XA60"]["median_delta_from_e11"] == 10


def test_build_check_and_stale_sidecar_detection(tmp_path: Path) -> None:
    project = tmp_path / "project"
    run_qc, thresholds = make_inputs(project)
    build_args = args(project, run_qc, thresholds)
    assert scanner_qc.build(build_args) == 0
    output = project / "qc" / "scanner_era"
    assert len(scanner_qc.read_tsv(output / "run_metrics.tsv")) == 12
    assert len(scanner_qc.read_tsv(output / "summary.tsv")) == 108
    assert len(list((output / "figures").glob("*_by_scanner_era.png"))) == 4
    assert scanner_qc.check(build_args) == 0

    sidecar = next((project / "bids").rglob("*.json"))
    payload = json.loads(sidecar.read_text())
    payload["SoftwareVersions"] = "syngo MR XA60"
    sidecar.write_text(json.dumps(payload))
    assert scanner_qc.check(build_args) == 1


def test_unknown_software_version_fails_closed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    run_qc, _thresholds = make_inputs(project)
    sidecar = next((project / "bids").rglob("*.json"))
    sidecar.write_text(json.dumps({"SoftwareVersions": "mystery"}))
    with pytest.raises(ValueError, match="unrecognized SoftwareVersions"):
        scanner_qc.load_run_metrics(project, run_qc)


def test_scanner_summary_keeps_task_and_session_separate():
    rows = [dict(subject="10001", paradigm="socialdoors", task=task, session=ses,
                 software_era="E11", tsnr=value, tsnr_outlier=False)
            for task, ses, value in (("doors", "01", 1), ("socialdoors", "01", 20),
                                     ("socialdoors", "02", 100))]
    thresholds = {(r["task"], r["session"], m): {"fence": 0, "direction": "lower"}
                  for r in rows for m in scanner_qc.METRICS}
    result = scanner_qc.summarize(rows, thresholds)
    assert {(r["task"], r["session"], r["median"]) for r in result if r["metric"] == "tsnr"} == {
        ("doors", "01", 1), ("socialdoors", "01", 20), ("socialdoors", "02", 100)}


def test_legacy_pooled_thresholds_rejected(tmp_path):
    path = tmp_path / "thresholds.tsv"
    path.write_text("paradigm\tmetric\toutlier_direction\tlower_fence\nugr\ttsnr\tlower\t1\n")
    with pytest.raises(ValueError, match="legacy pooled"):
        scanner_qc.load_thresholds(path)


def test_anisotropic_smoothness_units_and_xa30_comparison(tmp_path):
    run_qc, thresholds = make_inputs(tmp_path)
    rows, _ = scanner_qc.load_run_metrics(tmp_path, run_qc)
    first = rows[0]
    assert first["fwhm_avg"] == 2
    assert first["fwhm_avg_mm"] == pytest.approx((1 * 2 + 2 * 2 + 3 * 3) / 3)
    assert first["fwhm_avg_mm"] != first["fwhm_avg"] * (2 + 2 + 3) / 3
    summary = scanner_qc.summarize(rows, scanner_qc.load_thresholds(thresholds))
    xa60 = next(r for r in summary if r["task"] == "trust" and r["software_era"] == "XA60"
                and r["metric"] == "fwhm_avg_mm")
    assert xa60["median_delta_from_xa30"] == pytest.approx(7 / 3)
    assert xa60["cohort_fence"] is None
    assert xa60["cohort_outlier_n"] is None
    assert "brain_coverage_pct" not in scanner_qc.PLOT_METRICS
    assert "brain_coverage_pct" in scanner_qc.RUN_COLUMNS


@pytest.mark.parametrize("damage", ["absent", "invalid", "spacing", "nonfinite"])
def test_missing_smoothness_retains_run_and_reports_missingness(tmp_path, damage):
    run_qc, thresholds = make_inputs(tmp_path)
    record = scanner_qc.read_tsv(run_qc)[0]
    path = tmp_path / record["mriqc_json"]
    if damage == "absent":
        path.unlink()
    elif damage == "invalid":
        path.write_text("{")
    else:
        data = json.loads(path.read_text())
        data["spacing_z" if damage == "spacing" else "fwhm_z"] = 0 if damage == "spacing" else "nan"
        path.write_text(json.dumps(data))
    rows, _ = scanner_qc.load_run_metrics(tmp_path, run_qc)
    assert len(rows) == 12 and rows[0]["fwhm_avg_mm"] is None
    assert rows[0]["imaging_qc_outlier"] is False
    summary = scanner_qc.summarize(rows, scanner_qc.load_thresholds(thresholds))
    missing = next(r for r in summary if r["task"] == record["task"] and r["software_era"] == "E11"
                   and r["metric"] == "fwhm_avg_mm")
    assert (missing["n"], missing["n_total_runs"], missing["n_missing"]) == (0, 1, 1)
    assert missing["median"] is None


def test_mriqc_provenance_detects_change_and_preserves_canonical_qc(tmp_path):
    run_qc, thresholds = make_inputs(tmp_path)
    before = (run_qc.read_bytes(), thresholds.read_bytes())
    build_args = args(tmp_path, run_qc, thresholds)
    scanner_qc.build(build_args)
    assert scanner_qc.check(build_args) == 0
    path = next((tmp_path / "derivatives/mriqc").rglob("*.json"))
    data = json.loads(path.read_text())
    data["fwhm_x"] += 1
    path.write_text(json.dumps(data))
    assert scanner_qc.check(build_args) == 1
    assert (run_qc.read_bytes(), thresholds.read_bytes()) == before


def test_smoothness_run_identity_and_path_guard(tmp_path):
    run_qc, _ = make_inputs(tmp_path)
    record = scanner_qc.read_tsv(run_qc)[0]
    record["mriqc_json"] = record["mriqc_json"].replace("run-1", "run-2")
    with pytest.raises(ValueError, match="identity"):
        scanner_qc.load_smoothness(tmp_path, record)
    record["mriqc_json"] = "../other.json"
    with pytest.raises(ValueError, match="escapes"):
        scanner_qc.load_smoothness(tmp_path, record)
