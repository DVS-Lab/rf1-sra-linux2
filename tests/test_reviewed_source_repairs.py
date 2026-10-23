import hashlib
import json
import os
import stat
from pathlib import Path
import sys
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import reviewed_behavior_sources as reviewed
import heuristics_11935 as heuristic
from convert_behavior import resolve_sources
from run_reviewed_source_repairs import initialize, timing_matches, validate_bids
import run_reviewed_source_repairs as runner


def test_code_snapshot_ignores_untracked_unreadable_logs(tmp_path, monkeypatch):
    project = tmp_path / "repo"
    code = project / "code"
    code.mkdir(parents=True)
    script = code / "pipeline.py"
    script.write_text("# tracked pipeline\n")
    (code / "nohup.out").write_text("untracked log")
    runner.subprocess.run(["git", "init", "-q", str(project)], check=True)
    runner.subprocess.run(["git", "-C", str(project), "add", "code/pipeline.py"], check=True)
    original = Path.read_bytes
    def read_bytes(path):
        if path.name == "nohup.out":
            raise PermissionError("incidental log must never be opened")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    destination = project / "work/repair"
    receipt = runner.initialize(project, destination, "11935")
    assert set(receipt["code"]) == {"pipeline.py"}
    assert not (destination / "code/nohup.out").exists()
    assert runner.code_hashes(destination / "code", receipt["code"]) == receipt["code"]
    script.write_text("# tracked change\n")
    assert runner.code_hashes(code, runner.tracked_code_paths(code)) != receipt["code"]
    script.unlink()
    with pytest.raises(FileNotFoundError):
        runner.code_hashes(code, runner.tracked_code_paths(code))


def test_unreadable_tracked_code_fails_before_creating_workspace(tmp_path, monkeypatch):
    code = tmp_path / "code"
    code.mkdir()
    (code / "pipeline.py").write_text("# fixture\n")
    monkeypatch.setattr(runner, "tracked_code_paths", lambda root: ["pipeline.py"])
    def unreadable(path):
        raise PermissionError("tracked pipeline unreadable")
    monkeypatch.setattr(Path, "read_bytes", unreadable)
    destination = tmp_path / "work/repair"
    with pytest.raises(PermissionError):
        runner.initialize(tmp_path, destination, "11935")
    assert not destination.exists()


def test_shared_copy_does_not_inherit_readonly_modes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_text("unchanged")
    (source / "script").write_text("#!/bin/sh\n")
    (source / "data").chmod(0o444)
    (source / "script").chmod(0o555)
    source.chmod(0o555)
    before = runner.signatures([source])
    destination = tmp_path / "copy"
    old = os.umask(0o077)
    try:
        runner.copy_shared_tree(source, destination)
    finally:
        os.umask(old)
    assert runner.signatures([source]) == before
    assert stat.S_IMODE(source.stat().st_mode) == 0o555
    assert stat.S_IMODE((source / "data").stat().st_mode) == 0o444
    assert stat.S_IMODE(destination.stat().st_mode) == 0o777
    assert stat.S_IMODE((destination / "data").stat().st_mode) == 0o666
    assert stat.S_IMODE((destination / "script").stat().st_mode) == 0o777
    assert (destination / "data").read_text() == "unchanged"
    with pytest.raises(FileExistsError):
        runner.copy_shared_file(source / "data", destination / "data")


def test_cli_enforces_lab_umask_for_files_and_children(tmp_path, monkeypatch):
    def run(args):
        path = tmp_path / "created"
        path.write_text("shared")
        assert stat.S_IMODE(path.stat().st_mode) == 0o666
        result = runner.subprocess.check_output(
            [sys.executable, "-c", "import os; print(os.umask(0))"], text=True)
        assert result.strip() == "0"
    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(sys, "argv", ["repair", "plan", "--subject", "10964", "--private-dir", str(tmp_path)])
    old = os.umask(0o077)
    try:
        assert runner.main() == 0
    finally:
        os.umask(old)


def seqs():
    return [SimpleNamespace(series_id=f"{n}-task-SocialDoors_face", dim4=4 if n in (23,24,27,28) else 872,
        dim3=51, protocol_name="task-SocialDoors_face", image_type=("ORIGINAL", "FMRI"),
        series_description="task-SocialDoors_face_TR1615" + ("_SBRef" if n in (23,24,27,28) else "") + ("_Pha" if n % 2 == 0 else ""))
        for n in range(23,31)]


def test_exact_mapping_independent_of_list_order():
    # Base heuristic uses list adjacency; the override must replace those references.
    rows = seqs()
    rows = rows[4:] + rows[:4]
    result = {k[0]: v for k,v in heuristic.infotodict(rows).items()}
    for task, first in (("socialdoors",25),("doors",29)):
        for ending, number in (("_part-mag_bold",first),("_part-phase_bold",first+1),("_sbref",first-2)):
            values = [v for k,v in result.items() if f"_task-{task}_" in k and k.endswith(ending)]
            assert values == [[f"{number}-task-SocialDoors_face"]]


@pytest.mark.parametrize("damage", ["missing", "duplicate", "length", "phase", "reference"])
def test_mapping_fails_closed(damage):
    rows = seqs()
    if damage == "missing": rows.pop(0)
    elif damage == "duplicate": rows.append(rows[2])
    elif damage == "length": rows[2].dim4 = 840
    elif damage == "phase": rows[2].series_description += "_Pha"
    else: rows[0].series_description = "task-SocialDoors_face_TR1615"
    with pytest.raises(ValueError): heuristic.infotodict(rows)


def sources(tmp_path, monkeypatch):
    directory = tmp_path / "Scan-Social_Doors/data/10964"
    directory.mkdir(parents=True)
    paths = [directory / "sub-10964_ses-01_task-socialReward_doorsA3_events.tsv",
             directory / "sub-10964_ses-1_task-socialReward_doorsA3_events.tsv",
             directory / "sub-10964_ses-01_task-socialReward_doorsA3_desc-runtiming.jsonl"]
    for p, text in zip(paths, ("new", "old", "timing")): p.write_text(text)
    monkeypatch.setitem(reviewed.WAVE2_10964, "doors", ("doors", *[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]))
    return paths


def test_source_override_preserves_originals(tmp_path, monkeypatch):
    paths = sources(tmp_path, monkeypatch)
    before = [p.read_bytes() for p in paths]
    resolution = resolve_sources(tmp_path,"10964","02","doors",[1])[1]
    assert resolution.status == "available" and resolution.path == paths[0]
    assert [p.read_bytes() for p in paths] == before
    assert resolve_sources(tmp_path,"10965","02","doors",[1])[1].status == "missing"


@pytest.mark.parametrize("index", range(3))
def test_changed_source_or_baseline_or_timing_blocks(tmp_path, monkeypatch, index):
    paths = sources(tmp_path, monkeypatch)
    paths[index].write_text("changed")
    assert resolve_sources(tmp_path,"10964","02","doors",[1])[1].status == "ambiguous"


def test_new_correctly_named_candidate_blocks(tmp_path, monkeypatch):
    paths = sources(tmp_path, monkeypatch)
    paths[0].with_name(paths[0].name.replace("ses-01", "ses-02")).write_text("new")
    assert resolve_sources(tmp_path,"10964","02","doors",[1])[1].status == "ambiguous"


def test_timestamps_allow_clock_offset_not_earlier_attempt():
    acquisitions = [{"task": task,"series": n,"time": f"2026-10-05T15:{minute:02}:00"}
                    for task,n,minute in [("doors",9,0),("doors",13,3),("socialdoors",17,11),("ugr",21,19),("ugr",25,27)]]
    triggers = [f"2026-10-05T15:{m:02}:00" for m in (7,15,23,31)]
    found = timing_matches(acquisitions,triggers)
    assert len(found) == 1 and found[0]["series"] == [13,17,21,25]
    assert found[0]["offset_seconds"] == [240]*4
    triggers[0] = "2026-10-05T15:04:00"
    assert timing_matches(acquisitions,triggers)[0]["series"][0] == 9
    triggers[0] = "2026-10-05T15:05:00"
    assert not timing_matches(acquisitions,triggers)


def test_initialization_never_uses_production_destination(tmp_path):
    with pytest.raises(ValueError): initialize(tmp_path, tmp_path / "bids", "11935")


def test_bids_reference_and_volume_checks(tmp_path):
    func = tmp_path / "bids/sub-11935/ses-01/func"
    func.mkdir(parents=True)
    for task,n in (("socialdoors",25),("doors",29)):
        stem = f"sub-11935_ses-01_task-{task}_run-1"
        for echo in range(1,5):
            for part,offset in (("mag",0),("phase",1)):
                path = func / f"{stem}_echo-{echo}_part-{part}_bold.nii.gz"
                nib.save(nib.Nifti1Image(np.zeros((2,2,2,218)), np.eye(4)), path)
                path.with_name(path.name[:-7]+".json").write_text(json.dumps({"SeriesNumber":n+offset}))
        (func / f"{stem}_sbref.json").write_text(json.dumps({"SeriesNumber":n-2}))
    validate_bids(tmp_path,"11935")
    (func / "sub-11935_ses-01_task-socialdoors_run-1_sbref.json").write_text('{"SeriesNumber":27}')
    with pytest.raises(ValueError, match="reference"): validate_bids(tmp_path,"11935")


def test_isolated_runner_resume_and_unchanged_production(tmp_path, monkeypatch):
    production = tmp_path / "production"
    (production / "code").mkdir(parents=True)
    (production / "code/example.py").write_text("# fixture\n")
    (production / "bids/sub-11935/ses-01/func").mkdir(parents=True)
    original = production / "bids/sub-11935/ses-01/func/original"
    original.write_text("preserve me")
    excluded = tmp_path / "exclusions"
    excluded.mkdir()
    private = production / "work/repairs"
    monkeypatch.setattr(runner, "behavior_preflight", lambda *a: None)
    monkeypatch.setattr(runner, "tracked_code_paths", lambda root: ["example.py"])
    monkeypatch.setattr(runner, "validate_bids", lambda *a: None)
    monkeypatch.setattr(runner, "validate_mriqc", lambda *a: None)
    calls = []
    def execute(command, **kwargs):
        calls.append(command)
        dest = kwargs["cwd"]
        assert dest.is_relative_to(private)
        assert kwargs["env"]["SCRATCH_ROOT"] == str(dest / "scratch")
        assert kwargs["pass_fds"]
        if command[1] == "code/prepdata.sh":
            (dest / "bids/sub-11935/ses-01").mkdir(parents=True)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runner.subprocess, "run", execute)
    args = SimpleNamespace(project_root=production, private_dir=private, subject="11935",
                           exclusions_root=excluded, behavior_root=tmp_path, source_root=tmp_path,
                           command="build", jobs=8)
    runner.run(args)
    assert original.read_text() == "preserve me"
    first_count = len(calls)
    runner.run(args)
    resumed = calls[first_count:]
    assert not any(c[1] in ("code/prepdata.sh", "code/fmriprep.sh", "code/run_tedana.sh", "code/mriqc.sh") for c in resumed)
    args.command = "check"
    runner.run(args)
    assert json.loads((private / "sub-11935-project/validated.json").read_text())["validated"]
    original.write_text("changed externally")
    with pytest.raises(ValueError, match="Production inputs changed"):
        runner.run(args)


def test_source_exclusion_blocks_before_initialization(tmp_path, monkeypatch):
    excluded = tmp_path / "excluded"
    (excluded / "Smith-SRA-11935").mkdir(parents=True)
    args = SimpleNamespace(project_root=tmp_path, private_dir=tmp_path / "work/repair", subject="11935", exclusions_root=excluded)
    with pytest.raises(ValueError, match="source-excluded"):
        runner.run(args)
    assert not args.private_dir.exists()
