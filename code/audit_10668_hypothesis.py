#!/usr/bin/env python3
"""Read-only 10668 attempt timing/task-design audit; never assigns or trims data.

Uses the production converters and pooled activation renderer in temporary
storage. Task-only estimability is not certification of the full nuisance GLM.
An optional saved private inventory supplies an acquisition-parameter comparison.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import numpy as np

from convert_behavior import convert_source

PARAMETERS = (
    "RepetitionTime", "EchoTime", "FlipAngle", "MultibandAccelerationFactor",
    "ParallelReductionFactorInPlane", "PhaseEncodingDirection",
    "EffectiveEchoSpacing", "TotalReadoutTime", "SliceTiming",
    "AcquisitionMatrixPE", "ReconMatrixPE", "BaseResolution",
    "ImageOrientationPatientDICOM", "SliceThickness", "SpacingBetweenSlices",
    "PixelBandwidth", "InPlanePhaseEncodingDirectionDICOM", "PartialFourier",
    "ReceiveCoilName", "CoilString", "ScanningSequence", "SequenceVariant",
    "ScanOptions", "MRAcquisitionType", "PercentPhaseFOV",
)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fsl_matrix(path):
    text = path.read_text().split("/Matrix", 1)[1]
    return np.loadtxt(io.StringIO(text), ndmin=2)


def compare_parameters(inventory):
    """Only publish equality status, never arbitrary private metadata values."""
    results = []
    for echo in range(1, 5):
        metas = []
        for task, run in (("trust", 1), ("trust", 2), ("sharedreward", 1)):
            name = f"sub-10668_ses-01_task-{task}_run-{run}_echo-{echo}_part-mag_bold.json"
            found = [r["metadata"] for r in inventory["bids_sidecars"]
                     if Path(r["path"]).name == name]
            metas.append(found[0] if len(found) == 1 else {})
        for key in PARAMETERS:
            present = sum(key in m for m in metas)
            status = "unavailable" if not present else "incomplete" if present < 3 else (
                "equal" if metas[0][key] == metas[1][key] == metas[2][key] else "different")
            results.append({"echo": echo, "parameter": key, "status": status})
    return results


def task_design(events, nvols, sr_root, feat_model):
    renderer = module("pooled_renderer", sr_root / "code/render_pooled_fsf.py")
    evs = module("pooled_evs", sr_root / "code/generate_l1_evs.py")
    with tempfile.TemporaryDirectory(prefix="rf1-10668-design-") as temp:
        root = Path(temp)
        counts = Counter(r["trial_type"] for r in events)
        for label in evs.ALL_EVS:
            (root / f"{label}.txt").write_text("".join(
                f"{r['onset']}\t{r['duration']}\t1\n" for r in events if r["trial_type"] == label))
        text = renderer.render("act", renderer.SOURCES["act"],
                               sr_root / "templates/FULLTRIAL_CONTRAST_CANDIDATE.tsv")
        substitutions = {
            "OUTPUT": str(root / "not-run.feat"), "DATA": str(root / "not-loaded.nii.gz"),
            "EVDIR": str(root) + "/", "MISSED_TRIAL": str(root / "missed_trial.txt"),
            "CONFOUNDEVS": str(root / "no-confounds.txt"),
            "NVOLUMES": str(nvols), "TR_INFO": "1.615",
            "SHAPE_EV7": "3" if counts["event_computer_neutral"] else "10",
            "SHAPE_EV8": "3" if counts["event_friend_neutral"] else "10",
            "SHAPE_EV9": "3" if counts["event_stranger_neutral"] else "10",
            "SHAPE_EV": "3" if counts["missed_trial"] else "10",
        }
        for key, value in substitutions.items():
            text = text.replace(key, value)
        # Explicit task-only diagnostic: no fabricated nuisance matrix and no
        # BOLD residualization. FEAT design generation does not fit image data.
        text = re.sub(r"set fmri\(confoundevs\) .*", "set fmri(confoundevs) 0", text)
        prefix = root / "design"
        prefix.with_suffix(".fsf").write_text(text)
        subprocess.run([feat_model, str(prefix)], check=True, capture_output=True, text=True)
        design = fsl_matrix(prefix.with_suffix(".mat"))
        contrasts = fsl_matrix(prefix.with_suffix(".con"))
        # Estimability is membership of each contrast in the design row space.
        projection = np.linalg.pinv(design) @ design
        errors = np.linalg.norm(contrasts - contrasts @ projection, axis=1)
        retained = [*range(1, 7), *range(10, 20), *range(23, 29)]
        rank = int(np.linalg.matrix_rank(design))
        augmented = int(np.linalg.matrix_rank(np.column_stack([np.ones(nvols), design])))
        return {"volumes": nvols, "duration_seconds": nvols * 1.615,
                "design_shape": list(design.shape), "task_rank": rank,
                "task_plus_intercept_rank": augmented,
                "task_only_residual_dof": nvols - augmented,
                "estimable_retained_contrasts": [i for i in retained if errors[i - 1] < 1e-7],
                "nonestimable_retained_contrasts": [i for i in retained if errors[i - 1] >= 1e-7],
                "maximum_retained_estimability_error": float(max(errors[i - 1] for i in retained))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--behavior-root", required=True, type=Path)
    parser.add_argument("--sharedreward-root", required=True, type=Path)
    parser.add_argument("--feat-model", default="feat_model")
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    harmonizer = module("harmonizer", args.sharedreward_root / "code/convert_harmonized_events.py")
    report = {"scope": "hypothesis only; no source assignments or eligibility changes",
              "design_scope": "pooled activation task-only; real nuisance GLM not tested",
              "assumption": "behavioral trigger zero aligned to scan onset; not proven by this test",
              "sharedreward_attempts": []}
    for run in (1, 2):
        path = args.behavior_root / "Scan-Card_Guessing_Game/logs/10668" / f"sub-10668_task-sharedreward_run-{run}_raw.csv"
        converted = convert_source("sharedreward", path)
        events = harmonizer.rf1(converted.rows)
        report["sharedreward_attempts"].append({
            "segment": run, "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "trials": converted.trial_count,
            "conditions": dict(Counter(r["trial_type"] for r in events)),
            "first_onset": min(float(r["onset"]) for r in events),
            "last_trial_end": max(float(r["onset"]) + float(r["duration"]) for r in events),
            "designs": [task_design(events, n, args.sharedreward_root, args.feat_model) for n in (255, 280)]})
    trust = args.behavior_root / "Scan-Investment_Game/logs/10668/sub-10668_task-trust_run-0_raw.csv"
    converted = convert_source("trust", trust)
    report["trust_raw_run0"] = {"trials": converted.trial_count,
                                "source_sha256": hashlib.sha256(trust.read_bytes()).hexdigest()}
    if args.inventory:
        raw = args.inventory.read_bytes()
        report["inventory_sha256"] = hashlib.sha256(raw).hexdigest()
        report["parameter_comparison"] = compare_parameters(json.loads(raw))
        report["parameter_scope"] = "saved sidecars only; no independent native NIfTI geometry check"
    else:
        report["parameter_comparison"] = "not tested: private inventory unavailable locally"
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Private JSON/source errors must not leak raw metadata into run logs.
        print(f"ERROR: hypothesis audit stopped ({type(exc).__name__}); inspect inputs privately.",
              file=sys.stderr)
        sys.exit(2)
