#!/usr/bin/env python3
"""Package verified paired COPE differences; never change selection or run FSL."""
from __future__ import annotations

import argparse
import csv
import fcntl
import io
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import nibabel as nib
import numpy as np

import diagnose_socialdoors_difference as diag

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ("delta_fd", "delta_tsnr", "pair_mean_fd", "pair_mean_tsnr")
POLICY = dict(version=1, direction="socialdoors_minus_doors", session="01",
              selection="unchanged_strict_age55_pool", smoothing="existing_L1_sm5",
              tedana_regressors=False, new_exclusions=False, resampling=False,
              mask="per_contrast_intersection_of_selected_valid_pair_masks",
              covariates="candidates_only_centered_within_selected_cohort",
              design_created=False, randomise_run=False)


def table(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def atomic_text(path, text):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def read_rows(path):
    with path.open() as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = reader.fieldnames
        rows = list(reader)
    if not fields or len(set(fields)) != len(fields) or not rows:
        raise ValueError("Empty table or invalid header: " + str(path))
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("Malformed table: " + str(path))
    return fields, rows


def key(row):
    return row["subject"], row["session"], row["contrast"]


def strict_rows(manifest, saved):
    fields, rows = read_rows(manifest)
    expected = {key(r): r for r in saved["pairs"] if r["group"] == "strict_pass"}
    if len({key(r) for r in rows}) != len(rows) or {key(r) for r in rows} != set(expected):
        raise ValueError("Manifest must be the entire verified strict pool; subset with --cohort")
    for row in rows:
        original = expected[key(row)]
        if set(fields) != set(original) or any(row[f] != str(original[f]) for f in fields):
            raise ValueError("Strict manifest differs from verified diagnostic")
        if row["session"] != "01" or row["flags"] or not re.fullmatch(r"\d{5}", row["subject"]):
            raise ValueError("Invalid strict participant/session/flags")
        for task in diag.TASKS:
            values = {f: float(row[f"{task}_{f}"]) for f in
                      ("coverage_pct", "fd_mean", "tsnr", "fd_mean_fence", "tsnr_fence")}
            if (not all(np.isfinite(v) for v in values.values())
                    or not 95 <= values["coverage_pct"] <= 100
                    or not 0 <= values["fd_mean"] <= values["fd_mean_fence"]
                    or values["tsnr"] < max(0, values["tsnr_fence"])
                    or row[f"{task}_qc_failure_reasons"]):
                raise ValueError("Strict row fails settled run QC")
    for sub in {r["subject"] for r in rows}:
        subject_rows = [r for r in rows if r["subject"] == sub]
        if {r["contrast"] for r in subject_rows} != set(diag.LABELS):
            raise ValueError("Each participant needs all four matched contrasts")
        for task in diag.TASKS:
            for metric in ("fd_mean", "tsnr", "coverage_pct"):
                if len({r[f"{task}_{metric}"] for r in subject_rows}) != 1:
                    raise ValueError("Run QC differs across contrasts")
    return [expected[key(r)] for r in rows]


def choose_subjects(rows, cohort):
    pool = sorted({r["subject"] for r in rows})
    if cohort is None:
        subjects = pool
    else:
        fields, entries = read_rows(cohort)
        if fields != ["subject"]:
            raise ValueError("Cohort must be an ID-only TSV with exactly one header: subject")
        subjects = [r["subject"].removeprefix("sub-") for r in entries]
        if any(not re.fullmatch(r"\d{5}", s) for s in subjects) or len(set(subjects)) != len(subjects):
            raise ValueError("Invalid or duplicate cohort IDs")
        missing = sorted(set(subjects) - set(pool))
        if missing:
            raise ValueError("Cohort IDs outside settled strict pool; no silent exclusions: " + ", ".join(missing))
    if len(subjects) < 2:
        raise ValueError("At least two participants required")
    return subjects


def covariate_tables(plan):
    lookup = {r["subject"]: r for r in plan["pairs"] if r["contrast"] == "1"}
    order, raw = [], []
    for index, subject in enumerate(plan["subjects"]):
        identity = dict(volume_index=index, volume_number=index + 1, subject=subject, session="01")
        order.append(identity)
        r = lookup[subject]
        row = dict(identity)
        row.update({f"{t}_{m}": float(r[f"{t}_{m}"]) for t in diag.TASKS
                    for m in ("fd_mean", "tsnr", "coverage_pct")})
        row.update(delta_fd=row["socialdoors_fd_mean"] - row["doors_fd_mean"],
                   delta_tsnr=row["socialdoors_tsnr"] - row["doors_tsnr"],
                   pair_mean_fd=(row["socialdoors_fd_mean"] + row["doors_fd_mean"]) / 2,
                   pair_mean_tsnr=(row["socialdoors_tsnr"] + row["doors_tsnr"]) / 2)
        raw.append(row)
    matrix = np.array([[r[f] for f in DERIVED] for r in raw])
    means = matrix.mean(axis=0)
    centered = matrix - means
    centered_rows = [dict(identity, **dict(zip(DERIVED, vector))) for identity, vector in zip(order, centered)]
    info = dict(scope=plan["scope"], n=len(raw), means=dict(zip(DERIVED, means)),
                units=dict(delta_fd="mm", pair_mean_fd="mm", delta_tsnr="dimensionless", pair_mean_tsnr="dimensionless"),
                constant_columns=[f for i, f in enumerate(DERIVED) if np.ptp(matrix[:, i]) == 0],
                centered_candidate_rank=int(np.linalg.matrix_rank(centered)),
                automatically_selected_for_design=False)
    return {"subjects.tsv": table(order), "cohort_ids.tsv": table([dict(subject=s) for s in plan["subjects"]]),
            "qc_covariates_raw.tsv": table(raw), "qc_covariates_centered.tsv": table(centered_rows),
            "covariate_centering.json": json.dumps(info, indent=2, sort_keys=True) + "\n"}


def contrast_arrays(plan, contrast):
    rows = {r["subject"]: r for r in plan["pairs"] if r["contrast"] == contrast}
    reference, common, arrays = None, None, []
    for sub in plan["subjects"]:
        row = rows[sub]
        diag.verify_pair(Path(plan["diagnostic"]), row)
        folder = diag.directory(Path(plan["diagnostic"]), row)
        image = nib.load(folder / "difference.nii.gz")
        mask_image = nib.load(folder / "valid_mask.nii.gz")
        reference = image if reference is None else reference
        diag.same_grid(reference, image)
        diag.same_grid(reference, mask_image)
        mask_data = mask_image.get_fdata()
        if not np.isin(mask_data, (0, 1)).all():
            raise ValueError("Invalid pair mask")
        mask = mask_data.astype(bool)
        data = image.get_fdata()
        if not np.isfinite(data[mask]).all():
            raise ValueError("Nonfinite difference inside valid pair mask")
        common = mask.copy() if common is None else common & mask
        arrays.append(data)
    if not common.any():
        raise ValueError("Empty group intersection; no participant automatically removed")
    stack = np.zeros(reference.shape + (len(arrays),), dtype=np.float32)
    for index, data in enumerate(arrays):
        stack[..., index][common] = data[common]
    if not np.isfinite(stack).all():
        raise ValueError("Float32 overflow")
    return reference, common.astype(np.uint8), stack


def save_stack(path, stack, reference):
    header = reference.header.copy()
    header.set_data_dtype(np.float32)
    header.set_intent("none")
    image = nib.Nifti1Image(stack, reference.affine, header)
    image.header.set_xyzt_units(reference.header.get_xyzt_units()[0], "unknown")
    image.header.set_zooms((*reference.header.get_zooms()[:3], 1.0))
    image.header["descrip"] = b"SocialDoors minus Doors; fourth dimension is participant"
    tmp = path.with_name("difference_4d.tmp.nii.gz")
    nib.save(image, tmp)
    tmp.replace(path)


def prepare(args):
    print("Checking existing diagnostic and original L1 lineage (no processing rerun)", flush=True)
    diag.check(SimpleNamespace(output=args.diagnostic))
    saved = diag.load_plan(args.diagnostic)
    rows = strict_rows(args.manifest, saved)
    subjects = choose_subjects(rows, args.cohort)
    paths = [args.manifest, args.diagnostic / "plan.json", args.diagnostic / "artifacts.json", Path(__file__)]
    if args.cohort:
        paths.append(args.cohort)
    return dict(policy=POLICY, diagnostic=str(args.diagnostic), subjects=subjects,
                scope="provided_final_cohort" if args.cohort else "imaging_pool_not_final_paper_cohort",
                pairs=[r for r in rows if r["subject"] in subjects],
                sources=[diag.fingerprint(p) for p in paths],
                config=dict(manifest=str(args.manifest), diagnostic=str(args.diagnostic),
                            cohort=str(args.cohort) if args.cohort else None))


def load_plan(output):
    path = output / "plan.json"
    if diag.source.audit.sha(path) != (output / "plan.sha256").read_text().strip():
        raise ValueError("Bundle plan changed")
    plan = json.loads(path.read_text())
    if plan["policy"] != POLICY:
        raise ValueError("Bundle policy changed")
    diag.verify_fingerprints(plan["sources"])
    return plan


def receipt_valid(folder, plan_hash):
    receipt = json.loads((folder / "receipt.json").read_text())
    if receipt["plan_sha256"] != plan_hash or set(receipt["outputs"]) != {"difference_4d.nii.gz", "mask.nii.gz"}:
        raise ValueError("Contrast receipt changed")
    for name, digest in receipt["outputs"].items():
        if diag.source.audit.sha(folder / name) != digest:
            raise ValueError("Completed bundle image changed: " + str(folder / name))


def inventory(output):
    return {str(p.relative_to(output)): diag.source.audit.sha(p) for p in sorted(output.rglob("*"))
            if p.is_file() and p.name != "artifacts.json"}


def build(args):
    if args.output.is_relative_to(args.diagnostic) or args.diagnostic.is_relative_to(args.output):
        raise ValueError("Bundle output must not overlap the existing diagnostic directory")
    if (args.output / "plan.json").exists():
        plan = load_plan(args.output)
        expected = dict(manifest=str(args.manifest), diagnostic=str(args.diagnostic),
                        cohort=str(args.cohort) if args.cohort else None)
        if plan["config"] != expected:
            raise ValueError("Different cohort/configuration; use a new output directory")
        diag.check(SimpleNamespace(output=args.diagnostic))
        if (args.output / "artifacts.json").exists():
            check(SimpleNamespace(output=args.output), diagnostic_checked=True)
            print("UNCHANGED: complete verified bundle reused", flush=True)
            return
    else:
        if args.output.exists() and any(args.output.iterdir()):
            raise ValueError("Refusing unrecognized nonempty output")
        plan = prepare(args)
        args.output.mkdir(parents=True, exist_ok=True)
        diag.source.l1.write_json(args.output / "plan.json", plan)
        atomic_text(args.output / "plan.sha256", diag.source.audit.sha(args.output / "plan.json") + "\n")
    plan_hash = diag.source.audit.sha(args.output / "plan.json")
    for name, contents in covariate_tables(plan).items():
        atomic_text(args.output / name, contents)
    summaries = []
    for contrast, label in diag.LABELS.items():
        folder = args.output / ("cope-" + contrast)
        folder.mkdir(exist_ok=True)
        if (folder / "receipt.json").exists():
            receipt_valid(folder, plan_hash)
            voxels = int(nib.load(folder / "mask.nii.gz").get_fdata().sum())
            print("REUSED contrast " + contrast, flush=True)
        else:
            reference, mask, stack = contrast_arrays(plan, contrast)
            save_stack(folder / "difference_4d.nii.gz", stack, reference)
            diag.save_image(folder / "mask.nii.gz", mask, reference)
            diag.source.l1.write_json(folder / "receipt.json", dict(plan_sha256=plan_hash,
                outputs={n: diag.source.audit.sha(folder / n) for n in ("difference_4d.nii.gz", "mask.nii.gz")}))
            voxels = int(mask.sum())
            print(f"BUILT contrast {contrast} ({label}): {len(plan['subjects'])} participants; {voxels} mask voxels", flush=True)
        summaries.append(dict(contrast=contrast, label=label, n_participants=len(plan["subjects"]), mask_voxels=voxels))
    atomic_text(args.output / "counts.tsv", table(summaries))
    atomic_text(args.output / "README.md", "# Social Doors minus Doors randomise inputs\n\n"
                f"Scope: {plan['scope']}; N={len(plan['subjects'])}.\n\n"
                "Each cope-N/difference_4d.nii.gz is an effect stack in subjects.tsv order; use its mask.nii.gz.\n"
                "Contrasts: 1 win; 2 loss; 3 decision; 4 (social win-loss) minus (doors win-loss).\n"
                "QC tables contain candidate nuisance covariates, not additional exclusions.\n"
                "Centered values use this exact cohort. Do not subset without rebuilding/recentering.\n"
                "No design.mat/design.con created and no randomise run. Review the approved model first.\n"
                "Do not include all raw values plus their means/differences (linear dependence).\n"
                "VARCOPEs establish valid support/provenance; no variance weighting is applied to these COPE stacks.\n"
                "Images use the existing sm5 no-TEDANA L1 estimates, not experimental AFNI 6-mm outputs.\n"
                "All settled selection rules remain unchanged.\n")
    diag.verify_fingerprints(plan["sources"])
    diag.source.l1.write_json(args.output / "artifacts.json", inventory(args.output))


def check(args, diagnostic_checked=False):
    plan = load_plan(args.output)
    if not diagnostic_checked:
        diag.check(SimpleNamespace(output=Path(plan["diagnostic"])))
    if inventory(args.output) != json.loads((args.output / "artifacts.json").read_text()):
        raise ValueError("Bundle artifact inventory/hash changed")
    for name, contents in covariate_tables(plan).items():
        if (args.output / name).read_text() != contents:
            raise ValueError("Subject order/covariate alignment changed: " + name)
    summaries = []
    for contrast, label in diag.LABELS.items():
        folder = args.output / ("cope-" + contrast)
        receipt_valid(folder, diag.source.audit.sha(args.output / "plan.json"))
        reference, mask, stack = contrast_arrays(plan, contrast)
        actual_mask = nib.load(folder / "mask.nii.gz")
        actual = nib.load(folder / "difference_4d.nii.gz")
        diag.same_grid(reference, actual_mask)
        if (actual.shape != stack.shape or actual.get_data_dtype() != np.dtype("float32")
                or not np.allclose(actual.affine, reference.affine, rtol=0, atol=1e-5)
                or not np.array_equal(actual.get_fdata(), stack)
                or not np.array_equal(actual_mask.get_fdata(), mask)):
            raise ValueError("Difference direction/order/pixels/mask/grid mismatch")
        summaries.append(dict(contrast=contrast, label=label, n_participants=len(plan["subjects"]), mask_voxels=int(mask.sum())))
    if (args.output / "counts.tsv").read_text() != table(summaries):
        raise ValueError("Counts differ from images")
    diag.verify_fingerprints(plan["sources"])
    print(f"CHECK PASSED: {len(plan['subjects'])} participants; four signed effect stacks, finite masked pixels, "
          "subject order, raw/centered QC covariates and original lineage verified. "
          f"Scope={plan['scope']}. No exclusions changed; no randomise analysis run.", flush=True)
    print((args.output / "counts.tsv").read_text(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--manifest", type=Path, default=ROOT / "qc/paired_difference/socialdoors-v1/strict_pairs.tsv")
    parser.add_argument("--diagnostic", type=Path, default=ROOT / "work/socialdoors-paired-diagnostic-v1")
    parser.add_argument("--cohort", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for field in ("manifest", "diagnostic", "cohort", "output"):
        if getattr(args, field) is not None:
            setattr(args, field, getattr(args, field).resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with (args.output.parent / (args.output.name + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        {"build": build, "check": check}[args.command](args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAILED ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
