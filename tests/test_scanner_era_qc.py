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
                "software_era": era,
                "tsnr": value,
                "tsnr_outlier": False,
            }
        )
    thresholds = {
        (paradigm, metric): {"direction": "lower", "fence": 1.0}
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
    assert len(scanner_qc.read_tsv(output / "summary.tsv")) == 48
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
