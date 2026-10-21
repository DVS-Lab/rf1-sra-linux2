import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from test_no_tedana_l1 import fixture, frame, put, copy_task_repo
import finish_no_tedana as finish

l1 = finish.l1


def matrix(path, values):
    put(path, f"/NumContrasts {len(values)}\n/Matrix\n" +
        "\n".join(" ".join(map(str, row)) for row in values) + "\n")


def complete_l1(job):
    output = Path(job["output"])
    n = 17 if job["task"] == "ugr" else 4
    put(output / "design.fsf", f'set feat_files(1) "{job["bold"]}"\n'
        f'set confoundev_files(1) "{job["confounds"]}"\n'
        f'set fmri(outputdir) "{str(output)[:-5]}"\nset fmri(temphp_yn) 0\n')
    matrix(output / "design.mat", np.random.default_rng(42).normal(size=(40, n)))
    matrix(output / "design.con", np.eye(n))
    for path in ["mask.nii.gz", "cluster_mask_zstat1.nii.gz", "stats/dof"] + [
        f"stats/{kind}{i}.nii.gz" for i in range(1, n + 1) for kind in ("cope", "varcope", "zstat")]:
        put(output / path, "synthetic-output")
    products = [p for p in output.rglob("*") if p.is_file()]
    l1.write_json(l1.completion(job), dict(job=job, outputs=[l1.signature(p) for p in products]))
    l1.verified_complete(job)


def setup(tmp_path, monkeypatch, fewer=False):
    args = fixture(tmp_path, monkeypatch)
    if fewer:
        p = args.project_root / "derivatives/fmriprep/sub-12018/ses-01/func/sub-12018_ses-01_task-ugr_run-1_part-mag_desc-confounds_timeseries.tsv"
        frame().drop(columns="a_comp_cor_05").to_csv(p, sep="\t", index=False)
    l1.prepare(args)
    parent = l1.load_plan(args.private_dir)
    for job in parent["jobs"]:
        complete_l1(job)
    copy_task_repo(args.socdoors_root, "doors")
    for root, name, model in ((args.ugr_root, "ugr", 3), (args.socdoors_root, "socialdoors", 1)):
        source = Path(__file__).resolve().parents[2] / ("rf1-sra-ugr-handoff" if name == "ugr" else "rf1-sra-socdoors-handoff")
        for rel in ("code/L2stats.sh", f"templates/L2_task-{name}_model-{model}_type-act.fsf"):
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / rel, dest)
    paths = finish.audit.input_paths(args.project_root, "12018", "01", "doors", "1")
    oldpaths = finish.audit.input_paths(args.project_root, "12018", "01", "socialdoors", "1")
    for name in ("bids_bold", "bold", "events"):
        shutil.copy2(oldpaths[name], paths[name])
    source = paths["bold"].parent / "sub-12018_ses-01_task-doors_run-1_part-mag_desc-confounds_timeseries.tsv"
    frame().to_csv(source, sep="\t", index=False)
    for name in ("decision", "win", "loss"):
        put(args.socdoors_root / f"derivatives/fsl/EVfiles/sub-12018/ses-01/doors/run-1_{name}.txt", "0 1 1\n")
    put(args.project_root / "qc/run_qc.tsv", "subject\tsession\ttask\trun\tqc_status\n12018\t01\tdoors\t1\toutlier\n")
    args.parent_dir, args.private_dir = args.private_dir, args.project_root / "work/followup"
    args.timeout = 1
    return args, parent


def test_fewer_compcor_exact_production_base(tmp_path):
    p = tmp_path / "confounds.tsv"
    data = frame().drop(columns="a_comp_cor_05")
    data.to_csv(p, sep="\t", index=False)
    base = finish.base_confounds(p)
    expected = data[[c for c in l1.DESIRED_FMRIPREP_COLUMNS if c in data] +
                    ["cosine00", "non_steady_state_outlier00"]].fillna(0)
    pd.testing.assert_frame_equal(base, expected)
    assert not any("ICA" in c for c in base)
    data.drop(columns="trans_x").to_csv(p, sep="\t", index=False)
    with pytest.raises(ValueError, match="Missing motion"):
        finish.base_confounds(p)


def test_prepare_recovers_and_reuses_without_modifying_parent(tmp_path, monkeypatch):
    args, parent = setup(tmp_path, monkeypatch, fewer=True)
    before = (args.parent_dir / "plan.json").read_bytes()
    finish.prepare(args)
    plan = finish.load_plan(args.private_dir)
    assert len(plan["jobs"]) == 4 and len(plan["reused_keys"]) == 2
    assert len(plan["l2_jobs"]) == 2
    assert (args.parent_dir / "plan.json").read_bytes() == before
    for job in parent["jobs"]:
        assert job in plan["jobs"]
        l1.verified_complete(job)
    assert next(j for j in plan["jobs"] if j["task"] == "doors")["columns"] == list(finish.base_confounds(
        Path(next(j for j in plan["jobs"] if j["task"] == "doors")["source_confounds"])))


def test_doors_does_not_inherit_social_qc_or_disposition(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    rows, _ = finish.collect_rows(args)
    door = next(r for r in rows if r["task"] == "doors")
    assert door["recorded_qc_status"] == "outlier"
    assert l1.classify(door, 60)[0] == "candidate"
    args.dispositions = args.project_root / "decisions.tsv"
    put(args.dispositions, "subject\tsession\ttask\trun\tdecision\treason\tevidence\n"
        "12018\t01\tdoors\t1\texclude\tsettled\tnote\n")
    rows, _ = finish.collect_rows(args)
    assert l1.classify(next(r for r in rows if r["task"] == "doors"), 60)[0] == "held"


def test_l2_pairing_keeps_single_run_alternatives(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    plan = finish.load_plan(args.private_dir)
    rows = finish.handoff_rows(plan)
    assert {r["input_runs"] for r in rows if r["analysis"] == "ugr"} == {"1", "2", "1+2"}
    assert "socialdoors_doors_mean" in {r["analysis"] for r in rows}
    singles = [j for j in plan["jobs"] if j["key"] not in (plan["jobs"][0]["key"],)
               and j["task"] != "doors"]
    assert finish.l2_jobs(singles) == []


def test_real_doors_render(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    job = next(j for j in finish.load_plan(args.private_dir)["jobs"] if j["task"] == "doors")
    bins = tmp_path / "bin"
    put(bins / "fslnvols", "#!/bin/sh\necho 40\n")
    (bins / "fslnvols").chmod(0o755)
    cmd, env = finish.command(job, True)
    env["PATH"] = str(bins) + os.pathsep + env["PATH"]
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    l1.validate_fsf(Path(job["rendered"]), job)
    assert "/doors/run-1_win.txt" in Path(job["rendered"]).read_text()
    assert not Path(job["output"]).exists()


def fake_l2_fsl(monkeypatch, job):
    real_run = subprocess.run
    def fake(cmd, **kwargs):
        if cmd[0] != "feat":
            return real_run(cmd, **kwargs)
        output = Path(job["output"])
        for path in finish.l2_products(job):
            put(path, "synthetic")
        shutil.copy2(job["rendered"], output / "design.fsf")
        for folder in [output] + [output / f"cope{i}.feat" for i in range(1, job["ncopes"] + 1)]:
            matrix(folder / "design.mat", np.ones((2, 1)))
            matrix(folder / "design.con", np.ones((1, 1)))
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(finish.subprocess, "run", fake)


@pytest.mark.parametrize("task", ["ugr", "socialdoors"])
def test_canonical_l2_render_complete_resume_tamper(tmp_path, monkeypatch, task):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    plan = finish.load_plan(args.private_dir)
    jobs = {j["key"]: j for j in plan["jobs"]}
    for j in jobs.values():
        if not Path(j["output"]).exists():
            complete_l1(j)
    job = next(j for j in plan["l2_jobs"] if j["task"] == task)
    (args.private_dir / "logs").mkdir()
    fake_l2_fsl(monkeypatch, job)
    assert finish.execute_l2(job, jobs, args.private_dir, (), 1)["status"] == "COMPLETED"
    finish.verified_l2(job, jobs)
    assert finish.execute_l2(job, jobs, args.private_dir, (), 1)["status"] == "SKIPPED_COMPLETE"
    put(Path(job["output"]) / "cope1.feat/stats/varcope1.nii.gz", "changed")
    assert finish.execute_l2(job, jobs, args.private_dir, (), 1)["status"] == "FAILED"


def test_l2_rejects_original_paths_and_difference_model(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    plan = finish.load_plan(args.private_dir)
    j = plan["l2_jobs"][0]
    text = f'set fmri(outputdir) "{str(j["output"])[:-6]}"\n' + "\n".join(
        f'set feat_files({i}) "{p}"' for i, p in enumerate(j["inputs"], 1))
    text += f'\nset fmri(mixed_yn) 3\nset fmri(npts) 2\nset fmri(ncopeinputs) {j["ncopes"]}\n'
    text += 'set fmri(evg1.1) 1\nset fmri(evg2.1) 1\nset fmri(con_real1.1) 1\nset fmri(ncon_real) 1\n'
    p = tmp_path / "rendered.fsf"
    put(p, text)
    finish.validate_l2_fsf(p, j)
    for bad in [text.replace("fsl-no-tedana-age55", "fsl"), text.replace("evg2.1) 1", "evg2.1) -1")]:
        put(p, bad)
        with pytest.raises(ValueError):
            finish.validate_l2_fsf(p, j)


def test_partial_output_is_not_overwritten(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    plan = finish.load_plan(args.private_dir)
    j = next(j for j in plan["jobs"] if j["task"] == "doors")
    p = Path(j["output"]) / "keep.txt"
    put(p, "existing")
    assert finish.execute_l1(j, args.private_dir, ())["status"] == "FAILED"
    assert p.read_text() == "existing"


def test_plan_freezes_parent_and_canonical_l2_code(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    finish.load_plan(args.private_dir)
    with (args.ugr_root / "code/L2stats.sh").open("a") as handle:
        handle.write("\n# changed\n")
    with pytest.raises(ValueError, match="L2 inputs or canonical code"):
        finish.load_plan(args.private_dir)


def test_full_followup_run_and_handoff_with_mock_fsl(tmp_path, monkeypatch):
    args, parent = setup(tmp_path, monkeypatch, fewer=True)
    finish.prepare(args)
    plan = finish.load_plan(args.private_dir)
    parent_markers = {j["key"]: l1.completion(j).read_bytes() for j in parent["jobs"]}
    bins = tmp_path / "bin"
    put(bins / "fslnvols", "#!/bin/sh\necho 40\n")
    (bins / "fslnvols").chmod(0o755)
    monkeypatch.setenv("PATH", str(bins) + os.pathsep + os.environ["PATH"])
    real_run = subprocess.run

    def fake(cmd, **kwargs):
        if cmd[0] == "feat_model":
            stem = Path(cmd[1])
            job = next(j for j in plan["jobs"] if Path(j["rendered"]).with_suffix("") == stem)
            count = 17 if job["task"] == "ugr" else 4
            matrix(stem.with_suffix(".mat"), np.random.default_rng(1).normal(size=(40, count)))
            matrix(stem.with_suffix(".con"), np.eye(count))
        elif cmd[0] == "feat":
            j = next(j for j in plan["l2_jobs"] if j["rendered"] == cmd[1])
            for path in finish.l2_products(j):
                put(path, "synthetic")
            output = Path(j["output"])
            shutil.copy2(j["rendered"], output / "design.fsf")
            for folder in [output] + [output / f"cope{i}.feat" for i in range(1, j["ncopes"] + 1)]:
                matrix(folder / "design.mat", np.ones((2, 1)))
                matrix(folder / "design.con", np.ones((1, 1)))
        elif "--render-only" in cmd:
            return real_run(cmd, **kwargs)
        else:
            confounds = cmd[cmd.index("--confounds") + 1]
            job = next(j for j in plan["jobs"] if j["confounds"] == confounds)
            assert job["key"] not in plan["reused_keys"]
            complete_l1(job)
        assert "--overwrite" not in cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(finish.subprocess, "run", fake)
    finish.run(args)
    assert (args.private_dir / "handoff_candidates.tsv").is_file()
    rows = l1.read_tsv(args.private_dir / "handoff_candidates.tsv")[1]
    assert len(rows) == 2*17 + 2*4 + 17 + 4
    assert all(Path(r["dof"]).exists() for r in rows)
    for j in parent["jobs"]:
        assert l1.completion(j).read_bytes() == parent_markers[j["key"]]
    finish.run(args)
    assert all(r["status"] == "SKIPPED_COMPLETE" for r in json.loads((args.private_dir / "l1-status.json").read_text()))


def test_failed_l1_prevents_l2_and_handoff(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    monkeypatch.setattr(finish, "execute_l1", lambda *a: dict(key="synthetic", status="FAILED"))
    monkeypatch.setattr(finish, "execute_l2", lambda *a: pytest.fail("L2 must not run"))
    with pytest.raises(ValueError, match="l1 failed"):
        finish.run(args)
    assert not (args.private_dir / "handoff_candidates.tsv").exists()


def test_missing_l2_dof_fails_validation(tmp_path, monkeypatch):
    args, _ = setup(tmp_path, monkeypatch)
    finish.prepare(args)
    plan = finish.load_plan(args.private_dir)
    jobs = {j["key"]: j for j in plan["jobs"]}
    j = next(j for j in plan["l2_jobs"] if j["task"] == "ugr")
    (args.private_dir / "logs").mkdir()
    fake_l2_fsl(monkeypatch, j)
    assert finish.execute_l2(j, jobs, args.private_dir, (), 1)["status"] == "COMPLETED"
    (Path(j["output"]) / "cope1.feat/stats/tdof_t1.nii.gz").unlink()
    with pytest.raises(ValueError):
        finish.verified_l2(j, jobs)
