import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import nibabel as nib
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import run_no_tedana_l1 as runner
from genTedanaConfounds import build_confounds


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def frame(n=40):
    rng = np.random.default_rng(42)
    result = pd.DataFrame(rng.normal(size=(n, 13)), columns=runner.DESIRED_FMRIPREP_COLUMNS)
    result.loc[0, "framewise_displacement"] = np.nan
    result["cosine00"] = np.cos(np.linspace(0, np.pi, n))
    result["non_steady_state_outlier00"] = np.eye(n, 1)[:, 0]
    result["global_signal"] = 999
    return result


def row(**kwargs):
    return dict(subject="12018", session="01", task="ugr", run="1", roster_gate="member",
                existing_hold="", existing_decision="not_recorded", decision_reason="",
                technical_status="needs_review", missing_inputs="confounds:absent",
                input_findings="", recorded_qc_status="outlier", **kwargs)


def test_exact_production_base_without_ica(tmp_path):
    source, mixing, metrics = [tmp_path / f"{name}.tsv" for name in ("source", "mixing", "metrics")]
    frame().to_csv(source, sep="\t", index=False)
    pd.DataFrame({"ICA_00": range(40)}).to_csv(mixing, sep="\t", index=False)
    pd.DataFrame({"Component": ["ICA_00"], "classification": ["rejected"]}).to_csv(metrics, sep="\t", index=False)
    base = runner.base_confounds(source)
    full = build_confounds(source, mixing, metrics)
    pd.testing.assert_frame_equal(base, full.iloc[:, :-1])
    assert "global_signal" not in base and base.shape == (40, 15)
    assert base.loc[0, "framewise_displacement"] == 0


@pytest.mark.parametrize("bad", ["missing", "infinity", "text"])
def test_invalid_base_fails(tmp_path, bad):
    data = frame()
    if bad == "missing":
        data = data.drop(columns="trans_x")
    elif bad == "infinity":
        data.loc[1, "trans_x"] = np.inf
    else:
        data["trans_x"] = "broken"
    path = tmp_path / "source.tsv"
    data.to_csv(path, sep="\t", index=False)
    with pytest.raises(ValueError):
        runner.base_confounds(path)


def test_age_boundary_and_holds_not_qc(tmp_path):
    assert runner.classify(row(), Decimal("55"))[0] == "candidate"
    assert runner.classify(row(), Decimal("54.99"))[0] == "under_55"
    assert runner.classify(row(), None)[0] == "age_unknown"
    for changes in ({"existing_hold": "settled"}, {"roster_gate": "blocked"},
                    {"existing_decision": "exclude"}, {"existing_decision": "review"}):
        assert runner.classify(row() | changes, Decimal(60))[0] == "held"
    path = tmp_path / "participants.tsv"
    put(path, "participant_id\tage\nsub-12018\t055Y\nsub-12019\tn/a\n")
    assert runner.ages(path, ["12018", "12019", "12020"]) == {"12018": Decimal(55), "12019": None, "12020": None}
    put(path, "participant_id\tage\nsub-12018\t55\nsub-12018\t56\n")
    with pytest.raises(ValueError, match="Duplicate"):
        runner.ages(path, ["12018"])


def copy_task_repo(path, task):
    # Exercise the real shell renderer/templates in an isolated synthetic project.
    workspace = Path(__file__).resolve().parents[2]
    repo = workspace / ("rf1-sra-ugr-handoff" if task == "ugr" else "rf1-sra-socdoors-handoff")
    if not repo.exists():
        pytest.skip("cross-repository renderer fixture not present")
    for name in ("code/L1stats.sh", "code/project_config.sh",
                 f"templates/L1_task-{task}_model-{'3' if task == 'ugr' else '1'}_type-act.fsf"):
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, target)


def fixture(tmp_path, monkeypatch):
    project, ugr, doors = [tmp_path / p for p in ("upstream", "ugr", "doors")]
    excluded = tmp_path / "excluded"
    excluded.mkdir()
    put(project / "bids/participants.tsv", "participant_id\tage\nsub-12018\t55\n")
    copy_task_repo(ugr, "ugr")
    copy_task_repo(doors, "socialdoors")
    rows = []
    for task, run in (("ugr", "1"), ("ugr", "2"), ("socialdoors", "1")):
        rows.append(row() | {"task": task, "run": run})
        paths = runner.audit.input_paths(project, "12018", "01", task, run)
        for key in ("bids_bold", "bold"):
            path = paths[key]
            path.parent.mkdir(parents=True, exist_ok=True)
            img = nib.Nifti1Image(np.zeros((2, 2, 2, 40), dtype=np.float32), np.eye(4))
            img.header.set_zooms((1, 1, 1, 2))
            nib.save(img, path)
        put(paths["events"], "onset\tduration\ttrial_type\n0\t1\tdecision\n3\t1\twin\n6\t1\tloss\n")
        stem = f"sub-12018_ses-01_task-{task}_run-{run}"
        source = paths["bold"].parent / f"{stem}_part-mag_desc-confounds_timeseries.tsv"
        frame().to_csv(source, index=False, sep="\t")
        root = ugr if task == "ugr" else doors
        folder = root / f"derivatives/fsl/EVfiles/sub-12018/ses-01/{task}"
        if task == "ugr":
            folder /= "model-3"
        for name in runner.UGR_EVS if task == "ugr" else ["decision", "win", "loss"]:
            put(folder / f"run-{run}_{name}.txt", "0 1 1\n")
    monkeypatch.setattr(runner.audit, "collect", lambda args: (rows, [], [project / "bids/participants.tsv"]))
    return argparse.Namespace(project_root=project, ugr_root=ugr, socdoors_root=doors,
        exclusions_root=excluded, dispositions=None, age_file=None, private_dir=project / "work/test",
        jobs=2, command="prepare")


def test_prepare_isolated_all_runs_and_changed_input_rejected(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    runner.prepare(args)
    plan = runner.load_plan(args.private_dir)
    assert len(plan["jobs"]) == 3
    assert all("fsl-no-tedana-age55" in j["output"] for j in plan["jobs"])
    assert not list(args.ugr_root.glob("derivatives/fsl/sub-*"))
    assert all(j["session"] == "01" for j in plan["jobs"])
    confounds = Path(plan["jobs"][0]["confounds"])
    confounds.write_text("0\n")
    with pytest.raises(ValueError, match="Frozen input changed"):
        runner.load_plan(args.private_dir)


def test_real_shell_render_isolation(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    runner.prepare(args)
    plan = runner.load_plan(args.private_dir)
    bins = tmp_path / "bin"
    put(bins / "fslnvols", "#!/bin/sh\necho 40\n")
    (bins / "fslnvols").chmod(0o755)
    for job in plan["jobs"]:
        cmd, env = runner.command(job, render=True)
        env["PATH"] = str(bins) + os.pathsep + env["PATH"]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        fsf = Path(job["rendered"])
        runner.validate_fsf(fsf, job)
        text = fsf.read_text()
        assert str(Path(job["root"]) / "derivatives/fsl/EVfiles") in text
        assert "TedanaPlusConfounds" not in text
        assert not Path(job["output"]).exists()
        # Canonical shell defaults remain unchanged when overrides are absent.
        default_env = {k: v for k, v in env.items() if k not in {"EV_FILES_ROOT", "FSL_DERIVATIVES_ROOT"}}
        default = subprocess.run(cmd[:-1] + ["--dry-run"], env=default_env, capture_output=True, text=True)
        assert default.returncode == 0, default.stderr
        assert str(Path(job["root"]) / "derivatives/fsl/sub-12018") in default.stdout


def test_design_estimability(tmp_path):
    x = np.column_stack([np.ones(40), np.arange(40), np.zeros(40)])
    mat, con = tmp_path / "design.mat", tmp_path / "design.con"
    def save(path, values):
        with path.open("w") as handle:
            handle.write("/Matrix\n")
            np.savetxt(handle, values)
    save(mat, x)
    save(con, np.array([[1, 0, 0], [0, 1, 0], [1, 1, 0], [1, -1, 0]]))
    assert runner.validate_design(mat, con, {"nvol": 40, "task": "socialdoors"})["design_rank"] == 2
    save(con, np.array([[1, 0, 1]] * 4))
    with pytest.raises(ValueError, match="unestimable"):
        runner.validate_design(mat, con, {"nvol": 40, "task": "socialdoors"})


def test_no_unowned_existing_output_is_skipped(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    runner.prepare(args)
    job = runner.load_plan(args.private_dir)["jobs"][0]
    output = Path(job["output"])
    output.mkdir(parents=True)
    marker = output / "cluster_mask_zstat1.nii.gz"
    marker.write_text("existing")
    result = runner.execute_one(job, args.private_dir, False, ())
    assert result["status"] == "FAILED"
    assert marker.read_text() == "existing"


def test_exclusion_change_invalidates_plan(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    runner.prepare(args)
    (args.exclusions_root / "Smith-SRA-12018").mkdir()
    with pytest.raises(ValueError, match="Source exclusions changed"):
        runner.load_plan(args.private_dir)


def test_complete_resume_and_output_tamper(tmp_path, monkeypatch):
    args = fixture(tmp_path, monkeypatch)
    runner.prepare(args)
    plan = runner.load_plan(args.private_dir)
    (args.private_dir / "logs").mkdir()
    real_run = subprocess.run
    bins = tmp_path / "bin"
    put(bins / "fslnvols", "#!/bin/sh\necho 40\n")
    (bins / "fslnvols").chmod(0o755)
    monkeypatch.setenv("PATH", str(bins) + os.pathsep + os.environ["PATH"])
    calls = []

    def fake_fsl(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0] == "feat_model":
            stem = Path(cmd[1])
            job = next(j for j in plan["jobs"] if Path(j["rendered"]).with_suffix("") == stem)
            ncon = 17 if job["task"] == "ugr" else 4
            x = np.random.default_rng(1).normal(size=(40, ncon))
            for path, values in ((stem.with_suffix(".mat"), x), (stem.with_suffix(".con"), np.eye(ncon))):
                with path.open("w") as handle:
                    handle.write(f"/NumContrasts {ncon}\n/Matrix\n")
                    np.savetxt(handle, values)
        elif "--render-only" in cmd:
            return real_run(cmd, **kwargs)
        else:
            task = "socialdoors" if "socialdoors" in cmd else "ugr"
            job = next(j for j in plan["jobs"] if j["task"] == task and j["run"] == cmd[3])
            fsf, output = Path(job["rendered"]), Path(job["output"])
            output.mkdir(parents=True)
            for suffix in (".fsf", ".mat", ".con"):
                shutil.copy2(fsf.with_suffix(suffix), output / ("design" + suffix))
            ncon = 17 if task == "ugr" else 4
            for name in ["mask.nii.gz"] + [f"stats/{kind}{i}.nii.gz" for i in range(1, ncon + 1)
                                           for kind in ("cope", "varcope", "zstat")]:
                put(output / name, "synthetic-output")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(runner.subprocess, "run", fake_fsl)
    job = plan["jobs"][0]
    assert runner.execute_one(job, args.private_dir, False, ())["status"] == "COMPLETED"
    total = len(calls)
    assert runner.execute_one(job, args.private_dir, False, ())["status"] == "SKIPPED_COMPLETE"
    assert len(calls) == total
    assert all("--overwrite" not in call for call in calls)
    put(Path(job["output"]) / "stats/cope1.nii.gz", "changed")
    assert runner.execute_one(job, args.private_dir, False, ())["status"] == "FAILED"
    assert len(calls) == total
