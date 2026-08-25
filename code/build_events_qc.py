#!/usr/bin/env python3
"""Build and verify canonical response-miss QC from BIDS events files."""

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
from datetime import datetime, timezone
from pathlib import Path


TASKS = ("sharedreward", "trust", "ugr", "socialdoors", "doors")
EVENT_PATTERN = re.compile(
    r"^sub-(?P<subject>\d+)_ses-(?P<session>\d+)_task-"
    r"(?P<task>sharedreward|trust|ugr|socialdoors|doors)_run-"
    r"(?P<run>\d+)_events\.tsv$"
)
RUN_COLUMNS = (
    "subject",
    "session",
    "task",
    "run",
    "events_path",
    "events_sha256",
    "expected_trials",
    "response_trials",
    "trial_count_complete",
    "misses",
    "miss_fraction",
    "response_fraction",
    "first_miss_trial",
    "last_miss_trial",
    "longest_miss_streak",
    "longest_miss_streak_start_trial",
    "terminal_miss_streak",
    "terminal_miss_start_trial",
    "terminal_miss_start_onset_sec",
    "terminal_affected_duration_sec",
    "preterminal_trials",
    "preterminal_misses",
    "preterminal_miss_fraction",
    "retained_trial_fraction_if_terminal_trimmed",
    "overall_miss_rule_failed",
    "terminal_failure_candidate",
    "salvage_review_candidate",
    "review_status",
    "review_reasons",
    "miss_pattern",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_policy(path: Path) -> dict[str, object]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "overall_miss_fraction_review",
        "terminal_miss_streak_review_min",
        "salvage_min_preterminal_fraction",
        "expected_trials",
    }
    missing = required - set(policy)
    if missing:
        raise ValueError(f"policy lacks key(s): {', '.join(sorted(missing))}")
    threshold = float(policy["overall_miss_fraction_review"])
    terminal_min = int(policy["terminal_miss_streak_review_min"])
    preterminal_min = float(policy["salvage_min_preterminal_fraction"])
    if not 0 < threshold < 1:
        raise ValueError("overall miss threshold must be between zero and one")
    if terminal_min < 1:
        raise ValueError("terminal miss streak threshold must be positive")
    if not 0 < preterminal_min <= 1:
        raise ValueError("preterminal fraction must be in (0, 1]")
    expected = policy["expected_trials"]
    if not isinstance(expected, dict) or set(expected) != set(TASKS):
        raise ValueError("expected_trials must define every supported task")
    return policy


def read_subjects(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    subjects: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.split("#", 1)[0].strip().removeprefix("sub-")
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f"invalid subject in {path}: {raw}")
        subjects.add(value)
    if not subjects:
        raise ValueError(f"subject list is empty: {path}")
    return subjects


def source_excluded_subjects(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    excluded: set[str] = set()
    for item in path.glob("Smith-SRA-*"):
        subject = item.name.removeprefix("Smith-SRA-").split("-", 1)[0]
        if subject.isdigit():
            excluded.add(subject)
    return excluded


def discover_events(
    bids_root: Path,
    subjects: set[str] | None,
    excluded: set[str],
) -> list[tuple[tuple[str, str, str, int], Path]]:
    found: dict[tuple[str, str, str, int], Path] = {}
    for path in sorted(bids_root.glob("sub-*/ses-*/func/*_events.tsv")):
        match = EVENT_PATTERN.match(path.name)
        if not match:
            continue
        subject = match.group("subject")
        if subject in excluded or (subjects is not None and subject not in subjects):
            continue
        key = (
            subject,
            match.group("session"),
            match.group("task"),
            int(match.group("run")),
        )
        if key in found:
            raise ValueError(
                f"duplicate events inventory for {key}: {found[key]}, {path}"
            )
        found[key] = path
    return sorted(found.items())


def _number(value: object, name: str, path: Path) -> float:
    try:
        number = float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{path}: invalid {name}: {value}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{path}: non-finite {name}: {value}")
    return number


def decision_state(task: str, trial_type: str) -> bool | None:
    """Return True for a miss, False for a response, or None for nondecisions."""
    if task == "sharedreward":
        if trial_type == "missed_decision":
            return True
        if trial_type in {"computer_non-face", "stranger_face", "friend_face"}:
            return False
    elif task == "trust":
        if trial_type == "missed_trial":
            return True
        if trial_type.startswith("choice_"):
            return False
    elif task == "ugr":
        if trial_type == "missed_decision":
            return True
        if trial_type == "decision":
            return False
    elif task in {"socialdoors", "doors"}:
        if trial_type == "decision-missed":
            return True
        if trial_type == "decision":
            return False
    return None


def longest_true_streak(values: Sequence[bool]) -> tuple[int, int | None]:
    best_length = 0
    best_start: int | None = None
    current_length = 0
    current_start = 0
    for index, value in enumerate(values):
        if value:
            if current_length == 0:
                current_start = index
            current_length += 1
            if current_length > best_length:
                best_length = current_length
                best_start = current_start
        else:
            current_length = 0
    return best_length, best_start


def terminal_true_streak(values: Sequence[bool]) -> int:
    length = 0
    for value in reversed(values):
        if not value:
            break
        length += 1
    return length


def _format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def audit_events_file(
    key: tuple[str, str, str, int],
    path: Path,
    bids_root: Path,
    policy: dict[str, object],
) -> dict[str, str]:
    subject, session, task, run = key
    decisions: list[tuple[float, bool, int]] = []
    run_end = 0.0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"events file has no header: {path}")
        required = {"onset", "duration", "trial_type"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(sorted(missing))}")
        for row_index, row in enumerate(reader, start=2):
            onset = _number(row["onset"], "onset", path)
            duration = _number(row["duration"], "duration", path)
            if onset < 0 or duration < 0:
                raise ValueError(
                    f"{path}: negative onset or duration at row {row_index}"
                )
            run_end = max(run_end, onset + duration)
            missed = decision_state(task, str(row["trial_type"]).strip())
            if missed is not None:
                decisions.append((onset, missed, row_index))
    decisions.sort(key=lambda item: (item[0], item[2]))
    if not decisions:
        raise ValueError(f"{path}: no recognized response opportunities")

    sequence = [item[1] for item in decisions]
    onsets = [item[0] for item in decisions]
    count = len(sequence)
    misses = sum(sequence)
    miss_fraction = misses / count
    longest, longest_start = longest_true_streak(sequence)
    terminal = terminal_true_streak(sequence)
    terminal_start = count - terminal if terminal else None
    preterminal_count = count - terminal
    preterminal_misses = sum(sequence[:preterminal_count])
    preterminal_fraction = (
        preterminal_misses / preterminal_count if preterminal_count else 1.0
    )

    expected = int(policy["expected_trials"][task])  # type: ignore[index]
    overall_threshold = float(policy["overall_miss_fraction_review"])
    terminal_min = int(policy["terminal_miss_streak_review_min"])
    preterminal_min = float(policy["salvage_min_preterminal_fraction"])
    overall_failed = miss_fraction >= overall_threshold
    terminal_candidate = terminal >= terminal_min
    enough_preterminal = preterminal_count >= math.ceil(expected * preterminal_min)
    salvage_candidate = (
        terminal_candidate
        and enough_preterminal
        and preterminal_fraction < overall_threshold
    )
    reasons: list[str] = []
    if count != expected:
        reasons.append("unexpected_trial_count")
    if overall_failed:
        reasons.append("overall_miss_fraction_threshold")
    if terminal_candidate:
        reasons.append("terminal_miss_streak")

    first_miss = next(
        (index + 1 for index, value in enumerate(sequence) if value), None
    )
    last_miss = next(
        (count - index for index, value in enumerate(reversed(sequence)) if value),
        None,
    )
    terminal_onset = onsets[terminal_start] if terminal_start is not None else None
    affected_duration = (
        max(0.0, run_end - terminal_onset) if terminal_onset is not None else None
    )
    return {
        "subject": subject,
        "session": session,
        "task": task,
        "run": str(run),
        "events_path": str(path.relative_to(bids_root.parent)),
        "events_sha256": sha256_file(path),
        "expected_trials": str(expected),
        "response_trials": str(count),
        "trial_count_complete": _format_bool(count == expected),
        "misses": str(misses),
        "miss_fraction": _format_float(miss_fraction),
        "response_fraction": _format_float(1.0 - miss_fraction),
        "first_miss_trial": "" if first_miss is None else str(first_miss),
        "last_miss_trial": "" if last_miss is None else str(last_miss),
        "longest_miss_streak": str(longest),
        "longest_miss_streak_start_trial": (
            "" if longest_start is None else str(longest_start + 1)
        ),
        "terminal_miss_streak": str(terminal),
        "terminal_miss_start_trial": (
            "" if terminal_start is None else str(terminal_start + 1)
        ),
        "terminal_miss_start_onset_sec": _format_float(terminal_onset),
        "terminal_affected_duration_sec": _format_float(affected_duration),
        "preterminal_trials": str(preterminal_count),
        "preterminal_misses": str(preterminal_misses),
        "preterminal_miss_fraction": _format_float(preterminal_fraction),
        "retained_trial_fraction_if_terminal_trimmed": _format_float(
            preterminal_count / count
        ),
        "overall_miss_rule_failed": _format_bool(overall_failed),
        "terminal_failure_candidate": _format_bool(terminal_candidate),
        "salvage_review_candidate": _format_bool(salvage_candidate),
        "review_status": "review" if reasons else "pass",
        "review_reasons": ";".join(reasons),
        "miss_pattern": "".join("M" if value else "." for value in sequence),
    }


def build_rows(
    bids_root: Path,
    subjects: set[str] | None,
    excluded: set[str],
    policy: dict[str, object],
) -> list[dict[str, str]]:
    inventory = discover_events(bids_root, subjects, excluded)
    if not inventory:
        raise ValueError("no supported BIDS events files found")
    return [audit_events_file(key, path, bids_root, policy) for key, path in inventory]


def write_tsv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RUN_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def rows_manifest_sha256(rows: Sequence[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row["events_path"].encode())
        digest.update(b"\0")
        digest.update(row["events_sha256"].encode())
        digest.update(b"\n")
    return digest.hexdigest()


def write_plots(
    rows: Sequence[dict[str, str]], output_dir: Path, overall_threshold: float
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap

    colors = {
        "sharedreward": "#3f6f8f",
        "trust": "#7d5a9e",
        "ugr": "#d08b3e",
        "socialdoors": "#4f8a5b",
        "doors": "#b6504b",
    }
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for index, task in enumerate(TASKS):
        task_rows = [row for row in rows if row["task"] == task]
        x = np.full(len(task_rows), index, dtype=float)
        if len(task_rows):
            x += np.linspace(-0.18, 0.18, len(task_rows))
        y = [float(row["miss_fraction"]) for row in task_rows]
        ax.scatter(x, y, s=13, alpha=0.45, color=colors[task], label=task)
    ax.axhline(overall_threshold, color="#202020", linestyle="--", linewidth=1.2)
    ax.set_xticks(range(len(TASKS)), TASKS, rotation=20, ha="right")
    ax.set_ylabel("Miss fraction")
    ax.set_ylim(bottom=-0.02)
    ax.set_title("Response misses by task and run")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output_dir / "miss_fraction_by_task.png", dpi=180)
    plt.close(fig)

    review = [row for row in rows if row["review_status"] == "review"]
    review.sort(
        key=lambda row: (
            row["salvage_review_candidate"] != "true",
            -int(row["terminal_miss_streak"]),
            -float(row["miss_fraction"]),
            row["subject"],
            row["task"],
            int(row["run"]),
        )
    )
    if not review:
        fig, ax = plt.subplots(figsize=(8, 2))
        ax.text(0.5, 0.5, "No response-QC review candidates", ha="center", va="center")
        ax.axis("off")
    else:
        width = max(len(row["miss_pattern"]) for row in review)
        matrix = np.full((len(review), width), np.nan)
        for y_index, row in enumerate(review):
            for x_index, value in enumerate(row["miss_pattern"]):
                matrix[y_index, x_index] = 1 if value == "M" else 0
        height = max(3.5, min(18, 0.28 * len(review) + 1.8))
        fig, ax = plt.subplots(figsize=(11, height))
        cmap = ListedColormap(["#4f8a5b", "#c94f45"])
        cmap.set_bad("#dedede")
        ax.imshow(
            matrix, aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=1
        )
        labels = [
            f"sub-{row['subject']} ses-{row['session']} {row['task']} run-{row['run']}"
            for row in review
        ]
        ax.set_yticks(range(len(review)), labels, fontsize=7)
        ax.set_xlabel(
            "Response opportunity (green=response, red=miss, gray=not acquired)"
        )
        ax.set_title("Runs requiring response-pattern review")
    fig.tight_layout()
    fig.savefig(output_dir / "review_miss_patterns.png", dpi=180)
    plt.close(fig)


def print_summary(rows: Sequence[dict[str, str]]) -> None:
    review = [row for row in rows if row["review_status"] == "review"]
    overall = [row for row in rows if row["overall_miss_rule_failed"] == "true"]
    terminal = [row for row in rows if row["terminal_failure_candidate"] == "true"]
    salvage = [row for row in rows if row["salvage_review_candidate"] == "true"]
    print(f"Events runs audited: {len(rows)}")
    print(f"Runs at/above overall miss threshold: {len(overall)}")
    print(f"Terminal-failure candidates: {len(terminal)}")
    print(f"Potential terminal-trim salvage candidates: {len(salvage)}")
    print(f"Total runs requiring review: {len(review)}")
    for row in salvage:
        print(
            f"SALVAGE REVIEW sub-{row['subject']} ses-{row['session']} "
            f"task-{row['task']} run-{row['run']}: misses={row['misses']}/"
            f"{row['response_trials']}, terminal={row['terminal_miss_streak']}, "
            f"terminal onset={row['terminal_miss_start_onset_sec']}s, "
            f"preterminal miss fraction={row['preterminal_miss_fraction']}"
        )


def write_outputs(
    rows: list[dict[str, str]],
    output_dir: Path,
    policy_path: Path,
    sublist: Path | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_tsv(output_dir / "run_response_qc.tsv", rows)
    write_tsv(
        output_dir / "review_candidates.tsv",
        [row for row in rows if row["review_status"] == "review"],
    )
    policy = load_policy(policy_path)
    write_plots(
        rows,
        output_dir,
        float(policy["overall_miss_fraction_review"]),
    )
    provenance = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": str(policy_path),
        "policy_sha256": sha256_file(policy_path),
        "sublist": str(sublist) if sublist else None,
        "sublist_sha256": sha256_file(sublist) if sublist else None,
        "events_run_count": len(rows),
        "events_manifest_sha256": rows_manifest_sha256(rows),
        "review_count": sum(row["review_status"] == "review" for row in rows),
        "salvage_review_count": sum(
            row["salvage_review_candidate"] == "true" for row in rows
        ),
    }
    (output_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def common_rows(args: argparse.Namespace) -> tuple[list[dict[str, str]], Path]:
    bids_root = args.bids_root.expanduser().resolve()
    policy_path = args.policy.expanduser().resolve()
    subjects = read_subjects(
        args.sublist.expanduser().resolve() if args.sublist else None
    )
    excluded = source_excluded_subjects(
        args.excluded_source_root.expanduser().resolve()
    )
    policy = load_policy(policy_path)
    rows = build_rows(bids_root, subjects, excluded, policy)
    return rows, policy_path


def run_build(args: argparse.Namespace) -> int:
    rows, policy_path = common_rows(args)
    print_summary(rows)
    if args.dry_run:
        print("DRY RUN: canonical QC outputs were not changed.")
        return 0
    output_dir = args.output_dir.expanduser().resolve()
    if output_dir.exists() and not args.overwrite:
        raise ValueError(f"output exists; add --overwrite to replace: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        write_outputs(rows, staging, policy_path, args.sublist)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        os.replace(staging, output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f"WROTE canonical events QC: {output_dir}")
    return 0


def run_check(args: argparse.Namespace) -> int:
    rows, policy_path = common_rows(args)
    output_dir = args.output_dir.expanduser().resolve()
    errors: list[str] = []
    required = {
        "run_response_qc.tsv",
        "review_candidates.tsv",
        "provenance.json",
        "miss_fraction_by_task.png",
        "review_miss_patterns.png",
    }
    for name in sorted(required):
        if not (output_dir / name).is_file():
            errors.append(f"missing canonical output: {output_dir / name}")
    if not errors:
        if read_tsv(output_dir / "run_response_qc.tsv") != rows:
            errors.append("run_response_qc.tsv disagrees with live BIDS events")
        expected_review = [row for row in rows if row["review_status"] == "review"]
        if read_tsv(output_dir / "review_candidates.tsv") != expected_review:
            errors.append("review_candidates.tsv disagrees with run_response_qc.tsv")
        try:
            provenance = json.loads((output_dir / "provenance.json").read_text())
            if provenance.get("policy_sha256") != sha256_file(policy_path):
                errors.append("provenance policy checksum disagreement")
            if provenance.get("events_manifest_sha256") != rows_manifest_sha256(rows):
                errors.append("provenance events-manifest checksum disagreement")
            sublist = args.sublist.expanduser().resolve() if args.sublist else None
            expected_sublist_sha = sha256_file(sublist) if sublist else None
            if provenance.get("sublist_sha256") != expected_sublist_sha:
                errors.append("provenance subject-list checksum disagreement")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"invalid provenance.json: {exc}")
    print_summary(rows)
    if errors:
        for error in errors:
            print(f"CHECK FAILED: {error}")
        return 1
    print(
        f"CHECK PASSED: {len(rows)} events run(s) have complete, internally "
        "consistent response-pattern QC. Review flags remain scientific decisions."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--bids-root", type=Path, default=repo_root / "bids")
        subparser.add_argument(
            "--output-dir", type=Path, default=repo_root / "qc" / "events" / "results"
        )
        subparser.add_argument(
            "--policy", type=Path, default=repo_root / "qc" / "events" / "policy.json"
        )
        subparser.add_argument("--sublist", type=Path)
        subparser.add_argument(
            "--excluded-source-root",
            type=Path,
            default=Path("/ZPOOL/data/sourcedata/sourcedata/rf1-sra-exclusions"),
        )

    build = subparsers.add_parser("build", help="build canonical response-pattern QC")
    common(build)
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--dry-run", action="store_true")
    build.set_defaults(func=run_build)

    check = subparsers.add_parser("check", help="verify canonical response-pattern QC")
    common(check)
    check.set_defaults(func=run_check)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.func(args))
    except (OSError, ValueError, csv.Error) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
