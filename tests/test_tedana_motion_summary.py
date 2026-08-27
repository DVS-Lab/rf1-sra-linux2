from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


motion = load("summarize_tedana_motion", CODE / "summarize_tedana_motion.py")


def sentinel(subject: str) -> dict[str, str]:
    key = f"sub-{subject}_ses-01_task-trust_run-1"
    return {
        "subject": subject,
        "session": "01",
        "task": "trust",
        "run": "1",
        "run_key": key,
        "nss_count": "2",
        "selection_reason": "synthetic",
    }


def write_metric_inputs(
    project: Path,
    audit_root: Path,
    row: dict[str, str],
    changed_classification: bool = False,
) -> None:
    key = row["run_key"]
    for label, (source_config, motion_config) in motion.CONFIGS.items():
        components = (
            ["ICA_00", "ICA_01"]
            if label == "robustica"
            else [
                "ICA_00",
                "ICA_01",
                "ICA_02",
            ]
        )
        classifications = ["accepted", *("rejected" for _ in components[1:])]
        source = pd.DataFrame(
            {
                "Component": components,
                "classification": classifications,
                "normalized variance explained": [
                    0.6,
                    *([0.4] if len(components) == 2 else [0.25, 0.15]),
                ],
                "kappa": list(range(10, 10 - len(components), -1)),
                "rho": list(range(2, 2 + len(components))),
            }
        )
        audited = source.copy()
        if changed_classification and label == "robustica":
            audited.loc[0, "classification"] = "rejected"
        audited["R2stat motion24 model"] = [
            0.4,
            *([0.05] if len(components) == 2 else [0.3, 0.02]),
        ]
        audited["Fstat motion24 model"] = [4.0, *([1.0] * (len(components) - 1))]
        audited["pval motion24 model"] = [0.01, *([0.5] * (len(components) - 1))]
        for config, frame in ((source_config, source), (motion_config, audited)):
            directory = audit_root / "benchmark" / config / key
            directory.mkdir(parents=True, exist_ok=True)
            frame.to_csv(
                directory / f"{key}_desc-tedana_metrics.tsv", sep="\t", index=False
            )
            (directory / f"{key}_tedana_report.html").write_text("<html></html>\n")
            for index in range(len(components)):
                figure = directory / "figures" / f"comp_{index:03d}.png"
                figure.parent.mkdir(parents=True, exist_ok=True)
                figure.write_bytes(b"png")


def test_component_rows_reject_classification_changes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    audit_root = project / "derivatives" / "tedana-audit"
    row = sentinel("10001")
    write_metric_inputs(project, audit_root, row, changed_classification=True)

    with pytest.raises(ValueError, match="classification changed"):
        motion.component_rows(project, audit_root, row, "robustica")


def test_motion_summary_build_and_check(tmp_path: Path) -> None:
    project = tmp_path / "project"
    audit_root = project / "derivatives" / "tedana-audit"
    output = project / "qc" / "tedana_audit" / "motion"
    component_table = audit_root / "motion24_components.tsv"
    sentinel_path = project / "qc" / "tedana_audit" / "sentinel_runs.tsv"
    rows = [sentinel("10001"), sentinel("10002")]
    sentinel_path.parent.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(sentinel_path, sep="\t", index=False)
    for row in rows:
        write_metric_inputs(project, audit_root, row)
    args = Namespace(
        project_root=project,
        audit_root=audit_root,
        output_dir=output,
        component_table=component_table,
        sentinel_tsv=sentinel_path,
        overwrite=False,
        dry_run=False,
    )

    assert motion.run_build(args) == 0
    assert motion.run_check(args) == 0
    components = motion.read_tsv(component_table)
    summaries = motion.read_tsv(output / "summary_by_run_classification.tsv")
    review = motion.read_tsv(output / "review_manifest.tsv")
    assert len(components) == 10
    assert len(summaries) == 8
    assert review
    assert all(row["report_path"] for row in review)
    assert all(row["component_figure_path"] for row in review)
    accepted_fast = next(
        row
        for row in summaries
        if row["configuration"] == "fastica" and row["classification"] == "accepted"
    )
    assert float(accepted_fast["motion24_r2_median"]) == pytest.approx(0.4)
    assert (output / "figures" / "motion24_by_classification.png").is_file()
    assert "descriptive summaries" in (output / "report.md").read_text()

    with (output / "summary_by_task.tsv").open("a") as handle:
        handle.write("tampered\n")
    assert motion.run_check(args) == 1
