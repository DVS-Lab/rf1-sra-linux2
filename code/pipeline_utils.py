#!/usr/bin/env python3
"""Shared validation helpers for the RF1-SRA Linux2 preprocessing scripts."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path("/ZPOOL/data/projects/rf1-sra-linux2")
DEFAULT_SCANNER_CUTOFF = date.fromisoformat("2025-03-04")
TASKS_BY_SESSION = {
    "01": ("ugr", "trust", "sharedreward", "doors", "socialdoors"),
    "02": ("ugr", "doors", "socialdoors"),
}
RUNS_BY_TASK = {
    "doors": ("1",),
    "socialdoors": ("1",),
    "sharedreward": ("1", "2"),
    "trust": ("1", "2"),
    "ugr": ("1", "2"),
}


def read_subject_list(path: Path) -> list[str]:
    """Read subject IDs, ignoring blank lines and comments."""
    subjects: list[str] = []
    for line in path.read_text().splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            subjects.append(value.removeprefix("sub-"))
    return subjects


def tasks_for_session(session: str) -> tuple[str, ...]:
    return TASKS_BY_SESSION.get(session, TASKS_BY_SESSION["01"])


def runs_for_task(task: str) -> tuple[str, ...]:
    return RUNS_BY_TASK.get(task, ("1", "2"))


def choose_heuristic(session: str, newest_scan: date, subject: str = "") -> str:
    """Return the heudiconv heuristic file name for a session/date."""
    if session == "02":
        return "heuristics_XA30.py"
    if subject == "11433":
        return "heuristics_rf1.py"
    if newest_scan <= DEFAULT_SCANNER_CUTOFF:
        return "heuristics_rf1.py"
    return "heuristics_XA30.py"


def ensure_safe_child_path(root: Path, target: Path) -> Path:
    """Validate that target is a non-root path inside root."""
    root = root.resolve()
    target = target.resolve()
    if target in {Path("/"), root}:
        raise ValueError(f"Refusing unsafe path: {target}")
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path is outside expected root: {target}") from exc
    return target


@dataclass(frozen=True)
class IntendedForUpdate:
    json_path: Path
    intended_for: list[str]
    changed: bool
    reason: str = ""


def parse_task_run(filename: str, metadata: dict) -> tuple[str | None, str | None]:
    task = metadata.get("TaskName")
    task = task.lower() if isinstance(task, str) else None
    if task is None:
        task_match = re.search(r"_acq-([A-Za-z0-9]+)_", filename)
        task = task_match.group(1).lower() if task_match else None
    run_match = re.search(r"_run-([0-9]+)_", filename)
    run = run_match.group(1) if run_match else None
    if run is None and task in {"doors", "socialdoors"}:
        run = "1"
    return task, run


def intended_for_targets(
    bids_root: Path,
    subject: str,
    session: str | None,
    task: str,
    run: str,
) -> list[str]:
    ses_tag = f"_{session}" if session else ""
    func_rel = Path(session, "func") if session else Path("func")
    subject_dir = bids_root / subject
    targets: list[str] = []
    for echo in range(1, 5):
        name = f"{subject}{ses_tag}_task-{task}_run-{run}_echo-{echo}_part-mag_bold.nii.gz"
        rel = func_rel / name
        if (subject_dir / rel).exists():
            targets.append(rel.as_posix())
    return targets


def collect_intended_for_updates(bids_root: Path) -> list[IntendedForUpdate]:
    updates: list[IntendedForUpdate] = []
    for subject_dir in sorted(p for p in bids_root.glob("sub-*") if p.is_dir()):
        session_dirs = sorted(p for p in subject_dir.glob("ses-*") if p.is_dir())
        if not session_dirs:
            session_dirs = [subject_dir]
        for session_dir in session_dirs:
            session = session_dir.name if session_dir.name.startswith("ses-") else None
            fmap_dir = session_dir / "fmap"
            if not fmap_dir.is_dir():
                continue
            for json_path in sorted(fmap_dir.glob("*.json")):
                if "dwi" in json_path.name or not (
                    "fieldmap" in json_path.name or "magnitude" in json_path.name
                ):
                    continue
                data = json.loads(json_path.read_text())
                task, run = parse_task_run(json_path.name, data)
                if not task or not run:
                    updates.append(IntendedForUpdate(json_path, [], False, "could not parse task/run"))
                    continue
                targets = intended_for_targets(bids_root, subject_dir.name, session, task, run)
                if not targets:
                    updates.append(IntendedForUpdate(json_path, [], False, "no existing BOLD targets"))
                    continue
                changed = data.get("IntendedFor") != targets or data.get("Units") != "Hz"
                updates.append(IntendedForUpdate(json_path, targets, changed))
    return updates


def atomic_write_json(path: Path, data: dict) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as tmp:
            json.dump(data, tmp, indent=2, sort_keys=True)
            tmp.write("\n")
        Path(tmp_name).replace(path)
    finally:
        tmp_path = Path(tmp_name)
        if tmp_path.exists():
            tmp_path.unlink()


def warpkit_required_inputs(indir: Path, subject: str, session: str, task: str, run: str) -> list[Path]:
    stem = f"sub-{subject}_ses-{session}_task-{task}_run-{run}"
    paths: list[Path] = []
    for echo in range(1, 5):
        paths.append(indir / f"{stem}_echo-{echo}_part-mag_bold.nii.gz")
        paths.append(indir / f"{stem}_echo-{echo}_part-phase_bold.nii.gz")
        paths.append(indir / f"{stem}_echo-{echo}_part-phase_bold.json")
    return paths


def missing_paths(paths: Iterable[Path]) -> list[Path]:
    return [path for path in paths if not path.exists()]


def fmriprep_expected_outputs(bids_root: Path, deriv_root: Path, subject: str) -> list[Path]:
    outputs = [deriv_root / "fmriprep" / f"sub-{subject}.html"]
    for bold in sorted((bids_root / f"sub-{subject}").glob("ses-*/func/*_echo-1_part-mag_bold.nii.gz")):
        name = bold.name.replace("_bold.nii.gz", "_desc-preproc_bold.nii.gz")
        outputs.append(deriv_root / "fmriprep" / f"sub-{subject}" / bold.parents[1].name / "func" / name)
        confounds = bold.name.replace("_echo-1_part-mag_bold.nii.gz", "_part-mag_desc-confounds_timeseries.tsv")
        outputs.append(deriv_root / "fmriprep" / f"sub-{subject}" / bold.parents[1].name / "func" / confounds)
    return outputs


def is_fmriprep_complete(bids_root: Path, deriv_root: Path, subject: str) -> bool:
    expected = fmriprep_expected_outputs(bids_root, deriv_root, subject)
    return bool(expected) and all(path.exists() for path in expected)


def tedana_expected_outputs(deriv_root: Path, subject: str, session: str, task: str, run: str) -> list[Path]:
    prefix = f"sub-{subject}_ses-{session}_task-{task}_run-{run}"
    outdir = deriv_root / "tedana" / f"sub-{subject}" / f"ses-{session}"
    return [
        outdir / f"{prefix}_desc-denoised_bold.nii.gz",
        outdir / f"{prefix}_desc-ICA_mixing.tsv",
        outdir / f"{prefix}_desc-tedana_metrics.tsv",
    ]


def is_tedana_complete(deriv_root: Path, subject: str, session: str, task: str, run: str) -> bool:
    return all(path.exists() for path in tedana_expected_outputs(deriv_root, subject, session, task, run))
