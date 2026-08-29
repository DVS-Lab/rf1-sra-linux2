#!/usr/bin/env python3
"""Validate repository metadata that can be checked without production data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path


SCRIPT_RE = re.compile(
    r"`([^`]+\.(?:sh|py|m|json|txt))`|(?:bash|python(?:3)?)\s+([A-Za-z0-9_./+-]+\.(?:sh|py))"
)
QC_EXCLUSION_SHA256 = "1335b40c2ad94056cd54c1b41aea100f5063428045c63271f7909432f4e310ed"
DOCUMENTED_GENERATED_PATHS = {
    "qc/provenance.json",
    "qc/events/results/provenance.json",
}


def git_ls_files(repo: Path, pattern: str | None = None) -> list[str]:
    cmd = ["git", "-C", str(repo), "ls-files"]
    if pattern:
        cmd.append(pattern)
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return [line for line in result.stdout.splitlines() if line]


def validate_json(repo: Path) -> list[str]:
    errors: list[str] = []
    for rel in git_ls_files(repo, "*.json"):
        path = repo / rel
        try:
            json.loads(path.read_text())
        except (
            Exception
        ) as exc:  # noqa: BLE001 - include parser message in validation output.
            errors.append(f"{rel}: {exc}")
    return errors


def validate_no_tracked_bids(repo: Path) -> list[str]:
    tracked = git_ls_files(repo, "bids")
    if not tracked:
        return []
    preview = ", ".join(tracked[:5])
    suffix = "" if len(tracked) <= 5 else f", ... ({len(tracked)} total)"
    return [f"bids/ should not be tracked; found {preview}{suffix}"]


def validate_readme_paths(repo: Path) -> list[str]:
    errors: list[str] = []
    for readme in [repo / "README.md", repo / "code" / "README.md"]:
        if not readme.exists():
            errors.append(f"missing {readme.relative_to(repo)}")
            continue
        for match in SCRIPT_RE.finditer(readme.read_text()):
            token = next(group for group in match.groups() if group)
            if token.startswith("/") or "*" in token:
                continue
            rel = token.removeprefix("./")
            if rel in DOCUMENTED_GENERATED_PATHS:
                continue
            candidates = [repo / rel, repo / "code" / rel]
            if not any(candidate.exists() for candidate in candidates):
                errors.append(
                    f"{readme.relative_to(repo)} references missing path: {token}"
                )
    return errors


def validate_clean_status(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--short"],
        check=True,
        text=True,
        capture_output=True,
    )
    ignored = [
        line
        for line in result.stdout.splitlines()
        if line.startswith("?? .pytest_cache/")
    ]
    return [f"unexpected generated status line: {line}" for line in ignored]


def validate_qc(repo: Path) -> list[str]:
    errors: list[str] = []
    policy = repo / "qc" / "qc_policy.json"
    events_policy = repo / "qc" / "events" / "policy.json"
    exclusion = repo / "qc" / "reference" / "source-cerebellum-brainstem_mask.nii.gz"
    if not policy.is_file():
        errors.append("missing canonical QC policy: qc/qc_policy.json")
    if not events_policy.is_file():
        errors.append("missing canonical events QC policy: qc/events/policy.json")
    if not exclusion.is_file():
        errors.append("missing historical QC exclusion mask")
    elif hashlib.sha256(exclusion.read_bytes()).hexdigest() != QC_EXCLUSION_SHA256:
        errors.append("historical QC exclusion mask checksum mismatch")

    run_qc = repo / "qc" / "run_qc.tsv"
    if run_qc.is_file():
        with run_qc.open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            path_columns = (
                "bids_bold",
                "mriqc_json",
                "tedana_metrics",
                "fmriprep_brain_mask",
            )
            for line, row in enumerate(reader, start=2):
                for column in path_columns:
                    if str(row.get(column, "")).startswith("/"):
                        errors.append(
                            f"qc/run_qc.tsv:{line} contains an absolute {column} path"
                        )
    return errors


def validate_scanner_era_privacy(repo: Path) -> list[str]:
    errors: list[str] = []
    root = repo / "qc" / "tedana_audit" / "scanner_era"
    representatives = root / "dicom_representatives.tsv"
    parameters = root / "dicom_parameters.tsv"
    provenance = root / "provenance.json"
    forbidden_columns = {
        "representative_dicom", "source_scan_directory", "series_description"
    }
    forbidden_parameter = re.compile(
        r"date|time|uid|patient|subject|institution|address|physician|operator|"
        r"accession|birth|serial|studyid|comment|diagnos|^\([0-9a-f]{4},",
        re.I,
    )
    if representatives.is_file():
        with representatives.open(newline="") as handle:
            columns = set(csv.DictReader(handle, delimiter="\t").fieldnames or ())
        exposed = sorted(columns & forbidden_columns)
        if exposed:
            errors.append(
                "scanner-era DICOM mapping exposes forbidden columns: "
                + ", ".join(exposed)
            )
    if parameters.is_file():
        with parameters.open(newline="") as handle:
            for line, row in enumerate(csv.DictReader(handle, delimiter="\t"), start=2):
                if forbidden_parameter.search(str(row.get("parameter", ""))):
                    errors.append(
                        f"scanner-era DICOM parameter row {line} is not privacy-safe"
                    )
                    break
    if provenance.is_file():
        payload = json.loads(provenance.read_text())
        if payload.get("schema_version") != 2:
            errors.append("scanner-era provenance predates privacy-safe schema 2")
        if payload.get("dicom_scientific_keyword_allowlist_enforced") is not True:
            errors.append("scanner-era provenance lacks DICOM allowlist attestation")
        if payload.get("dicom_representative_paths_redacted") is not True:
            errors.append("scanner-era provenance lacks DICOM path-redaction attestation")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    repo = args.repo_root.resolve()

    errors = validate_json(repo)
    errors.extend(validate_no_tracked_bids(repo))
    errors.extend(validate_readme_paths(repo))
    errors.extend(validate_clean_status(repo))
    errors.extend(validate_qc(repo))
    errors.extend(validate_scanner_era_privacy(repo))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Repository metadata validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
