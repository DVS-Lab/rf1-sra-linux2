#!/usr/bin/env python3
"""Isolated Shared Reward-style 6-mm evaluation; never promote or exclude runs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

import measure_cohort_smoothness as baseline

ROOT = Path(__file__).resolve().parents[1]
TARGET, LOWER, UPPER = 6.0, 5.4, 6.6
ERAS = ("E11", "XA30", "XA60", "unknown")
SCRIPTS = ("smooth_to_target.sh", "measure_smoothness.sh", "project_config.sh")
METRICS = baseline.METRICS
LOCK_FDS = ()
UMASK = 0


def code_hashes():
    return {**baseline.code_hashes(), Path(__file__).name: baseline.digest(Path(__file__))}


def tools_contract():
    tools = baseline.tools_contract()
    blur = shutil.which("3dBlurToFWHM")
    if not blur:
        raise ValueError("3dBlurToFWHM is unavailable")
    tools["3dBlurToFWHM"] = {"path": str(Path(blur).resolve()), "sha256": baseline.digest(blur)}
    return tools


def get_baseline(folder):
    return baseline.load_plan(SimpleNamespace(output=folder))


def result_path(output, row):
    return output / "runs" / baseline.label(row)


def image_name(row):
    return f"{baseline.label(row)}_space-{baseline.SPACE}_desc-smoothToFWHM6_bold.nii.gz"


def baseline_result(folder, data, row, hash_inputs=False):
    directory = folder / "runs" / baseline.label(row)
    receipt_path = directory / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    hashes = baseline.signatures(row) if hash_inputs else receipt["input_hashes"]
    measured = baseline.validate_existing(directory, row, data, hashes)
    return measured, hashes, baseline.digest(receipt_path)


def plan(args):
    if (args.output / "plan.json").exists():
        raise ValueError("Evaluation plan exists; resume run/check, never overwrite it")
    data = get_baseline(args.baseline)
    if data["project"] != str(args.project):
        raise ValueError("Baseline belongs to a different project")
    tools = tools_contract()
    if any(tools[k] != v for k, v in data["tools"].items()):
        raise ValueError("Use the same AFNI measurement executables as the baseline")
    if baseline.digest(args.sharedreward_code / "measure_smoothness.sh") != data["wrapper_sha256"]:
        raise ValueError("Shared Reward measurement wrapper differs from the completed baseline")
    rows = []
    for source in data["rows"]:
        row = dict(source)
        if row["status"] == "source_excluded":
            row["evaluation_action"] = "source_excluded"
        elif row["status"] != "ready":
            raise ValueError(f"Unresolved baseline input: {baseline.label(row)}")
        else:
            measured, hashes, receipt_sha = baseline_result(args.baseline, data, row)
            row.update(before=measured, input_hashes=hashes, baseline_receipt_sha256=receipt_sha)
            row["evaluation_action"] = ("hold_at_or_above_target" if
                                        float(measured["classic_fwhm_combined"]) >= TARGET else "smooth")
        rows.append(row)
    frozen = args.output / "code"
    frozen.mkdir(exist_ok=True)
    for name in SCRIPTS:
        (frozen / name).write_bytes((args.sharedreward_code / name).read_bytes())
    provenance = {"schema": 1, "project": str(args.project), "baseline": str(args.baseline),
                  "baseline_plan_sha256": baseline.digest(args.baseline / "plan.json"),
                  "target_mm": TARGET, "lower_mm": LOWER, "upper_mm": UPPER,
                  "code_sha256": code_hashes(), "tools": tools,
                  "wrappers": {name: baseline.digest(frozen / name) for name in SCRIPTS},
                  "wrapper_source": str(args.sharedreward_code), "rows": rows,
                  "eligibility_changes": False, "production_promotion": False,
                  "blurmaster": "default subset, identical to Shared Reward; no automatic bmall retry"}
    baseline.atomic_json(args.output / "plan.json", provenance)
    upper_tail(args.output, rows)
    print(f"Evaluation actions: {dict(Counter(r['evaluation_action'] for r in rows))}")
    print("PLAN ONLY: no BOLD images written. Full input hashes revalidated before smoothing.")
    return 0


def upper_tail(output, rows):
    measured = [r for r in rows if "before" in r]
    details = [{**{k: r[k] for k in (*baseline.KEYS, "software_era", "evaluation_action")},
                **r["before"], "any_axis_at_or_above_6": any(float(r["before"][f"classic_fwhm_{a}"]) >= TARGET
                                                           for a in "xyz")}
               for r in measured]
    baseline.write_tsv(output / "baseline_runs.tsv", details,
                       (*baseline.KEYS, "software_era", "evaluation_action", *METRICS,
                        "any_axis_at_or_above_6"))
    groups = defaultdict(list)
    for r in measured:
        groups[(r["task"], r["session"], r["software_era"])].append(r)
    summary = []
    for (task, session, era), group in sorted(groups.items()):
        values = [float(r["before"]["classic_fwhm_combined"]) for r in group]
        summary.append(dict(task=task, session=session, software_era=era, n_runs=len(values),
                            n_subjects=len({r["subject"] for r in group}),
                            **{f"p{q}": baseline.linear_quantile(values, q / 100) for q in (50, 90, 95, 99)},
                            maximum=max(values), n_ge_5p4=sum(v >= LOWER for v in values),
                            n_ge_6=sum(v >= TARGET for v in values), n_gt_6p6=sum(v > UPPER for v in values),
                            n_any_axis_ge_6=sum(any(float(r["before"][f"classic_fwhm_{a}"]) >= TARGET
                                                   for a in "xyz") for r in group)))
    if summary:
        baseline.write_tsv(output / "upper_tail.tsv", summary, tuple(summary[0]))
    text = ["# Baseline upper tail: classic combined FWHM (mm)", "",
            "Receipt/result hashes and live input stamps checked; full input hashing occurs before execution.",
            "All tasks/sessions; no age or QC-flag filtering. Source exclusions remain parked.",
            "At/above 6 mm: left unchanged for target review, not a new exclusion.",
            "Axis values are reported separately; a combined target does not guarantee isotropy.", "",
            "| Task | Session | Era | Runs | Subjects | P95 | P99 | Max | >=5.4 | >=6 | >6.6 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in summary:
        text.append(f"| {s['task']} | {s['session']} | {s['software_era']} | {s['n_runs']} | {s['n_subjects']} | "
                    f"{s['p95']:.3f} | {s['p99']:.3f} | {s['maximum']:.3f} | {s['n_ge_5p4']} | "
                    f"{s['n_ge_6']} | {s['n_gt_6p6']} |")
    text += ["", "## At/above-target runs (not smoothed)", ""]
    holds = [r for r in measured if r["evaluation_action"] == "hold_at_or_above_target"]
    text += [f"- {baseline.label(r)}: {float(r['before']['classic_fwhm_combined']):.4f} mm"
             for r in holds] or ["None."]
    (output / "upper_tail.md").write_text("\n".join(text) + "\n")
    print("\n".join(text), flush=True)


def load_plan(args):
    p = json.loads((args.output / "plan.json").read_text())
    if p["project"] != str(args.project) or p["baseline"] != str(args.baseline):
        raise ValueError("Project/baseline directory differs from frozen evaluation")
    if p["code_sha256"] != code_hashes() or p["tools"] != tools_contract():
        raise ValueError("Code or AFNI identity changed; existing evaluation preserved")
    if p["baseline_plan_sha256"] != baseline.digest(args.baseline / "plan.json"):
        raise ValueError("Baseline plan changed")
    for name, sha in p["wrappers"].items():
        if baseline.digest(args.output / "code" / name) != sha:
            raise ValueError("Frozen Shared Reward script changed")
    data = get_baseline(args.baseline)
    for row in p["rows"]:
        if "before" in row:
            values, hashes, receipt_sha = baseline_result(args.baseline, data, row)
            if (values != row["before"] or hashes != row["input_hashes"] or
                    receipt_sha != row["baseline_receipt_sha256"]):
                raise ValueError(f"Baseline result changed: {baseline.label(row)}")
    return p


def output_geometry(path, row):
    import nibabel as nib
    import numpy as np
    dimensions = baseline.geometry(str(path), row["input_mask"])
    image, original = nib.load(path), nib.load(row["input_bold"])
    if (image.shape != original.shape or
            not np.allclose(image.header.get_zooms(), original.header.get_zooms(), rtol=0, atol=1e-5)):
        raise ValueError("Smoothing changed volume count, grid spacing, or TR")
    if not np.isfinite(np.asarray(image.dataobj)).all():
        raise ValueError("Nonfinite output image values")
    return dimensions


def verify_run(output, row, p):
    directory = result_path(output, row)
    image = directory / image_name(row)
    receipt = json.loads((directory / "receipt.json").read_text())
    if (receipt["input_hashes"] != row["input_hashes"] or receipt["wrappers"] != p["wrappers"]
            or receipt["tools"] != p["tools"] or receipt["target_mm"] != TARGET
            or receipt["output_sha256"] != baseline.digest(image)
            or receipt["measurement_sha256"] != baseline.digest(directory / "after.tsv")):
        raise ValueError("Completed result lineage/hash mismatch; preserved for review")
    measured_path = Path(receipt["measured_path"])
    if measured_path.name != image_name(row) or output / "attempts" not in measured_path.parents:
        raise ValueError("Invalid original measurement path")
    values = baseline.read_result(directory / "after.tsv",
                                  {"input_bold": str(measured_path), "input_mask": row["input_mask"]})
    output_geometry(image, row)
    return values


def smooth_one(output, row, p, threads):
    try:
        print(f"STARTED {baseline.label(row)}", flush=True)
        if baseline.signatures(row) != row["input_hashes"]:
            raise ValueError("Live input hashes differ from baseline")
        directory = result_path(output, row)
        if directory.exists():
            values = verify_run(output, row, p)
            return "verified", values
        baseline.geometry(row["input_bold"], row["input_mask"])
        attempt = Path(tempfile.mkdtemp(prefix=baseline.label(row) + "-", dir=output / "attempts"))
        attempt.chmod(0o777 & ~UMASK)
        image = attempt / image_name(row)
        command = ["bash", str(output / "code/smooth_to_target.sh"), "--input", row["input_bold"],
                   "--mask", row["input_mask"], "--output", str(image), "--target", "6",
                   "--qc-tsv", str(attempt / "after.tsv"), "--work-dir", str(attempt)]
        env = {**os.environ, "AFNI_OMP_NUM_THREADS": str(threads), "OMP_NUM_THREADS": str(threads),
               "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        with (attempt / "command.log").open("w") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, pass_fds=LOCK_FDS)
        if result.returncode:
            raise ValueError(f"AFNI exit {result.returncode}; see {attempt / 'command.log'}")
        values = baseline.read_result(attempt / "after.tsv",
                                      {"input_bold": str(image), "input_mask": row["input_mask"]})
        dimensions = output_geometry(image, row)
        if baseline.signatures(row) != row["input_hashes"]:
            raise ValueError("Input changed during smoothing")
        baseline.atomic_json(attempt / "receipt.json", {
            "input_hashes": row["input_hashes"], "wrappers": p["wrappers"], "tools": p["tools"],
            "target_mm": TARGET, "measured_path": str(image), "output_sha256": baseline.digest(image),
            "measurement_sha256": baseline.digest(attempt / "after.tsv"), "geometry": dimensions})
        # Preserve valid measurements even outside tolerance; never retry them automatically.
        os.replace(attempt, directory)
        return "completed", values
    except Exception as exc:
        return "failed", str(exc)


def run(args):
    p = load_plan(args)
    for folder in ("attempts", "runs"):
        (args.output / folder).mkdir(exist_ok=True)
    rows = [r for r in p["rows"] if r["evaluation_action"] == "smooth"]
    # Float output worst-case estimate, rather than assuming input compression ratios.
    estimated = 0
    import nibabel as nib
    import math
    for row in rows:
        if not result_path(args.output, row).exists():
            estimated += math.prod(nib.load(row["input_bold"]).shape) * 4
    if shutil.disk_usage(args.output).free < estimated * 1.2:
        raise ValueError(f"Insufficient free space for conservative {estimated / 2**30:.1f} GiB output estimate")
    print(f"6-mm evaluation: {len(rows)} runs; jobs={args.jobs}; threads/job={args.threads}; no overwrite", flush=True)
    print(f"Remaining uncompressed float-output estimate: {estimated / 2**30:.1f} GiB", flush=True)
    counts = Counter()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(smooth_one, args.output, row, p, args.threads): row for row in rows}
        for n, future in enumerate(as_completed(futures), 1):
            status, detail = future.result()
            counts[status] += 1
            if status != "failed":
                value = float(detail["classic_fwhm_combined"])
                detail = f"classic={value:.5f} mm; " + ("within tolerance" if LOWER <= value <= UPPER else "TARGET REVIEW REQUIRED")
            print(f"{status.upper()} {baseline.label(futures[future])} ({n}/{len(rows)}): {detail}", flush=True)
    print(f"Smoothing processing outcomes: {dict(counts)}")
    return int(bool(counts["failed"]))


def check(args):
    p = load_plan(args)
    rows = []
    for n, source in enumerate(p["rows"], 1):
        row = dict(source)
        row.update(status=row["evaluation_action"], reason="", after={})
        try:
            if "before" in row and baseline.signatures(row) != row["input_hashes"]:
                raise ValueError("Input hashes changed")
            if row["evaluation_action"] == "smooth":
                row["after"] = verify_run(args.output, row, p)
                value = float(row["after"]["classic_fwhm_combined"])
                row["status"] = "within_tolerance" if LOWER <= value <= UPPER else "outside_tolerance"
        except Exception as exc:
            row.update(status="failed", reason=str(exc), after={})
        rows.append(row)
        if n % 100 == 0:
            print(f"VERIFY {n}/{len(p['rows'])}", flush=True)
    report(args.output, rows)
    counts = Counter(r["status"] for r in rows)
    reviews = counts["outside_tolerance"] + counts["hold_at_or_above_target"]
    state = {"counts": dict(counts), "technical_complete": not counts["failed"],
             "all_active_runs_within_target": not counts["failed"] and not reviews,
             "eligibility_changed": False, "production_promoted": False}
    baseline.atomic_json(args.output / "validation.json", state)
    print(f"Evaluation outcomes: {dict(counts)}")
    if counts["failed"]:
        print("CHECK FAILED: missing/invalid processing results; inspect run_results.tsv")
    elif reviews:
        print("EVALUATION COMPLETE; TARGET REVIEW REQUIRED: held/out-of-band runs are not exclusions.")
    else:
        print("CHECK PASSED: all active runs have verified 6-mm outputs within 5.4-6.6 mm")
    return int(bool(counts["failed"] or reviews))


def report(output, rows):
    flat = []
    for r in rows:
        flat.append({**{k: r.get(k, "") for k in (*baseline.KEYS, "software_era", "status", "reason",
                                                "qc_status", "imaging_qc_outlier", "input_bold", "input_mask")},
                     **{f"{stage}_{m}": r.get(stage, {}).get(m, "") for stage in ("before", "after") for m in METRICS},
                     "output_bold": str(result_path(output, r) / image_name(r)) if r.get("after") else ""})
    baseline.write_tsv(output / "run_results.tsv", flat, tuple(flat[0]))
    groups = defaultdict(list)
    for row in rows:
        if "before" in row:
            groups[(row["task"], row["session"], row["software_era"])].append(row)
    summary = []
    text = ["# Isolated 6-mm smoothing evaluation", "",
            "No existing images, QC policies, settled exclusions, manifests, or task models changed.",
            "Paired results include valid outside-tolerance outputs; no successful-only selection.",
            "Held runs have baseline values only; they were not smoothed or assigned synthetic after values.",
            "Classic combined FWHM is the target. ACF is diagnostic and has no 6-mm acceptance band.",
            "Repeated runs are not independent participants. Before/after comparisons use identical paired run sets.", "",
            "| Task | Session | Era | Baseline runs | Paired | Paired subjects | Held | Failed | Outside band | Classic before | Classic after | ACF before | ACF after |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for (task, session, era), group in sorted(groups.items()):
        paired = [r for r in group if r.get("after")]
        counts = Counter(r["status"] for r in group)
        common = dict(task=task, session=session, software_era=era, n_baseline=len(group), n_paired=len(paired),
                      n_subjects=len({r["subject"] for r in paired}), n_held=counts["hold_at_or_above_target"],
                      n_failed=counts["failed"], n_outside=counts["outside_tolerance"])
        medians = {}
        for metric in METRICS:
            item = {**common, "metric": metric}
            for stage in ("before", "after"):
                values = [float(r[stage][metric]) for r in paired]
                for name, q in (("median", .5), ("q1", .25), ("q3", .75)):
                    item[f"{stage}_{name}"] = baseline.linear_quantile(values, q) if values else ""
                medians[stage, metric] = item[f"{stage}_median"]
            summary.append(item)
        nums = [medians[s, m] for m in ("classic_fwhm_combined", "acf_effective_fwhm") for s in ("before", "after")]
        fmt = lambda x: f"{x:.3f}" if isinstance(x, (float, int)) else "NA"
        text.append(f"| {task} | {session} | {era} | {len(group)} | {len(paired)} | {common['n_subjects']} | "
                    f"{common['n_held']} | {common['n_failed']} | {common['n_outside']} | " + " | ".join(map(fmt, nums)) + " |")
    if summary:
        baseline.write_tsv(output / "paired_summary.tsv", summary, tuple(summary[0]))
    (output / "report.md").write_text("\n".join(text) + "\n")
    plots(output, rows)
    print("\n".join(text), flush=True)


def plots(output, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    folder = output / "figures"
    folder.mkdir(exist_ok=True)
    colors = dict(zip(ERAS, ("#258179", "#b86d21", "#7051a3", "#777777")))
    for task, session in sorted({(r["task"], r["session"]) for r in rows if "before" in r}):
        group = [r for r in rows if (r["task"], r["session"]) == (task, session) and "before" in r]
        fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
        for era in ERAS:
            values = sorted(float(r["before"]["classic_fwhm_combined"]) for r in group if r["software_era"] == era)
            if values:
                ax.step(values, np.arange(1, len(values) + 1) / len(values), where="post", color=colors[era], label=f"{era}: n={len(values)}")
        ax.axvline(TARGET, color="black", linestyle="--", label="6-mm target")
        ax.set(xlabel="Baseline classic combined FWHM (mm)", ylabel="Cumulative fraction of runs",
               title=f"{task}, ses-{session}: full baseline distribution")
        ax.legend()
        fig.savefig(folder / f"task-{task}_ses-{session}_baseline.png", dpi=150)
        plt.close(fig)
        paired = [r for r in group if r.get("after")]
        if not paired:
            fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
            ax.axis("off")
            ax.text(.5, .5, "No validated paired outputs\nSee run_results.tsv for held/failed cases",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_title(f"{task}, ses-{session}: before/after comparison unavailable")
            fig.savefig(folder / f"task-{task}_ses-{session}_before_after.png", dpi=150)
            plt.close(fig)
            continue
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
        for col, (metric, title) in enumerate((("classic_fwhm_combined", "Classic combined FWHM"),
                                              ("acf_effective_fwhm", "ACF effective FWHM"))):
            boxes, labels, box_colors = [], [], []
            for era in ERAS:
                selected = [r for r in paired if r["software_era"] == era]
                if not selected:
                    continue
                before = [float(r["before"][metric]) for r in selected]
                after = [float(r["after"][metric]) for r in selected]
                boxes.extend((before, after))
                labels.extend((f"{era}\nbefore\nn={len(selected)}", f"{era}\nafter\nn={len(selected)}"))
                box_colors.extend((colors[era], colors[era]))
                axes[1, col].scatter(before, after, color=colors[era], alpha=.5, s=14, label=era)
            plotted = axes[0, col].boxplot(boxes, patch_artist=True)
            for patch, color in zip(plotted["boxes"], box_colors):
                patch.set_facecolor(color)
                patch.set_alpha(.4)
            axes[0, col].set_xticks(range(1, len(labels) + 1))
            axes[0, col].set_xticklabels(labels, fontsize=8)
            axes[0, col].set(title=title, ylabel="mm")
            axes[1, col].set(xlabel="Before (mm)", ylabel="After (mm)")
            limits = [float(r[s][metric]) for r in paired for s in ("before", "after")]
            lo, hi = min(limits) * .95, max(limits) * 1.05
            axes[1, col].plot([lo, hi], [lo, hi], color="grey", linestyle=":", linewidth=1)
            axes[1, col].set(xlim=(lo, hi), ylim=(lo, hi))
            axes[1, col].legend()
            if col == 0:
                for ax in (axes[0, col], axes[1, col]):
                    ax.axhspan(LOWER, UPPER, color="grey", alpha=.12)
                    ax.axhline(TARGET, color="black", linestyle="--", linewidth=1)
        held = sum(r["status"] == "hold_at_or_above_target" for r in group)
        failed = sum(r["status"] == "failed" for r in group)
        fig.suptitle(f"{task}, ses-{session}: {len(paired)} paired runs; {held} held, {failed} failed\n"
                     "Valid outside-tolerance outputs included; band applies to classic after values only")
        fig.savefig(folder / f"task-{task}_ses-{session}_before_after.png", dpi=150)
        plt.close(fig)


def main():
    global LOCK_FDS, UMASK
    UMASK = os.umask(0)
    os.umask(UMASK)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run", "check"))
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--baseline", type=Path, default=ROOT / "work/cohort-smoothness-v1")
    parser.add_argument("--output", type=Path, default=ROOT / "derivatives/smoothness-evaluation-6mm-v1")
    parser.add_argument("--sharedreward-code", type=Path, default=Path("/ZPOOL/data/projects/rf1-sra-sharedreward/code"))
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    for name in ("project", "baseline", "output", "sharedreward_code"):
        setattr(args, name, getattr(args, name).resolve())
    if (args.output.parent != args.project / "derivatives" or
            not args.output.name.startswith("smoothness-evaluation-6mm-") or
            args.project / "work" not in args.baseline.parents):
        parser.error("Use a dedicated derivatives/smoothness-evaluation-6mm-* directory and work/ baseline")
    if args.jobs < 1 or args.threads < 1:
        parser.error("jobs and threads must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        with ExitStack() as stack:
            locks = [stack.enter_context((folder / ".lock").open("a")) for folder in (args.baseline, args.output)]
            for lock in locks:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            LOCK_FDS = tuple(lock.fileno() for lock in locks)
            return {"plan": plan, "run": run, "check": check}[args.command](args)
    except (OSError, ValueError, KeyError) as exc:
        print(f"STOPPED: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
