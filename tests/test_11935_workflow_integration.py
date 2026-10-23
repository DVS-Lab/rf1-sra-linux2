"""Exercise real promotion-to-cohort lineage, including a newly available Doors run."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import nibabel as nib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import benchmark_tedana_cohort as cohort
import complete_11935_repair as staging
import promote_11935 as promotion
import revise_tedana_cohort as revision


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def acquisition(project, task, value):
    stem = f"sub-11935_ses-01_task-{task}_run-1"
    raw = project / "bids/sub-11935/ses-01/func"
    func = project / "derivatives/fmriprep/sub-11935/ses-01/func"
    raw.mkdir(parents=True, exist_ok=True)
    func.mkdir(parents=True, exist_ok=True)
    image = nib.Nifti1Image(np.full((2, 2, 2, 218), value, dtype=np.float32), np.eye(4))
    for echo in range(1, 5):
        name = f"{stem}_echo-{echo}_part-mag_bold.nii.gz"
        nib.save(image, raw / name)
        write(raw / name.replace(".nii.gz", ".json"), json.dumps(dict(EchoTime=echo * .01, SoftwareVersions="XA60")))
        nib.save(image, func / name.replace("_bold", "_desc-preproc_bold"))
    nib.save(nib.Nifti1Image(np.ones((2, 2, 2), dtype=np.uint8), np.eye(4)), func / f"{stem}_part-mag_desc-brain_mask.nii.gz")
    pd.DataFrame(dict(trans_x=np.arange(218) / 100, framewise_displacement=np.zeros(218))).to_csv(
        func / f"{stem}_part-mag_desc-confounds_timeseries.tsv", sep="\t", index=False)
    write(raw / f"{stem}_events.tsv", "onset\tduration\ttrial_type\n0\t1\tdecision\n")
    if task in {"doors", "socialdoors"}:
        for path in [project / f"bids/sub-11935/ses-01/fmap/sub-11935_ses-01_acq-{task}_run-1_fieldmap.json",
                     project / f"derivatives/warpkit/sub-11935/ses-01/{stem}.warpkit_done",
                     project / f"derivatives/mriqc/sub-11935/ses-01/func/{stem}_bold.json",
                     project / f"derivatives/tedana/sub-11935/ses-01/{stem}_desc-ICA_mixing.tsv",
                     project / f"derivatives/fsl/confounds_tedana/sub-11935/{stem}_desc-TedanaPlusConfounds.tsv"]:
            write(path, "{}")


def test_promotion_then_manifest_revision_preserves_unrelated_row(tmp_path):
    project = tmp_path / "production"
    stage = project / "work/repair/sub-11935-project"
    socdoors = tmp_path / "socdoors"
    socdoors.mkdir()
    excluded = tmp_path / "excluded"
    excluded.mkdir()
    root = project / "derivatives/tedana-audit/cohort-pca-v1"
    root.mkdir(parents=True)
    acquisition(project, "socialdoors", 1)
    acquisition(project, "ugr", 2)
    args = SimpleNamespace(excluded_source_root=excluded)
    assert cohort.prepare(args, project, root) == 0
    old = json.loads((root / "manifest.json").read_text())
    unaffected = next(r for r in old["rows"] if r["task"] == "ugr")
    old_mtime = (project / unaffected["fmriprep_mask"]).stat().st_mtime_ns
    acquisition(stage, "socialdoors", 3)
    acquisition(stage, "doors", 4)
    hashes = staging.publishable_files(stage)
    write(stage / "11935-ready.json", json.dumps(dict(validated=True, subject="11935", session="01",
          tasks=["doors", "socialdoors"], files=hashes)))
    installed = project / "work/repair/replaced-originals"
    planned = promotion.plan(project, stage, installed, socdoors, root)
    receipt = promotion.apply_plan(planned)
    assert receipt["state"] == "installed"
    assert promotion.check(installed / "promotion.json")["verified"]
    planned_revision = revision.plan_revision(project, root, sorted(revision.APPROVED_KEYS),
          project / "work/repair/cohort-revision", excluded_source_root=excluded)
    revision.apply_revision(planned_revision, promotion_receipt=installed / "promotion.json")
    updated = cohort.load_manifest(args, project, root)
    assert len(updated["rows"]) == 3
    assert next(r for r in updated["rows"] if r["task"] == "ugr") == unaffected
    assert (project / unaffected["fmriprep_mask"]).stat().st_mtime_ns == old_mtime
    assert {r["run_key"] for r in updated["rows"]} == {r["run_key"] for r in old["rows"]} | {
        "sub-11935_ses-01_task-doors_run-1"}
    assert (project / "work/repair/cohort-revision/complete.json").is_file()
