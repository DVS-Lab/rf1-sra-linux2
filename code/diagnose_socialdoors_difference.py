#!/usr/bin/env python3
"""Read-only L1 paired-difference diagnostic; never assigns paper exclusions."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import nibabel as nib
import numpy as np

import pair_paper_handoff as pairing

source = pairing.source
TASKS = ("socialdoors", "doors")
LABELS = {"1": "win", "2": "loss", "3": "decision", "4": "win-loss"}
ALLOWED = {"fd_mean:high_fd_mean", "tsnr:low_tsnr"}
POLICY = dict(schema_version=1, diagnostic_only=True, final_exclusions_made=False,
              session="01", age_pool="original_verified_age55_pool",
              source_exclusions="preserved", per_run_coverage_minimum_pct=95,
              fd_tsnr_flags="included_and_labeled_not_excluded",
              difference="socialdoors_cope_minus_doors_cope",
              variance="sum_of_VARCOPEs_assuming_independent_run_estimation_errors",
              summaries="intersection_of_valid_support_across_all_pairs_and_contrasts",
              effect_outlier_exclusion=False, resampling=False, ugr="unchanged")


def diagnostic_runs(rows):
    """Only relax known FD/tSNR gates, never a previous or current source hold."""
    result = []
    for original in rows:
        if original["task"] not in TASKS:
            continue
        row = dict(original)
        failures = set(filter(None, row["qc_failure_reasons"].split(";")))
        valid = (row["session"] == "01" and row["run"] == "1"
                 and row["previous_selection_status"] == "eligible"
                 and row["coverage_decision"] == "pass"
                 and source.old.coverage(row["coverage_pct"]) == "pass"
                 and row["fd_mean_decision"] in ("pass", "high_fd_mean")
                 and row["tsnr_decision"] in ("pass", "low_tsnr")
                 and all(source.number(row[m]) is not None and float(row[m]) >= 0
                         for m in ("fd_mean", "tsnr")))
        strict = valid and row["selection_status"] == "eligible" and not failures
        flagged = (valid and row["selection_status"] == "excluded_run_qc"
                   and bool(failures) and failures <= ALLOWED)
        row["diagnostic_included"] = strict or flagged
        row["strict_selection_status"] = row["selection_status"]
        row["diagnostic_group"] = "fd_tsnr_flagged" if flagged else "strict_pass" if strict else "not_included"
        if strict or flagged:
            row["selection_status"] = "eligible"
        else:
            row["selection_status"] = "not_in_diagnostic"
        result.append(row)
    return result


def membership(runs):
    lookup = source.audit.indexed(runs)
    result = []
    for sub, ses in sorted({(r["subject"], r["session"]) for r in runs}):
        tasks = {t: lookup.get((sub, ses, t, "1"), {}) for t in TASKS}
        missing = [t + ":" + (r.get("selection_reason") or r.get("strict_selection_status") or "no_run_record")
                   for t, r in tasks.items() if not r.get("diagnostic_included")]
        group = "not_paired" if missing else "fd_tsnr_flagged" if any(
            r.get("diagnostic_group") == "fd_tsnr_flagged" for r in tasks.values()) else "strict_pass"
        result.append(dict(subject=sub, session=ses, diagnostic_pair=not missing,
                           group=group, unavailable_partner_reasons="|".join(missing)))
    return result


def fingerprint(path):
    path = Path(path).resolve()
    record = source.l1.signature(path)
    if record.get("absent") or not path.is_file():
        raise ValueError("Required diagnostic input missing: " + str(path))
    record["sha256"] = source.audit.sha(path)
    return record


def verify_fingerprints(records):
    for record in records:
        if fingerprint(record["path"]) != record:
            raise ValueError("Diagnostic input changed: " + record["path"])


def prepare(previous):
    print("Validating the recorded handoff and completed L1 lineage", flush=True)
    source.check(SimpleNamespace(output=previous))
    saved = json.loads((previous / "provenance.json").read_text())
    original = Path(saved["config"]["previous"])
    old = json.loads((original / "provenance.json").read_text())
    plan_path = Path(old["config"]["finish_dir"]) / "plan.json"
    processing = json.loads(plan_path.read_text())
    _, decisions = pairing.parse((previous / "run_decisions.tsv").read_text())
    runs = diagnostic_runs(decisions)
    chosen = source.old.select(processing, runs)
    tables = {task: source.old.table([r for r in chosen if r["analysis"] == task],
                                   list(source.finish.handoff_rows(processing)[0])) for task in TASKS}
    files, _, n = pairing.pair_tables(tables, runs)
    if not n:
        raise ValueError("No source-valid coverage-passing pairs")
    _, pairs = pairing.parse(files["paired_socialdoors/selected_pairs.tsv"])
    members = {r["subject"] for r in pairs}
    paired_runs = [r for r in runs if r["subject"] in members and r["selection_status"] == "eligible"]
    source.verify_selected(processing, paired_runs)
    lookup = source.audit.indexed(paired_runs)
    for row in pairs:
        flags = []
        for task in TASKS:
            run = lookup[(row["subject"], row["session"], task, "1")]
            for field in ("fd_mean", "tsnr", "coverage_pct", "fd_mean_fence", "tsnr_fence", "qc_failure_reasons"):
                row[f"{task}_{field}"] = run[field]
            if run["diagnostic_group"] == "fd_tsnr_flagged":
                flags.append(task + ":" + run["qc_failure_reasons"])
        row["group"] = "fd_tsnr_flagged" if flags else "strict_pass"
        row["flags"] = "|".join(flags)
    paths = {previous / "provenance.json", previous / "provenance.sha256", plan_path,
             Path(__file__).resolve(), Path(pairing.__file__).resolve()}
    paths.update(previous / name for name in saved["outputs"])
    paths.update(Path(s["path"]) for s in saved["sources"] if not s.get("absent"))
    for row in pairs:
        for task in TASKS:
            paths.update(Path(row[f"{task}_{f}"]) for f in ("cope", "varcope", "mask", "dof"))
            feat = Path(row[f"{task}_feat_dir"])
            paths.update(feat / name for name in ("no_tedana_success.json", "design.fsf", "design.con", "design.mat"))
            fsf = (feat / "design.fsf").read_text()
            match = re.search(r'^set fmri\(conname_real\.' + row["contrast"] + r'\)\s+"([^"]+)"', fsf, re.M)
            if not match or match[1] != LABELS[row["contrast"]]:
                raise ValueError("Unexpected L1 contrast identity: " + str(feat))
            dof = float(Path(row[f"{task}_dof"]).read_text().strip())
            if not np.isfinite(dof) or dof <= 0:
                raise ValueError("Invalid L1 degrees of freedom")
            row[f"{task}_dof_value"] = dof
    print(f"Fingerprinting {len(paths)} inputs; no BOLD data or preprocessing is read/rerun", flush=True)
    records = [fingerprint(p) for p in sorted(paths)]
    return dict(policy=POLICY, previous=str(previous), pairs=pairs, runs=runs, sources=records)


def same_grid(a, b):
    if len(a.shape) != 3 or a.shape != b.shape or not np.allclose(a.affine, b.affine, rtol=0, atol=1e-5):
        raise ValueError("L1 image grids differ; no implicit resampling permitted")


def difference(row):
    images = {f"{t}_{f}": nib.load(row[f"{t}_{f}"]) for t in TASKS for f in ("cope", "varcope", "mask")}
    reference = images["socialdoors_cope"]
    for img in images.values():
        same_grid(reference, img)
    a = {k: img.get_fdata(dtype=np.float64) for k, img in images.items()}
    valid = np.ones(reference.shape, dtype=bool)
    for task in TASKS:
        mask, cope, variance = (a[f"{task}_{f}"] for f in ("mask", "cope", "varcope"))
        valid &= np.isfinite(mask) & (mask > 0) & np.isfinite(cope) & np.isfinite(variance) & (variance > 0)
    if not valid.any():
        raise ValueError("Pair has no finite positive-variance joint support")
    delta = np.full(reference.shape, np.nan)
    variance = delta.copy()
    delta[valid] = a["socialdoors_cope"][valid] - a["doors_cope"][valid]
    variance[valid] = a["socialdoors_varcope"][valid] + a["doors_varcope"][valid]
    if not np.isfinite(delta[valid]).all() or not np.isfinite(variance[valid]).all():
        raise ValueError("Overflow in paired difference/variance")
    arrays = dict(difference=delta, variance=variance, se=np.sqrt(variance), valid_mask=valid.astype(np.uint8))
    return reference, arrays


def directory(output, row):
    return output / "pairs" / f"sub-{row['subject']}_ses-{row['session']}" / ("cope-" + row["contrast"])


def save_image(path, data, reference):
    header = reference.header.copy()
    header.set_data_dtype(data.dtype)
    header.set_intent("none")
    img = nib.Nifti1Image(data, reference.affine, header)
    tmp = path.with_name(path.name.replace(".nii.gz", ".tmp.nii.gz"))
    nib.save(img, tmp)
    tmp.replace(path)


def verify_pair(output, row, recompute=False):
    dest = directory(output, row)
    receipt = json.loads((dest / "receipt.json").read_text())
    if receipt["pair"] != row or set(receipt["outputs"]) != {n + ".nii.gz" for n in ("difference", "variance", "se", "valid_mask")}:
        raise ValueError("Pair receipt differs")
    for name, digest in receipt["outputs"].items():
        if source.audit.sha(dest / name) != digest:
            raise ValueError("Completed diagnostic map changed: " + str(dest / name))
    if recompute:
        reference, expected = difference(row)
        for name, array in expected.items():
            image = nib.load(dest / (name + ".nii.gz"))
            same_grid(reference, image)
            if not np.array_equal(image.get_fdata(), array, equal_nan=True):
                raise ValueError("Paired map arithmetic failed: " + name)


def execute(output, row):
    dest = directory(output, row)
    if (dest / "receipt.json").exists():
        verify_pair(output, row)
        return "REUSED"
    dest.mkdir(parents=True, exist_ok=True)
    reference, arrays = difference(row)
    for name, data in arrays.items():
        save_image(dest / (name + ".nii.gz"), data, reference)
    source.l1.write_json(dest / "receipt.json", dict(pair=row, outputs={
        name + ".nii.gz": source.audit.sha(dest / (name + ".nii.gz")) for name in arrays}))
    return "BUILT"


def summaries(output, pairs):
    reference, common, union = None, None, None
    for row in pairs:
        img = nib.load(directory(output, row) / "valid_mask.nii.gz")
        if reference is None:
            reference = img
            common = np.ones(img.shape, dtype=bool)
            union = np.zeros(img.shape, dtype=bool)
        same_grid(reference, img)
        mask = img.get_fdata() > 0
        common &= mask
        union |= mask
    if not common.any():
        raise ValueError("Empty cohort-common support; inspect masks, do not silently drop subjects")
    rows = []
    for pair in pairs:
        dest = directory(output, pair)
        delta = nib.load(dest / "difference.nii.gz").get_fdata()[common]
        se = nib.load(dest / "se.nii.gz").get_fdata()[common]
        joint_n = int(np.count_nonzero(nib.load(dest / "valid_mask.nii.gz").get_fdata()))
        row = {k: v for k, v in sorted(pair.items()) if not any(k.endswith("_" + f) for f in ("cope", "varcope", "mask", "dof", "feat_dir"))}
        row.update(contrast_name=LABELS[pair["contrast"]], mean_difference=float(np.mean(delta)),
                   rms_difference=float(np.sqrt(np.mean(delta ** 2))),
                   median_se=float(np.median(se)), p95_se=float(np.percentile(se, 95)),
                   common_voxels=int(common.sum()), joint_valid_voxels=joint_n,
                   common_fraction_of_pair=float(common.sum() / joint_n),
                   difference_map=str(dest / "difference.nii.gz"), se_map=str(dest / "se.nii.gz"))
        row["fd_difference"] = float(pair["socialdoors_fd_mean"]) - float(pair["doors_fd_mean"])
        row["tsnr_difference"] = float(pair["socialdoors_tsnr"]) - float(pair["doors_tsnr"])
        rows.append(row)
    return reference, common, union, rows


def plot(output, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"strict_pass": "#247b8a", "fd_tsnr_flagged": "#ba3b56"}
    fig, axes = plt.subplots(4, 3, figsize=(12, 13), constrained_layout=True)
    for i, contrast in enumerate(LABELS):
        selected = [r for r in rows if r["contrast"] == contrast]
        for j, (metric, title) in enumerate((("mean_difference", "Mean difference (COPE units)"),
                                           ("rms_difference", "RMS difference (COPE units)"),
                                           ("median_se", "Median SE (COPE units)"))):
            ax = axes[i, j]
            for x, (group, color) in enumerate(colors.items()):
                values = np.array([r[metric] for r in selected if r["group"] == group])
                if len(values):
                    ax.boxplot(values, positions=[x], widths=.45, showfliers=False)
                    ax.scatter(x + np.linspace(-.14, .14, len(values)), values, color=color, s=13, alpha=.7)
            ax.set_xticks([0, 1], ["Strict pass", "FD/tSNR flagged"])
            ax.set_title(LABELS[contrast] + ": " + title, fontsize=10)
            ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Social Doors minus Doors: common-support descriptive diagnostics\nAll coverage-valid pairs; no outcome-based exclusions", fontsize=13)
    fig.savefig(output / "paired_difference_summary.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 4, figsize=(16, 7), constrained_layout=True)
    selected = [r for r in rows if r["contrast"] == "4"]
    for j, (metric, title) in enumerate((("max_fd", "Maximum run mean FD (mm)"), ("min_tsnr", "Minimum run tSNR"),
                                       ("fd_difference", "Social - Doors mean FD (mm)"), ("tsnr_difference", "Social - Doors tSNR"))):
        for i, y in enumerate(("rms_difference", "median_se")):
            for group, color in colors.items():
                data = [r for r in selected if r["group"] == group]
                xs = [max(float(r[t + "_fd_mean"]) for t in TASKS) if metric == "max_fd" else
                      min(float(r[t + "_tsnr"]) for t in TASKS) if metric == "min_tsnr" else r[metric] for r in data]
                axes[i, j].scatter(xs, [r[y] for r in data], color=color, label=group, s=20, alpha=.7)
            axes[i, j].set(xlabel=title, ylabel=y.replace("_", " ") + " (COPE units)")
            axes[i, j].spines[["top", "right"]].set_visible(False)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("(Social win - loss) - (Doors win - loss): QC associations\nFD/tSNR differences are descriptive, not contrast-quality thresholds")
    fig.savefig(output / "paired_qc_associations.png", dpi=150)
    plt.close(fig)


def report(output, plan):
    reference, common, union, rows = summaries(output, plan["pairs"])
    save_image(output / "common_support.nii.gz", common.astype(np.uint8), reference)
    save_image(output / "union_support.nii.gz", union.astype(np.uint8), reference)
    (output / "pair_metrics.tsv").write_text(source.old.table(rows, list(rows[0])))
    (output / "diagnostic_pairs.tsv").write_text(source.old.table(plan["pairs"], list(plan["pairs"][0])))
    (output / "run_membership.tsv").write_text(source.old.table(plan["runs"], list(plan["runs"][0])))
    members = membership(plan["runs"])
    (output / "pair_membership.tsv").write_text(source.old.table(members, list(members[0])))
    subjects = {r["subject"]: r for r in plan["pairs"]}
    counts = dict(diagnostic_pairs=len(subjects), strict_pass_pairs=sum(r["group"] == "strict_pass" for r in subjects.values()),
                  fd_tsnr_flagged_pairs=sum(r["group"] == "fd_tsnr_flagged" for r in subjects.values()),
                  common_voxels=int(common.sum()), union_voxels=int(union.sum()),
                  common_fraction_of_union=float(common.sum() / union.sum()), final_paper_N="not_finalized")
    source.l1.write_json(output / "summary.json", dict(policy=POLICY, counts=counts))
    plot(output, rows)
    text = ("# Paired Difference Diagnostic\n\nKatie's final exclusions remain pending; UGR and all prior handoffs are unchanged.\n\n"
            f"Pairs: {counts['diagnostic_pairs']}; strict-pass: {counts['strict_pass_pairs']}; FD/tSNR-flagged: {counts['fd_tsnr_flagged_pairs']}.\n\n"
            "Age-55+ baseline no-TEDANA L1 inputs only. Both runs retain >=95% canonical coverage and settled source-validity decisions.\n"
            "No participant is excluded because of an extreme effect, standard error, or FD/tSNR difference.\n\n"
            "Difference = Social Doors COPE - Doors COPE. Variance = sum of the two VARCOPEs, assuming independent run estimation errors.\n"
            "Cross-run error covariance is not estimated; this is not proof that motion cancels. No p-values or group tests are computed.\n"
            "Contrasts 1-4 are win, loss, decision, win-loss. Contrast 4 is a difference of win-loss contrasts, not an all-trials task difference.\n"
            "The old cross-task L2 mean is not used. All maps stay on the existing L1 grid without resampling.\n"
            "Invalid/outside-joint-support map voxels are NaN, not zero effects. Every pair's full joint support is retained in its maps.\n\n"
            f"Cross-participant summaries use {counts['common_voxels']} voxels common to every pair/contrast "
            f"({counts['common_fraction_of_union']:.1%} of their union). This can hide peripheral artifacts; review full-support maps too.\n"
            "Per-run coverage percentages refer to the canonical QC target, NOT this common-support fraction. No new support threshold is applied.\n"
            "Whole-mask means/RMS are descriptive, not ROI effects or a measure of biological validity. Boxplot whiskers do not define exclusions.\n\n"
            "![Difference and uncertainty](paired_difference_summary.png)\n\n![QC associations](paired_qc_associations.png)\n\n"
            "Review pair_metrics.tsv, diagnostic_pairs.tsv, pair_membership.tsv and per-pair difference/se maps. run_membership.tsv keeps prior reasons, "
            "including runs lacking a usable partner. diagnostic_included there describes run-level availability, not a final paper selection.\n")
    (output / "README.md").write_text(text)
    print(json.dumps(counts, indent=2), flush=True)


def load_plan(output):
    path = output / "plan.json"
    if source.audit.sha(path) != (output / "plan.sha256").read_text().strip():
        raise ValueError("Diagnostic plan changed")
    plan = json.loads(path.read_text())
    if plan["policy"] != POLICY:
        raise ValueError("Diagnostic policy changed")
    verify_fingerprints(plan["sources"])
    return plan


def build(args):
    if (args.output / "plan.json").exists():
        plan = load_plan(args.output)
        if plan["previous"] != str(args.previous):
            raise ValueError("Cannot change source handoff on resume")
    else:
        if args.output.exists():
            raise ValueError("Output exists without a verified plan; use a new directory")
        plan = prepare(args.previous)
        args.output.mkdir(parents=True)
        source.l1.write_json(args.output / "plan.json", plan)
        (args.output / "plan.sha256").write_text(source.audit.sha(args.output / "plan.json") + "\n")
    if (args.output / "artifacts.json").exists():
        check(args)
        return
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i, state in enumerate(pool.map(lambda row: execute(args.output, row), plan["pairs"]), 1):
            if i % 20 == 0 or i == len(plan["pairs"]):
                print(f"{state}: checked/built {i}/{len(plan['pairs'])} paired contrasts", flush=True)
    report(args.output, plan)
    verify_fingerprints(plan["sources"])
    outputs = {str(p.relative_to(args.output)): source.audit.sha(p)
               for p in sorted(args.output.rglob("*")) if p.is_file() and not p.name.endswith(".tmp")}
    source.l1.write_json(args.output / "artifacts.json", outputs)
    print("BUILT: diagnostic only; run check before interpreting results", flush=True)


def check(args):
    plan = load_plan(args.output)
    artifacts = json.loads((args.output / "artifacts.json").read_text())
    actual = {str(p.relative_to(args.output)) for p in args.output.rglob("*")
              if p.is_file() and p.name != "artifacts.json" and not p.name.endswith(".tmp")}
    if set(artifacts) != actual:
        raise ValueError("Diagnostic artifact inventory changed")
    for name, digest in artifacts.items():
        if Path(name).is_absolute() or ".." in Path(name).parts or source.audit.sha(args.output / name) != digest:
            raise ValueError("Diagnostic artifact changed: " + name)
    for row in plan["pairs"]:
        verify_pair(args.output, row, recompute=True)
    _, common, union, rows = summaries(args.output, plan["pairs"])
    if (args.output / "pair_metrics.tsv").read_text() != source.old.table(rows, list(rows[0])):
        raise ValueError("Summary values differ from maps")
    for name, array in (("common_support", common), ("union_support", union)):
        if not np.array_equal(nib.load(args.output / (name + ".nii.gz")).get_fdata(), array):
            raise ValueError("Summary support changed")
    verify_fingerprints(plan["sources"])
    print("CHECK PASSED: source/coverage gates, paired direction/variance arithmetic, common-support summaries and artifact hashes. "
          "No final exclusions assigned; UGR and existing outputs unchanged.", flush=True)
    print((args.output / "summary.json").read_text(), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.previous:
        args.previous = args.previous.resolve()
    if args.jobs < 1 or (args.command == "build" and args.previous is None):
        parser.error("build requires --previous; jobs must be positive")
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
