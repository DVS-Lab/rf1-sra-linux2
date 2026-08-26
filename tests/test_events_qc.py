from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from build_events_qc import (  # noqa: E402
    audit_events_file,
    decision_state,
    run_build,
    run_check,
)


def policy() -> dict[str, object]:
    return {
        "schema_version": 1,
        "overall_miss_fraction_review": 0.25,
        "terminal_miss_streak_review_min": 5,
        "salvage_min_preterminal_fraction": 0.4,
        "expected_trials": {
            "sharedreward": 54,
            "trust": 42,
            "ugr": 48,
            "socialdoors": 40,
            "doors": 40,
        },
    }


def write_events(path: Path, trial_types: list[str], spacing: float = 5.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["onset", "duration", "trial_type"], delimiter="\t"
        )
        writer.writeheader()
        for index, trial_type in enumerate(trial_types):
            writer.writerow(
                {"onset": index * spacing, "duration": 1, "trial_type": trial_type}
            )


def event_path(bids: Path, subject: str, task: str, run: int = 1) -> Path:
    return (
        bids
        / f"sub-{subject}"
        / "ses-01"
        / "func"
        / f"sub-{subject}_ses-01_task-{task}_run-{run}_events.tsv"
    )


@pytest.mark.parametrize(
    ("task", "responded", "missed"),
    [
        ("sharedreward", "friend_face", "missed_decision"),
        ("trust", "choice_friend", "missed_trial"),
        ("ugr", "decision", "missed_decision"),
        ("socialdoors", "decision", "decision-missed"),
        ("doors", "decision", "decision-missed"),
    ],
)
def test_task_specific_response_states(task: str, responded: str, missed: str) -> None:
    assert decision_state(task, responded) is False
    assert decision_state(task, missed) is True
    assert decision_state(task, "outcome_friend_recip") is None


def test_terminal_button_failure_is_a_salvage_review_candidate(tmp_path: Path) -> None:
    bids = tmp_path / "bids"
    path = event_path(bids, "11984", "ugr", 2)
    write_events(path, ["decision"] * 20 + ["missed_decision"] * 28)

    row = audit_events_file(("11984", "01", "ugr", 2), path, bids, policy())

    assert row["response_trials"] == "48"
    assert row["misses"] == "28"
    assert row["longest_miss_streak"] == "28"
    assert row["terminal_miss_streak"] == "28"
    assert row["terminal_miss_start_trial"] == "21"
    assert row["terminal_miss_start_onset_sec"] == "100"
    assert row["preterminal_miss_fraction"] == "0"
    assert row["overall_miss_rule_failed"] == "true"
    assert row["terminal_failure_candidate"] == "true"
    assert row["salvage_review_candidate"] == "true"


def test_scattered_or_early_misses_do_not_imply_terminal_failure(
    tmp_path: Path,
) -> None:
    bids = tmp_path / "bids"
    path = event_path(bids, "10001", "doors")
    pattern = [
        "decision-missed" if index % 4 == 0 else "decision" for index in range(40)
    ]
    write_events(path, pattern)

    row = audit_events_file(("10001", "01", "doors", 1), path, bids, policy())

    assert row["misses"] == "10"
    assert row["miss_fraction"] == "0.25"
    assert row["overall_miss_rule_failed"] == "true"
    assert row["longest_miss_streak"] == "1"
    assert row["terminal_miss_streak"] == "0"
    assert row["terminal_failure_candidate"] == "false"
    assert row["salvage_review_candidate"] == "false"


def test_build_and_check_detect_live_events_drift(tmp_path: Path) -> None:
    bids = tmp_path / "bids"
    write_events(event_path(bids, "10001", "doors"), ["decision"] * 40)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy()), encoding="utf-8")
    sublist = tmp_path / "subjects.txt"
    sublist.write_text("10001\n", encoding="utf-8")
    output = tmp_path / "qc" / "events" / "results"
    common = {
        "bids_root": bids,
        "output_dir": output,
        "policy": policy_path,
        "sublist": sublist,
        "excluded_source_root": tmp_path / "exclusions",
    }

    assert run_build(argparse.Namespace(**common, overwrite=False, dry_run=False)) == 0
    assert run_check(argparse.Namespace(**common)) == 0
    assert (output / "run_response_qc.tsv").is_file()
    assert (output / "review_miss_patterns.png").is_file()

    sublist.write_text("10001\n99999\n", encoding="utf-8")
    assert run_check(argparse.Namespace(**common)) == 1
    sublist.write_text("10001\n", encoding="utf-8")

    write_events(
        event_path(bids, "10001", "doors"),
        ["decision"] * 35 + ["decision-missed"] * 5,
    )
    assert run_check(argparse.Namespace(**common)) == 1


def test_build_output_directory_honors_permissive_umask(tmp_path: Path) -> None:
    bids = tmp_path / "bids"
    write_events(event_path(bids, "10001", "doors"), ["decision"] * 40)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy()), encoding="utf-8")
    output = tmp_path / "qc" / "events" / "results"
    args = argparse.Namespace(
        bids_root=bids,
        output_dir=output,
        policy=policy_path,
        sublist=None,
        excluded_source_root=tmp_path / "exclusions",
        overwrite=False,
        dry_run=False,
    )
    previous = os.umask(0)
    try:
        assert run_build(args) == 0
    finally:
        os.umask(previous)
    assert output.stat().st_mode & 0o777 == 0o777
    assert (output / "run_response_qc.tsv").stat().st_mode & 0o777 == 0o666
