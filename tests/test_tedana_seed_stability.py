from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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


seed_audit = load(
    "audit_tedana_seed_stability", CODE / "audit_tedana_seed_stability.py"
)


def candidate(era: str, index: int) -> dict[str, str]:
    subject = f"{10000 + index + {'E11': 0, 'XA30': 100, 'XA60': 200}[era]}"
    key = f"sub-{subject}_ses-01_task-trust_run-1"
    return {
        "subject": subject, "session": "01", "task": "trust", "run": "1",
        "run_key": key, "software_versions": era, "software_era": era,
        "nss_count": "1", "number_of_original_volumes": "100",
        "echo_times": "0.01;0.02;0.03;0.04", "echo_files": "a;b;c;d",
        "echo_jsons": "a.json;b.json;c.json;d.json", "fmriprep_mask": "mask.nii.gz",
        "fmriprep_confounds": "confounds.tsv", "n_ica": str(10 + index),
        "rejected_fraction": str(index / 10), "mean_fd": str(index / 20),
        "tedana_incremental_rank_fraction": str(index / 15),
    }


def test_seed_selection_is_deterministic_and_covers_all_eras() -> None:
    candidates = [candidate(era, index) for era in ("E11", "XA30", "XA60") for index in range(1, 8)]

    first = seed_audit.select_runs(candidates)
    second = seed_audit.select_runs(list(reversed(candidates)))

    assert first == second
    assert len(first) == 12
    assert {row["software_era"] for row in first} == {"E11", "XA30", "XA60"}
    reasons = ";".join(row["selection_reason"] for row in first)
    assert "typical_dimensionality" in reasons
    assert "high_incremental_rank" in reasons
    assert "high_rejected_fraction" in reasons
    assert "low_motion" in reasons
    assert "high_motion" in reasons


def test_seed_config_parser_rejects_unprespecified_seed() -> None:
    benchmark = load("benchmark_tedana_for_seed_test", CODE / "benchmark_tedana.py")

    assert benchmark.parse_configs("nss-fastica-seed-1,nss-fastica-seed-1000") == (
        "nss-fastica-seed-1", "nss-fastica-seed-1000"
    )
    with pytest.raises(Exception, match="unknown benchmark configuration"):
        benchmark.parse_configs("nss-fastica-seed-2")
