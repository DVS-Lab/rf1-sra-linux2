from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from check_events import audit_subject_session
from audit_openneuro_events import audit_key
from convert_behavior import (
    _atomic_write_tsv,
    ConversionError,
    RunKey,
    convert_behavior,
    convert_source,
    event_path,
    load_curation_approvals,
    preserve_existing_events,
    resolve_sources,
    ugr_broad_trial_epoch,
)


def write_delimited(
    path: Path, rows: list[dict[str, object]], delimiter: str = ","
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def write_bold(bids: Path, key: RunKey) -> None:
    func = bids / f"sub-{key.subject}" / f"ses-{key.session}" / "func"
    func.mkdir(parents=True, exist_ok=True)
    (
        func
        / f"sub-{key.subject}_ses-{key.session}_task-{key.task}_run-{key.run}_echo-1_part-mag_bold.nii.gz"
    ).write_text("nii")


def shared_row(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "TrialNumber": 1,
        "decision_onset": 10.0,
        "resp": 1,
        "rt": 0.8,
        "outcome_onset": 13.0,
        "outcome_offset": 13.7,
        "Feedback": 3,
        "Partner": 3,
    }
    row.update(updates)
    return row


def trust_row(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "TrialNumber": 1,
        "onset": 10.0,
        "resp": 4,
        "rt": 1.2,
        "Partner": 3,
        "Reciprocate": 1,
        "highlow": "high",
        "cLeft": 2,
        "cRight": 4,
        "ISI_onset": 13.0,
        "outcome_onset": 15.0,
        "outcome_offset": 17.05,
    }
    row.update(updates)
    return row


def ugr_row(**updates: object) -> dict[str, object]:
    row: dict[str, object] = {
        "TrialNumber": 1,
        "nTrial": 1,
        "Block": 3,
        "Endowment": 32,
        "ISI": 1.0,
        "L_Option": 0,
        "R_Option": 8,
        "cue_Onset": 8.0,
        "decision_onset": 10.0,
        "resp": 2,
        "rt": 1.0,
        "resp_onset": 11.0,
        "decision_offset": 13.75,
    }
    row.update(updates)
    return row


def social_rows(misses: int = 0, decisions: int = 1) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(decisions):
        rows.append(
            {
                "onset": index * 2,
                "duration": 1,
                "trial_type": "decision-missed" if index < misses else "decision",
                "rt": "999" if index < misses else "0.5",
                "resp": "999" if index < misses else "left",
                "gender": "n/a",
                "image_left": "left.png",
                "image_right": "right.png",
            }
        )
    return rows


def test_historical_zero_based_run_mapping_and_explicit_sessions(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    trust = behavior / "Scan-Investment_Game" / "logs" / "10001"
    write_delimited(trust / "sub-10001_task-trust_run-0_raw.csv", [trust_row()])
    write_delimited(trust / "sub-10001_task-trust_run-1_raw.csv", [trust_row()])

    resolutions = resolve_sources(behavior, "10001", "01", "trust", [1, 2])

    assert resolutions[1].path.name.endswith("run-0_raw.csv")
    assert resolutions[2].path.name.endswith("run-1_raw.csv")

    ugr = behavior / "Scan-Lets_Make_A_Deal" / "logs" / "10001"
    write_delimited(ugr / "sub-10001_ses-02_task-ultimatum_run-0_raw.csv", [ugr_row()])
    assert resolve_sources(behavior, "10001", "02", "ugr", [1])[1].status == "available"
    assert resolve_sources(behavior, "10001", "01", "ugr", [1])[1].status == "missing"


def test_sharedreward_supports_historical_and_newer_run_numbering(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    source = behavior / "Scan-Card_Guessing_Game" / "logs" / "10001"
    write_delimited(
        source / "sub-10001_task-sharedreward_run-0_raw.csv", [shared_row()]
    )
    write_delimited(
        source / "sub-10001_task-sharedreward_run-1_raw.csv", [shared_row()]
    )
    historical = resolve_sources(behavior, "10001", "01", "sharedreward", [1, 2])
    assert historical[1].path.name.endswith("run-0_raw.csv")
    assert historical[2].path.name.endswith("run-1_raw.csv")

    source2 = behavior / "Scan-Card_Guessing_Game" / "logs" / "10002"
    write_delimited(
        source2 / "sub-10002_task-sharedreward_run-1_raw.csv", [shared_row()]
    )
    write_delimited(
        source2 / "sub-10002_task-sharedreward_run-2_raw.csv", [shared_row()]
    )
    newer = resolve_sources(behavior, "10002", "01", "sharedreward", [1, 2])
    assert newer[1].path.name.endswith("run-1_raw.csv")
    assert newer[2].path.name.endswith("run-2_raw.csv")


def test_lone_sharedreward_run_one_requires_fingerprint_bound_mapping(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    source = behavior / "Scan-Card_Guessing_Game" / "logs" / "10001"
    raw = source / "sub-10001_task-sharedreward_run-1_raw.csv"
    write_delimited(raw, [shared_row()])

    unresolved = resolve_sources(behavior, "10001", "01", "sharedreward", [1, 2])
    assert unresolved[1].status == "ambiguous"
    assert unresolved[2].status == "ambiguous"

    converted = convert_source("sharedreward", raw)
    curation = tmp_path / "curation.tsv"
    write_delimited(
        curation,
        [
            {
                "subject": "10001",
                "session": "01",
                "task": "sharedreward",
                "run": 2,
                "issue": "ambiguous_run_label",
                "source_sha256": converted.source_sha256,
                "trial_fingerprint": converted.trial_fingerprint,
                "reviewer": "reviewer@example.edu",
                "note": "Matched to scanner run 2 and historical reference.",
            }
        ],
        delimiter="\t",
    )

    resolved = resolve_sources(
        behavior,
        "10001",
        "01",
        "sharedreward",
        [1, 2],
        load_curation_approvals(curation),
    )

    assert resolved[1].status == "missing"
    assert resolved[2].path == raw
    assert "fingerprint-bound approval" in resolved[2].detail


def test_explicit_and_implicit_session_sources_are_ambiguous(tmp_path: Path) -> None:
    behavior = tmp_path / "behavior"
    source = behavior / "Scan-Lets_Make_A_Deal" / "logs" / "10001"
    write_delimited(source / "sub-10001_task-ultimatum_run-0_raw.csv", [ugr_row()])
    write_delimited(
        source / "sub-10001_ses-01_task-ultimatum_run-0_raw.csv", [ugr_row()]
    )

    resolution = resolve_sources(behavior, "10001", "01", "ugr", [1])[1]

    assert resolution.status == "ambiguous"


def test_sharedreward_writes_measured_outcomes_and_two_rows_for_miss(
    tmp_path: Path,
) -> None:
    source = tmp_path / "shared.csv"
    write_delimited(
        source,
        [
            shared_row(),
            shared_row(
                TrialNumber=2,
                decision_onset=20.0,
                resp=0,
                rt=3.0,
                outcome_onset=23.2,
                outcome_offset=23.85,
                Feedback=1,
                Partner=2,
            ),
        ],
    )

    converted = convert_source("sharedreward", source)
    missed = [
        row for row in converted.rows if str(row["trial_type"]).startswith("missed_")
    ]

    assert [row["trial_type"] for row in missed] == [
        "missed_decision",
        "missed_outcome",
    ]
    assert missed[0]["duration"] == pytest.approx(3.2)
    assert missed[1]["duration"] == pytest.approx(0.65)
    outcome = [
        row for row in converted.rows if row["trial_type"] == "event_friend_reward"
    ][0]
    assert outcome["onset"] == 13.0
    assert outcome["duration"] == pytest.approx(0.7)


def test_sharedreward_preserves_reward_neutral_and_punish_labels(
    tmp_path: Path,
) -> None:
    source = tmp_path / "shared.csv"
    write_delimited(
        source,
        [
            shared_row(TrialNumber=1, Feedback=1, Partner=1),
            shared_row(TrialNumber=2, Feedback=2, Partner=2),
            shared_row(TrialNumber=3, Feedback=3, Partner=3),
        ],
    )

    converted = convert_source("sharedreward", source)
    labels = {row["trial_type"] for row in converted.rows}

    assert "event_computer_punish" in labels
    assert "event_stranger_neutral" in labels
    assert "event_friend_reward" in labels


def test_malformed_executed_source_row_is_a_hard_failure(tmp_path: Path) -> None:
    source = tmp_path / "shared.csv"
    write_delimited(
        source,
        [shared_row(), shared_row(TrialNumber=2, outcome_onset="", outcome_offset="")],
    )

    with pytest.raises(ConversionError, match="source row 3.*outcome_onset"):
        convert_source("sharedreward", source)


def test_explicit_unrun_placeholder_is_the_only_skipped_raw_row(tmp_path: Path) -> None:
    source = tmp_path / "shared.csv"
    write_delimited(
        source,
        [
            shared_row(ran=1),
            shared_row(
                TrialNumber=2,
                ran=0,
                decision_onset="--",
                outcome_onset="--",
                outcome_offset="--",
            ),
        ],
    )

    converted = convert_source("sharedreward", source)

    assert converted.trial_count == 1
    assert converted.notes == ["omitted 1 explicit ran=0 placeholder row(s)"]


def test_appended_header_is_rejected_as_multiple_run_segments(tmp_path: Path) -> None:
    source = tmp_path / "shared.csv"
    write_delimited(
        source, [shared_row(), shared_row(TrialNumber=2, decision_onset=20)]
    )
    text = source.read_text()
    source.write_text(text + text)

    with pytest.raises(ConversionError, match="multiple run segments: repeated header"):
        convert_source("sharedreward", source)


def test_trial_reset_without_repeated_header_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "ugr.csv"
    write_delimited(
        source,
        [
            ugr_row(TrialNumber=1, nTrial=1, decision_onset=10),
            ugr_row(TrialNumber=2, nTrial=2, decision_onset=20),
            ugr_row(TrialNumber=1, nTrial=1, decision_onset=30),
        ],
    )

    with pytest.raises(ConversionError, match="trial numbering resets"):
        convert_source("ugr", source)


def test_column_shift_corruption_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "shared.csv"
    write_delimited(source, [shared_row()])
    with source.open("a") as handle:
        handle.write("2,2,4,2,1,8.08E,1,1.0,0.0,extra,fields\n")

    with pytest.raises(ConversionError, match=r"source row 3 has .* field"):
        convert_source("sharedreward", source)


def test_historical_tab_delimited_raw_file_is_detected_safely(tmp_path: Path) -> None:
    source = tmp_path / "shared.csv"
    write_delimited(source, [shared_row()], delimiter="\t")

    converted = convert_source("sharedreward", source)

    assert converted.trial_count == 1


def test_trust_uses_measured_outcome_duration_and_skips_zero_outcome(
    tmp_path: Path,
) -> None:
    source = tmp_path / "trust.csv"
    write_delimited(
        source,
        [trust_row(), trust_row(TrialNumber=2, onset=20, resp=0, cLeft=0, cRight=2)],
    )

    converted = convert_source("trust", source)
    outcomes = [
        row for row in converted.rows if str(row["trial_type"]).startswith("outcome_")
    ]

    assert len(outcomes) == 1
    assert outcomes[0]["duration"] == pytest.approx(2.05)
    assert any(
        row["trial_type"] == "choice_friend" and row["trust_value"] == 0
        for row in converted.rows
    )


def test_ugr_reconstructs_phases_choices_and_historical_broad_epoch(
    tmp_path: Path,
) -> None:
    source = tmp_path / "ugr.csv"
    write_delimited(
        source,
        [
            ugr_row(),
            ugr_row(
                TrialNumber=2,
                nTrial=2,
                Block=2,
                Endowment=16,
                L_Option=6,
                R_Option=0,
                decision_onset=20,
                cue_Onset=18,
                resp=999,
                rt=999,
                resp_onset=999,
                decision_offset=23.25,
            ),
        ],
    )

    converted = convert_source("ugr", source)
    first = [row for row in converted.rows if row["trial_id"] == "1"]
    second = [row for row in converted.rows if row["trial_id"] == "2"]

    assert [row["phase"] for row in first] == [
        "partner_cue",
        "endowment",
        "decision",
        "choice_feedback",
    ]
    assert first[0]["onset"] == 7.5
    assert first[1]["duration"] == 2.0
    assert first[2]["duration"] == 1.0
    assert first[3]["duration"] == 2.75
    assert all(row["decision"] == "accept" for row in first)
    assert [row["phase"] for row in second][-2:] == ["decision", "missed_feedback"]
    assert ugr_broad_trial_epoch(first) == (7.5, 6.25)


def test_ugr_accept_reject_uses_raw_left_right_mapping(tmp_path: Path) -> None:
    source = tmp_path / "ugr.csv"
    write_delimited(source, [ugr_row(resp=1, L_Option=0, R_Option=8)])

    converted = convert_source("ugr", source)

    assert all(row["decision"] == "reject" for row in converted.rows)
    assert all(
        row["left_option"] == 0 and row["right_option"] == 8 for row in converted.rows
    )


def test_socialdoors_incomplete_and_poor_runs_are_written_not_suppressed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "social.tsv"
    write_delimited(source, social_rows(misses=10, decisions=12), delimiter="\t")

    converted = convert_source("socialdoors", source)

    assert len(converted.rows) == 12
    assert converted.unexpected_trial_count
    assert converted.behaviorally_poor


def test_socialdoors_source_mapping_supports_session_two_and_rejects_ambiguity(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    source = behavior / "Scan-Social_Doors" / "data" / "10001"
    write_delimited(
        source / "sub-10001_ses-02_task-socialReward_facesA1_events.tsv",
        social_rows(),
        delimiter="\t",
    )
    assert (
        resolve_sources(behavior, "10001", "02", "socialdoors", [1])[1].status
        == "available"
    )

    write_delimited(
        source / "sub-10001_ses-02_task-socialReward_facesB2_events.tsv",
        social_rows(),
        delimiter="\t",
    )
    assert (
        resolve_sources(behavior, "10001", "02", "socialdoors", [1])[1].status
        == "ambiguous"
    )


def test_conversion_is_idempotent_with_explicit_overwrite(tmp_path: Path) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    write_bold(bids, key)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    rows = [
        trust_row(
            TrialNumber=index,
            onset=index * 20,
            ISI_onset=index * 20 + 3,
            outcome_onset=index * 20 + 5,
            outcome_offset=index * 20 + 7,
        )
        for index in range(1, 43)
    ]
    write_delimited(source / "sub-10001_task-trust_run-0_raw.csv", rows)

    assert convert_behavior("10001", "01", ("trust",), behavior, bids) == 0
    original = event_path(bids, key).read_text()
    assert convert_behavior("10001", "01", ("trust",), behavior, bids) == 1
    assert (
        convert_behavior("10001", "01", ("trust",), behavior, bids, overwrite=True) == 0
    )
    assert event_path(bids, key).read_text() == original
    assert (bids / "task-trust_events.json").is_file()


def test_conversion_can_target_one_exact_run(tmp_path: Path) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    run_one = RunKey("10001", "01", "trust", 1)
    run_two = RunKey("10001", "01", "trust", 2)
    write_bold(bids, run_one)
    write_bold(bids, run_two)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    for raw_run in (0, 1):
        rows = [
            trust_row(
                TrialNumber=index,
                onset=index * 20,
                ISI_onset=index * 20 + 3,
                outcome_onset=index * 20 + 5,
                outcome_offset=index * 20 + 7,
            )
            for index in range(1, 43)
        ]
        write_delimited(source / f"sub-10001_task-trust_run-{raw_run}_raw.csv", rows)

    assert (
        convert_behavior(
            "10001", "01", ("trust",), behavior, bids, runs=(2,)
        )
        == 0
    )
    assert not event_path(bids, run_one).exists()
    assert event_path(bids, run_two).is_file()


def test_short_run_needs_fingerprint_bound_human_approval(tmp_path: Path) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    write_bold(bids, key)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    raw = source / "sub-10001_task-trust_run-0_raw.csv"
    write_delimited(raw, [trust_row()])

    assert convert_behavior("10001", "01", ("trust",), behavior, bids) == 1
    assert not event_path(bids, key).exists()

    converted = convert_source("trust", raw)
    curation = tmp_path / "curation.tsv"
    write_delimited(
        curation,
        [
            {
                "subject": "10001",
                "session": "01",
                "task": "trust",
                "run": 1,
                "issue": "unexpected_trial_count",
                "source_sha256": converted.source_sha256,
                "trial_fingerprint": converted.trial_fingerprint,
                "reviewer": "reviewer@example.edu",
                "note": "Verified against scanner notes and task log.",
            }
        ],
        delimiter="\t",
    )
    approvals = load_curation_approvals(curation)
    assert approvals[(key, "unexpected_trial_count")].reviewer == "reviewer@example.edu"
    assert (
        convert_behavior(
            "10001",
            "01",
            ("trust",),
            behavior,
            bids,
            curation_file=curation,
        )
        == 0
    )

    raw.write_text(raw.read_text().replace("10.0", "10.1", 1))
    assert (
        convert_behavior(
            "10001",
            "01",
            ("trust",),
            behavior,
            bids,
            overwrite=True,
            curation_file=curation,
        )
        == 1
    )


def test_audit_flags_unapproved_short_run_for_human_review(tmp_path: Path) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    write_bold(bids, key)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    raw = source / "sub-10001_task-trust_run-0_raw.csv"
    write_delimited(raw, [trust_row()])
    converted = convert_source("trust", raw)
    destination = event_path(bids, key)
    _atomic_write_tsv(destination, converted, overwrite=False, dry_run=False)
    (bids / "task-trust_events.json").write_text("{}\n")
    findings: list[dict[str, str]] = []

    failed, counts = audit_subject_session(
        bids,
        behavior,
        "10001",
        "01",
        ("trust",),
        quiet_ok=True,
        review_findings=findings,
    )

    assert failed == 1
    assert counts["review required"] == 1
    assert findings[0]["issue"] == "unexpected_trial_count"
    assert findings[0]["source_sha256"] == converted.source_sha256


def test_audit_detects_changed_event_contents_even_when_row_count_matches(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    write_bold(bids, key)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    rows = [
        trust_row(
            TrialNumber=index,
            onset=index * 20,
            ISI_onset=index * 20 + 3,
            outcome_onset=index * 20 + 5,
            outcome_offset=index * 20 + 7,
        )
        for index in range(1, 43)
    ]
    write_delimited(source / "sub-10001_task-trust_run-0_raw.csv", rows)
    assert convert_behavior("10001", "01", ("trust",), behavior, bids) == 0
    destination = event_path(bids, key)
    destination.write_text(
        destination.read_text().replace("choice_friend", "choice_stranger", 1)
    )

    failed, counts = audit_subject_session(
        bids, behavior, "10001", "01", ("trust",), quiet_ok=True
    )

    assert failed == 1
    assert counts["conversion failed"] == 1


def test_openneuro_audit_identifies_likely_run_swap(tmp_path: Path) -> None:
    behavior = tmp_path / "behavior"
    reference = tmp_path / "openneuro"
    key = RunKey("10001", "01", "trust", 1)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    write_delimited(source / "sub-10001_task-trust_run-0_raw.csv", [trust_row()])
    func = reference / "sub-10001" / "func"
    write_delimited(
        func / "sub-10001_task-trust_run-1_events.tsv",
        [
            {
                "onset": 1,
                "duration": 1,
                "trial_type": "choice_computer",
                "response_time": 1,
                "trust_value": 2,
                "choice": "high",
                "cLow": 0,
                "cHigh": 2,
            }
        ],
        delimiter="\t",
    )
    write_delimited(
        func / "sub-10001_task-trust_run-2_events.tsv",
        [
            {
                "onset": 1,
                "duration": 1,
                "trial_type": "choice_friend",
                "response_time": 1,
                "trust_value": 4,
                "choice": "high",
                "cLow": 2,
                "cHigh": 4,
            },
            {
                "onset": 3,
                "duration": 1,
                "trial_type": "outcome_friend_recip",
                "response_time": 1,
                "trust_value": 4,
                "choice": "high",
                "cLow": 2,
                "cHigh": 4,
            },
        ],
        delimiter="\t",
    )

    result = audit_key(key, behavior, reference)

    assert result["status"] == "run_swap_risk"
    assert "run(s) [2]" in result["detail"]


def test_preserve_existing_events_copies_only_matching_bold_runs(
    tmp_path: Path,
) -> None:
    stage = tmp_path / "stage"
    live = tmp_path / "live"
    matching = RunKey("10001", "01", "ugr", 1)
    orphan = RunKey("10001", "01", "ugr", 2)
    write_bold(stage, matching)
    event_path(live, matching).parent.mkdir(parents=True)
    event_path(live, matching).write_text(
        "onset\tduration\ttrial_type\n0\t1\tdecision\n"
    )
    event_path(live, orphan).write_text("onset\tduration\ttrial_type\n0\t1\tdecision\n")

    copied = preserve_existing_events(stage, live, [matching], dry_run=False)

    assert copied == 1
    assert event_path(stage, matching).is_file()
    assert not event_path(stage, orphan).exists()


def test_events_audit_fails_when_source_exists_but_events_are_missing(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    write_bold(bids, key)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    rows = [
        trust_row(
            TrialNumber=index,
            onset=index * 20,
            ISI_onset=index * 20 + 3,
            outcome_onset=index * 20 + 5,
            outcome_offset=index * 20 + 7,
        )
        for index in range(1, 43)
    ]
    write_delimited(source / "sub-10001_task-trust_run-0_raw.csv", rows)

    failed, counts = audit_subject_session(
        bids, behavior, "10001", "01", ("trust",), quiet_ok=True
    )

    assert failed == 1
    assert counts["events missing"] == 1


def test_events_audit_diagnoses_bad_source_before_missing_output(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    write_bold(bids, key)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    raw = source / "sub-10001_task-trust_run-0_raw.csv"
    raw.parent.mkdir(parents=True)
    raw.write_text("TrialNumber,onset\nTrialNumber,onset\n")

    findings: list[dict[str, str]] = []
    failed, counts = audit_subject_session(
        bids,
        behavior,
        "10001",
        "01",
        ("trust",),
        quiet_ok=True,
        review_findings=findings,
    )

    assert failed == 1
    assert counts["conversion failed"] == 1
    assert counts["events missing"] == 0
    assert findings[0]["issue"] == "conversion_failed"


def test_events_audit_diagnoses_review_issue_before_missing_output(
    tmp_path: Path,
) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    write_bold(bids, key)
    source = behavior / "Scan-Investment_Game" / "logs" / "10001"
    write_delimited(source / "sub-10001_task-trust_run-0_raw.csv", [trust_row()])

    findings: list[dict[str, str]] = []
    failed, counts = audit_subject_session(
        bids,
        behavior,
        "10001",
        "01",
        ("trust",),
        quiet_ok=True,
        review_findings=findings,
    )

    assert failed == 1
    assert counts["unexpected trial count"] == 1
    assert counts["events missing"] == 0
    assert findings[0]["issue"] == "unexpected_trial_count"


def test_events_audit_rejects_event_file_without_matching_bold(tmp_path: Path) -> None:
    behavior = tmp_path / "behavior"
    bids = tmp_path / "bids"
    key = RunKey("10001", "01", "trust", 1)
    destination = event_path(bids, key)
    destination.parent.mkdir(parents=True)
    destination.write_text("onset\tduration\ttrial_type\n0\t1\tchoice_friend\n")

    failed, counts = audit_subject_session(
        bids, behavior, "10001", "01", ("trust",), quiet_ok=True
    )

    assert failed == 1
    assert counts["BOLD missing"] == 1
