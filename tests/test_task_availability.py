import argparse
import csv
from pathlib import Path
import sys

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import audit_task_availability as audit


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def image(path, n=4):
    path.parent.mkdir(parents=True, exist_ok=True)
    nii = nib.Nifti1Image(np.zeros((2, 2, 2, n), dtype=np.float32), np.eye(4))
    nii.header.set_zooms((1, 1, 1, 2))
    nib.save(nii, path)


def setup(tmp_path):
    project, ugr, doors, excluded = [tmp_path / name for name in ("project", "ugr", "doors", "excluded")]
    for p in (project / "derivatives/fmriprep", project / "derivatives/fsl/confounds_tedana",
              ugr / "derivatives/fsl", doors / "derivatives/fsl", excluded):
        p.mkdir(parents=True)
    put(project / "bids/participants.tsv", "participant_id\nsub-12018\n")
    rows = []
    for task, run in audit.UNITS:
        rows.append(dict(subject="12018", session="01", task=task, run=run,
                         paradigm="socialdoors" if task == "socialdoors" else "ugr",
                         tsnr="30", fd_mean="0.1", tedana_rejected_components="20",
                         brain_coverage_pct="99", missing_metrics="", qc_status="outlier"))
    (project / "qc").mkdir()
    audit.write_table(project / "qc/run_qc.tsv", rows)
    put(project / "qc/thresholds.tsv", "paradigm\tmetric\nugr\ttsnr\n")
    return argparse.Namespace(project_root=project, ugr_root=ugr, socdoors_root=doors,
                              exclusions_root=excluded, sublist=None, sessions="01", dispositions=None)


def populate(args, sub="12018", task="ugr", run="1"):
    paths = audit.input_paths(args.project_root, sub, "01", task, run)
    image(paths["bids_bold"])
    image(paths["bold"])
    put(paths["events"], "onset\tduration\ttrial_type\n0\t1\tdecision\n2\t1\twin\n4\t1\tloss\n")
    put(paths["confounds"], "0\t1\n0\t1\n0\t1\n0\t1\n")
    return paths


def test_all_expected_runs_including_missing_events(tmp_path):
    args = setup(tmp_path)
    paths = populate(args)
    paths["events"].unlink()
    rows, _, _ = audit.collect(args)
    assert len(rows) == 3
    ugr = next(r for r in rows if r["task"] == "ugr" and r["run"] == "1")
    assert "events:absent" in ugr["missing_inputs"]
    assert ugr["bold_state"] == "present"
    assert ugr["technical_status"] == "needs_review"


def test_qc_flag_does_not_exclude_and_12018_needs_no_exception(tmp_path):
    args = setup(tmp_path)
    populate(args)
    rows, _, _ = audit.collect(args)
    row = next(r for r in rows if r["task"] == "ugr" and r["run"] == "1")
    assert row["technical_status"] == "inputs_present_aligned"
    assert row["recorded_qc_status"] == "outlier"
    assert row["existing_decision"] == "not_recorded"
    assert row["final_analysis_eligibility"] == "not_assigned_by_audit"


def test_source_exclusion_overrides_residual_files(tmp_path):
    args = setup(tmp_path)
    populate(args)
    (args.exclusions_root / "Smith-SRA-12018").mkdir()
    rows, _, _ = audit.collect(args)
    assert all(r["roster_gate"] == "blocked" and r["next_action"] == "preserve_existing_block" for r in rows)


def test_missing_live_root_is_not_empty_cohort(tmp_path):
    args = setup(tmp_path)
    (args.ugr_root / "derivatives/fsl").rmdir()
    with pytest.raises(ValueError, match="live root"):
        audit.collect(args)


def test_permission_failure_not_absence(tmp_path, monkeypatch):
    def denied(self):
        raise PermissionError("denied")
    monkeypatch.setattr(Path, "stat", denied)
    with pytest.raises(PermissionError):
        audit.file_state(tmp_path / "file")


def test_mismatch_and_invalid_events_reported(tmp_path):
    args = setup(tmp_path)
    paths = populate(args)
    put(paths["confounds"], "1\n2\n")
    put(paths["events"], "onset\tduration\ttrial_type\n20\t1\tdecision\n")
    result = audit.validate_inputs(paths, {k: "present" for k in paths}, "ugr")
    assert "bold_confound_row_mismatch" in result[-1]
    assert "event_extends_past_bold" in result[-1]
    image(paths["bids_bold"], n=5)
    result = audit.validate_inputs(paths, {k: "present" for k in paths}, "ugr")
    assert "bids_preproc_length_or_tr_mismatch" in result[-1]


def test_reviewed_exclusion_preserved(tmp_path):
    args = setup(tmp_path)
    populate(args)
    args.dispositions = tmp_path / "reviewed.tsv"
    audit.write_table(args.dispositions, [dict(subject="12018", session="01", task="ugr", run="1",
                     decision="exclude", reason="fixture prior decision", evidence="fixture reviewer")])
    rows, _, _ = audit.collect(args)
    row = next(r for r in rows if r["task"] == "ugr" and r["run"] == "1")
    assert row["existing_decision"] == "exclude"
    assert row["next_action"] == "preserve_existing_block"


def test_known_model_hold_not_cleared_by_file_presence(tmp_path):
    args = setup(tmp_path)
    put(args.project_root / "bids/participants.tsv", "participant_id\nsub-11201\n")
    populate(args, sub="11201")
    rows, _, _ = audit.collect(args)
    row = next(r for r in rows if r["task"] == "ugr" and r["run"] == "1")
    assert row["existing_hold"]
    assert row["next_action"] == "preserve_existing_block"


def test_duplicate_qc_keys_fail(tmp_path):
    args = setup(tmp_path)
    path = args.project_root / "qc/run_qc.tsv"
    _, rows, _ = audit.read_tsv(path)
    audit.write_table(path, rows + rows[:1])
    with pytest.raises(ValueError, match="duplicate run"):
        audit.collect(args)


def test_feat_requires_varcope_and_does_not_claim_lineage(tmp_path):
    base = tmp_path / "run.feat"
    for name in ("design.mat", "design.fsf", "mask.nii.gz", "stats/cope1.nii.gz", "stats/zstat1.nii.gz"):
        put(base / name, "fixture")
    put(base / "design.con", "/NumContrasts 1\n")
    state, missing = audit.feat_evidence(base)
    assert state == "partial" and "varcope1" in missing
    put(base / "stats/varcope1.nii.gz", "fixture")
    assert audit.feat_evidence(base)[0] == "files_present"


def test_cli_build_verify_and_detect_changed_input(tmp_path, monkeypatch):
    args = setup(tmp_path)
    paths = populate(args)
    output = args.project_root / "work/audit"
    argv = ["audit_task_availability.py", "--project-root", str(args.project_root),
            "--ugr-root", str(args.ugr_root), "--socdoors-root", str(args.socdoors_root),
            "--exclusions-root", str(args.exclusions_root), "--private-dir", str(output)]
    monkeypatch.setattr(sys, "argv", argv)
    assert audit.main() == 0
    assert output.stat().st_mode & 0o777 == 0o700
    assert audit.check_saved(output) == 0
    put(paths["confounds"], "0\n")
    with pytest.raises(ValueError, match="input changed"):
        audit.check_saved(output)


def test_saved_manifest_omission_does_not_block_current_inputs(tmp_path):
    args = setup(tmp_path)
    populate(args)
    for name in ("L1-ready.tsv", "L1-missing.tsv"):
        put(args.ugr_root / "logs/runlists" / name, "subject\tsession\trun\n")
    rows, _, _ = audit.collect(args)
    row = next(r for r in rows if r["task"] == "ugr" and r["run"] == "1")
    assert row["prior_manifest_state"] == "absent_from_both"
    assert row["technical_status"] == "inputs_present_aligned"
