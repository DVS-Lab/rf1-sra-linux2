"""Plot session-01 medians from the published matched TEDANA cohort report."""
import argparse
import csv
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "logs/records/20261120-102748_tedana-era-results-20261120-102748.md"
OUTPUT = ROOT / "qc/tedana_audit/scanner_era/figures/pca_rejections_ses-01.png"
TASKS = {"doors": "Doors", "socialdoors": "Social Doors", "sharedreward": "Shared Reward",
         "trust": "Trust", "ugr": "UGR"}
STYLES = {"E11": ("#3069a2", "o", "-"), "XA30": ("#218773", "^", "--"),
          "XA60": ("#c04a54", "s", "-")}
METHODS = ("AIC", "KIC", "MDL")


def load_record(path):
    text = path.read_text()
    verified = re.search(r"^Verified (\d+) complete matched runs\.", text, re.M)
    if not verified or "\nCOMMAND EXIT: 0\n" not in text:
        raise ValueError("Not a completed matched-run report")
    table = text[text.index("session\ttask\tscanner_software\t"):].split("\n\n", 1)[0]
    rows = list(csv.DictReader(table.splitlines(), delimiter="\t"))
    if sum(int(r["runs"]) for r in rows) != int(verified[1]):
        raise ValueError("Table run count differs from verification")
    wave1 = [r for r in rows if r["session"] == "01"]
    cells = {(r["task"], r["scanner_software"].removeprefix("syngo MR ")): r for r in wave1}
    if len(cells) != len(wave1) or set(cells) != {(t, e) for t in TASKS for e in STYLES}:
        raise ValueError("Unexpected or duplicate session-01 task/era strata")
    return cells


def plot(cells, out):
    fig, axs = plt.subplots(2, 5, figsize=(12, 5.6), sharex=True, sharey="row")
    fig.subplots_adjust(left=.075, right=.985, bottom=.15, top=.78, hspace=.25, wspace=.13)
    fig.suptitle("MDL reduces rejected counts, but XA60 still rejects a larger share",
                 x=.075, y=.97, ha="left", fontsize=16, fontweight="bold")
    n = sum(int(r["runs"]) for r in cells.values())
    fig.text(.075, .87, f"Session 01   |   {n:,} runs   |   Medians across runs within each task and scanner era", fontsize=11)
    for j, (task, name) in enumerate(TASKS.items()):
        axs[0, j].set_title(name, fontsize=11, fontweight="bold")
        for ax, field in zip(axs[:, j], ("rejected", "rejected_pct")):
            for era, (color, marker, ls) in STYLES.items():
                row = cells[task, era]
                ax.plot(METHODS, [float(row[f"{m}_{field}"]) for m in METHODS],
                        label=era, color=color, marker=marker, ls=ls, lw=2, ms=5)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.grid(axis="y", color="#e3e5e8")
            ax.set_axisbelow(True)
            ax.tick_params(length=0, pad=4, labelsize=9)
            ax.margins(x=.13)
    axs[0, 0].set(ylim=(0, 35), yticks=(0, 10, 20, 30), ylabel="Rejected components")
    axs[1, 0].set(ylim=(0, 80), yticks=(0, 20, 40, 60, 80), ylabel="Percentage rejected")
    axs[1, 0].yaxis.set_major_formatter(PercentFormatter(100))
    handles, labels = axs[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(.5, .015))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=RECORD)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    plot(load_record(args.record), args.output)
