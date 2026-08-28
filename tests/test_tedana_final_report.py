from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


final = load("build_tedana_final_report", CODE / "build_tedana_final_report.py")


def test_final_report_uses_simultaneous_glm_architecture() -> None:
    burden = [
        {
            "design_status": "complete", "software_era": era, "n_ica": count,
            "rejected_on_accepted_variance": "0.1",
        }
        for era, count in (("E11", "10"), ("XA30", "20"), ("XA60", "30"))
    ]
    nuisance = [
        {
            "comparison": comparison, "nss_count": "0",
            "candidate_minus_reference_standardized_dvars": "0",
            "candidate_minus_reference_fd_dvars_spearman": "0",
            "candidate_minus_reference_variance_removed_fraction": "0",
            "normalized_rmse": "0", "median_voxelwise_temporal_correlation": "1",
        }
        for comparison in ("base_vs_tedana_full", "tedana_full_vs_tedana_nss")
    ]
    l1 = [
        {
            "condition": condition, "residual_df": "100",
            "incremental_total_rank_vs_base": "2",
            "max_task_ev_nuisance_r_squared": "0.1",
            "minimum_relative_contrast_efficiency_vs_base": "0.9",
        }
        for condition in ("base", "tedana_full", "tedana_nss")
    ]
    tables = {
        "burden": burden, "classification": [], "statistical": [], "tails": [],
        "scanner_protocol": [{"status": "identical_across_eras"}],
        "scanner_runs": [{}], "scanner_pairs": [], "nuisance_pairs": nuisance,
        "l1_runs": l1, "l1_evs": [], "l1_contrasts": [],
        "high_pass": [{"temphp_yn": "0"}],
        "seed_pairs": [
            {
                "candidate_seed": "1", "candidate_minus_reference_incremental_nuisance_rank": "0",
                "normalized_rmse": "0.001",
            }
        ],
        "t2s": [{}],
    }

    report = final.build_report(tables)

    assert "fits task EVs" in report
    assert "simultaneously" in report
    assert "No aggressive/non-aggressive/tedort" in report
    assert "no residualized BOLD" in report
