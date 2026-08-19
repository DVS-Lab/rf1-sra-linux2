from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

import build_run_qc as qc  # noqa: E402


def policy() -> dict:
    return qc.load_policy(Path(__file__).resolve().parents[1] / "qc" / "qc_policy.json")


def metric_row(
    subject: str,
    task: str,
    *,
    tsnr: float = 10.0,
    fd_mean: float = 0.1,
    rejected: int = 2,
    coverage: float = 95.0,
    missing: str = "",
) -> dict:
    return {
        "subject": subject,
        "session": "01",
        "paradigm": "socialdoors" if task in {"socialdoors", "doors"} else task,
        "task": task,
        "run": "1",
        "tsnr": tsnr,
        "fd_mean": fd_mean,
        "tedana_total_components": 10,
        "tedana_accepted_components": 8,
        "tedana_rejected_components": rejected,
        "tedana_rejected_fraction": rejected / 10,
        "brain_coverage_pct": coverage,
        "missing_metrics": missing,
    }


def save_mask(path: Path, data: np.ndarray, affine: np.ndarray | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(
        nib.Nifti1Image(data.astype(np.uint8), np.eye(4) if affine is None else affine),
        path,
    )


def test_linear_quartiles_and_single_pass_threshold() -> None:
    assert qc.linear_quantile([0, 1, 2, 3], 0.25) == 0.75
    assert qc.linear_quantile([0, 1, 2, 3], 0.75) == 2.25

    rows = [
        metric_row(str(index), "trust", fd_mean=value)
        for index, value in enumerate([1, 2, 3, 4, 100])
    ]
    thresholds = qc.compute_thresholds(rows, policy())
    fd = next(
        row
        for row in thresholds
        if row["paradigm"] == "trust" and row["metric"] == "fd_mean"
    )
    assert (fd["q1"], fd["q3"], fd["iqr"], fd["upper_fence"]) == (2, 4, 2, 7)
    qc.apply_thresholds(rows, thresholds, policy())
    assert rows[-1]["fd_mean_outlier"] is True
    assert fd["upper_fence"] == 7


def test_only_poor_quality_direction_is_flagged() -> None:
    row = metric_row("10001", "trust", tsnr=1000, fd_mean=0, rejected=0, coverage=100)
    thresholds = []
    for metric, spec in policy()["metrics"].items():
        thresholds.append(
            {
                "paradigm": "trust",
                "metric": metric,
                "n": 10,
                "lower_fence": 1,
                "upper_fence": 10,
                "n_outliers": 0,
            }
        )
    qc.apply_thresholds([row], thresholds, policy())
    assert not row["imaging_qc_outlier"]
    assert all(row[flag] is False for flag in qc.METRIC_FLAGS.values())

    poor = metric_row("10002", "trust", tsnr=0, fd_mean=11, rejected=11, coverage=0)
    qc.apply_thresholds([poor], thresholds, policy())
    assert poor["imaging_qc_outlier"] is True
    assert all(poor[flag] is True for flag in qc.METRIC_FLAGS.values())
    assert poor["outlier_reasons"] == (
        "low_tsnr;high_fd_mean;high_tedana_rejected_components;low_brain_coverage"
    )


def test_socialdoors_and_doors_share_one_threshold_distribution() -> None:
    rows = [
        metric_row("10001", "socialdoors", tsnr=0),
        metric_row("10002", "socialdoors", tsnr=1),
        metric_row("10003", "doors", tsnr=100),
        metric_row("10004", "doors", tsnr=101),
    ]
    threshold = next(
        row
        for row in qc.compute_thresholds(rows, policy())
        if row["paradigm"] == "socialdoors" and row["metric"] == "tsnr"
    )
    assert threshold["bids_tasks"] == "socialdoors;doors"
    assert threshold["n"] == 4
    assert threshold["q1"] == 0.75
    assert threshold["q3"] == 100.25


def test_socialdoors_pair_flags_and_missing_pair() -> None:
    social = metric_row("10001", "socialdoors")
    social.update(qc_complete=True, imaging_qc_outlier=False, outlier_reasons="")
    doors = metric_row("10001", "doors")
    doors.update(
        qc_complete=True,
        imaging_qc_outlier=True,
        outlier_reasons="high_fd_mean",
    )
    lone = metric_row("10002", "socialdoors")
    lone.update(qc_complete=True, imaging_qc_outlier=False, outlier_reasons="")

    pairs = qc.build_socialdoors_pairs([social, doors, lone])
    complete, incomplete = pairs
    assert complete["either_run_imaging_qc_outlier"] is True
    assert complete["both_runs_imaging_qc_pass"] is False
    assert complete["pair_qc_complete"] is True
    assert incomplete["pair_qc_complete"] is False
    assert incomplete["pair_issue"] == "doors_missing"
    assert "exclude_subject" not in complete


def test_mriqc_exact_missing_and_ambiguous_sources(tmp_path: Path) -> None:
    source = tmp_path / "iqm.json"
    source.write_text(json.dumps({"tsnr": 42.5, "fd_mean": 0.12}))
    assert qc.extract_mriqc([source]) == ({"tsnr": 42.5, "fd_mean": 0.12}, [])
    values, missing = qc.extract_mriqc([])
    assert values == {"tsnr": None, "fd_mean": None}
    assert set(missing) == {
        "tsnr:missing_mriqc_json",
        "fd_mean:missing_mriqc_json",
    }
    _values, ambiguous = qc.extract_mriqc([source, source])
    assert all("ambiguous_mriqc_json" in issue for issue in ambiguous)


def test_mriqc_index_uses_only_echo2_part_mag(tmp_path: Path) -> None:
    func = tmp_path / "sub-10001" / "ses-01" / "func"
    func.mkdir(parents=True)
    for echo in (1, 2, 3):
        (
            func / f"sub-10001_ses-01_task-trust_run-1_echo-{echo}_part-mag_bold.json"
        ).touch()
    index = qc.index_run_files(
        tmp_path,
        "*_bold.json",
        {"trust"},
        lambda _path, entities: entities.get("echo") == "2"
        and entities.get("part") == "mag",
    )
    assert list(index) == [qc.RunKey("10001", "01", "trust", "1")]
    assert len(next(iter(index.values()))) == 1


def test_tedana_final_classification_counts(tmp_path: Path) -> None:
    source = tmp_path / "metrics.tsv"
    source.write_text(
        "component\tclassification\n0\taccepted\n1\trejected\n2\trejected\n"
    )
    values, missing = qc.extract_tedana([source])
    assert missing == []
    assert values == {
        "tedana_total_components": 3,
        "tedana_accepted_components": 1,
        "tedana_rejected_components": 2,
        "tedana_rejected_fraction": 2 / 3,
    }
    source.write_text("component\tclassification\n0\tignored\n")
    values, missing = qc.extract_tedana([source])
    assert values["tedana_rejected_components"] is None
    assert missing == ["tedana_rejected_components:invalid_classification_schema"]


def test_coverage_is_target_intersection_not_dice(tmp_path: Path) -> None:
    target = tmp_path / "target.nii.gz"
    target_data = np.zeros((2, 2, 2), dtype=np.uint8)
    target_data.flat[:4] = 1
    save_mask(target, target_data)
    for expected, count in ((100.0, 4), (75.0, 3), (50.0, 2)):
        run = tmp_path / f"run-{count}.nii.gz"
        run_data = np.zeros((2, 2, 2), dtype=np.uint8)
        run_data.flat[:count] = 1
        run_data.flat[4:] = 1
        save_mask(run, run_data)
        assert qc.compute_coverage(target, run) == expected


def test_coverage_resamples_target_to_run_mask_grid(tmp_path: Path) -> None:
    target = tmp_path / "target.nii.gz"
    run = tmp_path / "run.nii.gz"
    save_mask(target, np.ones((2, 2, 2), dtype=np.uint8))
    save_mask(run, np.ones((1, 1, 1), dtype=np.uint8), np.diag([2, 2, 2, 1]))
    assert qc.compute_coverage(target, run) == 100.0


def make_upstream_run(project: Path, subject: str, task: str, value: float) -> None:
    prefix = f"sub-{subject}_ses-01_task-{task}_run-1"
    bids = project / "bids" / f"sub-{subject}" / "ses-01" / "func"
    bids.mkdir(parents=True, exist_ok=True)
    (bids / f"{prefix}_echo-2_part-mag_bold.nii.gz").touch()

    mriqc = project / "derivatives" / "mriqc" / f"sub-{subject}" / "ses-01" / "func"
    mriqc.mkdir(parents=True, exist_ok=True)
    (mriqc / f"{prefix}_echo-2_part-mag_bold.json").write_text(
        json.dumps({"tsnr": 20 + value, "fd_mean": 0.1 + value / 100})
    )

    tedana = project / "derivatives" / "tedana" / f"sub-{subject}" / "ses-01" / "func"
    tedana.mkdir(parents=True, exist_ok=True)
    (tedana / f"{prefix}_desc-tedana_metrics.tsv").write_text(
        "component\tclassification\n0\taccepted\n1\trejected\n"
    )

    fmriprep = (
        project / "derivatives" / "fmriprep" / f"sub-{subject}" / "ses-01" / "func"
    )
    save_mask(
        fmriprep / f"{prefix}_part-mag_space-MNI152NLin6Asym_desc-brain_mask.nii.gz",
        np.ones((2, 2, 2), dtype=np.uint8),
    )


def test_complete_build_check_and_deterministic_regeneration(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    for index, task in enumerate(("sharedreward", "trust", "ugr"), start=1):
        make_upstream_run(project, f"1000{index}", task, float(index))
    make_upstream_run(project, "10004", "socialdoors", 4.0)
    make_upstream_run(project, "10004", "doors", 5.0)

    template = tmp_path / "template.nii.gz"
    exclusion = tmp_path / "exclusion.nii.gz"
    save_mask(template, np.ones((2, 2, 2), dtype=np.uint8))
    exclusion_data = np.zeros((2, 2, 2), dtype=np.uint8)
    exclusion_data[0, 0, 0] = 1
    save_mask(exclusion, exclusion_data)

    policy_data = json.loads(
        (Path(__file__).resolve().parents[1] / "qc" / "qc_policy.json").read_text()
    )
    policy_data["coverage"]["exclusion_mask_sha256"] = qc.sha256_file(exclusion)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy_data))
    output = project / "qc"
    excluded = tmp_path / "source-exclusions"
    excluded.mkdir()
    monkeypatch.setattr(qc, "utc_now", lambda: "2026-08-19T12:00:00+00:00")

    build_args = argparse.Namespace(
        project_root=project,
        output_dir=output,
        policy=policy_path,
        exclusion_mask=exclusion,
        excluded_source_root=excluded,
        include_source_excluded=False,
        template_brain_mask=template,
        overwrite=False,
        dry_run=False,
    )
    assert qc.run_build(build_args) == 0
    first_hashes = {
        relative: hashlib.sha256((output / relative).read_bytes()).hexdigest()
        for relative in qc.CANONICAL_OUTPUTS
    }
    build_args.overwrite = True
    assert qc.run_build(build_args) == 0
    second_hashes = {
        relative: hashlib.sha256((output / relative).read_bytes()).hexdigest()
        for relative in qc.CANONICAL_OUTPUTS
    }
    assert first_hashes == second_hashes

    check_args = argparse.Namespace(
        project_root=project,
        output_dir=output,
        policy=policy_path,
        excluded_source_root=excluded,
        include_source_excluded=False,
    )
    assert qc.run_check(check_args) == 0
    assert len(list((output / "spreadsheets").glob("*_qc.xlsx"))) == 4
    assert len(list((output / "figures").glob("*_histograms.png"))) == 4


def test_missing_metric_is_incomplete_not_pass_or_outlier() -> None:
    row = metric_row("10001", "trust", missing="tsnr:missing_mriqc_json")
    row["tsnr"] = None
    thresholds = qc.compute_thresholds([row], policy())
    tsnr_threshold = next(
        item
        for item in thresholds
        if item["paradigm"] == "trust" and item["metric"] == "tsnr"
    )
    assert tsnr_threshold["n"] == 0
    qc.apply_thresholds([row], thresholds, policy())
    assert row["qc_complete"] is False
    assert row["qc_status"] == "incomplete"
    assert row["tsnr_outlier"] is None
    assert row["imaging_qc_outlier"] is False
