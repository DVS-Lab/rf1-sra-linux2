#!/usr/bin/env python3
"""Compare ordered trial identity, not timing, with an OpenNeuro snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections.abc import Sequence
from pathlib import Path

from convert_behavior import (
    TASKS,
    ConversionError,
    RunKey,
    convert_source,
    discover_bold_runs,
    normalize_session,
    normalize_subject,
    parse_tasks,
    resolve_sources,
)
from pipeline_utils import read_subject_list


class ReferenceDataError(ConversionError):
    """Raised when the frozen public reference cannot be interpreted."""


def _read_events(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ReferenceDataError("reference events file has no header")
        rows = [
            {name: (row.get(name) or "").strip() for name in reader.fieldnames}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]
    if not rows:
        raise ReferenceDataError("reference events file has no event rows")
    return rows


def _hash_records(records: list[tuple[str, ...]]) -> str:
    payload = json.dumps(records, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean(value: object) -> str:
    text = str(value).strip()
    if text.lower() in {"", "n/a", "nan", "none", "--"}:
        return "n/a"
    try:
        number = float(text)
    except ValueError:
        return text.lower()
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _canonical_records(
    task: str, rows: list[dict[str, object]]
) -> list[tuple[str, ...]]:
    if task == "sharedreward":
        seen: set[str] = set()
        records: list[tuple[str, ...]] = []
        for row in rows:
            trial = str(row["trial_id"])
            if trial in seen:
                continue
            seen.add(trial)
            records.append((_clean(row["partner"]), _clean(row["feedback"])))
        return records
    if task == "trust":
        records: list[list[str]] = []
        by_trial: dict[str, list[str]] = {}
        for row in rows:
            trial = str(row["trial_id"])
            if trial not in by_trial:
                record = [
                    _clean(row["partner"]),
                    _clean(row["trust_value"]),
                    _clean(row["cLow"]),
                    _clean(row["cHigh"]),
                    "n/a",
                ]
                records.append(record)
                by_trial[trial] = record
            if _clean(row.get("reciprocate")) != "n/a":
                by_trial[trial][4] = _clean(row["reciprocate"])
        return [tuple(record) for record in records]
    if task == "ugr":
        seen = set()
        records = []
        for row in rows:
            trial = str(row["trial_id"])
            if trial in seen:
                continue
            seen.add(trial)
            records.append(
                (
                    _clean(row["sociality"]),
                    _clean(row["endowment"]),
                )
            )
        return records
    return [
        (
            _clean(row.get("trial_type")),
            _clean(row.get("image_left")),
            _clean(row.get("image_right")),
            _clean(row.get("resp")),
        )
        for row in rows
        if _clean(row.get("trial_type")) in {"decision", "decision-missed"}
    ]


def _reference_records(task: str, rows: list[dict[str, str]]) -> list[tuple[str, ...]]:
    if task == "sharedreward":
        records = []
        for row in rows:
            label = _clean(row.get("trial_type"))
            if not label.startswith("event_"):
                continue
            parts = label.split("_", 2)
            if len(parts) == 3:
                records.append((parts[1], parts[2]))
        return records
    if task == "trust":
        records: list[list[str]] = []
        for row in rows:
            label = _clean(row.get("trial_type"))
            if label.startswith("choice_"):
                records.append(
                    [
                        label.removeprefix("choice_"),
                        _clean(row.get("trust_value")),
                        _clean(row.get("cLow")),
                        _clean(row.get("cHigh")),
                        "n/a",
                    ]
                )
            elif label.startswith("outcome_") and records:
                records[-1][4] = label.rsplit("_", 1)[-1]
        return [tuple(record) for record in records]
    if task == "ugr":
        records = []
        for row in rows:
            label = _clean(row.get("trial_type"))
            if label not in {"cue_social", "cue_nonsocial"}:
                continue
            endowment = row.get("Endowment", row.get("endowment", ""))
            records.append((label.removeprefix("cue_"), _clean(endowment)))
        return records
    return [
        (
            _clean(row.get("trial_type")),
            _clean(row.get("image_left")),
            _clean(row.get("image_right")),
            _clean(row.get("resp")),
        )
        for row in rows
        if _clean(row.get("trial_type")) in {"decision", "decision-missed"}
    ]


def _reference_path(root: Path, key: RunKey) -> Path | None:
    name = f"sub-{key.subject}_task-{key.task}_run-{key.run}_events.tsv"
    candidates = [
        root
        / f"sub-{key.subject}"
        / f"ses-{key.session}"
        / "func"
        / (
            f"sub-{key.subject}_ses-{key.session}_task-{key.task}_run-{key.run}_events.tsv"
        )
    ]
    if key.session == "01":
        candidates.append(root / f"sub-{key.subject}" / "func" / name)
    return next((path for path in candidates if path.is_file()), None)


def _reference_fingerprints(
    root: Path, subject: str, session: str, task: str
) -> tuple[dict[int, tuple[str, Path, int, list[tuple[str, ...]]]], dict[int, str]]:
    found: dict[int, tuple[str, Path, int, list[tuple[str, ...]]]] = {}
    errors: dict[int, str] = {}
    for run in (1, 2):
        key = RunKey(subject, session, task, run)
        path = _reference_path(root, key)
        if path is None:
            continue
        try:
            records = _reference_records(task, _read_events(path))
        except (ReferenceDataError, OSError, csv.Error) as exc:
            errors[run] = str(exc)
            continue
        if records:
            found[run] = (_hash_records(records), path, len(records), records)
        else:
            errors[run] = "reference events have no usable trial-identity records"
    return found, errors


def _records_match(
    private: list[tuple[str, ...]], reference: list[tuple[str, ...]]
) -> bool:
    if len(private) != len(reference):
        return False
    return all(_record_matches(left, right) for left, right in zip(private, reference))


def _record_matches(private: tuple[str, ...], reference: tuple[str, ...]) -> bool:
    return len(private) == len(reference) and all(
        a == b or a == "n/a" for a, b in zip(private, reference)
    )


def _is_reference_subsequence(
    private: list[tuple[str, ...]], reference: list[tuple[str, ...]]
) -> bool:
    position = 0
    for reference_record in reference:
        while position < len(private) and not _record_matches(
            private[position], reference_record
        ):
            position += 1
        if position == len(private):
            return False
        position += 1
    return bool(reference)


def audit_key(
    key: RunKey,
    behavior_root: Path,
    openneuro_root: Path,
) -> dict[str, str]:
    resolution = resolve_sources(
        behavior_root, key.subject, key.session, key.task, [key.run]
    )[key.run]
    result = {
        "subject": key.subject,
        "session": key.session,
        "task": key.task,
        "run": str(key.run),
        "status": "",
        "source": str(resolution.path or ""),
        "reference": "",
        "source_fingerprint": "",
        "reference_fingerprint": "",
        "detail": "",
    }
    ambiguous_lone_run = (
        resolution.status == "ambiguous"
        and resolution.path is not None
        and "lone raw run-1" in resolution.detail
    )
    if (
        resolution.status != "available" and not ambiguous_lone_run
    ) or resolution.path is None:
        result["status"] = f"source_{resolution.status}"
        result["detail"] = resolution.detail
        return result
    try:
        converted = convert_source(key.task, resolution.path)
        source_records = _canonical_records(key.task, converted.rows)
        if not source_records:
            raise ConversionError("private source has no trial-identity records")
        source_fingerprint = _hash_records(source_records)
    except (ConversionError, OSError, csv.Error) as exc:
        result["status"] = "conversion_failed"
        result["detail"] = str(exc)
        return result
    try:
        references, reference_errors = _reference_fingerprints(
            openneuro_root, key.subject, key.session, key.task
        )
    except (ReferenceDataError, OSError, csv.Error) as exc:
        result["status"] = "reference_invalid"
        result["detail"] = str(exc)
        return result
    result["source_fingerprint"] = source_fingerprint
    same = references.get(key.run)
    if same is None:
        if key.run in reference_errors:
            result["status"] = "reference_invalid"
            result["detail"] = reference_errors[key.run]
        else:
            result["status"] = "reference_unavailable"
        return result
    result["reference"] = str(same[1])
    result["reference_fingerprint"] = same[0]
    matching_runs = sorted(
        run
        for run, value in references.items()
        if _records_match(source_records, value[3])
    )
    if key.run in matching_runs and len(matching_runs) == 1:
        if ambiguous_lone_run:
            result["status"] = "ambiguous_label_matches_target"
            result["detail"] = (
                "OpenNeuro supports this target run; human approval is still required"
            )
        else:
            result["status"] = "match"
    elif key.run in matching_runs:
        result["status"] = "reference_nonunique"
        result["detail"] = f"same sequence appears in reference run(s) {matching_runs}"
    elif matching_runs:
        result["status"] = "run_swap_risk"
        result["detail"] = f"private source matches OpenNeuro run(s) {matching_runs}"
    elif len(same[3]) < len(source_records) and _is_reference_subsequence(
        source_records, same[3]
    ):
        result["status"] = "partial_reference_match"
        result["detail"] = (
            f"OpenNeuro retains {same[2]}/{len(source_records)} ordered trial(s)"
        )
    elif (
        len(same[3]) > len(source_records)
        and len(same[3]) % len(source_records) == 0
        and all(
            _records_match(source_records, same[3][start : start + len(source_records)])
            for start in range(0, len(same[3]), len(source_records))
        )
    ):
        result["status"] = "duplicated_reference_match"
        result["detail"] = (
            f"OpenNeuro contains {len(same[3]) // len(source_records)} copies of the run"
        )
    else:
        result["status"] = "reference_mismatch"
        result["detail"] = (
            f"private sequence has {len(source_records)} trial(s); "
            f"same-run OpenNeuro sequence has {same[2]}"
        )
    return result


def build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--subject", type=normalize_subject)
    group.add_argument("--sublist", type=Path)
    parser.add_argument(
        "--session", action="append", type=normalize_session, dest="sessions"
    )
    parser.add_argument("--tasks", nargs="+", default=list(TASKS))
    parser.add_argument("--openneuro-root", type=Path, required=True)
    parser.add_argument(
        "--behavior-root",
        type=Path,
        default=Path(
            os.environ.get("BEHAVIOR_ROOT", "/ZPOOL/data/projects/rf1-sra/stimuli")
        ),
    )
    parser.add_argument("--bids-root", type=Path, default=project_root / "bids")
    parser.add_argument("--report-tsv", type=Path, required=True)
    parser.add_argument(
        "--informational",
        action="store_true",
        help="report mismatches without returning a failing exit status",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        tasks = parse_tasks(args.tasks)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    if not args.openneuro_root.is_dir():
        parser.error(f"OpenNeuro root is not a directory: {args.openneuro_root}")
    subjects = [args.subject] if args.subject else read_subject_list(args.sublist)
    sessions = tuple(dict.fromkeys(args.sessions or ["01", "02"]))
    rows: list[dict[str, str]] = []
    for subject in subjects:
        for session in sessions:
            for key in discover_bold_runs(args.bids_root, subject, session, tasks):
                rows.append(audit_key(key, args.behavior_root, args.openneuro_root))
    columns = (
        "subject",
        "session",
        "task",
        "run",
        "status",
        "source",
        "reference",
        "source_fingerprint",
        "reference_fingerprint",
        "detail",
    )
    args.report_tsv.parent.mkdir(parents=True, exist_ok=True)
    with args.report_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    print(f"OpenNeuro run-identity report: {args.report_tsv}")
    for status, count in sorted(statuses.items()):
        print(f"  {status}: {count}")
    blocking = {
        "source_ambiguous",
        "source_missing",
        "conversion_failed",
        "reference_nonunique",
        "reference_mismatch",
        "run_swap_risk",
        "ambiguous_label_matches_target",
    }
    return (
        0
        if args.informational or not any(row["status"] in blocking for row in rows)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
