import json
from pathlib import Path
import sys
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import diagnose_socialdoors_difference as diagnostic


def decision(**changes):
    row = dict(subject="10001", session="01", task="socialdoors", run="1",
               previous_selection_status="eligible", selection_status="eligible", selection_reason="",
               qc_failure_reasons="", coverage_pct="95", coverage_decision="pass",
               fd_mean="0.1", tsnr="30", fd_mean_decision="pass", tsnr_decision="pass")
    return dict(row, **changes)


def test_include_only_known_fd_tsnr_flags_preserve_original_rows():
    strict = decision()
    flagged = decision(selection_status="excluded_run_qc", qc_failure_reasons="fd_mean:high_fd_mean;tsnr:low_tsnr",
                       fd_mean_decision="high_fd_mean", tsnr_decision="low_tsnr")
    runs = diagnostic.diagnostic_runs([strict, flagged])
    assert [r["diagnostic_group"] for r in runs] == ["strict_pass", "fd_tsnr_flagged"]
    assert all(r["selection_status"] == "eligible" for r in runs)
    assert flagged["selection_status"] == "excluded_run_qc"


@pytest.mark.parametrize("change", [
    {"previous_selection_status": "held_existing_decision"},
    {"selection_status": "held_existing_decision"},
    {"coverage_pct": "94.999"}, {"coverage_decision": "review_missing_or_invalid"},
    {"session": "02"}, {"run": "2"}, {"fd_mean": "nan"}, {"tsnr": ""},
    {"fd_mean_decision": "review_missing_or_invalid"},
    {"selection_status": "excluded_run_qc", "qc_failure_reasons": "coverage:exclude_below_95"},
    {"selection_status": "excluded_run_qc", "qc_failure_reasons": "tedana:high"},
])
def test_never_relax_other_requirements(change):
    result = diagnostic.diagnostic_runs([decision(**change)])[0]
    assert result["diagnostic_included"] is False
    assert result["selection_status"] == "not_in_diagnostic"


def test_ugr_untouched():
    assert diagnostic.diagnostic_runs([decision(task="ugr")]) == []


def test_one_valid_task_never_becomes_a_pair():
    runs = diagnostic.diagnostic_runs([decision(), decision(task="doors", selection_status="held_existing_decision",
                                                           selection_reason="settled")])
    rows = diagnostic.membership(runs)
    assert len(rows) == 1 and rows[0]["diagnostic_pair"] is False
    assert rows[0]["unavailable_partner_reasons"] == "doors:settled"


def image_pair(tmp_path, subject="10001"):
    row = dict(subject=subject, session="01", contrast="4", group="fd_tsnr_flagged", flags="socialdoors:fd_mean:high_fd_mean")
    for task, cope, variance in (("socialdoors", 7., 4.), ("doors", 2., 5.)):
        row.update({task + "_fd_mean": ".4", task + "_tsnr": "30"})
        for field, value in (("cope", cope), ("varcope", variance), ("mask", 1.)):
            path = tmp_path / f"{subject}_{task}_{field}.nii.gz"
            nib.save(nib.Nifti1Image(np.full((4, 5, 6), value), np.diag([2., 2., 2., 1.])), path)
            row[task + "_" + field] = str(path)
    return row


def test_direction_variance_and_invalid_support(tmp_path):
    row = image_pair(tmp_path)
    path = Path(row["doors_varcope"])
    img = nib.load(path)
    data = img.get_fdata()
    data[0, 0, 0] = 0
    data[0, 0, 1] = np.nan
    nib.save(nib.Nifti1Image(data, img.affine), path)
    _, arrays = diagnostic.difference(row)
    valid = arrays["valid_mask"].astype(bool)
    assert valid.sum() == 118
    assert (arrays["difference"][valid] == 5).all()
    assert (arrays["variance"][valid] == 9).all()
    assert (arrays["se"][valid] == 3).all()
    assert np.isnan(arrays["difference"][~valid]).all()


def test_refuse_grid_mismatch(tmp_path):
    row = image_pair(tmp_path)
    path = Path(row["doors_cope"])
    img = nib.load(path)
    affine = img.affine.copy()
    affine[0, 3] += 1
    nib.save(nib.Nifti1Image(img.get_fdata(), affine), path)
    with pytest.raises(ValueError, match="grids differ"):
        diagnostic.difference(row)


def test_build_resume_check_and_changed_input(tmp_path, monkeypatch):
    row = image_pair(tmp_path)
    records = [diagnostic.fingerprint(row[t + "_" + f]) for t in diagnostic.TASKS for f in ("cope", "varcope", "mask")]
    plan = dict(policy=diagnostic.POLICY, previous=str(tmp_path / "previous"), pairs=[row],
                runs=diagnostic.diagnostic_runs([decision()]), sources=records)
    monkeypatch.setattr(diagnostic, "prepare", lambda _: plan)
    args = SimpleNamespace(previous=tmp_path / "previous", output=tmp_path / "diagnostic", jobs=2)
    diagnostic.build(args)
    diagnostic.check(args)
    product = diagnostic.directory(args.output, row) / "difference.nii.gz"
    stamp = product.stat().st_mtime_ns
    diagnostic.build(args)
    assert product.stat().st_mtime_ns == stamp
    summary = json.loads((args.output / "summary.json").read_text())
    assert summary["counts"]["fd_tsnr_flagged_pairs"] == 1
    assert summary["policy"]["final_exclusions_made"] is False
    img = nib.load(row["doors_cope"])
    nib.save(nib.Nifti1Image(img.get_fdata() + 1, img.affine), row["doors_cope"])
    with pytest.raises(ValueError, match="input changed"):
        diagnostic.check(args)


def test_pair_resume_does_not_replace_corrupt_completed_output(tmp_path):
    row = image_pair(tmp_path)
    output = tmp_path / "out"
    assert diagnostic.execute(output, row) == "BUILT"
    assert diagnostic.execute(output, row) == "REUSED"
    product = diagnostic.directory(output, row) / "difference.nii.gz"
    product.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="map changed"):
        diagnostic.execute(output, row)
    assert product.read_bytes() == b"corrupt"


def test_common_support_not_different_support_per_group(tmp_path):
    first = image_pair(tmp_path)
    second = image_pair(tmp_path, "10002")
    second["group"] = "strict_pass"
    img = nib.load(second["doors_mask"])
    mask = img.get_fdata()
    mask[0] = 0
    nib.save(nib.Nifti1Image(mask, img.affine), second["doors_mask"])
    for row in (first, second):
        diagnostic.execute(tmp_path / "out", row)
    _, common, union, rows = diagnostic.summaries(tmp_path / "out", [first, second])
    assert common.sum() == 90 and union.sum() == 120
    assert {r["common_voxels"] for r in rows} == {90}
    assert [r["joint_valid_voxels"] for r in rows] == [120, 90]
    assert {r["median_se"] for r in rows} == {3}


def test_missing_or_tampered_receipt_fails_check(tmp_path):
    row = image_pair(tmp_path)
    diagnostic.execute(tmp_path / "out", row)
    receipt = diagnostic.directory(tmp_path / "out", row) / "receipt.json"
    saved = json.loads(receipt.read_text())
    saved["pair"]["contrast"] = "1"
    receipt.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="receipt differs"):
        diagnostic.verify_pair(tmp_path / "out", row)


def test_signed_handoff_to_four_contrast_diagnostic(tmp_path, monkeypatch):
    from test_handoff_fd_tsnr import historical_fixture
    args = historical_fixture(tmp_path)
    source = diagnostic.source
    plan_path = tmp_path / "work/finish/plan.json"
    plan = json.loads(plan_path.read_text())
    for job in plan["jobs"]:
        job["output"] = str(tmp_path / "feat" / job["key"])
        if job["task"] not in diagnostic.TASKS:
            continue
        feat = Path(job["output"])
        (feat / "stats").mkdir(parents=True)
        for contrast in range(1, 5):
            for prefix in ("cope", "varcope"):
                nib.save(nib.Nifti1Image(np.ones((3, 4, 5)), np.eye(4)), feat / "stats" / f"{prefix}{contrast}.nii.gz")
        nib.save(nib.Nifti1Image(np.ones((3, 4, 5)), np.eye(4)), feat / "mask.nii.gz")
        (feat / "stats/dof").write_text("100\n")
        (feat / "design.fsf").write_text("".join(f'set fmri(conname_real.{c}) "{label}"\n' for c, label in diagnostic.LABELS.items()))
        for name in ("design.con", "design.mat", "no_tedana_success.json"):
            (feat / name).write_text("fixture")
    plan_path.write_text(json.dumps(plan))
    (plan_path.parent / "plan.sha256").write_text(source.audit.sha(plan_path))
    _, runs = diagnostic.pairing.parse((args.previous / "run_decisions.tsv").read_text())
    files, _ = source.old.render(plan, runs, {})
    for name, content in files.items():
        (args.previous / name).write_text(content)
    old = json.loads((args.previous / "provenance.json").read_text())
    old["sources"] = [source.l1.signature(plan_path)]
    old["outputs"] = {name: source.audit.sha(args.previous / name) for name in files}
    (args.previous / "provenance.json").write_text(json.dumps(old))
    (args.previous / "provenance.sha256").write_text(source.audit.sha(args.previous / "provenance.json"))
    # L1 verification has separate tests; here exercise real handoff authentication,
    # restored-run selection, contrast identity, pairing, image math and reporting.
    monkeypatch.setattr(source, "verify_selected", lambda *a: None)
    fields, qc = diagnostic.pairing.parse((tmp_path / "qc/run_qc.tsv").read_text())
    for row in qc:
        row["fd_mean"] = float(row["fd_mean"])
        row["tsnr"] = float(row["tsnr"])
        if row["subject"] == "11935" and row["task"] == "socialdoors":
            row["fd_mean"] = 1000.
    policy = json.loads((tmp_path / "qc/qc_policy.json").read_text())
    thresholds = source.canonical.compute_thresholds(qc, policy)
    for row in qc:
        for metric in policy["metrics"]:
            threshold = next(t for t in thresholds if (t["task"], t["session"], t["metric"]) == (row["task"], row["session"], metric))
            row[metric + "_outlier"] = row[metric] > threshold["upper_fence"] if metric == "fd_mean" else row[metric] < threshold["lower_fence"]
    (tmp_path / "qc/run_qc.tsv").write_text(source.old.table(qc, fields))
    (tmp_path / "qc/thresholds.tsv").write_text(source.old.table(thresholds, list(thresholds[0])))
    source.build(args)
    ugr_hash = source.audit.sha(args.output / "ugr/selected_inputs.tsv")
    diagnostic_args = SimpleNamespace(previous=args.output, output=tmp_path / "work/diagnostic", jobs=2)
    diagnostic.build(diagnostic_args)
    diagnostic.check(diagnostic_args)
    assert source.audit.sha(args.output / "ugr/selected_inputs.tsv") == ugr_hash
    frozen = json.loads((diagnostic_args.output / "plan.json").read_text())
    assert len(frozen["pairs"]) == 4
    assert {r["contrast"] for r in frozen["pairs"]} == {"1", "2", "3", "4"}
    assert all(r["group"] == "fd_tsnr_flagged" for r in frozen["pairs"])
    holds = tmp_path / "code/task_availability_holds.tsv"
    holds.write_text(holds.read_text() + "11935\t01\tdoors\t1\tnew hold\n")
    with pytest.raises(ValueError, match="input changed"):
        diagnostic.check(diagnostic_args)
