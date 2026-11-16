#!/usr/bin/env python3
"""Plot the published paired AFNI summaries without reading or changing images."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASKS = {"doors": "Doors", "socialdoors": "Social Doors", "sharedreward": "Shared Reward",
         "trust": "Trust", "ugr": "UGR"}
ERAS = {"E11": "#3069a2", "XA30": "#218773", "XA60": "#c04a54"}
METRICS = {"classic_fwhm_combined": ("classic", "Classic combined FWHM (mm)"),
           "acf_effective_fwhm": ("acf", "ACF effective FWHM (mm)")}


def load_summary(path):
    with path.open() as handle:
        rows = [r for r in csv.DictReader(handle, delimiter="\t") if r["metric"] in METRICS]
    seen = set()
    for row in rows:
        key = tuple(row[f] for f in ("task", "session", "software_era", "metric"))
        if key in seen:
            raise ValueError("Duplicate summary cell: " + str(key))
        seen.add(key)
        if row["task"] not in TASKS or row["software_era"] not in ERAS:
            raise ValueError("Unrecognized task/era; update labels rather than silently omit")
        for name in ("n_baseline", "n_paired", "n_subjects", "n_held", "n_failed", "n_outside"):
            row[name] = int(row[name])
            if row[name] < 0:
                raise ValueError("Negative count")
        if not 0 < row["n_subjects"] <= row["n_paired"] <= row["n_baseline"]:
            raise ValueError("Invalid paired sample counts")
        for stage in ("before", "after"):
            for stat in ("q1", "median", "q3"):
                field = f"{stage}_{stat}"
                row[field] = float(row[field])
                if not math.isfinite(row[field]) or row[field] <= 0:
                    raise ValueError("Nonpositive/nonfinite smoothness")
            if not row[f"{stage}_q1"] <= row[f"{stage}_median"] <= row[f"{stage}_q3"]:
                raise ValueError("Invalid quartile order")
    if not rows:
        raise ValueError("No paired summaries")
    for task, session, era in {key[:3] for key in seen}:
        group = [r for r in rows if (r["task"], r["session"], r["software_era"]) == (task, session, era)]
        if {r["metric"] for r in group} != set(METRICS):
            raise ValueError("Missing metric for task/session/era")
        for field in ("n_baseline", "n_paired", "n_subjects", "n_held", "n_failed", "n_outside"):
            if len({r[field] for r in group}) != 1:
                raise ValueError("Metric sample counts disagree")
    return rows


def era_gaps(rows):
    result = []
    for session, task, metric in sorted({(r["session"], r["task"], r["metric"]) for r in rows}):
        group = [r for r in rows if (r["session"], r["task"], r["metric"]) == (session, task, metric)]
        if len(group) < 2:
            continue
        before = max(r["before_median"] for r in group) - min(r["before_median"] for r in group)
        after = max(r["after_median"] for r in group) - min(r["after_median"] for r in group)
        result.append(dict(session=session, task=task, metric=metric,
                           eras=";".join(r["software_era"] for r in group),
                           before_era_median_range_mm=before, after_era_median_range_mm=after,
                           range_reduction_pct=100 * (1 - after / before) if before > 0 else None))
    return result


def plot(rows, session, metric, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    selected = [r for r in rows if r["session"] == session and r["metric"] == metric]
    tasks = [t for t in TASKS if any(r["task"] == t for r in selected)]
    eras = [e for e in ERAS if any(r["software_era"] == e for r in selected)]
    classic = metric == "classic_fwhm_combined"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.1), sharey=True)
    fig.subplots_adjust(left=.075, right=.98, bottom=.29, top=.73, wspace=.12)
    fig.text(.075, .955, "Scanner-era smoothness before and after AFNI", fontsize=21, weight="bold", va="top")
    subtitle = ("Classic FWHM converges near the 6-mm target" if classic else
                "Residual ACF differences remain; this metric was not targeted at 6 mm")
    fig.text(.075, .885, f"Session {session}  |  {subtitle}", fontsize=12, color="#444444")
    handles = [Line2D([], [], color=ERAS[e], marker="o", linewidth=1.5, label=e) for e in eras]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.068, .855), ncol=len(eras), frameon=False)
    low = min(r[f"{stage}_q1"] for r in selected for stage in ("before", "after"))
    high = max(r[f"{stage}_q3"] for r in selected for stage in ("before", "after"))
    if classic:
        high = max(high, 6)
    margin = max(.25, (high - low) * .12)
    for ax, stage, title in zip(axes, ("before", "after"), ("Before: fMRIPrep output", "After: AFNI 3dBlurToFWHM")):
        ax.set_title(title, loc="left", pad=12, fontsize=13)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#e1e4e8", linewidth=.8)
        for i, task in enumerate(tasks):
            for j, era in enumerate(eras):
                matches = [r for r in selected if r["task"] == task and r["software_era"] == era]
                if not matches:
                    continue
                row = matches[0]
                m, q1, q3 = (row[f"{stage}_{s}"] for s in ("median", "q1", "q3"))
                ax.errorbar(i + .19 * (j - (len(eras) - 1) / 2), m,
                            yerr=[[m - q1], [q3 - m]], fmt="o", color=ERAS[era],
                            markersize=6, capsize=4, elinewidth=2, markeredgecolor="white", markeredgewidth=.5)
        ax.set_xticks(range(len(tasks)), [TASKS[t].replace(" ", "\n") for t in tasks])
        ax.tick_params(axis="x", length=0, pad=9)
        ax.set_xlim(-.5, len(tasks) - .5)
        ax.set_ylim(low - margin, high + margin)
        if classic:
            ax.axhline(6, color="#444444", linestyle="--", linewidth=1)
            ax.text(.98, 6.035, "6-mm target", transform=ax.get_yaxis_transform(), ha="right", fontsize=10, color="#444444")
    axes[0].set_ylabel(METRICS[metric][1])
    count = sum(r["n_paired"] for r in selected)
    fig.text(.075, .16, f"Points: run-level medians. Bars: interquartile ranges, not confidence intervals. Same {count:,} runs before/after.", fontsize=10)
    fig.text(.075, .115, "Independent 3dFWHMx estimates on BOLD; identical y-axis scales. Repeated runs are not independent participants.", fontsize=10, color="#444444")
    note = ("Session 02 XA30 contains one participant per task; interpret that comparison cautiously."
            if session == "02" else "Original completed evaluation, including slightly off-target runs; no new exclusions or replacement by retry results.")
    fig.text(.075, .07, note, fontsize=10, color="#444444")
    path = destination / f"ses-{session}_{METRICS[metric][0]}_before_after.png"
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)
    return path.name


def build(summary, validation, output):
    rows = load_summary(summary)
    state = json.loads(validation.read_text())
    if state.get("technical_complete") is not True:
        raise ValueError("Evaluation is not technically complete")
    classic = [r for r in rows if r["metric"] == "classic_fwhm_combined"]
    counts = state["counts"]
    if (sum(r["n_paired"] for r in classic) != counts["within_tolerance"] + counts["outside_tolerance"]
            or sum(r["n_outside"] for r in classic) != counts["outside_tolerance"]):
        raise ValueError("Published validation and summary counts disagree")
    output.mkdir(parents=True, exist_ok=True)
    figures = [plot(rows, session, metric, output) for session in sorted({r["session"] for r in rows}) for metric in METRICS]
    gaps = era_gaps(rows)
    with (output / "era_median_gaps.tsv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(gaps[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(gaps)
    text = ["# Scanner-era smoothness: before and after AFNI", "",
            "Report-only replot of the completed isolated 6-mm evaluation. No image processing,",
            "eligibility decisions, or analysis inputs changed. Figures use the published run-level",
            "medians and interquartile ranges, not reconstructed raw distributions or confidence intervals.", "",
            "Baseline is unsmoothed non-echo fMRIPrep MNI BOLD, **not raw BIDS/MRIQC**.",
            "After is the original AFNI `3dBlurToFWHM` 6-mm-target output, independently measured",
            "with the frozen Shared Reward `3dFWHMx -ShowMeClassicFWHM -detrend -mask ... -acf NULL` method.",
            "Classic combined FWHM and ACF effective FWHM are different measures. Only classic FWHM",
            "was targeted; these are BOLD smoothness estimates, not task-model residual estimates.", "",
            f"All {sum(r['n_paired'] for r in classic):,} paired runs are represented, including the {counts['outside_tolerance']} original",
            "outside-band outputs. No successful-only filtering or substitution of 10657 `-bmall`",
            "retry values. That retry changed the five estimates little and is a separate experiment.",
            f"The validation separately records {counts.get('source_excluded', 0)} source-excluded entries without paired estimates.",
            "Existing source/task exclusions remain binding; measurement inclusion does not grant analysis eligibility.", "",
            "## Figures", ""]
    for name in figures:
        text += [f"![{name.removesuffix('.png').replace('_', ' ')}]({name})", ""]
    text += ["## Scanner-era separation", "",
             "Range = largest minus smallest scanner-era median **within the same task/session**.",
             "Reduction describes this median separation, not variance explained, statistical significance,",
             "or proof that scanner software caused the difference. Do not pool tasks or sessions.", "",
             "| Session | Task | Metric | Before range (mm) | After range (mm) | Reduction |",
             "|---|---|---|---:|---:|---:|"]
    for row in gaps:
        reduction = "NA" if row["range_reduction_pct"] is None else f"{row['range_reduction_pct']:.1f}%"
        text.append(f"| {row['session']} | {TASKS[row['task']]} | {METRICS[row['metric']][0]} | "
                    f"{row['before_era_median_range_mm']:.4f} | {row['after_era_median_range_mm']:.4f} | {reduction} |")
    text += ["", "## Sample sizes", "", "Counts are runs / participants within each cell; do not sum subjects across tasks.",
             "Session 02 has only one XA30 participant per task (two UGR runs).", "",
             "| Session | Task | Era | Paired runs | Participants | Outside original band |",
             "|---|---|---|---:|---:|---:|"]
    for row in classic:
        text.append(f"| {row['session']} | {TASKS[row['task']]} | {row['software_era']} | "
                    f"{row['n_paired']} | {row['n_subjects']} | {row['n_outside']} |")
    text += ["", "## Reproduce", "", "From the repository root:", "", "```bash",
             "umask 0000", "python3 code/plot_smoothness_era_overview.py", "```", "",
             "Requires matplotlib. Reads only the tracked summary and validation JSON; no Linux2 imaging access is needed.",
             "Sources: [paired summary](../paired_summary.tsv), [validation](../validation.json),",
             "[measurement method](../../../docs/cohort-afni-smoothness.md).", ""]
    (output / "README.md").write_text("\n".join(text))
    provenance = dict(summary_sha256=hashlib.sha256(summary.read_bytes()).hexdigest(),
                      validation_sha256=hashlib.sha256(validation.read_bytes()).hexdigest(),
                      script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      aggregation="published_run_median_and_IQR", figures=figures,
                      original_evaluation=True, bmall_retry_substituted=False, exclusions_changed=False)
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(figures)} figures and descriptive era-gap table to {output}")
    for row in gaps:
        if row["session"] == "01":
            print(f"{row['task']} {METRICS[row['metric']][0]}: "
                  f"{row['before_era_median_range_mm']:.4f} -> {row['after_era_median_range_mm']:.4f} mm "
                  f"({row['range_reduction_pct']:.1f}% reduction)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / "qc/smoothness_evaluation_6mm/paired_summary.tsv")
    parser.add_argument("--validation", type=Path, default=ROOT / "qc/smoothness_evaluation_6mm/validation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "qc/smoothness_evaluation_6mm/scanner_era_overview")
    args = parser.parse_args()
    build(args.summary, args.validation, args.output)
