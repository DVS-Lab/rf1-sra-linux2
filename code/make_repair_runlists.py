#!/usr/bin/env python3
"""Create subject runlists for repairing incomplete pipeline stages."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipeline_utils import (
    collect_intended_for_updates,
    fmriprep_missing_outputs,
    missing_paths,
    read_subject_list,
    runs_for_task,
    tasks_for_session,
    warpkit_required_inputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBLIST = Path(__file__).resolve().parent / "sublist-new.txt"


@dataclass
class Issue:
    subject: str
    stage: str
    session: str
    task: str
    run: str
    path: str
    message: str


def add_issue(
    issues: list[Issue],
    subject: str,
    stage: str,
    *,
    session: str = "",
    task: str = "",
    run: str = "",
    path: str | Path = "",
    message: str = "",
) -> None:
    issues.append(
        Issue(
            subject=subject,
            stage=stage,
            session=session,
            task=task,
            run=run,
            path=str(path),
            message=message,
        )
    )


def write_subject_list(path: Path, subjects: set[str]) -> None:
    path.write_text("".join(f"{subject}\n" for subject in sorted(subjects)))


def source_has_dicoms(source_root: Path, folder_sub: str) -> bool:
    scans = source_root / f"Smith-SRA-{folder_sub}" / f"Smith-SRA-{folder_sub}" / "scans"
    return scans.is_dir() and any(scans.glob("*/*/DICOM/files/*.dcm"))


def bids_session_ok(project_root: Path, subject: str, session: str) -> tuple[bool, list[Path]]:
    bids_root = project_root / "bids"
    session_dir = bids_root / f"sub-{subject}" / f"ses-{session}"
    scans_tsv = session_dir / f"sub-{subject}_ses-{session}_scans.tsv"
    expected = [session_dir, scans_tsv]
    if session_dir.is_dir():
        has_bold = any((session_dir / "func").glob("*_bold.nii.gz"))
        if not has_bold:
            expected.append(session_dir / "func" / "*_bold.nii.gz")
    return all(path.exists() for path in expected[:2]) and not missing_paths(expected), missing_paths(expected)


def add_bids_issues(
    issues: list[Issue],
    project_root: Path,
    source_root: Path,
    subjects: list[str],
) -> set[str]:
    needs_repair: set[str] = set()
    for subject in subjects:
        for session in ("01", "02"):
            folder_sub = subject if session == "01" else f"{subject}-2"
            if not source_has_dicoms(source_root, folder_sub):
                if session == "01":
                    needs_repair.add(subject)
                    add_issue(
                        issues,
                        subject,
                        "bids",
                        session=session,
                        path=source_root / f"Smith-SRA-{folder_sub}",
                        message="required source DICOMs not found",
                    )
                continue
            ok, missing = bids_session_ok(project_root, subject, session)
            if ok:
                continue
            needs_repair.add(subject)
            for path in missing:
                add_issue(
                    issues,
                    subject,
                    "bids",
                    session=session,
                    path=path,
                    message="expected BIDS/prepdata output missing",
                )
    return needs_repair


def add_mriqc_issues(issues: list[Issue], project_root: Path, subjects: list[str]) -> set[str]:
    needs_repair: set[str] = set()
    bids_root = project_root / "bids"
    mriqc_root = project_root / "derivatives" / "mriqc"
    for subject in subjects:
        subject_dir = bids_root / f"sub-{subject}"
        if not subject_dir.is_dir():
            needs_repair.add(subject)
            add_issue(issues, subject, "mriqc", path=subject_dir, message="BIDS subject missing")
            continue
        subject_had_inputs = False
        for session_dir in sorted(subject_dir.glob("ses-*")):
            inputs = sorted((session_dir / "func").glob("*_echo-2_part-mag_bold.nii.gz"))
            if not inputs:
                needs_repair.add(subject)
                add_issue(
                    issues,
                    subject,
                    "mriqc",
                    session=session_dir.name.removeprefix("ses-"),
                    path=session_dir / "func",
                    message="no echo-2 magnitude BOLD inputs found",
                )
                continue
            subject_had_inputs = True
            for bold in inputs:
                rel = bold.relative_to(subject_dir)
                expected = mriqc_root / f"sub-{subject}" / rel.with_suffix("").with_suffix(".json")
                if not expected.is_file():
                    needs_repair.add(subject)
                    add_issue(
                        issues,
                        subject,
                        "mriqc",
                        session=session_dir.name.removeprefix("ses-"),
                        path=expected,
                        message="MRIQC JSON missing",
                    )
        if not subject_had_inputs:
            needs_repair.add(subject)
    return needs_repair


def add_warpkit_issues(issues: list[Issue], project_root: Path, subjects: list[str]) -> set[str]:
    needs_repair: set[str] = set()
    bids_root = project_root / "bids"
    for subject in subjects:
        for session in ("01", "02"):
            session_dir = bids_root / f"sub-{subject}" / f"ses-{session}"
            if not session_dir.is_dir():
                continue
            for task in tasks_for_session(session):
                for run in runs_for_task(task):
                    stem = f"sub-{subject}_ses-{session}_task-{task}_run-{run}"
                    func_dir = session_dir / "func"
                    if not (func_dir / f"{stem}_echo-1_part-mag_bold.nii.gz").is_file():
                        continue
                    required_inputs = warpkit_required_inputs(func_dir, subject, session, task, run)
                    missing_inputs = missing_paths(required_inputs)
                    if missing_inputs:
                        needs_repair.add(subject)
                        for path in missing_inputs:
                            add_issue(
                                issues,
                                subject,
                                "warpkit-input",
                                session=session,
                                task=task,
                                run=run,
                                path=path,
                                message="WarpKit input missing",
                            )
                        continue
                    outdir = project_root / "derivatives" / "warpkit" / f"sub-{subject}" / f"ses-{session}"
                    fmapdir = session_dir / "fmap"
                    expected = [
                        outdir / f"{stem}.warpkit_done",
                        fmapdir / f"sub-{subject}_ses-{session}_acq-{task}_run-{run}_fieldmap.nii.gz",
                        fmapdir / f"sub-{subject}_ses-{session}_acq-{task}_run-{run}_magnitude.nii.gz",
                        fmapdir / f"sub-{subject}_ses-{session}_acq-{task}_run-{run}_fieldmap.json",
                        fmapdir / f"sub-{subject}_ses-{session}_acq-{task}_run-{run}_magnitude.json",
                    ]
                    missing_outputs = missing_paths(expected)
                    if missing_outputs:
                        needs_repair.add(subject)
                        for path in missing_outputs:
                            add_issue(
                                issues,
                                subject,
                                "warpkit",
                                session=session,
                                task=task,
                                run=run,
                                path=path,
                                message="WarpKit output missing",
                            )
    return needs_repair


def add_intendedfor_issues(issues: list[Issue], project_root: Path, subjects: list[str]) -> set[str]:
    wanted = {f"sub-{subject}" for subject in subjects}
    needs_repair: set[str] = set()
    for update in collect_intended_for_updates(project_root / "bids"):
        subject = next((part for part in update.json_path.parts if part.startswith("sub-")), "")
        if subject not in wanted:
            continue
        subject_id = subject.removeprefix("sub-")
        if update.reason:
            needs_repair.add(subject_id)
            add_issue(
                issues,
                subject_id,
                "intendedfor",
                path=update.json_path,
                message=update.reason,
            )
        elif update.changed:
            needs_repair.add(subject_id)
            add_issue(
                issues,
                subject_id,
                "intendedfor",
                path=update.json_path,
                message="IntendedFor or Units differs from current BOLD targets",
            )
    return needs_repair


def add_fmriprep_issues(issues: list[Issue], project_root: Path, subjects: list[str]) -> set[str]:
    needs_repair: set[str] = set()
    bids_root = project_root / "bids"
    deriv_root = project_root / "derivatives"
    for subject in subjects:
        missing = fmriprep_missing_outputs(bids_root, deriv_root, subject)
        if not missing:
            continue
        needs_repair.add(subject)
        for path in missing:
            add_issue(
                issues,
                subject,
                "fmriprep",
                path=path,
                message="fMRIPrep completion output missing",
            )
    return needs_repair


def write_issues(path: Path, issues: list[Issue]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("subject", "stage", "session", "task", "run", "path", "message"),
            dialect="excel-tab",
        )
        writer.writeheader()
        for issue in issues:
            writer.writerow(issue.__dict__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sublist", type=Path, default=DEFAULT_SUBLIST)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra"),
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=PROJECT_ROOT / "logs" / "runlists",
        help="Directory for repair runlists and the missing-path TSV.",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Output filename prefix. Defaults to repair-YYYYmmdd-HHMMSS.",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    outdir = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or f"repair-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    subjects = read_subject_list(args.sublist)
    issues: list[Issue] = []

    bids = add_bids_issues(issues, project_root, args.source_root, subjects)
    mriqc = add_mriqc_issues(issues, project_root, subjects)
    warpkit = add_warpkit_issues(issues, project_root, subjects)
    intendedfor = add_intendedfor_issues(issues, project_root, subjects)
    fmriprep = add_fmriprep_issues(issues, project_root, subjects)

    prereq_repair = bids | warpkit | intendedfor
    fmriprep_ready = set(subjects) - prereq_repair

    outputs = {
        "bids-repair": bids,
        "mriqc-repair": mriqc,
        "warpkit-repair": warpkit,
        "intendedfor-repair": intendedfor,
        "fmriprep-prereq-repair": prereq_repair,
        "fmriprep-ready": fmriprep_ready,
        "fmriprep-incomplete": fmriprep,
    }
    for suffix, subject_set in outputs.items():
        path = outdir / f"{prefix}_{suffix}.txt"
        write_subject_list(path, subject_set)
        print(f"{path}: {len(subject_set)} subject(s)")

    issue_path = outdir / f"{prefix}_missing-paths.tsv"
    write_issues(issue_path, issues)
    print(f"{issue_path}: {len(issues)} issue row(s)")

    print()
    print("Use fmriprep-ready for subjects whose BIDS/WarpKit/IntendedFor prerequisites look complete.")
    print("Use fmriprep-incomplete later to resume fMRIPrep subjects that still lack completion outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
