import argparse
import fcntl
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
import rebuild_11935_models as rebuild


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def image(path, n=218):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.ones((2, 2, 2, n), dtype=np.float32)
    img = nib.Nifti1Image(data, np.eye(4))
    img.header.set_zooms((1, 1, 1, 1.615))
    nib.save(img, path)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    project = tmp_path / "production"
    root = tmp_path / "socdoors"
    source = Path(__file__).resolve().parents[2] / "rf1-sra-socdoors-handoff"
    assert source.is_dir(), "Required sibling SocDoors renderer fixture unavailable"
    for path in rebuild.task_code(root):
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / path.relative_to(root), path)
    put(project / "bids/participants.tsv", "participant_id\tage\nsub-11935\t55\n")
    put(project / "code/task_availability_holds.tsv", "subject\tsession\ttask\trun\treason\n"
        "11201\t01\tugr\t1\tsettled\n")
    put(project / "qc/run_qc.tsv", "subject\tsession\ttask\trun\tqc_status\n"
        "11935\t01\tsocialdoors\t1\toutlier\n")
    for task, series in (("socialdoors", 25), ("doors", 29)):
        stem = f"sub-11935_ses-01_task-{task}_run-1"
        paths = rebuild.l1.audit.input_paths(project, "11935", "01", task, "1")
        raw, func = paths["events"].parent, paths["bold"].parent
        image(paths["bold"])
        put(paths["events"], "onset\tduration\ttrial_type\n0\t1\tdecision\n3\t1\twin\n6\t1\tloss\n")
        for echo in range(1, 5):
            for part, offset in (("mag", 0), ("phase", 1)):
                path = raw / f"{stem}_echo-{echo}_part-{part}_bold.nii.gz"
                image(path)
                put(path.with_name(path.name[:-7] + ".json"), json.dumps({"SeriesNumber": series + offset}))
            image(func / f"{stem}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz")
        image(raw / f"{stem}_echo-1_sbref.nii.gz", 1)
        put(raw / f"{stem}_echo-1_sbref.json", json.dumps({"SeriesNumber": series - 2}))
        for space in ("", "_space-MNI152NLin6Asym"):
            image(func / f"{stem}_part-mag{space}_desc-brain_mask.nii.gz", 1)
        rng = np.random.default_rng(8)
        columns = rebuild.l1.DESIRED_FMRIPREP_COLUMNS[:-1] + ["framewise_displacement"]
        data = pd.DataFrame(rng.normal(size=(218, len(columns))), columns=columns)
        data = data.drop(columns="a_comp_cor_05")
        data["cosine00"] = np.cos(np.arange(218))
        data["non_steady_state_outlier00"] = np.eye(218, 1)[:, 0]
        data["global_signal"] = 123
        data.loc[0, "framewise_displacement"] = np.nan
        source_conf = func / f"{stem}_part-mag_desc-confounds_timeseries.tsv"
        data.to_csv(source_conf, sep="\t", index=False)
        tedana = project / "derivatives/tedana/sub-11935/ses-01"
        mixing = tedana / f"{stem}_desc-ICA_mixing.tsv"
        metrics = tedana / f"{stem}_desc-tedana_metrics.tsv"
        tedana.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"ICA_00": np.sin(np.arange(218))}).to_csv(mixing, sep="\t", index=False)
        pd.DataFrame({"Component": ["ICA_00"], "classification": ["rejected"]}).to_csv(metrics, sep="\t", index=False)
        rebuild.l1.atomic_write_tsv(rebuild.build_confounds(source_conf, mixing, metrics), paths["confounds"])
    exclusions = tmp_path / "exclusions"
    exclusions.mkdir()
    args = argparse.Namespace(project_root=project, socdoors_root=root,
        private_dir=project / "work/models", promotion_receipt=project / "work/promotion/receipt.json",
        exclusions_root=exclusions, timeout=1)
    refresh_receipt(args)
    bins = tmp_path / "bin"
    for name in ("feat", "feat_model", "fslnvols"):
        put(bins / name, "#!/bin/sh\necho 218\n")
        (bins / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bins) + os.pathsep + os.environ["PATH"])
    # Every inherited path override must be replaced explicitly by the driver.
    for name in ("BIDS_ROOT", "FMRIPREP_ROOT", "EV_FILES_ROOT", "FSL_DERIVATIVES_ROOT", "CONFOUNDS_ROOT"):
        monkeypatch.setenv(name, "/unrelated/poison")
    return args


def refresh_receipt(args):
    files = sorted({p for task in rebuild.TASKS for p in rebuild.canonical_inputs(args.project_root, task)[-1]})
    installs = [dict(relpath=str(p.relative_to(args.project_root)),
                     sha256=rebuild.signature(p)["sha256"]) for p in files]
    plan = dict(schema=1, project=str(args.project_root), socdoors_root=str(args.socdoors_root),
                installs=installs, staged_hashes={i["relpath"]: i["sha256"] for i in installs},
                changed_keys=sorted(f"sub-11935_ses-01_task-{task}_run-1" for task in rebuild.TASKS),
                moves=[], source_original_inputs={}, cohort_manifest=None, scans_merge=None,
                remove_directories=[], requires_rebuild=[], stale_l3_report={})
    receipt = dict(state="installed", plan=plan, installs=installs, staged_hashes=plan["staged_hashes"],
                   changed_keys=plan["changed_keys"])
    put(args.promotion_receipt, json.dumps(receipt))


def matrix(path, values):
    put(path, f"/NumContrasts {len(values)}\n/Matrix\n" +
        "\n".join(" ".join(map(str, row)) for row in values) + "\n")


def full_mock_fsl(monkeypatch, plan):
    original = subprocess.run
    calls = []

    def fake(cmd, **kwargs):
        calls.append((cmd, kwargs))
        assert "--overwrite" not in cmd
        if cmd[0] == "feat_model":
            stem = Path(cmd[1])
            matrix(stem.with_suffix(".mat"), np.random.default_rng(5).normal(size=(218, 4)))
            matrix(stem.with_suffix(".con"), np.eye(4))
        elif cmd[0] == "feat":
            job = next(j for j in plan["l2_jobs"] if j["rendered"] == cmd[1])
            for path in rebuild.finish.l2_products(job):
                put(path, "synthetic")
            output = Path(job["output"])
            shutil.copy2(job["rendered"], output / "design.fsf")
            for folder in [output] + [output / f"cope{i}.feat" for i in range(1, 5)]:
                matrix(folder / "design.mat", np.ones((2, 1)))
                matrix(folder / "design.con", np.ones((1, 1)))
        elif "--render-only" in cmd:
            return original(cmd, **kwargs)
        else:
            job = next(j for j in plan["jobs"] if j["confounds"] == cmd[cmd.index("--confounds") + 1])
            output = Path(job["output"])
            output.mkdir(parents=True)
            shutil.copy2(job["rendered"], output / "design.fsf")
            shutil.copy2(Path(job["rendered"]).with_suffix(".mat"), output / "design.mat")
            shutil.copy2(Path(job["rendered"]).with_suffix(".con"), output / "design.con")
            for path in ["mask.nii.gz", "cluster_mask_zstat1.nii.gz", "stats/dof", "reg/example_func2standard.mat"] + [
                f"stats/{kind}{i}.nii.gz" for kind in ("cope", "varcope", "zstat") for i in range(1, 5)]:
                put(output / path, "synthetic")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(rebuild.subprocess, "run", fake)
    return calls


def test_prepare_exact_scope_and_no_qc_selection(setup, monkeypatch):
    args = setup
    monkeypatch.setattr(rebuild.l1.audit, "collect", lambda *a: pytest.fail("No cohort/QC selection"))
    historical = args.project_root / "work/coverage95-handoff-20261021-204525/keep.txt"
    unrelated = args.socdoors_root / "derivatives/fsl/sub-11935/ses-02/keep.txt"
    other = args.socdoors_root / "derivatives/fsl/sub-12018/ses-01/keep.txt"
    for p in (historical, unrelated, other):
        put(p, "unchanged")
    rebuild.prepare(args)
    plan = rebuild.load_plan(args)
    for task in rebuild.TASKS:
        ev = args.socdoors_root / f"derivatives/fsl/EVfiles/sub-11935/ses-01/{task}/run-1_win.txt"
        assert np.allclose(np.loadtxt(ev), [3, 1, 1])
    assert len(plan["jobs"]) == 4 and len(plan["l2_jobs"]) == 2
    assert {(j["subject"], j["session"], j["run"]) for j in plan["jobs"]} == {("11935", "01", "1")}
    assert {j["task"] for j in plan["jobs"]} == {"socialdoors", "doors"}
    for j in plan["jobs"]:
        assert j["nvol"] == 218
        assert not Path(j["output"]).exists()
        if j["variant"] == rebuild.finish.VARIANT:
            assert "a_comp_cor_05" not in j["columns"]
            assert "global_signal" not in j["columns"]
            rebuild.l1.verify_existing(rebuild.finish.base_confounds(Path(j["source_confounds"])), Path(j["confounds"]))
        else:
            assert j["confounds"] == str(rebuild.l1.audit.input_paths(args.project_root, "11935", "01", j["task"], "1")["confounds"])
    assert plan["paper_eligibility"] == "unchanged_not_reinstated" and plan["l3_requires_rerun"]
    assert all(p.read_text() == "unchanged" for p in (historical, unrelated, other))
    with pytest.raises(ValueError, match="immutable"):
        rebuild.prepare(args)


@pytest.mark.parametrize("age,expected", [("55", 4), ("54.99", 2), ("n/a", None)])
def test_age_only_gates_base_variant(setup, age, expected):
    args = setup
    put(args.project_root / "bids/participants.tsv", f"participant_id\tage\nsub-11935\t{age}\n")
    if expected is None:
        with pytest.raises(ValueError, match="age is unavailable"):
            rebuild.prepare(args)
    else:
        rebuild.prepare(args)
        plan = rebuild.load_plan(args)
        assert len(plan["jobs"]) == expected
        if expected == 2:
            assert {j["variant"] for j in plan["jobs"]} == {"fsl"}


@pytest.mark.parametrize("gate", ["excluded", "held", "disposition"])
def test_no_automatic_exclusion_or_hold_override(setup, gate):
    args = setup
    if gate == "excluded":
        (args.exclusions_root / "Smith-SRA-11935").mkdir()
    elif gate == "held":
        put(args.project_root / "code/task_availability_holds.tsv", "subject\tsession\ttask\trun\treason\n"
            "11935\t01\tdoors\t1\tsettled\n")
    else:
        put(args.project_root / "qc/run_disposition.tsv", "subject\tsession\ttask\trun\tdecision\n"
            "11935\t01\tsocialdoors\t1\texclude\n")
    with pytest.raises(ValueError, match="excluded|hold|disposition"):
        rebuild.prepare(args)
    assert not args.private_dir.exists()


@pytest.mark.parametrize("change", ["uninstalled", "missing_hash", "source", "series", "length", "production"])
def test_requires_installed_verified_canonical_sources(setup, change):
    args = setup
    paths = rebuild.l1.audit.input_paths(args.project_root, "11935", "01", "socialdoors", "1")
    if change in {"uninstalled", "missing_hash"}:
        receipt = json.loads(args.promotion_receipt.read_text())
        if change == "uninstalled":
            receipt["state"] = "prepared"
        else:
            receipt["plan"]["installs"].pop()
            receipt["installs"] = receipt["plan"]["installs"]
        put(args.promotion_receipt, json.dumps(receipt))
    elif change == "source":
        put(paths["events"], "changed")
    elif change == "series":
        p = paths["bids_bold"].with_name(paths["bids_bold"].name[:-7] + ".json")
        put(p, '{"SeriesNumber": 29}')
        refresh_receipt(args)
    elif change == "length":
        image(paths["bold"], 217)
        refresh_receipt(args)
    else:
        put(paths["confounds"], "0\n" * 218)
        refresh_receipt(args)
    with pytest.raises(ValueError):
        rebuild.prepare(args)


@pytest.mark.parametrize("kind", ["feat", "design", "ev", "symlink"])
def test_stale_outputs_are_never_overwritten(setup, kind):
    args = setup
    output, rendered = rebuild.model_paths(args.socdoors_root, "fsl", "socialdoors")
    if kind == "feat":
        path = output / "keep.txt"
    elif kind == "design":
        path = rendered
    else:
        path = args.socdoors_root / "derivatives/fsl/EVfiles/sub-11935/ses-01/socialdoors/run-1_win.txt"
    if kind == "symlink":
        output.parent.mkdir(parents=True)
        output.symlink_to(args.project_root, target_is_directory=True)
    else:
        put(path, "keep")
    with pytest.raises(ValueError, match="Unowned|symlink"):
        rebuild.prepare(args)
    if kind != "symlink":
        assert path.read_text() == "keep"


def test_variant_env_and_real_l1_l2_renderers(setup):
    args = setup
    rebuild.prepare(args)
    plan = rebuild.load_plan(args)
    for job in plan["jobs"]:
        cmd, env = rebuild.command(job, True)
        assert cmd[2:6] == ["11935", "1", "0", job["task"]]
        assert env["FMRIPREP_ROOT"] == str(args.project_root / "derivatives/fmriprep")
        assert env["BIDS_ROOT"] == str(args.project_root / "bids")
        assert env["EV_FILES_ROOT"] == str(args.socdoors_root / "derivatives/fsl/EVfiles")
        assert env["FSL_DERIVATIVES_ROOT"] == str(args.socdoors_root / "derivatives" / job["variant"])
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        rebuild.l1.validate_fsf(Path(job["rendered"]), job)
        assert f"/{job['task']}/run-1_win.txt" in Path(job["rendered"]).read_text()
    assert rebuild.finish.VARIANT == "fsl-no-tedana-age55"


@pytest.mark.parametrize("change", ["receipt", "confounds", "code", "exclusion", "image_same_stat"])
def test_frozen_lineage_detects_changes(setup, change):
    args = setup
    rebuild.prepare(args)
    plan = rebuild.load_plan(args)
    if change == "receipt":
        path = args.promotion_receipt
    elif change == "confounds":
        path = Path(plan["jobs"][0]["confounds"])
    elif change == "code":
        path = args.socdoors_root / "code/L2stats.sh"
    elif change == "exclusion":
        (args.exclusions_root / "Smith-SRA-11935").mkdir()
        path = None
    else:
        path = Path(plan["jobs"][0]["bold"])
        stat = path.stat()
        values = bytearray(path.read_bytes())
        values[-1] ^= 1
        path.write_bytes(values)
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    if path and change != "image_same_stat":
        path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="changed|excluded"):
        rebuild.load_plan(args)


def test_full_run_check_resume_and_output_tamper(setup, monkeypatch):
    args = setup
    rebuild.prepare(args)
    plan = rebuild.load_plan(args)
    monkeypatch.setattr(rebuild.promote, "check", lambda *a: pytest.fail("Promoter absence check only before EV creation"))
    calls = full_mock_fsl(monkeypatch, plan)
    rebuild.run(args)
    before = len(calls)
    rebuild.check(args)
    rebuild.run(args)
    assert len(calls) == before
    statuses = json.loads((args.private_dir / "run-status.json").read_text())
    assert len(statuses) == 6 and all(r["status"] == "SKIPPED_COMPLETE" for r in statuses)
    ready = rebuild.l1.read_tsv(args.private_dir / "subject_ready.tsv")[1]
    assert len(ready) == 6 and {r["level"] for r in ready} == {"L1", "L2"}
    assert all(r["paper_eligibility"] == "unchanged_not_reinstated" for r in ready)
    assert json.loads((args.private_dir / "completion.json").read_text())["l3_requires_rerun"]
    assert all(kwargs["pass_fds"] for _, kwargs in calls)
    job = plan["jobs"][0]
    put(Path(job["output"]) / "reg/example_func2standard.mat", "changed")
    with pytest.raises(ValueError, match="products changed"):
        rebuild.check(args)
    assert json.loads((args.private_dir / "completion.json").read_text())["validated"] is False


def test_unowned_run_output_fails_before_feat(setup, monkeypatch):
    args = setup
    rebuild.prepare(args)
    job = rebuild.load_plan(args)["jobs"][0]
    put(Path(job["output"]) / "keep.txt", "keep")
    monkeypatch.setattr(rebuild.subprocess, "run", lambda *a, **kw: pytest.fail("Do not run FEAT"))
    with pytest.raises(ValueError, match="Unowned/stale L1"):
        rebuild.run(args)
    assert (Path(job["output"]) / "keep.txt").read_text() == "keep"
    assert not (args.private_dir / "subject_ready.tsv").exists()


def test_failed_l1_prevents_l2(setup, monkeypatch):
    args = setup
    rebuild.prepare(args)
    def fail(*a):
        raise ValueError("L1 failed")
    monkeypatch.setattr(rebuild, "execute_l1", fail)
    monkeypatch.setattr(rebuild, "execute_l2", lambda *a: pytest.fail("No L2 after failed L1"))
    with pytest.raises(ValueError, match="L1 failed"):
        rebuild.run(args)
    assert not (args.private_dir / "subject_ready.tsv").exists()


@pytest.mark.parametrize("variant", rebuild.VARIANTS)
def test_shared_variant_lock_prevents_prepare(setup, variant):
    args = setup
    lock = args.socdoors_root / "derivatives" / variant / ".runner.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="already locked"):
            rebuild.prepare(args)
    assert not args.private_dir.exists()


def test_missing_dependencies_fail_clearly(setup, monkeypatch):
    args = setup
    real = shutil.which
    monkeypatch.setattr(rebuild.shutil, "which", lambda name: None if name == "feat_model" else real(name))
    with pytest.raises(ValueError, match="Required executable unavailable: feat_model"):
        rebuild.prepare(args)
    assert not args.private_dir.exists()


def test_real_promotion_receipt_merged_scans_hash(setup):
    args = setup
    receipt = json.loads(args.promotion_receipt.read_text())
    plan = receipt["plan"]
    content = "filename\tacq_time\nfunc/repaired.nii.gz\tn/a\n"
    put(args.project_root / rebuild.promote.SCANS, content)
    # The staged scan table is not the installed merged table.
    plan["staged_hashes"][rebuild.promote.SCANS] = "0" * 64
    plan["scans_merge"] = dict(content=content, staged_sha256="0" * 64)
    plan["installs"].append(dict(relpath=rebuild.promote.SCANS,
                                sha256=rebuild.signature(args.project_root / rebuild.promote.SCANS)["sha256"]))
    receipt["staged_hashes"] = plan["staged_hashes"]
    receipt["installs"] = plan["installs"]
    put(args.promotion_receipt, json.dumps(receipt))
    rebuild.verify_promotion(args.project_root, args.promotion_receipt, args.socdoors_root)
    # Exercise the real promoter API against its actual receipt-shaped fixture.
    assert rebuild.promote.check(args.promotion_receipt)["verified"]
    put(args.project_root / rebuild.promote.SCANS, content + "changed\tn/a\n")
    with pytest.raises(ValueError, match="canonical input changed"):
        rebuild.verify_promotion(args.project_root, args.promotion_receipt, args.socdoors_root)


def test_resume_has_no_retired_cohort_archive_dependency(setup):
    args = setup
    receipt = json.loads(args.promotion_receipt.read_text())
    receipt["plan"]["cohort_manifest"] = dict(archive_path="/not/available/cohort/manifest.json", sha256="0" * 64)
    put(args.promotion_receipt, json.dumps(receipt))
    rebuild.verify_promotion(args.project_root, args.promotion_receipt, args.socdoors_root)


def test_extra_installed_canonical_file_is_also_hashed(setup):
    args = setup
    receipt = json.loads(args.promotion_receipt.read_text())
    rel = "derivatives/mriqc/sub-11935_ses-01_task-doors_run-1_echo-2_part-mag_bold.html"
    put(args.project_root / rel, "promoted report")
    digest = rebuild.signature(args.project_root / rel)["sha256"]
    receipt["plan"]["staged_hashes"][rel] = digest
    receipt["plan"]["installs"].append(dict(relpath=rel, sha256=digest))
    receipt["installs"] = receipt["plan"]["installs"]
    receipt["staged_hashes"] = receipt["plan"]["staged_hashes"]
    put(args.promotion_receipt, json.dumps(receipt))
    rebuild.verify_promotion(args.project_root, args.promotion_receipt, args.socdoors_root)
    put(args.project_root / rel, "changed report")
    with pytest.raises(ValueError, match="canonical input changed"):
        rebuild.verify_promotion(args.project_root, args.promotion_receipt, args.socdoors_root)
