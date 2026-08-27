from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


summary = load(
    "summarize_tedana_dimensionality", CODE / "summarize_tedana_dimensionality.py"
)


def write_decomposition(
    directory: Path,
    key: str,
    pca_count: int,
    accepted: int,
    rejected: int,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"Component": [f"PCA_{index:02d}" for index in range(pca_count)]}).to_csv(
        directory / f"{key}_desc-PCA_metrics.tsv", sep="\t", index=False
    )
    (directory / f"{key}_desc-PCACrossComponent_metrics.json").write_text(
        json.dumps(
            {
                "aic": {"n_components": pca_count},
                "kic": {"n_components": max(1, pca_count - 2)},
                "mdl": {"n_components": max(1, pca_count - 4)},
                "varex_90": {"n_components": max(1, pca_count - 3)},
                "varex_95": {"n_components": max(1, pca_count - 1)},
            }
        )
    )
    classifications = ["accepted"] * accepted + ["rejected"] * rejected
    pd.DataFrame(
        {
            "Component": [f"ICA_{index:02d}" for index in range(len(classifications))],
            "classification": classifications,
        }
    ).to_csv(directory / f"{key}_desc-tedana_metrics.tsv", sep="\t", index=False)
    pd.DataFrame(
        {
            f"ICA_{index:02d}": [float(index), float(index + 1), float(index + 2)]
            for index in range(len(classifications))
        }
    ).to_csv(directory / f"{key}_desc-ICA_mixing.tsv", sep="\t", index=False)
    (directory / f"{key}_desc-denoised_bold.nii.gz").touch()
    (directory / "rf1_audit_provenance.json").write_text("{}\n")


def test_end_to_end_matched_dimensionality_summary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    audit_root = project / "derivatives" / "tedana-audit"
    output = project / "qc" / "tedana_audit" / "dimensionality"
    sentinel = project / "qc" / "tedana_audit" / "sentinel_runs.tsv"
    key = "sub-10001_ses-01_task-trust_run-1"
    historical = project / "derivatives" / "tedana" / "sub-10001" / "ses-01"
    write_decomposition(historical, key, 12, 5, 7)
    for config, pca, accepted, rejected in (
        ("full-fastica", 10, 5, 5),
        ("nss-fastica", 16, 5, 11),
        ("nss-robustica", 16, 4, 8),
    ):
        write_decomposition(
            audit_root / "benchmark" / config / key,
            key,
            pca,
            accepted,
            rejected,
        )
    row = {
        "subject": "10001",
        "session": "01",
        "task": "trust",
        "run": "1",
        "run_key": key,
        "nss_count": "2",
        "number_of_original_volumes": "100",
        "number_of_steady_state_volumes": "98",
        "software_versions": "XA60",
        "selection_reason": "synthetic",
        "tedana_pca_metrics": (
            historical / f"{key}_desc-PCA_metrics.tsv"
        ).relative_to(project).as_posix(),
        "tedana_metrics": (
            historical / f"{key}_desc-tedana_metrics.tsv"
        ).relative_to(project).as_posix(),
        "tedana_mixing": (
            historical / f"{key}_desc-ICA_mixing.tsv"
        ).relative_to(project).as_posix(),
    }
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row]).to_csv(sentinel, sep="\t", index=False)
    args = Namespace(
        project_root=project,
        audit_root=audit_root,
        output_dir=output,
        sentinel_tsv=sentinel,
        overwrite=False,
        dry_run=False,
    )

    assert summary.build(args) == 0
    assert summary.check(args) == 0

    result = summary.read_tsv(output / "paired_dimensionality.tsv")[0]
    assert result["historical_pca_components"] == "12"
    assert result["nss_minus_full_pca_components"] == "6"
    assert result["robustica_minus_fastica_ica_components"] == "-4"
    assert result["nss_robustica_pca_minus_ica_components"] == "4"
    assert result["nss_fastica_robustica_pca_contract_identical"] == "1"
    assert result["flag_nss_changes_pca_by_at_least_5"] == "1"
    assert len(summary.read_tsv(output / "review_runs.tsv")) == 1
    assert "Only `--dummy-scans 0`" in (output / "report.md").read_text()

    with (output / "paired_dimensionality.tsv").open("a") as handle:
        handle.write("tampered\n")
    assert summary.check(args) == 1
