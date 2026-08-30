from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np


CODE = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


audit = load("audit_tedana_l1_design", CODE / "audit_tedana_l1_design.py")


def test_nuisance_overlap_detects_task_collinearity() -> None:
    time = np.linspace(-1, 1, 20)
    task = np.column_stack((time, np.sin(3 * time)))
    nuisance = np.column_stack((time, np.cos(2 * time)))
    rows, remaining, canonical = audit.nuisance_overlap(task, nuisance)
    assert rows[0]["nuisance_r_squared"] > 0.999999
    assert np.isinf(rows[0]["vif"]) or rows[0]["vif"] > 1e10
    assert rows[0]["remaining_norm_fraction"] < 1e-6
    assert 0 <= remaining < 1
    assert canonical > 0.999999


def test_contrast_efficiency_declines_with_collinear_nuisance() -> None:
    time = np.linspace(-1, 1, 40)
    task = np.column_stack((np.sin(3 * time), np.cos(5 * time)))
    nuisance = (task[:, 0] + 0.1 * np.sin(11 * time))[:, None]
    base = np.column_stack((task, np.ones(len(time))))
    candidate = np.column_stack((task, np.ones(len(time)), nuisance))
    contrast = np.array([[1.0, 0.0]])
    base_variance = audit.contrast_variances(base, contrast, 2)[0]
    candidate_variance = audit.contrast_variances(candidate, contrast, 2)[0]
    assert base_variance / candidate_variance < 1


def test_render_audit_fsf_only_changes_output_and_confounds(tmp_path: Path) -> None:
    source = tmp_path / "source.fsf"
    source.write_text(
        'set fmri(outputdir) "/old/output"\n'
        'set fmri(temphp_yn) 0\n'
        'set confoundev_files(1) "/old/confounds.tsv"\n'
    )
    confounds = tmp_path / "new.tsv"; confounds.write_text("0\n")
    rendered = audit.render_audit_fsf(source, confounds, tmp_path / "audit" / "design")
    text = rendered.read_text()
    assert str(confounds) in text
    assert str(tmp_path / "audit" / "design.feat") in text
    assert "/old/" not in text


def test_read_vest(tmp_path: Path) -> None:
    path = tmp_path / "design.mat"
    path.write_text("/NumWaves 2\n/NumPoints 2\n/Matrix\n1 2\n3 4\n")
    assert np.array_equal(audit.read_vest(path), np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_render_only_commands_match_downstream_interfaces(tmp_path: Path) -> None:
    base = {
        "subject": "10785", "session": "01", "run": "1",
        "run_key": "sub-10785_ses-01_task-sharedreward_run-1",
    }
    shared = audit.render_only_command(tmp_path, {**base, "task": "sharedreward"})
    assert shared == [
        "bash", str(tmp_path / "code" / "L1stats.sh"), "10785", "1", "0",
        "--session", "01", "--render-only",
    ]
    doors = audit.render_only_command(tmp_path, {**base, "task": "socialdoors"})
    assert doors == [
        "bash", str(tmp_path / "code" / "L1stats.sh"), "10785", "1", "0",
        "socialdoors", "--session", "01", "--render-only",
    ]


def test_render_missing_pins_project_and_derivative_roots(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "upstream"
    repo = tmp_path / "rf1-sra-sharedreward"
    script = repo / "code" / "L1stats.sh"
    script.parent.mkdir(parents=True); script.write_text("#!/usr/bin/env bash\n")
    row = {
        "subject": "10785", "session": "01", "task": "sharedreward", "run": "1",
        "run_key": "sub-10785_ses-01_task-sharedreward_run-1",
    }

    def fake_run(command, *, cwd, env, text, capture_output):
        assert cwd == repo
        assert env["RF1_SRA_UPSTREAM_ROOT"] == str(project)
        assert env["FSL_DERIVATIVES_ROOT"] == str(repo / "derivatives" / "fsl")
        target = (
            repo / "derivatives" / "fsl" / "sub-10785" / "ses-01" /
            "L1_sub-10785_task-sharedreward_ses-01_model-1_type-act_run-1.fsf"
        )
        target.parent.mkdir(parents=True); target.write_text("set fmri(temphp_yn) 0\n")
        return SimpleNamespace(returncode=0, stdout=f"Rendered: {target}\n", stderr="")

    monkeypatch.setattr(audit.subprocess, "run", fake_run)
    models = audit.render_missing_activation_fsf(project, repo, row)
    assert len(models) == 1
    assert models[0].name.endswith("_type-act_run-1.fsf")
