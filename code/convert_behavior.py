#!/usr/bin/env python3
"""Convert private RF1-SRA behavioral logs into canonical BIDS events files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pipeline_utils import apply_umask_mode


TASKS = ("sharedreward", "trust", "ugr", "socialdoors", "doors")
STANDARD_RUNS = {
    "sharedreward": (1, 2),
    "trust": (1, 2),
    "ugr": (1, 2),
    "socialdoors": (1,),
    "doors": (1,),
}
TASK_SOURCE_DIRS = {
    "sharedreward": Path("Scan-Card_Guessing_Game/logs"),
    "trust": Path("Scan-Investment_Game/logs"),
    "ugr": Path("Scan-Lets_Make_A_Deal/logs"),
    "socialdoors": Path("Scan-Social_Doors/data"),
    "doors": Path("Scan-Social_Doors/data"),
}


class ConversionError(RuntimeError):
    """Raised when a source exists but cannot be converted safely."""


@dataclass(frozen=True, order=True)
class RunKey:
    subject: str
    session: str
    task: str
    run: int

    @property
    def event_name(self) -> str:
        return (
            f"sub-{self.subject}_ses-{self.session}_task-{self.task}_"
            f"run-{self.run}_events.tsv"
        )


@dataclass(frozen=True)
class SourceResolution:
    status: str
    path: Path | None = None
    detail: str = ""


@dataclass
class ConvertedRun:
    rows: list[dict[str, object]]
    columns: tuple[str, ...]
    trial_count: int
    expected_trial_count: int | None = None
    behaviorally_poor: bool = False
    notes: list[str] = field(default_factory=list)
    source_sha256: str = ""
    trial_fingerprint: str = ""

    @property
    def unexpected_trial_count(self) -> bool:
        return (
            self.expected_trial_count is not None
            and self.trial_count != self.expected_trial_count
        )

    @property
    def review_issues(self) -> tuple[str, ...]:
        issues: list[str] = []
        if self.unexpected_trial_count:
            issues.append("unexpected_trial_count")
        if self.behaviorally_poor:
            issues.append("behaviorally_poor")
        return tuple(issues)


@dataclass(frozen=True)
class CurationApproval:
    source_sha256: str
    trial_fingerprint: str
    reviewer: str
    note: str


CurationKey = tuple[RunKey, str]


def normalize_subject(value: str) -> str:
    subject = value.strip().removeprefix("sub-")
    if not subject or not subject.isdigit():
        raise argparse.ArgumentTypeError(f"invalid subject: {value}")
    return subject


def normalize_session(value: str) -> str:
    session = value.strip().removeprefix("ses-")
    if session in {"1", "2"}:
        session = f"0{session}"
    if session not in {"01", "02"}:
        raise argparse.ArgumentTypeError(f"session must be 01 or 02: {value}")
    return session


def normalize_run(value: str) -> int:
    try:
        run = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid run: {value}") from exc
    if run < 1:
        raise argparse.ArgumentTypeError(f"run must be positive: {value}")
    return run


def parse_tasks(value: str | Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return TASKS
    values = [value] if isinstance(value, str) else list(value)
    parsed: list[str] = []
    for item in values:
        parsed.extend(part.strip().lower() for part in item.split(",") if part.strip())
    if parsed == ["all"]:
        return TASKS
    invalid = sorted(set(parsed) - set(TASKS))
    if invalid:
        raise argparse.ArgumentTypeError(f"unknown task(s): {', '.join(invalid)}")
    return tuple(dict.fromkeys(parsed))


def _entities(path: Path) -> dict[str, str]:
    name = path.name
    if name.endswith(".nii.gz"):
        name = name[:-7]
    elif name.endswith(".nii"):
        name = name[:-4]
    entities: dict[str, str] = {}
    for part in name.split("_"):
        if "-" in part:
            key, value = part.split("-", 1)
            entities[key] = value
    return entities


def discover_bold_runs(
    bids_root: Path,
    subject: str,
    session: str,
    tasks: Sequence[str] = TASKS,
) -> list[RunKey]:
    func = bids_root / f"sub-{subject}" / f"ses-{session}" / "func"
    keys: set[RunKey] = set()
    if not func.is_dir():
        return []
    for path in sorted(func.glob("*_bold.nii*")):
        entities = _entities(path)
        task = entities.get("task")
        run = entities.get("run")
        if task not in tasks or run is None or not run.isdigit():
            continue
        keys.add(RunKey(subject, session, task, int(run)))
    return sorted(keys)


def event_path(bids_root: Path, key: RunKey) -> Path:
    return (
        bids_root
        / f"sub-{key.subject}"
        / f"ses-{key.session}"
        / "func"
        / key.event_name
    )


def _same_subject(left: str, right: str) -> bool:
    return left.lstrip("0") == right.lstrip("0")


def _session_matches(explicit: str | None, requested: str) -> bool:
    if explicit is None:
        return requested == "01"
    return explicit.zfill(2) == requested


def _raw_candidates(
    behavior_root: Path,
    key_task: str,
    subject: str,
    session: str,
) -> list[tuple[int, Path]]:
    source_dir = behavior_root / TASK_SOURCE_DIRS[key_task] / subject
    if not source_dir.is_dir():
        return []
    raw_task = {"sharedreward": "sharedreward", "trust": "trust", "ugr": "ultimatum"}[
        key_task
    ]
    pattern = re.compile(
        rf"^sub-?(?P<subject>\d+)(?:_ses-(?P<session>0?[12]))?_task-{raw_task}_run-(?P<run>\d+)_raw\.csv$",
        re.IGNORECASE,
    )
    candidates: list[tuple[int, Path]] = []
    for path in sorted(source_dir.glob("*.csv")):
        match = pattern.match(path.name)
        if not match or not _same_subject(match.group("subject"), subject):
            continue
        if not _session_matches(match.group("session"), session):
            continue
        candidates.append((int(match.group("run")), path))
    return candidates


def _resolve_numbered_sources(
    behavior_root: Path,
    subject: str,
    session: str,
    task: str,
    expected_runs: Sequence[int],
    approvals: dict[CurationKey, CurationApproval] | None = None,
) -> dict[int, SourceResolution]:
    candidates = _raw_candidates(behavior_root, task, subject, session)
    by_raw_run: dict[int, list[Path]] = {}
    for raw_run, path in candidates:
        by_raw_run.setdefault(raw_run, []).append(path)

    resolutions = {run: SourceResolution("missing") for run in expected_runs}
    duplicate_runs = {run: paths for run, paths in by_raw_run.items() if len(paths) > 1}
    if duplicate_runs:
        detail = "; ".join(
            f"raw run-{run}: {', '.join(path.name for path in paths)}"
            for run, paths in sorted(duplicate_runs.items())
        )
        return {
            run: SourceResolution("ambiguous", detail=detail) for run in expected_runs
        }

    raw_runs = set(by_raw_run)
    mapping_note = ""
    if task == "sharedreward":
        if 0 in raw_runs and 2 in raw_runs:
            detail = "both zero-based raw run-0 and one-based raw run-2 are present"
            return {
                run: SourceResolution("ambiguous", detail=detail)
                for run in expected_runs
            }
        if 0 in raw_runs:
            mapping = {0: 1, 1: 2}
        elif 2 in raw_runs:
            mapping = {1: 1, 2: 2}
        elif raw_runs == {1}:
            # Shared Reward has explicitly prompted for one-based run labels
            # since its first repository version. A lone raw run-1 therefore
            # belongs to BIDS run-1; it is not evidence for run-2.
            mapping = {1: 1}
            mapping_note = "one-based Shared Reward source label"
        else:
            mapping = {1: 1, 2: 2}
    else:
        mapping = {0: 1, 1: 2}

    for raw_run, bids_run in mapping.items():
        path = by_raw_run.get(raw_run, [None])[0]
        if path is not None and bids_run in resolutions:
            resolutions[bids_run] = SourceResolution("available", path, mapping_note)
    return resolutions


def _resolve_socialdoors_sources(
    behavior_root: Path,
    subject: str,
    session: str,
    task: str,
    expected_runs: Sequence[int],
) -> dict[int, SourceResolution]:
    resolutions = {run: SourceResolution("missing") for run in expected_runs}
    if 1 not in resolutions:
        return resolutions
    source_dir = behavior_root / TASK_SOURCE_DIRS[task] / subject
    if not source_dir.is_dir():
        return resolutions
    raw_task = "faces" if task == "socialdoors" else "doors"
    pattern = re.compile(
        rf"^sub-?(?P<subject>\d+)(?:_ses-(?P<session>0?[12]))?_task-socialReward_"
        rf"{raw_task}[AB][1-4]_events\.tsv$",
        re.IGNORECASE,
    )
    matches: list[Path] = []
    for path in sorted(source_dir.glob("*_events.tsv")):
        match = pattern.match(path.name)
        if not match or not _same_subject(match.group("subject"), subject):
            continue
        if _session_matches(match.group("session"), session):
            matches.append(path)
    if len(matches) == 1:
        resolutions[1] = SourceResolution("available", matches[0])
    elif len(matches) > 1:
        session_entity = "" if session == "01" else f"_ses-{session}"
        historical = (
            source_dir
            / f"sub-{subject}{session_entity}_task-{task}_run-1_events.tsv"
        )
        matching: list[Path] = []
        if historical.is_file():
            try:
                fingerprint = convert_source(task, historical).trial_fingerprint
                matching = [
                    path
                    for path in matches
                    if convert_source(task, path).trial_fingerprint == fingerprint
                ]
            except (ConversionError, OSError, csv.Error):
                matching = []
        if len(matching) == 1:
            resolutions[1] = SourceResolution(
                "available",
                matching[0],
                "matched historical canonical events fingerprint",
            )
        else:
            resolutions[1] = SourceResolution(
                "ambiguous", detail=", ".join(path.name for path in matches)
            )
    return resolutions


def resolve_sources(
    behavior_root: Path,
    subject: str,
    session: str,
    task: str,
    expected_runs: Sequence[int],
    approvals: dict[CurationKey, CurationApproval] | None = None,
) -> dict[int, SourceResolution]:
    if task in {"socialdoors", "doors"}:
        return _resolve_socialdoors_sources(
            behavior_root, subject, session, task, expected_runs
        )
    return _resolve_numbered_sources(
        behavior_root, subject, session, task, expected_runs, approvals
    )


def _read_delimited(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        first_line = handle.readline()
        alternate = "\t" if delimiter == "," else ","
        if delimiter not in first_line and alternate in first_line:
            delimiter = alternate
        handle.seek(0)
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ConversionError(f"source has no header: {path}") from exc
        header = [name.lstrip("\ufeff").strip() for name in raw_header]
        if not header or not any(header):
            raise ConversionError(f"source has no header: {path}")
        if any(not name for name in header):
            raise ConversionError(f"source header contains an empty column: {path}")
        duplicates = sorted({name for name in header if header.count(name) > 1})
        if duplicates:
            raise ConversionError(
                f"source header contains duplicate column(s): {', '.join(duplicates)}"
            )
        rows: list[dict[str, str]] = []
        previous_trial: int | None = None
        previous_onset: float | None = None
        for line_number, raw in enumerate(reader, start=2):
            values = [value.strip() for value in raw]
            if not any(values):
                continue
            normalized_values = [value.lstrip("\ufeff") for value in values]
            if normalized_values == header:
                raise ConversionError(
                    f"multiple run segments: repeated header at source row {line_number}"
                )
            if len(values) != len(header):
                raise ConversionError(
                    f"source row {line_number} has {len(values)} field(s); "
                    f"header has {len(header)}"
                )
            row = dict(zip(header, values))
            row["__source_line__"] = str(line_number)

            trial_text = next(
                (
                    row[name]
                    for name in ("TrialNumber", "Trial", "nTrial")
                    if row.get(name)
                ),
                "",
            )
            try:
                trial = int(float(trial_text)) if trial_text else None
            except ValueError:
                trial = None
            if trial == 1 and previous_trial is not None and previous_trial > 1:
                raise ConversionError(
                    f"multiple run segments: trial numbering resets at source row {line_number}"
                )
            if trial is not None:
                previous_trial = trial

            onset_text = next(
                (row[name] for name in ("decision_onset", "onset") if row.get(name)),
                "",
            )
            try:
                onset = float(onset_text) if onset_text else None
            except ValueError:
                onset = None
            if (
                onset is not None
                and math.isfinite(onset)
                and previous_onset is not None
                and onset + 1e-6 < previous_onset
            ):
                raise ConversionError(
                    f"multiple run segments: onset decreases at source row {line_number}"
                )
            if onset is not None and math.isfinite(onset):
                previous_onset = onset
            rows.append(row)
        return rows


def _source_line(row: dict[str, str], fallback: int) -> str:
    return row.get("__source_line__", str(fallback))


def _is_unrun_placeholder(row: dict[str, str]) -> bool:
    value = row.get("ran", "").strip().lower()
    return value in {"0", "0.0", "false", "no"}


def _explicitly_started(row: dict[str, str]) -> bool:
    value = row.get("ran", "").strip().lower()
    return value in {"1", "1.0", "true", "yes"}


def _trial_rows(
    source_rows: Sequence[dict[str, str]], marker_column: str, task_label: str
) -> tuple[list[dict[str, str]], int, int]:
    trials: list[dict[str, str]] = []
    placeholders = 0
    incomplete_terminal = 0
    for index, row in enumerate(source_rows, start=1):
        marker = row.get(marker_column, "").strip().lower()
        if _is_unrun_placeholder(row):
            placeholders += 1
            continue
        if not marker or marker in {marker_column.lower(), "nan", "n/a", "--", "none"}:
            if _explicitly_started(row) and all(
                _is_unrun_placeholder(later) for later in source_rows[index:]
            ):
                incomplete_terminal += 1
                continue
            raise ConversionError(
                f"{task_label} source row {_source_line(row, index)} claims to have run "
                f"but lacks {marker_column}"
            )
        trials.append(row)
    return trials, placeholders, incomplete_terminal


def _missing_number(row: dict[str, str], name: str) -> bool:
    value = row.get(name, "").strip().lower()
    if not value or value in {"nan", "n/a", "--", "none"}:
        return True
    try:
        return not math.isfinite(float(value))
    except ValueError:
        return True


def source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


FINGERPRINT_FIELDS = {
    "sharedreward": ("trial_id", "partner", "feedback"),
    "trust": ("trial_id", "partner", "cLow", "cHigh", "trust_value", "reciprocate"),
    "ugr": (
        "trial_id",
        "sociality",
        "endowment",
        "left_option",
        "right_option",
        "decision",
    ),
    "socialdoors": ("trial_type", "image_left", "image_right", "resp"),
    "doors": ("trial_type", "image_left", "image_right", "resp"),
}


def _trial_fingerprint(task: str, converted: ConvertedRun) -> str:
    fields = FINGERPRINT_FIELDS[task]
    seen: set[str] = set()
    records: list[list[str]] = []
    for row in converted.rows:
        trial_id = str(row.get("trial_id", len(records) + 1))
        if task in {"sharedreward", "trust", "ugr"} and trial_id in seen:
            continue
        seen.add(trial_id)
        records.append([_format_value(row.get(field)) for field in fields])
    payload = json.dumps(records, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


CURATION_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "issue",
    "source_sha256",
    "trial_fingerprint",
    "reviewer",
    "note",
)


def load_curation_approvals(path: Path | None) -> dict[CurationKey, CurationApproval]:
    if path is None or not path.exists():
        return {}
    approvals: dict[CurationKey, CurationApproval] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ConversionError(f"curation file has no header: {path}")
        missing = set(CURATION_COLUMNS) - set(reader.fieldnames)
        if missing:
            raise ConversionError(
                f"curation file lacks column(s): {', '.join(sorted(missing))}"
            )
        for line_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            if None in row or any(
                row.get(column) is None for column in CURATION_COLUMNS
            ):
                raise ConversionError(
                    f"curation row does not match header at {path}:{line_number}"
                )
            try:
                key = RunKey(
                    normalize_subject(row["subject"]),
                    normalize_session(row["session"]),
                    row["task"].strip().lower(),
                    int(row["run"]),
                )
            except (ValueError, argparse.ArgumentTypeError) as exc:
                raise ConversionError(
                    f"invalid curation identity at {path}:{line_number}: {exc}"
                ) from exc
            issue = row["issue"].strip()
            if key.task not in TASKS or issue not in {
                "unexpected_trial_count",
                "behaviorally_poor",
                "ambiguous_run_label",
            }:
                raise ConversionError(
                    f"invalid curation task/issue at {path}:{line_number}"
                )
            source_digest = row["source_sha256"].strip().lower()
            trial_digest = row["trial_fingerprint"].strip().lower()
            reviewer = row["reviewer"].strip()
            note = row["note"].strip()
            if not re.fullmatch(r"[0-9a-f]{64}", source_digest):
                raise ConversionError(f"invalid source_sha256 at {path}:{line_number}")
            if not re.fullmatch(r"[0-9a-f]{64}", trial_digest):
                raise ConversionError(
                    f"invalid trial_fingerprint at {path}:{line_number}"
                )
            if not reviewer or not note:
                raise ConversionError(
                    f"curation approval needs reviewer and note at {path}:{line_number}"
                )
            curation_key = (key, issue)
            if curation_key in approvals:
                raise ConversionError(
                    f"duplicate curation approval for {key.event_name} issue {issue}"
                )
            approvals[curation_key] = CurationApproval(
                source_digest, trial_digest, reviewer, note
            )
    return approvals


def issue_is_approved(
    key: RunKey,
    issue: str,
    converted: ConvertedRun,
    approvals: dict[CurationKey, CurationApproval],
) -> bool:
    approval = approvals.get((key, issue))
    return bool(
        approval
        and approval.source_sha256 == converted.source_sha256
        and approval.trial_fingerprint == converted.trial_fingerprint
    )


def _number(value: object, name: str) -> float:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "n/a", "--", "none"}:
        raise ConversionError(f"missing numeric {name}")
    try:
        result = float(text)
    except ValueError as exc:
        raise ConversionError(f"invalid numeric {name}: {text}") from exc
    if not math.isfinite(result):
        raise ConversionError(f"non-finite numeric {name}: {text}")
    return result


def _integer(value: object, name: str) -> int:
    result = _number(value, name)
    if not result.is_integer():
        raise ConversionError(f"non-integer {name}: {result}")
    return int(result)


def _duration(start: float, stop: float, name: str) -> float:
    value = stop - start
    if not math.isfinite(value) or value < 0:
        raise ConversionError(f"invalid {name}: {value}")
    return value


def _trial_id(row: dict[str, str], fallback: int) -> str:
    # Row order stays unique even in historical files that contain an appended
    # second run with TrialNumber values restarting from one.
    del row
    return str(fallback)


def _convert_sharedreward(path: Path) -> ConvertedRun:
    source_rows, placeholders, incomplete_terminal = _trial_rows(
        _read_delimited(path, ","), "decision_onset", "Shared Reward"
    )
    output: list[dict[str, object]] = []
    trial_count = 0
    partner_map = {1: "computer", 2: "stranger", 3: "friend"}
    feedback_map = {1: "punish", 2: "neutral", 3: "reward"}
    face_map = {1: "computer_non-face", 2: "stranger_face", 3: "friend_face"}
    for index, row in enumerate(source_rows, start=1):
        if (
            index == len(source_rows)
            and _explicitly_started(row)
            and any(
                _missing_number(row, name)
                for name in ("resp", "outcome_onset", "outcome_offset")
            )
        ):
            incomplete_terminal += 1
            continue
        checkpoint = len(output)
        try:
            decision_onset = _number(row.get("decision_onset"), "decision_onset")
            outcome_onset = _number(row.get("outcome_onset"), "outcome_onset")
            outcome_offset = _number(row.get("outcome_offset"), "outcome_offset")
            response = _number(row.get("resp"), "resp")
            partner_code = _integer(row.get("Partner"), "Partner")
            feedback_code = _integer(row.get("Feedback"), "Feedback")
            if partner_code not in partner_map or feedback_code not in feedback_map:
                raise ConversionError("unknown Shared Reward partner or feedback code")
            partner = partner_map[partner_code]
            trial_id = _trial_id(row, index)
            outcome_duration = _duration(
                outcome_onset, outcome_offset, "Shared Reward outcome duration"
            )
            if response <= 0:
                common = {
                    "response_time": "n/a",
                    "partner": partner,
                    "feedback": "n/a",
                    "trial_id": trial_id,
                }
                output.append(
                    {
                        "onset": decision_onset,
                        "duration": _duration(
                            decision_onset,
                            outcome_onset,
                            "Shared Reward missed-decision duration",
                        ),
                        "trial_type": "missed_decision",
                        **common,
                    }
                )
                output.append(
                    {
                        "onset": outcome_onset,
                        "duration": outcome_duration,
                        "trial_type": "missed_outcome",
                        **common,
                    }
                )
            else:
                response_time = _number(row.get("rt"), "rt")
                feedback = feedback_map[feedback_code]
                common = {
                    "response_time": response_time,
                    "partner": partner,
                    "feedback": feedback,
                    "trial_id": trial_id,
                }
                output.append(
                    {
                        "onset": decision_onset,
                        "duration": response_time,
                        "trial_type": face_map[partner_code],
                        **common,
                    }
                )
                output.append(
                    {
                        "onset": outcome_onset,
                        "duration": outcome_duration,
                        "trial_type": f"event_{partner}_{feedback}",
                        **common,
                    }
                )
        except ConversionError as exc:
            del output[checkpoint:]
            raise ConversionError(
                f"Shared Reward source row {_source_line(row, index)} is invalid: {exc}"
            ) from exc
        trial_count += 1
    if not output:
        raise ConversionError("no usable Shared Reward trials")
    notes: list[str] = []
    if placeholders:
        notes.append(f"omitted {placeholders} explicit ran=0 placeholder row(s)")
    if incomplete_terminal:
        notes.append(
            f"omitted {incomplete_terminal} terminal interrupted trial row(s)"
        )
    return ConvertedRun(
        output,
        (
            "onset",
            "duration",
            "trial_type",
            "response_time",
            "partner",
            "feedback",
            "trial_id",
        ),
        trial_count,
        expected_trial_count=54,
        notes=notes,
    )


def _convert_trust(path: Path) -> ConvertedRun:
    source_rows, placeholders, incomplete_terminal = _trial_rows(
        _read_delimited(path, ","), "onset", "Trust"
    )
    output: list[dict[str, object]] = []
    trial_count = 0
    partner_map = {1: "computer", 2: "stranger", 3: "friend"}
    for index, row in enumerate(source_rows, start=1):
        checkpoint = len(output)
        try:
            onset = _number(row.get("onset"), "onset")
            response = _number(row.get("resp"), "resp")
            partner_code = _integer(row.get("Partner"), "Partner")
            if partner_code not in partner_map:
                raise ConversionError("unknown Trust partner code")
            partner = partner_map[partner_code]
            left = _integer(row.get("cLeft"), "cLeft")
            right = _integer(row.get("cRight"), "cRight")
            low, high = min(left, right), max(left, right)
            trial_id = _trial_id(row, index)
            if response == 999:
                isi_onset_text = row.get("ISI_onset", "").strip()
                if isi_onset_text:
                    decision_duration = _duration(
                        onset,
                        _number(isi_onset_text, "ISI_onset"),
                        "Trust missed-decision duration",
                    )
                else:
                    decision_duration = 3.0
                output.append(
                    {
                        "onset": onset,
                        "duration": decision_duration,
                        "trial_type": "missed_trial",
                        "response_time": "n/a",
                        "trust_value": "n/a",
                        "choice": "n/a",
                        "cLow": low,
                        "cHigh": high,
                        "partner": partner,
                        "reciprocate": "n/a",
                        "trial_id": trial_id,
                    }
                )
            else:
                response_time = _number(row.get("rt"), "rt")
                choice = row.get("highlow", "").strip().lower()
                if choice not in {"high", "low"}:
                    choice = "n/a"
                common = {
                    "response_time": response_time,
                    "trust_value": int(response),
                    "choice": choice,
                    "cLow": low,
                    "cHigh": high,
                    "partner": partner,
                    "trial_id": trial_id,
                }
                output.append(
                    {
                        "onset": onset,
                        "duration": response_time,
                        "trial_type": f"choice_{partner}",
                        "reciprocate": "n/a",
                        **common,
                    }
                )
                if response > 0:
                    outcome_onset = _number(row.get("outcome_onset"), "outcome_onset")
                    outcome_offset = _number(
                        row.get("outcome_offset"), "outcome_offset"
                    )
                    reciprocate = _integer(row.get("Reciprocate"), "Reciprocate")
                    if reciprocate not in {0, 1}:
                        raise ConversionError("unknown Trust reciprocation code")
                    outcome_label = "recip" if reciprocate else "defect"
                    output.append(
                        {
                            "onset": outcome_onset,
                            "duration": _duration(
                                outcome_onset, outcome_offset, "Trust outcome duration"
                            ),
                            "trial_type": f"outcome_{partner}_{outcome_label}",
                            "reciprocate": outcome_label,
                            **common,
                        }
                    )
        except ConversionError as exc:
            del output[checkpoint:]
            raise ConversionError(
                f"Trust source row {_source_line(row, index)} is invalid: {exc}"
            ) from exc
        trial_count += 1
    if not output:
        raise ConversionError("no usable Trust trials")
    notes: list[str] = []
    if placeholders:
        notes.append(f"omitted {placeholders} explicit ran=0 placeholder row(s)")
    if incomplete_terminal:
        notes.append(
            f"omitted {incomplete_terminal} terminal interrupted trial row(s)"
        )
    return ConvertedRun(
        output,
        (
            "onset",
            "duration",
            "trial_type",
            "response_time",
            "trust_value",
            "choice",
            "cLow",
            "cHigh",
            "partner",
            "reciprocate",
            "trial_id",
        ),
        trial_count,
        expected_trial_count=42,
        notes=notes,
    )


def _ugr_decision(response: int, left: int, right: int) -> str:
    if response == 1:
        return "accept" if left > 0 else "reject"
    if response == 2:
        return "accept" if right > 0 else "reject"
    return "n/a"


def _convert_ugr(path: Path) -> ConvertedRun:
    source_rows, placeholders, incomplete_terminal = _trial_rows(
        _read_delimited(path, ","), "decision_onset", "UGR"
    )
    output: list[dict[str, object]] = []
    trial_count = 0
    for index, row in enumerate(source_rows, start=1):
        checkpoint = len(output)
        try:
            decision_onset = _number(row.get("decision_onset"), "decision_onset")
            isi = _number(row.get("ISI"), "ISI")
            block = _integer(row.get("Block"), "Block")
            sociality = {2: "nonsocial", 3: "social"}.get(block)
            if sociality is None:
                raise ConversionError(f"unknown UGR Block code: {block}")
            endowment = _integer(row.get("Endowment"), "Endowment")
            left = _integer(row.get("L_Option"), "L_Option")
            right = _integer(row.get("R_Option"), "R_Option")
            offer = max(left, right)
            response = _integer(row.get("resp"), "resp")
            trial_id = _trial_id(row, index)
            partner_cue_onset = decision_onset - isi - 1.5
            if partner_cue_onset < 0:
                raise ConversionError("reconstructed UGR partner cue onset is negative")
            decision = _ugr_decision(response, left, right)
            common = {
                "trial_id": trial_id,
                "sociality": sociality,
                "endowment": endowment,
                "offer": offer,
                "decision": decision,
                "response": response if response in {1, 2} else "n/a",
                "left_option": left,
                "right_option": right,
            }
            output.append(
                {
                    "onset": partner_cue_onset,
                    "duration": 0.5,
                    "trial_type": "partner_cue",
                    "response_time": "n/a",
                    "phase": "partner_cue",
                    "timing_source": "reconstructed_from_decision_onset_and_isi",
                    **common,
                }
            )
            endowment_onset = partner_cue_onset + 0.5
            output.append(
                {
                    "onset": endowment_onset,
                    "duration": _duration(
                        endowment_onset,
                        decision_onset,
                        "UGR endowment display duration",
                    ),
                    "trial_type": "endowment",
                    "response_time": "n/a",
                    "phase": "endowment",
                    "timing_source": "reconstructed_visible_interval",
                    **common,
                }
            )
            decision_offset = _number(row.get("decision_offset"), "decision_offset")
            if response == 999:
                decision_duration = _duration(
                    decision_onset, decision_offset, "UGR missed-decision duration"
                )
                output.append(
                    {
                        "onset": decision_onset,
                        "duration": decision_duration,
                        "trial_type": "missed_decision",
                        "response_time": "n/a",
                        "phase": "decision",
                        "timing_source": "logged_boundaries",
                        **common,
                    }
                )
                output.append(
                    {
                        "onset": decision_offset,
                        "duration": 0.5,
                        "trial_type": "missed_feedback",
                        "response_time": "n/a",
                        "phase": "missed_feedback",
                        "timing_source": "reconstructed_from_task_sequence",
                        **common,
                    }
                )
            else:
                if response not in {1, 2}:
                    raise ConversionError(f"unknown UGR response code: {response}")
                response_time = _number(row.get("rt"), "rt")
                response_onset = _number(row.get("resp_onset"), "resp_onset")
                output.append(
                    {
                        "onset": decision_onset,
                        "duration": response_time,
                        "trial_type": "decision",
                        "response_time": response_time,
                        "phase": "decision",
                        "timing_source": "logged",
                        **common,
                    }
                )
                output.append(
                    {
                        "onset": response_onset,
                        "duration": _duration(
                            response_onset,
                            decision_offset,
                            "UGR choice-feedback duration",
                        ),
                        "trial_type": "choice_feedback",
                        "response_time": response_time,
                        "phase": "choice_feedback",
                        "timing_source": "logged_boundaries",
                        **common,
                    }
                )
        except ConversionError as exc:
            del output[checkpoint:]
            raise ConversionError(
                f"UGR source row {_source_line(row, index)} is invalid: {exc}"
            ) from exc
        trial_count += 1
    if not output:
        raise ConversionError("no usable UGR trials")
    return ConvertedRun(
        output,
        (
            "onset",
            "duration",
            "trial_type",
            "response_time",
            "trial_id",
            "phase",
            "sociality",
            "endowment",
            "offer",
            "decision",
            "response",
            "left_option",
            "right_option",
            "timing_source",
        ),
        trial_count,
        expected_trial_count=48,
        notes=(
            [
                "Historical cue_Onset was overwritten each frame; partner-cue timing is reconstructed."
            ]
            + (
                [f"omitted {placeholders} explicit ran=0 placeholder row(s)"]
                if placeholders
                else []
            )
            + (
                [
                    f"omitted {incomplete_terminal} terminal interrupted trial row(s)"
                ]
                if incomplete_terminal
                else []
            )
        ),
    )


def _convert_socialdoors(path: Path) -> ConvertedRun:
    source_rows = _read_delimited(path, "\t")
    if not source_rows:
        raise ConversionError("no Social Doors/Doors rows")
    source_columns = tuple(
        column for column in source_rows[0] if not column.startswith("__")
    )
    required = {"onset", "duration", "trial_type"}
    if not required.issubset(source_columns):
        raise ConversionError("Social Doors/Doors source lacks required BIDS columns")
    columns = ("onset", "duration", "trial_type") + tuple(
        column for column in source_columns if column not in required
    )
    output: list[dict[str, object]] = []
    for row in source_rows:
        onset = _number(row.get("onset"), "onset")
        duration = _number(row.get("duration"), "duration")
        if duration < 0:
            raise ConversionError("negative Social Doors/Doors event duration")
        converted: dict[str, object] = {
            name: value for name, value in row.items() if not name.startswith("__")
        }
        converted["onset"] = onset
        converted["duration"] = duration
        output.append(converted)
    decisions = [
        row
        for row in output
        if str(row["trial_type"]) in {"decision", "decision-missed"}
    ]
    misses = sum(str(row["trial_type"]) == "decision-missed" for row in decisions)
    return ConvertedRun(
        output,
        columns,
        len(decisions),
        expected_trial_count=40,
        behaviorally_poor=misses >= 10,
    )


def convert_source(task: str, path: Path) -> ConvertedRun:
    if task == "sharedreward":
        converted = _convert_sharedreward(path)
    elif task == "trust":
        converted = _convert_trust(path)
    elif task == "ugr":
        converted = _convert_ugr(path)
    elif task in {"socialdoors", "doors"}:
        converted = _convert_socialdoors(path)
    else:
        raise ConversionError(f"unsupported task: {task}")
    converted.source_sha256 = source_sha256(path)
    converted.trial_fingerprint = _trial_fingerprint(task, converted)
    return converted


def _format_value(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "n/a"
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return text if text and text != "-0" else "0"
    text = str(value).strip()
    return text if text else "n/a"


def _atomic_write_tsv(
    path: Path,
    converted: ConvertedRun,
    overwrite: bool,
    dry_run: bool,
) -> None:
    if path.exists() and not overwrite:
        raise ConversionError(f"refusing to overwrite existing events file: {path}")
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=converted.columns,
                delimiter="\t",
                lineterminator="\n",
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in converted.rows:
                writer.writerow(
                    {name: _format_value(row.get(name)) for name in converted.columns}
                )
        apply_umask_mode(Path(temporary))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _sidecars() -> dict[str, dict[str, object]]:
    common = {
        "onset": {
            "Description": "Event onset relative to the start of the task run.",
            "Units": "s",
        },
        "duration": {
            "Description": "Observed or reconstructed event duration.",
            "Units": "s",
        },
        "trial_type": {"Description": "Canonical event label."},
        "response_time": {
            "Description": "Response time; n/a when not applicable.",
            "Units": "s",
        },
    }
    return {
        "sharedreward": {
            "TaskName": "sharedreward",
            **common,
            "partner": {
                "Description": "Partner type.",
                "Levels": {
                    "friend": "Friend",
                    "stranger": "Stranger",
                    "computer": "Computer",
                },
            },
            "feedback": {
                "Description": "Observed outcome category; n/a for missed trials.",
                "Levels": {
                    "reward": "Rewarding outcome",
                    "neutral": "Neutral outcome",
                    "punish": "Punishing outcome",
                },
            },
            "trial_id": {
                "Description": "Stable source-row identifier joining rows from one trial."
            },
        },
        "trust": {
            "TaskName": "trust",
            **common,
            "trust_value": {"Description": "Amount invested, from 0 through 8."},
            "choice": {
                "Description": "Whether the higher or lower displayed option was selected.",
                "Levels": {"high": "Higher option", "low": "Lower option"},
            },
            "cLow": {"Description": "Lower displayed investment option."},
            "cHigh": {"Description": "Higher displayed investment option."},
            "partner": {"Description": "Partner type."},
            "reciprocate": {
                "Description": "Partner outcome for positive investments; n/a otherwise.",
                "Levels": {
                    "recip": "Partner reciprocated",
                    "defect": "Partner defected",
                },
            },
            "trial_id": {
                "Description": "Stable source-row identifier joining rows from one trial."
            },
        },
        "ugr": {
            "TaskName": "ugr",
            "Description": "Phase-resolved Ultimatum Game events. Historical partner-cue and missed-feedback timing is reconstructed from the executed task sequence because cue_Onset was overwritten during display refreshes.",
            **common,
            "trial_id": {
                "Description": "Stable source-row identifier joining all phases from one trial."
            },
            "phase": {
                "Description": "Displayed task phase.",
                "Levels": {
                    "partner_cue": "Partner-only cue",
                    "endowment": "Partner and endowment display",
                    "decision": "Offer decision",
                    "choice_feedback": "Highlighted selected option",
                    "missed_feedback": "Explicit no-response feedback",
                },
            },
            "sociality": {
                "Description": "Social or nonsocial partner context.",
                "Levels": {
                    "social": "Human-face partner",
                    "nonsocial": "Computer partner",
                },
            },
            "endowment": {"Description": "Partner endowment."},
            "offer": {"Description": "Nonzero offer shown to the participant."},
            "decision": {
                "Description": "Accept or reject choice; n/a for misses.",
                "Levels": {
                    "accept": "Accepted nonzero offer",
                    "reject": "Selected zero/reject option",
                },
            },
            "response": {
                "Description": "Raw left/right button code (1 or 2); n/a for misses."
            },
            "left_option": {"Description": "Raw left-side option value."},
            "right_option": {"Description": "Raw right-side option value."},
            "timing_source": {
                "Description": "Whether phase timing was logged directly or reconstructed from task structure."
            },
        },
        "socialdoors": {
            "TaskName": "socialdoors",
            **common,
            "rt": {
                "Description": "Legacy response-time field retained from the task export.",
                "Units": "s",
            },
            "resp": {
                "Description": "Legacy response field retained from the task export."
            },
            "gender": {"Description": "Stimulus gender metadata."},
            "image_left": {"Description": "Left stimulus identifier."},
            "image_right": {"Description": "Right stimulus identifier."},
        },
        "doors": {
            "TaskName": "doors",
            **common,
            "rt": {
                "Description": "Legacy response-time field retained from the task export.",
                "Units": "s",
            },
            "resp": {
                "Description": "Legacy response field retained from the task export."
            },
            "gender": {"Description": "Stimulus gender metadata when present."},
            "image_left": {"Description": "Left stimulus identifier when present."},
            "image_right": {"Description": "Right stimulus identifier when present."},
        },
    }


def write_sidecars(bids_root: Path, overwrite: bool, dry_run: bool) -> None:
    for task, payload in _sidecars().items():
        path = bids_root / f"task-{task}_events.json"
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if path.exists():
            if path.read_text(encoding="utf-8") == serialized:
                continue
            if not overwrite:
                raise ConversionError(f"refusing to overwrite changed sidecar: {path}")
        if dry_run:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(serialized, encoding="utf-8")
        os.replace(temporary, path)


def preserve_existing_events(
    bids_root: Path,
    existing_bids_root: Path,
    keys: Iterable[RunKey],
    dry_run: bool,
) -> int:
    copied = 0
    for key in keys:
        source = event_path(existing_bids_root, key)
        target = event_path(bids_root, key)
        if not source.is_file() or target.exists():
            continue
        print(f"PRESERVE {key.event_name}")
        copied += 1
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return copied


def ugr_broad_trial_epoch(rows: Sequence[dict[str, object]]) -> tuple[float, float]:
    """Return the historical broad UGR epoch using only canonical event rows."""
    partner = [row for row in rows if row.get("phase") == "partner_cue"]
    terminal = [
        row for row in rows if row.get("phase") in {"choice_feedback", "decision"}
    ]
    if len(partner) != 1 or not terminal:
        raise ConversionError("UGR rows do not define one reconstructable broad epoch")
    onset = float(partner[0]["onset"])
    offset = max(float(row["onset"]) + float(row["duration"]) for row in terminal)
    return onset, offset - onset


def convert_behavior(
    subject: str,
    session: str,
    tasks: Sequence[str],
    behavior_root: Path,
    bids_root: Path,
    overwrite: bool = False,
    dry_run: bool = False,
    preserve_from: Path | None = None,
    curation_file: Path | None = None,
    runs: Sequence[int] | None = None,
) -> int:
    try:
        approvals = load_curation_approvals(curation_file)
    except (ConversionError, OSError, csv.Error) as exc:
        print(f"CONVERSION FAILED curation file: {exc}")
        return 1
    keys = discover_bold_runs(bids_root, subject, session, tasks)
    if runs is not None:
        selected_runs = set(runs)
        keys = [key for key in keys if key.run in selected_runs]
    if preserve_from is not None:
        preserve_existing_events(bids_root, preserve_from, keys, dry_run)
    if not keys:
        print(f"BOLD MISSING sub-{subject} ses-{session}: no selected task runs")
        return 1 if runs is not None else 0

    failed = 0
    for task in tasks:
        task_keys = [key for key in keys if key.task == task]
        if not task_keys:
            continue
        resolutions = resolve_sources(
            behavior_root,
            subject,
            session,
            task,
            [key.run for key in task_keys],
            approvals,
        )
        for key in task_keys:
            resolution = resolutions[key.run]
            destination = event_path(bids_root, key)
            if resolution.status == "missing":
                preserved = (
                    " (preserved existing events)" if destination.is_file() else ""
                )
                print(f"REVIEW REQUIRED {key.event_name}: source_missing{preserved}")
                failed = 1
                continue
            if resolution.status == "ambiguous":
                print(f"SOURCE AMBIGUOUS {key.event_name}: {resolution.detail}")
                failed = 1
                continue
            assert resolution.path is not None
            try:
                converted = convert_source(task, resolution.path)
                unapproved = [
                    issue
                    for issue in converted.review_issues
                    if not issue_is_approved(key, issue, converted, approvals)
                ]
                if unapproved:
                    print(
                        f"REVIEW REQUIRED {key.event_name}: {', '.join(unapproved)}; "
                        f"source_sha256={converted.source_sha256}; "
                        f"trial_fingerprint={converted.trial_fingerprint}"
                    )
                    failed = 1
                    continue
                _atomic_write_tsv(destination, converted, overwrite, dry_run)
            except (ConversionError, OSError, csv.Error) as exc:
                print(f"CONVERSION FAILED {key.event_name}: {exc}")
                failed = 1
                continue
            action = "WOULD WRITE" if dry_run else "WROTE"
            print(
                f"{action} {key.event_name}: {converted.trial_count} trial(s), "
                f"{len(converted.rows)} event row(s)"
            )
            if resolution.detail:
                print(f"SOURCE NOTE {key.event_name}: {resolution.detail}")
            if converted.unexpected_trial_count:
                approval = approvals[(key, "unexpected_trial_count")]
                print(
                    f"APPROVED REVIEW {key.event_name}: unexpected trial count "
                    f"{converted.trial_count}/{converted.expected_trial_count}; "
                    f"reviewer={approval.reviewer}"
                )
            if converted.behaviorally_poor:
                approval = approvals[(key, "behaviorally_poor")]
                print(
                    f"APPROVED REVIEW {key.event_name}: behaviorally poor; "
                    f"reviewer={approval.reviewer}"
                )
            for note in converted.notes:
                print(f"SOURCE NOTE {key.event_name}: {note}")
    if not failed:
        try:
            write_sidecars(bids_root, overwrite=overwrite, dry_run=dry_run)
        except ConversionError as exc:
            print(f"CONVERSION FAILED sidecars: {exc}")
            failed = 1
    return failed


def build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True, type=normalize_subject)
    parser.add_argument("--session", required=True, type=normalize_session)
    parser.add_argument("--tasks", nargs="+", default=list(TASKS))
    parser.add_argument(
        "--run",
        action="append",
        type=normalize_run,
        dest="runs",
        help="process only this BIDS run number; repeat to select multiple runs",
    )
    parser.add_argument(
        "--behavior-root",
        type=Path,
        default=Path(
            os.environ.get("BEHAVIOR_ROOT", "/ZPOOL/data/projects/rf1-sra/stimuli")
        ),
    )
    parser.add_argument("--bids-root", type=Path, default=project_root / "bids")
    parser.add_argument("--preserve-existing-from", type=Path)
    parser.add_argument(
        "--curation-file",
        type=Path,
        default=Path(
            os.environ.get(
                "BEHAVIOR_CURATION_FILE",
                project_root / "code" / "behavior_curation.tsv",
            )
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        tasks = parse_tasks(args.tasks)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    return convert_behavior(
        args.subject,
        args.session,
        tasks,
        args.behavior_root.resolve(),
        args.bids_root.resolve(),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        preserve_from=(
            args.preserve_existing_from.resolve()
            if args.preserve_existing_from
            else None
        ),
        curation_file=args.curation_file.resolve() if args.curation_file else None,
        runs=args.runs,
    )


if __name__ == "__main__":
    raise SystemExit(main())
