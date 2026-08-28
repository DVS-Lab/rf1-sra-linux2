#!/usr/bin/env python3
"""Build the decision-facing RF1 TEDANA final report from validated audit tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from pipeline_utils import apply_umask_mode, ensure_safe_child_path


INPUTS = {
    "burden": Path("design/cohort_design_burden.tsv"),
    "classification": Path("design/classification_burden_summary.tsv"),
    "statistical": Path("design/statistical_burden_summary.tsv"),
    "tails": Path("design/extreme_tail_runs.tsv"),
    "scanner_protocol": Path("scanner_era/protocol_parameters.tsv"),
    "scanner_runs": Path("scanner_era/run_properties.tsv"),
    "scanner_pairs": Path("scanner_era/within_subject_pairs.tsv"),
    "nuisance_pairs": Path("nuisance_qc/paired_conditions.tsv"),
    "l1_runs": Path("l1_design/design_runs.tsv"),
    "l1_evs": Path("l1_design/task_ev_overlap.tsv"),
    "l1_contrasts": Path("l1_design/contrast_efficiency.tsv"),
    "high_pass": Path("l1_design/high_pass_audit.tsv"),
    "seed_pairs": Path("seed_stability/pairwise_vs_seed42.tsv"),
    "t2s": Path("benchmark/paired_t2s.tsv"),
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def numbers(rows: Sequence[dict[str, str]], column: str) -> np.ndarray:
    output = []
    for row in rows:
        try:
            value = float(row[column])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value):
            output.append(value)
    return np.asarray(output, dtype=float)


def median(rows: Sequence[dict[str, str]], column: str) -> float:
    values = numbers(rows, column)
    return float(np.median(values)) if len(values) else math.nan


def minimum(rows: Sequence[dict[str, str]], column: str) -> float:
    values = numbers(rows, column)
    return float(np.min(values)) if len(values) else math.nan


def maximum(rows: Sequence[dict[str, str]], column: str) -> float:
    values = numbers(rows, column)
    return float(np.max(values)) if len(values) else math.nan


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}" if math.isfinite(value) else "not available"


def by_value(rows: Sequence[dict[str, str]], column: str, value: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get(column) == value]


def build_report(tables: dict[str, list[dict[str, str]]]) -> str:
    burden = [row for row in tables["burden"] if row.get("design_status") == "complete"]
    nuisance_base_full = by_value(tables["nuisance_pairs"], "comparison", "base_vs_tedana_full")
    nuisance_full_nss = by_value(tables["nuisance_pairs"], "comparison", "tedana_full_vs_tedana_nss")
    l1_base = by_value(tables["l1_runs"], "condition", "base")
    l1_full = by_value(tables["l1_runs"], "condition", "tedana_full")
    l1_nss = by_value(tables["l1_runs"], "condition", "tedana_nss")
    seed_nonreference = [row for row in tables["seed_pairs"] if row.get("candidate_seed") != "42"]
    era_ica = {
        era: median(by_value(burden, "software_era", era), "n_ica")
        for era in ("E11", "XA30", "XA60")
    }
    protocol_counts: dict[str, int] = {}
    for row in tables["scanner_protocol"]:
        protocol_counts[row["status"]] = protocol_counts.get(row["status"], 0) + 1
    high_pass_ok = all(row.get("temphp_yn") == "0" for row in tables["high_pass"])
    n0 = [row for row in nuisance_full_nss if row.get("nss_count") == "0"]
    n0_exact = all(
        abs(float(row.get("normalized_rmse", "nan"))) == 0
        and abs(float(row.get("median_voxelwise_temporal_correlation", "nan")) - 1) < 1e-12
        for row in n0
    )
    lines = [
        "# RF1-SRA TEDANA Final Decision Audit", "",
        "## Scope And Production Architecture", "",
        "RF1 does not pre-residualize the BOLD series with TEDANA before task modeling. The production model starts from the full-length fMRIPrep preprocessed BOLD and fits task EVs, selected fMRIPrep nuisance EVs, and rejected TEDANA IC timecourses simultaneously in the same FSL/FEAT GLM. Audit-only nuisance projections below are task-independent QC comparisons; no residualized BOLD is a production input or output.", "",
        "No production derivative, component classification, event timing, or analysis exclusion is changed by this report.", "",
        "## Evidence Coverage", "",
        f"- Complete cohort burden rows: {len(burden)}",
        f"- Scanner-era run-property rows: {len(tables['scanner_runs'])}",
        f"- Within-subject cross-era pairs: {len(tables['scanner_pairs'])}",
        f"- Nuisance-QC run comparisons: {len(tables['nuisance_pairs'])}",
        f"- Canonical L1 condition/model rows: {len(tables['l1_runs'])}",
        f"- FastICA non-reference seed comparisons: {len(seed_nonreference)}", "",
        "## Decision Answers", "",
        "### 1. Is raw rejected-component count useful for RF1 QC?", "",
        "Only as a descriptive quantity. It does not measure independent model cost and must not independently determine exclusion.", "",
        "### 2. What are the primary TEDANA QC quantities?", "",
        "In order: actual incremental nuisance rank and residual DF; rejected fraction; rejected normalized variance; accepted/rejected overlap as descriptive ICA QC; and raw rejected count last.", "",
        "### 3. Is high dimensionality associated with XA60?", "",
        f"Median ICA count is E11={fmt(era_ica['E11'], 1)}, XA30={fmt(era_ica['XA30'], 1)}, and XA60={fmt(era_ica['XA60'], 1)}. Interpret this association together with task/session-stratified tables, not as a causal scanner-software effect.", "",
        "### 4. Can the XA60 association be linked to protocol or reconstruction?", "",
        f"The sidecar audit found {protocol_counts.get('identical_across_eras', 0)} invariant parameter groups, {protocol_counts.get('differs_systematically_by_era', 0)} systematic era differences, {protocol_counts.get('varies_within_era', 0)} within-era variations, and {protocol_counts.get('insufficient_cross_era_coverage', 0)} groups with insufficient coverage. Review the DICOM and image-property tables before attributing a mechanism. An unresolved mechanism should be described as an association with reconstructed-data/noise properties.", "",
        "### 5. Does TEDANA add artifact-control benefit beyond base fMRIPrep confounds?", "",
        f"For BASE to TEDANA-FULL, the median change in standardized DVARS is {fmt(median(nuisance_base_full, 'candidate_minus_reference_standardized_dvars'))}, FD-DVARS Spearman is {fmt(median(nuisance_base_full, 'candidate_minus_reference_fd_dvars_spearman'))}, and variance removed is {fmt(median(nuisance_base_full, 'candidate_minus_reference_variance_removed_fraction'))}. These are nuisance-model QC metrics, not reproductions of the production GLM.", "",
        "### 6. Does excluding NSS volumes improve the nuisance model?", "",
        f"For TEDANA-FULL to TEDANA-NSS, the median change in standardized DVARS is {fmt(median(nuisance_full_nss, 'candidate_minus_reference_standardized_dvars'))}, FD-DVARS Spearman is {fmt(median(nuisance_full_nss, 'candidate_minus_reference_fd_dvars_spearman'))}, and normalized RMSE is {fmt(median(nuisance_full_nss, 'normalized_rmse'))}. N=0 numerical identity: {'passed' if n0_exact else 'failed or unavailable'}.", "",
        "### 7. How much rank and DF does TEDANA consume in actual L1 designs?", "",
        f"Median residual DF is BASE={fmt(median(l1_base, 'residual_df'), 1)}, TEDANA-FULL={fmt(median(l1_full, 'residual_df'), 1)}, and TEDANA-NSS={fmt(median(l1_nss, 'residual_df'), 1)}. Median incremental total rank versus BASE is FULL={fmt(median(l1_full, 'incremental_total_rank_vs_base'), 1)} and NSS={fmt(median(l1_nss, 'incremental_total_rank_vs_base'), 1)}.", "",
        "### 8. Are designs close to saturation or poor estimability?", "",
        f"The minimum observed residual DF is FULL={fmt(minimum(l1_full, 'residual_df'), 1)} and NSS={fmt(minimum(l1_nss, 'residual_df'), 1)}. The maximum task-EV nuisance R-squared is FULL={fmt(maximum(l1_full, 'max_task_ev_nuisance_r_squared'))} and NSS={fmt(maximum(l1_nss, 'max_task_ev_nuisance_r_squared'))}; minimum relative contrast efficiency versus BASE is FULL={fmt(minimum(l1_full, 'minimum_relative_contrast_efficiency_vs_base'))} and NSS={fmt(minimum(l1_nss, 'minimum_relative_contrast_efficiency_vs_base'))}. Review extreme runs individually; no automatic threshold is imposed here.", "",
        "### 9. Do rejected ICs overlap accepted-component variance?", "",
        f"Across complete cohort rows, median rejected-on-accepted variance is {fmt(median(burden, 'rejected_on_accepted_variance'))} and the maximum is {fmt(maximum(burden, 'rejected_on_accepted_variance'))}. This remains descriptive component QC. It is not evidence that RF1 removes accepted signal before fitting task EVs.", "",
        "### 10. Is an aggressive-denoising comparison required?", "",
        "No. That framing does not describe RF1 production. Task and nuisance EVs are estimated simultaneously, so actual task/nuisance geometry and contrast precision are the relevant tests. No aggressive/non-aggressive/tedort production comparison or BOLD residualization is introduced.", "",
        "### 11. Should production remain AIC + FastICA + tedana_orig?", "",
        f"Across prespecified seeds versus seed 42, the maximum absolute change in incremental nuisance rank is {fmt(maximum([{'value': str(abs(float(row['candidate_minus_reference_incremental_nuisance_rank'])))} for row in seed_nonreference], 'value'), 1)}, and the maximum normalized RMSE is {fmt(maximum(seed_nonreference, 'normalized_rmse'))}. Interpret these with classification and QC deltas in the seed tables. Retain ordinary FastICA only if the observed changes are not scientifically consequential; do not match components by number.", "",
        "### 12. Should Motion24 remain QC-only?", "",
        "Yes unless a separate reviewed decision changes the production nuisance specification. This audit does not use Motion24 resemblance to alter TEDANA classification.", "",
        "### 13. Does the empirical T2*/optcom result warrant an fMRIPrep issue?", "",
        f"The tracked benchmark contains {len(tables['t2s'])} matched T2*/optcom comparison rows. Use those empirical results to support a narrowly scoped enhancement suggestion if the effect is reproducible and operationally relevant; this audit does not claim a correctness defect in fMRIPrep.", "",
        "## Production Gate", "",
        f"Canonical FEAT temporal high-pass disabled in every audited template: {'yes' if high_pass_ok else 'NO - resolve before production'}.", "",
        "If NSS-aware TEDANA is approved, keep the implementation narrow: derive validated N from fMRIPrep; run TEDANA 26.0.3 with `--dummy-scans N`; retain the canonical full-length fMRIPrep BOLD; prepend exactly N zeros to ICA timecourses; retain fMRIPrep NSS spikes; combine rejected ICs with full-length base confounds; and do not shift events. A reconstructed full-length TEDANA-denoised BOLD is unnecessary for the current RF1 architecture.", "",
        "Production remains unchanged until this report and the targeted run tables receive scientific review.",
    ]
    return "\n".join(lines) + "\n"


def build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); root = ensure_safe_child_path(project / "qc", args.audit_dir)
    paths = {name: root / relative for name, relative in INPUTS.items()}
    missing = [path for path in paths.values() if not path.is_file()]
    if args.dry_run:
        print(f"Final report inputs present: {len(paths) - len(missing)}/{len(paths)}")
        for path in missing: print(f"MISSING {path}")
        print(f"Tracked report: {root / 'final_report.md'}")
        return 1 if missing else 0
    if missing: raise ValueError("missing validated audit inputs: " + ", ".join(map(str, missing)))
    tables = {name: read_tsv(path) for name, path in paths.items()}
    report = root / "final_report.md"; provenance = root / "final_report_provenance.json"
    report.write_text(build_report(tables)); apply_umask_mode(report)
    payload = {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_derivatives_modified": False, "production_bold_residualized": False,
        "task_and_nuisance_fit_simultaneously_in_production": True,
        "inputs": {name: {"path": path.relative_to(project).as_posix(), "sha256": sha256(path)} for name, path in paths.items()},
        "report_sha256": sha256(report),
    }
    provenance.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n"); apply_umask_mode(provenance)
    print(f"Final report: {report}"); return 0


def check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); root = ensure_safe_child_path(project / "qc", args.audit_dir)
    report, provenance = root / "final_report.md", root / "final_report_provenance.json"; failures = []
    if not report.is_file(): failures.append("missing_final_report")
    if not provenance.is_file(): failures.append("missing_final_report_provenance")
    if not failures:
        payload = json.loads(provenance.read_text())
        if payload.get("report_sha256") != sha256(report): failures.append("report_checksum")
        for name, relative in INPUTS.items():
            path = root / relative
            if not path.is_file() or payload.get("inputs", {}).get(name, {}).get("sha256") != sha256(path): failures.append(f"input:{name}")
    for failure in failures: print(f"FAILED {failure}")
    if failures: print(f"CHECK FAILED: {len(failures)} final-report issue(s)."); return 1
    print("CHECK PASSED: TEDANA final decision report is current."); return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]; result = argparse.ArgumentParser(description=__doc__); children = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = children.add_parser(name); child.add_argument("--project-root", type=Path, default=project)
        child.add_argument("--audit-dir", type=Path, default=project / "qc" / "tedana_audit")
    children.choices["build"].add_argument("--dry-run", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try: return build(args) if args.command == "build" else check(args)
    except Exception as exc: print(f"ERROR: {exc}"); return 1


if __name__ == "__main__": raise SystemExit(main())
