#!/usr/bin/env python3
"""Audit BASE, TEDANA-FULL, and TEDANA-NSS in canonical RF1 FEAT designs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from audit_tedana_design import selected_base_confounds, software_era
from genTedanaConfounds import rejected_component_columns
from pipeline_utils import apply_umask_mode, ensure_safe_child_path


CONDITIONS = ("base", "tedana_full", "tedana_nss")
REPOSITORIES = {
    "sharedreward": "rf1-sra-sharedreward",
    "trust": "rf1-sra-trust",
    "ugr": "rf1-sra-ugr",
    "doors": "rf1-sra-socdoors",
    "socialdoors": "rf1-sra-socdoors",
}
RUN_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "software_era", "analysis_type",
    "condition", "status", "issues", "n_rows", "n_task_columns", "n_nuisance_columns",
    "n_total_columns", "task_rank", "nuisance_rank", "total_rank", "residual_df",
    "rank_fraction", "condition_number", "exact_zero_columns", "duplicate_columns",
    "incremental_total_rank_vs_base", "residual_df_change_vs_base",
    "max_task_ev_nuisance_r_squared", "median_task_ev_nuisance_r_squared",
    "max_task_ev_vif", "min_task_ev_remaining_norm_fraction",
    "task_subspace_remaining_norm_fraction", "max_task_nuisance_canonical_correlation",
    "median_relative_contrast_efficiency_vs_base", "minimum_relative_contrast_efficiency_vs_base",
    "high_pass_enabled", "rendered_fsf", "design_matrix", "contrast_matrix",
)
EV_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "analysis_type", "condition",
    "task_ev_index", "nuisance_r_squared", "vif", "remaining_norm_fraction",
)
CONTRAST_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "analysis_type", "condition",
    "contrast_index", "contrast_variance", "relative_efficiency_vs_base",
)
OUTPUTS = (
    Path("design_runs.tsv"), Path("task_ev_overlap.tsv"), Path("contrast_efficiency.tsv"),
    Path("source_fsfs.tsv"), Path("high_pass_audit.tsv"), Path("report.md"),
    Path("provenance.json"),
)
SOURCE_FSF_COLUMNS = (
    "subject", "session", "task", "run", "run_key", "repository",
    "rendered_fsf", "source_status",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    apply_umask_mode(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def finite_matrix(frame: pd.DataFrame) -> np.ndarray:
    values = frame.apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(dtype=float)
    if not np.all(np.isfinite(values)): raise ValueError("nonfinite confound value")
    return values


def matrix_rank(values: np.ndarray) -> int:
    return int(np.linalg.matrix_rank(values)) if values.shape[1] else 0


def centered(values: np.ndarray) -> np.ndarray:
    return values - np.mean(values, axis=0, keepdims=True)


def basis(values: np.ndarray) -> np.ndarray:
    if not values.shape[1]: return np.empty((len(values), 0))
    u, singular, _ = np.linalg.svd(centered(values), full_matrices=False)
    if not len(singular) or singular[0] == 0: return np.empty((len(values), 0))
    tolerance = max(values.shape) * np.finfo(float).eps * singular[0]
    return u[:, singular > tolerance]


def standardized_condition_number(values: np.ndarray) -> float:
    current = centered(values)
    norms = np.linalg.norm(current, axis=0)
    current = current[:, norms > 0]
    if not current.shape[1]: return math.nan
    current = current / np.linalg.norm(current, axis=0)
    singular = np.linalg.svd(current, compute_uv=False)
    tolerance = max(current.shape) * np.finfo(float).eps * singular[0]
    positive = singular[singular > tolerance]
    return float(positive[0] / positive[-1]) if len(positive) == current.shape[1] else math.inf


def duplicate_columns(values: np.ndarray) -> int:
    signatures: dict[bytes, int] = {}
    duplicates = 0
    for index in range(values.shape[1]):
        item = np.ascontiguousarray(values[:, index]).copy(); item[item == 0] = 0
        signature = item.tobytes()
        if signature in signatures: duplicates += 1
        signatures[signature] = signatures.get(signature, 0) + 1
    return duplicates


def read_vest(path: Path) -> np.ndarray:
    lines = path.read_text().splitlines()
    try:
        start = lines.index("/Matrix") + 1
    except ValueError as exc:
        raise ValueError(f"VEST matrix marker missing: {path}") from exc
    rows = [[float(value) for value in line.split()] for line in lines[start:] if line.strip()]
    values = np.asarray(rows, dtype=float)
    if values.ndim != 2 or not values.size or not np.all(np.isfinite(values)):
        raise ValueError(f"invalid VEST matrix: {path}")
    return values


def nuisance_overlap(task: np.ndarray, nuisance: np.ndarray) -> tuple[list[dict[str, float]], float, float]:
    nuisance_basis = basis(nuisance)
    rows = []
    for index in range(task.shape[1]):
        ev = centered(task[:, [index]])[:, 0]
        total = float(np.dot(ev, ev))
        predicted = nuisance_basis @ (nuisance_basis.T @ ev) if nuisance_basis.shape[1] else np.zeros_like(ev)
        r2 = float(np.dot(predicted, predicted) / total) if total else 0.0
        rows.append(
            {
                "task_ev_index": index + 1, "nuisance_r_squared": min(max(r2, 0.0), 1.0),
                "vif": 1 / (1 - r2) if r2 < 1 else math.inf,
                "remaining_norm_fraction": math.sqrt(max(0.0, 1 - r2)),
            }
        )
    task_basis = basis(task)
    if task_basis.shape[1] and nuisance_basis.shape[1]:
        canonical = np.linalg.svd(task_basis.T @ nuisance_basis, compute_uv=False)
        maximum = float(canonical[0]) if len(canonical) else 0.0
        projected = task_basis - nuisance_basis @ (nuisance_basis.T @ task_basis)
        remaining = float(np.linalg.norm(projected) / np.linalg.norm(task_basis))
    else:
        maximum = 0.0; remaining = 1.0
    return rows, remaining, maximum


def contrast_variances(design: np.ndarray, contrasts: np.ndarray, task_columns: int) -> np.ndarray:
    inverse = np.linalg.pinv(design.T @ design)
    output = []
    for contrast in contrasts:
        vector = np.zeros(design.shape[1])
        vector[: min(task_columns, len(contrast))] = contrast[:task_columns]
        output.append(float(vector @ inverse @ vector))
    return np.asarray(output)


def rejected_frame(directory: Path, key: str, full_grid: bool) -> pd.DataFrame:
    metrics = pd.read_csv(directory / f"{key}_desc-tedana_metrics.tsv", sep="\t")
    name = f"{key}_desc-ICA_mixingFullGrid.tsv" if full_grid else f"{key}_desc-ICA_mixing.tsv"
    mixing = pd.read_csv(directory / name, sep="\t")
    indices = rejected_component_columns(metrics)
    return mixing.iloc[:, indices] if indices else pd.DataFrame(index=mixing.index)


def confound_frames(project: Path, audit_root: Path, row: dict[str, str]) -> dict[str, pd.DataFrame]:
    key = row["run_key"]
    base = selected_base_confounds(project / row["fmriprep_confounds"])
    full = rejected_frame(audit_root / "benchmark" / "full-fastica" / key, key, False)
    nss = rejected_frame(audit_root / "benchmark" / "nss-fastica" / key, key, True)
    return {
        "base": base,
        "tedana_full": pd.concat((base, full), axis=1),
        "tedana_nss": pd.concat((base, nss), axis=1),
    }


def find_rendered_fsf(fsl_root: Path, row: dict[str, str], include_ppi: bool) -> list[Path]:
    subject, session, task, run = (row[name] for name in ("subject", "session", "task", "run"))
    pattern = f"L1_sub-{subject}_task-{task}_ses-{session}_model-*_type-*_run-{run}*.fsf"
    candidates = sorted((fsl_root / f"sub-{subject}" / f"ses-{session}").glob(pattern))
    canonical = [path for path in candidates if "_type-act_" in path.name]
    if include_ppi: canonical.extend(path for path in candidates if "_type-act_" not in path.name)
    return canonical


def canonical_bold(project: Path, row: dict[str, str]) -> Path:
    return (
        project / "derivatives" / "fmriprep" / f"sub-{row['subject']}" /
        f"ses-{row['session']}" / "func" /
        f"{row['run_key']}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
    )


def canonical_confounds(project: Path, row: dict[str, str]) -> Path:
    return (
        project / "derivatives" / "fsl" / "confounds_tedana" /
        f"sub-{row['subject']}" / f"{row['run_key']}_desc-TedanaPlusConfounds.tsv"
    )


def generate_evs_command(repo: Path, row: dict[str, str]) -> list[str]:
    common = [
        "--subject", row["subject"], "--session", row["session"],
        "--run", row["run"], "--overwrite",
    ]
    if row["task"] == "ugr":
        return ["bash", str(repo / "code" / "run_gen3colfiles.sh"), *common, "--jobs", "1"]
    command = ["bash", str(repo / "code" / "gen3colfiles.sh"), *common]
    if row["task"] in ("doors", "socialdoors"):
        command.extend(("--task", row["task"]))
    return command


def render_only_command(
    repo: Path, row: dict[str, str], bold: Path | None = None,
    confounds: Path | None = None,
) -> list[str]:
    """Build the authoritative activation-only rendering command for one task."""
    command = [
        "bash", str(repo / "code" / "L1stats.sh"), row["subject"], row["run"], "0",
    ]
    if row["task"] in ("doors", "socialdoors"):
        command.append(row["task"])
    command.extend(("--session", row["session"]))
    if bold is not None:
        command.extend(("--bold", str(bold)))
    if confounds is not None:
        command.extend(("--confounds", str(confounds)))
    command.append("--render-only")
    return command


def render_missing_activation_fsf(
    project: Path, repo: Path, row: dict[str, str], fsl_root: Path,
) -> list[Path]:
    script = repo / "code" / "L1stats.sh"
    if not script.is_file():
        raise ValueError(f"canonical L1 renderer missing: {script}")
    ev_command = generate_evs_command(repo, row)
    command = render_only_command(
        repo, row, bold=canonical_bold(project, row),
        confounds=canonical_confounds(project, row),
    )
    environment = os.environ.copy()
    environment.update(
        {
            "RF1_SRA_UPSTREAM_ROOT": str(project),
            "BIDS_ROOT": str(project / "bids"),
            "FMRIPREP_ROOT": str(project / "derivatives" / "fmriprep"),
            "CONFOUNDS_ROOT": str(project / "derivatives" / "fsl" / "confounds_tedana"),
            "FSL_DERIVATIVES_ROOT": str(fsl_root),
            "HARMONIZED_ROOT": str(fsl_root / "harmonized"),
        }
    )
    ev_result = subprocess.run(
        ev_command, cwd=repo, env=environment, text=True, capture_output=True
    )
    if ev_result.returncode:
        detail = (ev_result.stderr or ev_result.stdout).strip()
        raise ValueError(
            f"{row['run_key']}: canonical task-EV generation failed in {repo}: {detail}"
        )
    result = subprocess.run(
        command, cwd=repo, env=environment, text=True, capture_output=True
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(
            f"{row['run_key']}: canonical activation FSF render failed in {repo}: {detail}"
        )
    models = find_rendered_fsf(fsl_root, row, include_ppi=False)
    if not models:
        raise ValueError(
            f"{row['run_key']}: render-only worker exited successfully but produced no "
            f"canonical activation FSF under {fsl_root}"
        )
    return models


def render_audit_fsf(source: Path, confounds: Path, output_stem: Path) -> Path:
    text = source.read_text()
    if not re.search(r"set fmri\(temphp_yn\)\s+0(?:\s|$)", text):
        raise ValueError(f"temporal high-pass is not disabled: {source}")
    text, output_count = re.subn(
        r'^set fmri\(outputdir\)\s+"[^"]*"', f'set fmri(outputdir) "{output_stem}.feat"', text,
        count=1, flags=re.MULTILINE,
    )
    text, confound_count = re.subn(
        r'^set confoundev_files\(1\)\s+"[^"]*"', f'set confoundev_files(1) "{confounds}"', text,
        count=1, flags=re.MULTILINE,
    )
    if output_count != 1 or confound_count != 1:
        raise ValueError(f"could not replace output/confound setting: {source}")
    fsf = output_stem.with_suffix(".fsf"); fsf.parent.mkdir(parents=True, exist_ok=True)
    fsf.write_text(text); apply_umask_mode(fsf); return fsf


def run_feat_model(command: str, fsf: Path) -> tuple[Path, Path]:
    stem = fsf.with_suffix("")
    result = subprocess.run([command, str(stem)], text=True, capture_output=True)
    if result.returncode:
        raise ValueError(f"feat_model failed for {fsf}: {(result.stderr or result.stdout).strip()}")
    matrix, contrasts = stem.with_suffix(".mat"), stem.with_suffix(".con")
    if not matrix.is_file() or not contrasts.is_file(): raise ValueError(f"feat_model outputs missing: {stem}")
    apply_umask_mode(matrix); apply_umask_mode(contrasts); return matrix, contrasts


def analysis_type(path: Path) -> str:
    match = re.search(r"_type-(.+?)_run-", path.name)
    return match.group(1) if match else "unknown"


def audit_model(
    project: Path, audit_root: Path, output_root: Path, repo: Path,
    row: dict[str, str], source_fsf: Path, feat_model: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    frames = confound_frames(project, audit_root, row)
    key = row["run_key"]; kind = analysis_type(source_fsf)
    common = {name: row[name] for name in ("subject", "session", "task", "run", "run_key")}
    common.update({"software_era": software_era(row.get("software_versions", "")), "analysis_type": kind})
    designs: dict[str, np.ndarray] = {}; contrasts: dict[str, np.ndarray] = {}
    paths: list[Path] = [source_fsf]
    metadata: dict[str, tuple[Path, Path, Path]] = {}
    for condition, frame in frames.items():
        directory = output_root / "rendered" / key / kind / condition
        confound_path = directory / f"{key}_{condition}_confounds.tsv"
        directory.mkdir(parents=True, exist_ok=True)
        frame.to_csv(confound_path, sep="\t", index=False, header=False); apply_umask_mode(confound_path)
        fsf = render_audit_fsf(source_fsf, confound_path, directory / "design")
        matrix_path, contrast_path = run_feat_model(feat_model, fsf)
        designs[condition] = read_vest(matrix_path); contrasts[condition] = read_vest(contrast_path)
        metadata[condition] = (fsf, matrix_path, contrast_path); paths.extend((confound_path, fsf, matrix_path, contrast_path))
    if len({matrix.shape[0] for matrix in designs.values()}) != 1: raise ValueError(f"{key}: design rows differ")
    run_rows = []; ev_rows = []; contrast_rows = []; base_variance = None
    base_rank = matrix_rank(designs["base"])
    for condition in CONDITIONS:
        design = designs[condition]; nuisance_columns = frames[condition].shape[1]
        if nuisance_columns >= design.shape[1]: raise ValueError(f"{key}: no task columns in {condition}")
        task_columns = design.shape[1] - nuisance_columns
        task = design[:, :task_columns]; nuisance = design[:, task_columns:]
        overlaps, remaining, canonical = nuisance_overlap(task, nuisance)
        variance = contrast_variances(design, contrasts[condition], task_columns)
        if condition == "base": base_variance = variance
        assert base_variance is not None
        relative = np.divide(base_variance, variance, out=np.full_like(variance, np.nan), where=variance > 0)
        total_rank = matrix_rank(design); fsf, matrix_path, contrast_path = metadata[condition]
        overlap_values = np.asarray([item["nuisance_r_squared"] for item in overlaps])
        vif_values = np.asarray([item["vif"] for item in overlaps])
        remaining_values = np.asarray([item["remaining_norm_fraction"] for item in overlaps])
        run_rows.append(
            {
                **common, "condition": condition, "status": "complete", "issues": "",
                "n_rows": design.shape[0], "n_task_columns": task_columns,
                "n_nuisance_columns": nuisance_columns, "n_total_columns": design.shape[1],
                "task_rank": matrix_rank(task), "nuisance_rank": matrix_rank(nuisance),
                "total_rank": total_rank, "residual_df": design.shape[0] - total_rank,
                "rank_fraction": total_rank / design.shape[0],
                "condition_number": standardized_condition_number(design),
                "exact_zero_columns": int(np.sum(np.all(design == 0, axis=0))),
                "duplicate_columns": duplicate_columns(design),
                "incremental_total_rank_vs_base": total_rank - base_rank,
                "residual_df_change_vs_base": base_rank - total_rank,
                "max_task_ev_nuisance_r_squared": float(np.max(overlap_values)),
                "median_task_ev_nuisance_r_squared": float(np.median(overlap_values)),
                "max_task_ev_vif": float(np.max(vif_values)),
                "min_task_ev_remaining_norm_fraction": float(np.min(remaining_values)),
                "task_subspace_remaining_norm_fraction": remaining,
                "max_task_nuisance_canonical_correlation": canonical,
                "median_relative_contrast_efficiency_vs_base": float(np.nanmedian(relative)),
                "minimum_relative_contrast_efficiency_vs_base": float(np.nanmin(relative)),
                "high_pass_enabled": 0, "rendered_fsf": fsf.relative_to(project).as_posix(),
                "design_matrix": matrix_path.relative_to(project).as_posix(),
                "contrast_matrix": contrast_path.relative_to(project).as_posix(),
            }
        )
        ev_rows.extend({**common, "condition": condition, **item} for item in overlaps)
        contrast_rows.extend(
            {
                **common, "condition": condition, "contrast_index": index + 1,
                "contrast_variance": variance[index], "relative_efficiency_vs_base": relative[index],
            }
            for index in range(len(variance))
        )
    return run_rows, ev_rows, contrast_rows, paths


def make_report(rows: Sequence[dict[str, Any]], high_pass: Sequence[dict[str, Any]], path: Path) -> None:
    complete = [row for row in rows if row["status"] == "complete"]
    lines = [
        "# TEDANA Canonical First-Level Design Audit", "",
        "This audit uses `feat_model` on copies of the canonical rendered RF1 first-level FSFs. It does not run FEAT, inspect task-effect magnitude, modify downstream repositories, or residualize production BOLD.", "",
        "## Coverage", "", f"- Complete condition/model rows: {len(complete)}",
        f"- Canonical models: {len(complete) // 3}", f"- Repository high-pass checks: {len(high_pass)}", "",
        "## Interpretation", "",
        "BASE, TEDANA-FULL, and TEDANA-NSS fit task and nuisance EVs simultaneously. Relative contrast efficiency is BASE contrast variance divided by candidate contrast variance; values below one indicate loss of precision after adding TEDANA nuisance EVs. Task-EV R-squared and VIF quantify task/nuisance collinearity rather than activation magnitude.", "",
        "The audit fails if a rendered canonical model enables FEAT temporal high-pass filtering. fMRIPrep cosine regressors remain in the nuisance matrix, and no second temporal high-pass is introduced.",
    ]
    path.write_text("\n".join(lines) + "\n"); apply_umask_mode(path)


def build(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    audit_root = ensure_safe_child_path(project / "derivatives", args.audit_root)
    rendered_root = ensure_safe_child_path(project / "derivatives", args.rendered_root)
    source_model_root = rendered_root / "source-models"
    rows = read_tsv(args.sentinel_tsv); repo_parent = args.repository_parent.resolve()
    repositories = {name: repo_parent / dirname for name, dirname in REPOSITORIES.items()}
    if args.dry_run:
        print(f"Would audit canonical FEAT design geometry for {len(rows)} sentinel run(s).")
        for repo in sorted(set(repositories.values())): print(f"  downstream: {repo}")
        print("Only feat_model will run; FEAT and production derivatives will not."); return 0
    if output.exists() and not args.overwrite: raise ValueError(f"output exists; review it or use --overwrite: {output}")
    run_rows = []; ev_rows = []; contrast_rows = []; source_rows = []
    inputs = [args.sentinel_tsv.resolve()]
    high_pass = []
    for repo in sorted(set(repositories.values())):
        templates = sorted((repo / "templates").glob("L1*.fsf"))
        for template in templates:
            match = re.search(r"set fmri\(temphp_yn\)\s+(\d+)", template.read_text())
            high_pass.append({"repository": repo.name, "template": str(template), "temphp_yn": match.group(1) if match else "missing"})
            if not match or match.group(1) != "0": raise ValueError(f"canonical high-pass audit failed: {template}")
    for index, row in enumerate(rows, start=1):
        repo = repositories.get(row["task"])
        if repo is None or not repo.is_dir(): raise ValueError(f"downstream repository missing for {row['task']}: {repo}")
        models = find_rendered_fsf(repo / "derivatives" / "fsl", row, args.include_ppi)
        source_status = "existing_downstream"
        if not models and args.render_missing:
            print(f"Preparing task EVs and activation FSF for {row['run_key']}", flush=True)
            models = render_missing_activation_fsf(
                project, repo, row, source_model_root / repo.name
            )
            source_status = "rendered_in_audit_workspace"
        if not models:
            command = " ".join(render_only_command(repo, row))
            raise ValueError(
                f"{row['run_key']}: canonical rendered activation FSF not found in {repo}; "
                f"rerun with --render-missing or render it explicitly with: {command}"
            )
        for source in models:
            source_rows.append(
                {
                    **{name: row[name] for name in ("subject", "session", "task", "run", "run_key")},
                    "repository": repo.name, "rendered_fsf": str(source),
                    "source_status": source_status,
                }
            )
            current_runs, current_evs, current_contrasts, current_inputs = audit_model(
                project, audit_root, rendered_root, repo, row, source, args.feat_model,
            )
            run_rows.extend(current_runs); ev_rows.extend(current_evs); contrast_rows.extend(current_contrasts); inputs.extend(current_inputs)
        print(f"Audited {index}/{len(rows)} {row['run_key']}", flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tedana-l1-design-", dir=output.parent) as temp:
        stage = Path(temp)
        write_tsv(stage / "design_runs.tsv", run_rows, RUN_COLUMNS)
        write_tsv(stage / "task_ev_overlap.tsv", ev_rows, EV_COLUMNS)
        write_tsv(stage / "contrast_efficiency.tsv", contrast_rows, CONTRAST_COLUMNS)
        write_tsv(stage / "source_fsfs.tsv", source_rows, SOURCE_FSF_COLUMNS)
        write_tsv(stage / "high_pass_audit.tsv", high_pass, ("repository", "template", "temphp_yn"))
        make_report(run_rows, high_pass, stage / "report.md")
        provenance = {
            "schema_version": 1, "generated_at": utc_now(), "sentinel_sha256": sha256(args.sentinel_tsv),
            "models": len(run_rows) // 3, "condition_rows": len(run_rows), "include_ppi": args.include_ppi,
            "feat_model_only": True, "full_feat_run": False, "production_derivatives_modified": False,
            "audit_source_fsfs_rendered": sum(
                row["source_status"] == "rendered_in_audit_workspace" for row in source_rows
            ),
            "downstream_feat_directories_modified": False,
            "task_effect_magnitude_inspected": False, "outputs": {},
        }
        for item in OUTPUTS:
            if item.name != "provenance.json": provenance["outputs"][item.as_posix()] = sha256(stage / item)
        (stage / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n"); apply_umask_mode(stage / "provenance.json")
        backup = output.with_name(f".{output.name}.backup")
        if backup.exists(): shutil.rmtree(backup)
        if output.exists(): output.rename(backup)
        stage.rename(output)
        if backup.exists(): shutil.rmtree(backup)
    print(f"Canonical models audited: {len(run_rows) // 3}"); print(f"Tracked report: {output / 'report.md'}"); return 0


def check(args: argparse.Namespace) -> int:
    project = args.project_root.resolve(); output = ensure_safe_child_path(project / "qc" / "tedana_audit", args.output_dir)
    failures = []; provenance_path = output / "provenance.json"; provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    if not provenance: failures.append("missing_provenance")
    run_path = output / "design_runs.tsv"
    if not run_path.is_file(): failures.append("missing_design_runs")
    else:
        rows = read_tsv(run_path); groups: dict[tuple[str, str], set[str]] = {}
        for row in rows: groups.setdefault((row["run_key"], row["analysis_type"]), set()).add(row["condition"])
        if any(value != set(CONDITIONS) for value in groups.values()): failures.append("condition_coverage")
    source_path = output / "source_fsfs.tsv"
    if not source_path.is_file():
        failures.append("missing_source_fsfs")
    else:
        source_rows = read_tsv(source_path)
        if len(source_rows) != provenance.get("models"):
            failures.append("source_fsf_coverage")
        if any(row["source_status"] not in ("existing_downstream", "rendered_in_audit_workspace") for row in source_rows):
            failures.append("source_fsf_status")
        rendered = sum(row["source_status"] == "rendered_in_audit_workspace" for row in source_rows)
        if rendered != provenance.get("audit_source_fsfs_rendered"):
            failures.append("source_fsf_provenance")
    for item in OUTPUTS:
        path = output / item
        if not path.is_file(): failures.append(f"missing:{path}")
        elif item.name != "provenance.json" and provenance.get("outputs", {}).get(item.as_posix()) != sha256(path): failures.append(f"checksum:{path}")
    if provenance.get("sentinel_sha256") != sha256(args.sentinel_tsv): failures.append("sentinel_checksum")
    for failure in failures: print(f"FAILED {failure}")
    if failures: print(f"CHECK FAILED: {len(failures)} L1-design issue(s)."); return 1
    print(f"CHECK PASSED: TEDANA canonical L1 design audit validated for {provenance['models']} model(s)."); return 0


def parser() -> argparse.ArgumentParser:
    project = Path(__file__).resolve().parents[1]
    result = argparse.ArgumentParser(description=__doc__); children = result.add_subparsers(dest="command", required=True)
    for name in ("build", "check"):
        child = children.add_parser(name)
        child.add_argument("--project-root", type=Path, default=project)
        child.add_argument("--sentinel-tsv", type=Path, default=project / "qc" / "tedana_audit" / "sentinel_runs.tsv")
        child.add_argument("--audit-root", type=Path, default=project / "derivatives" / "tedana-audit")
        child.add_argument("--rendered-root", type=Path, default=project / "derivatives" / "tedana-audit" / "l1-design")
        child.add_argument("--output-dir", type=Path, default=project / "qc" / "tedana_audit" / "l1_design")
        child.add_argument("--repository-parent", type=Path, default=Path("/ZPOOL/data/projects"))
        child.add_argument("--feat-model", default="feat_model")
        child.add_argument("--include-ppi", action="store_true")
    children.choices["build"].add_argument("--overwrite", action="store_true")
    children.choices["build"].add_argument("--dry-run", action="store_true")
    children.choices["build"].add_argument(
        "--render-missing", action="store_true",
        help="Render missing canonical activation FSFs with downstream --render-only workers",
    )
    return result


def main() -> int:
    args = parser().parse_args()
    try: return build(args) if args.command == "build" else check(args)
    except Exception as exc: print(f"ERROR: {exc}"); return 1


if __name__ == "__main__": raise SystemExit(main())
