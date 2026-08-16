#!/usr/bin/env python3
"""Audit RF1-SRA behavioral source, BOLD runs, and canonical BIDS events."""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from convert_behavior import (
    CurationApproval,
    CurationKey,
    STANDARD_RUNS,
    TASKS,
    ConversionError,
    ConvertedRun,
    RunKey,
    convert_source,
    discover_bold_runs,
    event_path,
    issue_is_approved,
    load_curation_approvals,
    normalize_session,
    normalize_subject,
    parse_tasks,
    resolve_sources,
)
from pipeline_utils import read_subject_list


EVENT_RE = re.compile(
    r"^sub-(?P<subject>[^_]+)_ses-(?P<session>0[12])_task-(?P<task>[^_]+)_run-(?P<run>\d+)_events\.tsv$"
)


def _event_runs(
    bids_root: Path,
    subject: str,
    session: str,
    tasks: Sequence[str],
) -> set[RunKey]:
    func = bids_root / f"sub-{subject}" / f"ses-{session}" / "func"
    found: set[RunKey] = set()
    if not func.is_dir():
        return found
    for path in func.glob("*_events.tsv"):
        match = EVENT_RE.match(path.name)
        if not match or match.group("task") not in tasks:
            continue
        found.add(
            RunKey(
                match.group("subject"),
                match.group("session"),
                match.group("task"),
                int(match.group("run")),
            )
        )
    return found


def _validate_event_file(
    path: Path,
) -> tuple[int, list[dict[str, str]], tuple[str, ...]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ConversionError("events file has no header")
        if any(not name for name in reader.fieldnames) or len(
            set(reader.fieldnames)
        ) != len(reader.fieldnames):
            raise ConversionError("events file has empty or duplicate header columns")
        missing = {"onset", "duration", "trial_type"} - set(reader.fieldnames)
        if missing:
            raise ConversionError(
                f"events file lacks columns: {', '.join(sorted(missing))}"
            )
        count = 0
        rows: list[dict[str, str]] = []
        for row in reader:
            if None in row or any(row.get(name) is None for name in reader.fieldnames):
                raise ConversionError(
                    "events file row does not match header field count"
                )
            if not any((value or "").strip() for value in row.values()):
                continue
            try:
                onset = float(row["onset"])
                duration = float(row["duration"])
            except (TypeError, ValueError) as exc:
                raise ConversionError(
                    "events file has nonnumeric onset/duration"
                ) from exc
            if not (onset == onset and duration == duration) or duration < 0:
                raise ConversionError("events file has invalid onset/duration")
            if not (row.get("trial_type") or "").strip():
                raise ConversionError("events file has empty trial_type")
            count += 1
            rows.append(
                {name: (row.get(name) or "").strip() for name in reader.fieldnames}
            )
    if count == 0:
        raise ConversionError("events file has no event rows")
    return count, rows, tuple(reader.fieldnames)


def _canonical_text(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        text = f"{value:.6f}".rstrip("0").rstrip(".")
        return text if text and text != "-0" else "0"
    text = str(value).strip()
    return text if text else "n/a"


def _matches_canonical_events(
    event_rows: list[dict[str, str]],
    event_columns: tuple[str, ...],
    converted: ConvertedRun,
) -> bool:
    columns = converted.columns
    if event_columns != columns:
        return False
    if len(event_rows) != len(converted.rows):
        return False
    for observed, expected in zip(event_rows, converted.rows):
        if any(
            observed.get(column, "") != _canonical_text(expected.get(column))
            for column in columns
        ):
            return False
    return True


def _add_review(
    findings: list[dict[str, str]] | None,
    key: RunKey,
    issue: str,
    detail: str,
    source: Path | None = None,
    source_sha256: str = "",
    trial_fingerprint: str = "",
) -> None:
    if findings is None:
        return
    findings.append(
        {
            "subject": key.subject,
            "session": key.session,
            "task": key.task,
            "run": str(key.run),
            "issue": issue,
            "source": str(source or ""),
            "source_sha256": source_sha256,
            "trial_fingerprint": trial_fingerprint,
            "detail": detail,
        }
    )


def audit_subject_session(
    bids_root: Path,
    behavior_root: Path,
    subject: str,
    session: str,
    tasks: Sequence[str],
    quiet_ok: bool = False,
    approvals: dict[CurationKey, CurationApproval] | None = None,
    review_findings: list[dict[str, str]] | None = None,
) -> tuple[int, Counter[str]]:
    approvals = approvals or {}
    bold_keys = set(discover_bold_runs(bids_root, subject, session, tasks))
    events_keys = _event_runs(bids_root, subject, session, tasks)
    failed = 0
    counts: Counter[str] = Counter()

    for task in tasks:
        bold_runs = {key.run for key in bold_keys if key.task == task}
        event_runs = {key.run for key in events_keys if key.task == task}
        observed_runs = bold_runs | event_runs
        candidate_runs = sorted(observed_runs or set(STANDARD_RUNS[task]))
        resolutions = resolve_sources(
            behavior_root, subject, session, task, candidate_runs, approvals
        )
        for run in candidate_runs:
            key = RunKey(subject, session, task, run)
            has_bold = key in bold_keys
            has_events = key in events_keys
            source = resolutions[run]
            if not has_bold and not has_events and source.status == "missing":
                continue
            if has_bold:
                counts["BOLD runs found"] += 1
            if has_events:
                counts["events files found"] += 1
            if source.status == "available":
                counts["behavioral source runs found"] += 1
                if source.detail:
                    print(f"APPROVED REVIEW {key.event_name}: {source.detail}")
                    counts["approved human review"] += 1

            if source.status == "ambiguous":
                print(f"BEHAVIOR SOURCE AMBIGUOUS {key.event_name}: {source.detail}")
                counts["behavior source ambiguous"] += 1
                counts["review required"] += 1
                failed = 1
                source_digest = ""
                trial_digest = ""
                if source.path is not None:
                    try:
                        candidate = convert_source(task, source.path)
                        source_digest = candidate.source_sha256
                        trial_digest = candidate.trial_fingerprint
                    except (ConversionError, OSError, csv.Error):
                        pass
                _add_review(
                    review_findings,
                    key,
                    (
                        "ambiguous_run_label"
                        if source.path is not None and "lone raw run-1" in source.detail
                        else "source_ambiguous"
                    ),
                    source.detail,
                    source.path,
                    source_digest,
                    trial_digest,
                )
                continue

            if not has_bold:
                print(f"BOLD MISSING {key.event_name}")
                counts["BOLD missing"] += 1
                if has_events:
                    failed = 1
                continue

            if source.status == "missing":
                print(f"REVIEW REQUIRED {key.event_name}: behavior source missing")
                counts["behavior source missing"] += 1
                counts["review required"] += 1
                _add_review(
                    review_findings,
                    key,
                    "source_missing",
                    "BOLD run has no uniquely resolved private behavioral source",
                )
                failed = 1
                if not has_events:
                    continue

            if not has_events:
                print(f"EVENTS MISSING {key.event_name}")
                counts["events missing"] += 1
                failed = 1
                _add_review(
                    review_findings,
                    key,
                    "events_missing",
                    "behavioral source and BOLD exist but events file is missing",
                    source.path,
                )
                continue

            destination = event_path(bids_root, key)
            try:
                event_rows, observed_rows, observed_columns = _validate_event_file(
                    destination
                )
                converted = (
                    convert_source(task, source.path)
                    if source.status == "available" and source.path is not None
                    else None
                )
                if converted is not None and not _matches_canonical_events(
                    observed_rows, observed_columns, converted
                ):
                    raise ConversionError(
                        "events contents differ from canonical source conversion"
                    )
            except (ConversionError, OSError, csv.Error) as exc:
                print(f"CONVERSION FAILED {key.event_name}: {exc}")
                counts["conversion failed"] += 1
                failed = 1
                _add_review(
                    review_findings,
                    key,
                    "conversion_failed",
                    str(exc),
                    source.path,
                )
                continue

            if converted is None:
                continue
            if converted is not None:
                for issue in converted.review_issues:
                    if issue_is_approved(key, issue, converted, approvals):
                        print(f"APPROVED REVIEW {key.event_name}: {issue}")
                        counts["approved human review"] += 1
                    else:
                        detail = issue
                        if issue == "unexpected_trial_count":
                            detail = (
                                f"trial count {converted.trial_count}/"
                                f"{converted.expected_trial_count}"
                            )
                            counts["unexpected trial count"] += 1
                        elif issue == "behaviorally_poor":
                            counts["behaviorally poor"] += 1
                        print(
                            f"REVIEW REQUIRED {key.event_name}: {detail}; "
                            f"source_sha256={converted.source_sha256}; "
                            f"trial_fingerprint={converted.trial_fingerprint}"
                        )
                        counts["review required"] += 1
                        failed = 1
                        _add_review(
                            review_findings,
                            key,
                            issue,
                            detail,
                            source.path,
                            converted.source_sha256,
                            converted.trial_fingerprint,
                        )
                for note in converted.notes:
                    print(f"SOURCE NOTE {key.event_name}: {note}")
                    counts["source note"] += 1
            if not quiet_ok:
                print(f"OK {key.event_name}: {event_rows} event row(s)")
            counts["OK"] += 1

    event_tasks = {key.task for key in events_keys if key in bold_keys}
    for task in sorted(event_tasks):
        sidecar = bids_root / f"task-{task}_events.json"
        if not sidecar.is_file():
            print(f"EVENTS SIDECAR MISSING {sidecar}")
            counts["events missing"] += 1
            failed = 1
    return failed, counts


def _subjects(args: argparse.Namespace) -> list[str]:
    if args.subject:
        return [args.subject]
    if args.sublist:
        return read_subject_list(args.sublist)
    raise SystemExit("one of --subject or --sublist is required")


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
    parser.add_argument(
        "--behavior-root",
        type=Path,
        default=Path(
            os.environ.get("BEHAVIOR_ROOT", "/ZPOOL/data/projects/rf1-sra/stimuli")
        ),
    )
    parser.add_argument("--bids-root", type=Path, default=project_root / "bids")
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
    parser.add_argument(
        "--review-tsv",
        type=Path,
        help="write unresolved cases for independent human review",
    )
    parser.add_argument("--quiet-ok", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        tasks = parse_tasks(args.tasks)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    sessions = tuple(dict.fromkeys(args.sessions or ["01", "02"]))
    subjects = _subjects(args)
    try:
        approvals = load_curation_approvals(
            args.curation_file.resolve() if args.curation_file else None
        )
    except (ConversionError, OSError, csv.Error) as exc:
        print(f"CHECK FAILED: invalid behavioral curation file: {exc}")
        return 1
    review_findings: list[dict[str, str]] = []
    total: Counter[str] = Counter()
    failed = 0
    breakdown: dict[tuple[str, str], Counter[str]] = {}
    for session in sessions:
        for task in tasks:
            subtotal: Counter[str] = Counter()
            for subject in subjects:
                session_failed, counts = audit_subject_session(
                    args.bids_root.resolve(),
                    args.behavior_root.resolve(),
                    subject,
                    session,
                    (task,),
                    quiet_ok=args.quiet_ok,
                    approvals=approvals,
                    review_findings=review_findings,
                )
                failed = max(failed, session_failed)
                subtotal.update(counts)
                total.update(counts)
            breakdown[(session, task)] = subtotal
    print("Events audit summary:")
    for status in (
        "BOLD runs found",
        "behavioral source runs found",
        "events files found",
        "OK",
        "behavior source missing",
        "BOLD missing",
        "events missing",
        "behavior source ambiguous",
        "conversion failed",
        "unexpected trial count",
        "behaviorally poor",
        "review required",
        "approved human review",
        "source note",
    ):
        print(f"  {status}: {total[status]}")
    print("Events audit by task/session:")
    for (session, task), subtotal in breakdown.items():
        if not subtotal:
            continue
        print(
            f"  ses-{session} task-{task}: "
            f"BOLD={subtotal['BOLD runs found']} "
            f"source={subtotal['behavioral source runs found']} "
            f"events={subtotal['events files found']} "
            f"OK={subtotal['OK']} "
            f"source-missing={subtotal['behavior source missing']} "
            f"BOLD-missing={subtotal['BOLD missing']} "
            f"events-missing={subtotal['events missing']} "
            f"ambiguous={subtotal['behavior source ambiguous']} "
            f"failed={subtotal['conversion failed']} "
            f"unexpected-count={subtotal['unexpected trial count']} "
            f"poor={subtotal['behaviorally poor']} "
            f"review-required={subtotal['review required']} "
            f"approved-review={subtotal['approved human review']}"
        )
    if args.review_tsv:
        args.review_tsv.parent.mkdir(parents=True, exist_ok=True)
        columns = (
            "subject",
            "session",
            "task",
            "run",
            "issue",
            "source",
            "source_sha256",
            "trial_fingerprint",
            "detail",
        )
        with args.review_tsv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t")
            writer.writeheader()
            writer.writerows(review_findings)
        print(f"Human-review report: {args.review_tsv} ({len(review_findings)} row(s))")
    print(
        "CHECK FAILED: behavioral BIDS events need attention."
        if failed
        else "CHECK PASSED: behavioral BIDS events are internally consistent."
    )
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
    issue_is_approved,
    load_curation_approvals,
