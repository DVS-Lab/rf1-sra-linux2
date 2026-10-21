import os
from pathlib import Path
import shutil
import subprocess
import sys

import nibabel as nib
import numpy as np
import pandas as pd
import pytest

CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))
import genTedanaConfounds as gen
from pipeline_utils import tedana_expected_outputs


def put(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def image(path, n=4):
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(np.zeros((2, 2, 2, n)), np.eye(4)), path)


def tree(tmp_path):
    code = tmp_path / "code"
    code.mkdir()
    for name in ("run_tedana.sh", "tedana.sh", "check_tedana.sh", "pipeline_common.sh",
                 "pipeline_utils.py", "print_subjects.py", "check_pipeline_state.py",
                 "genTedanaConfounds.py", "resume_wave2_tedana.sh"):
        shutil.copy2(CODE / name, code / name)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").symlink_to(sys.executable)
    fake = put(bin_dir / "tedana", '#!/bin/bash\nif [[ "$1" == --version ]]; then echo test; exit 0; fi\necho unexpected-compute >&2\nexit 99\n')
    fake.chmod(0o755)
    (tmp_path / "excluded").mkdir()
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", TEDANA_CMD=str(fake),
               SOURCEDATA_EXCLUSIONS_ROOT=str(tmp_path / "excluded"), AUDIT_BIN=str(bin_dir))
    put(tmp_path / "subjects.txt", "10001\n")
    return env


def run(root, env, script, *args):
    return subprocess.run(["bash", str(root / "code" / script), *map(str, args)],
                          env=env, capture_output=True, text=True, timeout=90)


def inputs(root, sub="10001", ses="02", task="ugr", run="1", complete=True):
    stem = f"sub-{sub}_ses-{ses}_task-{task}_run-{run}"
    bids = root / f"bids/sub-{sub}/ses-{ses}/func"
    func = root / f"derivatives/fmriprep/sub-{sub}/ses-{ses}/func"
    for echo in range(1, 5):
        image(bids / f"{stem}_echo-{echo}_part-mag_bold.nii.gz")
        image(func / f"{stem}_echo-{echo}_part-mag_desc-preproc_bold.nii.gz")
        put(bids / f"{stem}_echo-{echo}_part-mag_bold.json", '{"EchoTime": 0.015}')
    put(bids / f"{stem}_events.tsv", "onset\tduration\n0\t1\n")
    put(func / f"{stem}_part-mag_desc-confounds_timeseries.tsv", "trans_x\n0\n1\n2\n3\n")
    denoised, mixing, metrics = tedana_expected_outputs(root / "derivatives", sub, ses, task, run)
    if complete:
        image(denoised)
        put(mixing, "ICA_0\tICA_1\n0\t1\n1\t2\n2\t3\n3\t4\n")
        put(metrics, "Component\tclassification\nICA_0\taccepted\nICA_1\trejected\n")
    return stem


def gen_main(root, monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["gen", "--fmriprep-dir", str(root / "derivatives/fmriprep"),
                                    "--tedana-dir", str(root / "derivatives/tedana"),
                                    "--output-dir", str(root / "confounds"), *args])
    return gen.main()


def test_worker_and_batch_session_selection_skip_complete(tmp_path):
    env = tree(tmp_path)
    inputs(tmp_path, ses="01", complete=False)
    inputs(tmp_path)
    files = tedana_expected_outputs(tmp_path / "derivatives", "10001", "02", "ugr", "1")
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in files]
    proc = run(tmp_path, env, "run_tedana.sh", "--sublist", tmp_path / "subjects.txt", "--session", "02", "--jobs", "1")
    assert proc.returncode == 0, proc.stderr
    assert "EXISTS (skipping)" in proc.stdout
    assert "ses-01" not in proc.stdout
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in files]
    assert not (tmp_path / "derivatives/tedana/sub-10001/ses-01").exists()


def test_partial_outputs_preserved_and_dry_run_new_run(tmp_path):
    env = tree(tmp_path)
    stem = inputs(tmp_path, complete=False)
    proc = run(tmp_path, env, "tedana.sh", "--session", "02", "--dry-run", "10001")
    assert proc.returncode == 0
    assert "TEDANA command:" in proc.stdout
    assert "--overwrite" not in proc.stdout
    partial = put(tmp_path / f"derivatives/tedana/sub-10001/ses-02/{stem}_desc-ICA_mixing.tsv", "partial")
    proc = run(tmp_path, env, "tedana.sh", "--session", "02", "10001")
    assert proc.returncode == 1
    assert "INCOMPLETE existing" in proc.stderr
    assert partial.read_text() == "partial"


def test_checker_requires_expected_count_and_ignores_other_session(tmp_path):
    env = tree(tmp_path)
    inputs(tmp_path, ses="01", complete=False)
    inputs(tmp_path)
    args = ("--sublist", tmp_path / "subjects.txt", "--session", "02")
    assert run(tmp_path, env, "check_tedana.sh", *args, "--expected-runs", "1").returncode == 0
    assert run(tmp_path, env, "check_tedana.sh", *args, "--expected-runs", "20").returncode == 1
    assert run(tmp_path, env, "check_tedana.sh", "--sublist", tmp_path / "subjects.txt").returncode == 1


@pytest.mark.parametrize("script", ["tedana.sh", "run_tedana.sh", "check_tedana.sh"])
def test_invalid_session_rejected(tmp_path, script):
    env = tree(tmp_path)
    assert run(tmp_path, env, script, "--session", "03").returncode == 2


def test_zero_run_checker_fails(tmp_path):
    env = tree(tmp_path)
    assert run(tmp_path, env, "check_tedana.sh", "--sublist", tmp_path / "subjects.txt").returncode == 1


def test_confounds_preserve_verify_session_and_mismatch(tmp_path, monkeypatch):
    inputs(tmp_path, ses="01")
    stem = inputs(tmp_path)
    args = ("--session", "02", "--expected-runs", "1")
    assert gen_main(tmp_path, monkeypatch, *args, "--preserve-existing") == 0
    output = tmp_path / f"confounds/sub-10001/{stem}_desc-TedanaPlusConfounds.tsv"
    before = (output.read_bytes(), output.stat().st_mtime_ns)
    assert gen_main(tmp_path, monkeypatch, *args, "--preserve-existing") == 0
    assert gen_main(tmp_path, monkeypatch, *args, "--check") == 0
    assert before == (output.read_bytes(), output.stat().st_mtime_ns)
    assert len(list((tmp_path / "confounds").rglob("*.tsv"))) == 1
    output.write_text("99\t99\n" * 4)
    assert gen_main(tmp_path, monkeypatch, *args, "--preserve-existing") == 1
    assert output.read_text() == "99\t99\n" * 4


def test_confounds_check_no_write_missing_and_count(tmp_path, monkeypatch):
    inputs(tmp_path)
    assert gen_main(tmp_path, monkeypatch, "--session", "02", "--check") == 1
    assert not (tmp_path / "confounds").exists()
    assert gen_main(tmp_path, monkeypatch, "--session", "01", "--check") == 1
    assert gen_main(tmp_path, monkeypatch, "--expected-runs", "20", "--check") == 1


def test_confounds_alignment_and_nonfinite_fail_without_write(tmp_path, monkeypatch):
    stem = inputs(tmp_path)
    bold = tmp_path / f"derivatives/fmriprep/sub-10001/ses-02/func/{stem}_echo-1_part-mag_desc-preproc_bold.nii.gz"
    image(bold, n=5)
    assert gen_main(tmp_path, monkeypatch, "--preserve-existing") == 1
    assert not (tmp_path / "confounds").exists()
    image(bold)
    mixing = tmp_path / f"derivatives/tedana/sub-10001/ses-02/{stem}_desc-ICA_mixing.tsv"
    mixing.write_text(mixing.read_text().replace("0\t1", "0\tinf"))
    assert gen_main(tmp_path, monkeypatch, "--preserve-existing") == 1
    assert not (tmp_path / "confounds").exists()


def test_atomic_publication_never_overwrites_and_honors_umask(tmp_path):
    path = put(tmp_path / "existing.tsv", "old")
    with pytest.raises(FileExistsError):
        gen.atomic_write_tsv(pd.DataFrame([[1.0]]), path, preserve_existing=True)
    assert path.read_text() == "old"
    old = os.umask(0o002)
    try:
        gen.atomic_write_tsv(pd.DataFrame([[1.0]]), tmp_path / "new.tsv", preserve_existing=True)
    finally:
        os.umask(old)
    assert (tmp_path / "new.tsv").stat().st_mode & 0o777 == 0o664
    assert not list(tmp_path.glob(".*.tsv.*"))


def test_resume_runner_dry_run_and_fail_closed_after_qc(tmp_path):
    env = tree(tmp_path)
    # macOS lacks flock; lock behavior itself uses Linux's system flock in production.
    if shutil.which("flock") is None:
        lock = put(tmp_path / "bin/flock", "#!/bin/sh\nexit 0\n")
        lock.chmod(0o755)
    for sub in ("11083", "11084", "11110", "11120", "11193"):
        for task, number in (("doors", "1"), ("socialdoors", "1"), ("ugr", "1"), ("ugr", "2")):
            inputs(tmp_path, sub=sub, task=task, run=number)
    proc = run(tmp_path, env, "resume_wave2_tedana.sh", "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PREFLIGHT PASSED: 20" in proc.stdout
    assert "DRY RUN COMPLETE" in proc.stdout
    assert not (tmp_path / "derivatives/fsl").exists()
    put(tmp_path / "qc/run_qc.tsv", "before")
    put(tmp_path / "qc/thresholds.tsv", "before")
    put(tmp_path / "code/build_run_qc.py", "import sys\nprint('synthetic QC')\nsys.exit(1 if sys.argv[1] == 'check' else 0)\n")
    proc = run(tmp_path, env, "resume_wave2_tedana.sh")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "Processed 20 TEDANA metric file(s)." in proc.stdout
    assert "STAGE: descriptive scanner-era" not in proc.stdout
    assert "ALL STAGES PASSED" not in proc.stdout
    put(tmp_path / "code/build_run_qc.py", "print('synthetic QC passes')\n")
    put(tmp_path / "code/build_scanner_era_qc.py", "print('synthetic era QC passes')\n")
    put(tmp_path / "code/refresh_task_handoff.py", "print('synthetic handoff passes')\n")
    outputs = list((tmp_path / "derivatives/fsl").rglob("*.tsv"))
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in outputs}
    proc = run(tmp_path, env, "resume_wave2_tedana.sh")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ALL STAGES PASSED" in proc.stdout
    assert before == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in outputs}
