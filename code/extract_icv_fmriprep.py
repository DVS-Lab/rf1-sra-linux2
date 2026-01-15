#!/usr/bin/env python3
"""
Extract (approx.) intracranial volume across subjects in an fMRIPrep directory.

Preferred method:
  ICV ≈ sum(GM_probseg + WM_probseg + CSF_probseg) * voxel_volume

Fallback:
  Brain volume ≈ count(desc-brain_mask > 0) * voxel_volume

Outputs:
  - icv_volumes.csv
  - icv_histogram.png
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
import nibabel as nib
import matplotlib.pyplot as plt


SUB_RE = re.compile(r"(sub-[a-zA-Z0-9]+)")
SES_RE = re.compile(r"(ses-[a-zA-Z0-9]+)")


def parse_entities(p: Path) -> tuple[str | None, str | None]:
    s = str(p)
    sub = SUB_RE.search(s)
    ses = SES_RE.search(s)
    return (sub.group(1) if sub else None, ses.group(1) if ses else None)


def voxel_volume_mm3(img: nib.Nifti1Image) -> float:
    zooms = img.header.get_zooms()[:3]
    return float(np.prod(zooms))


def compute_from_probsegs(gm_path: Path, wm_path: Path, csf_path: Path) -> float:
    gm_img = nib.load(str(gm_path))
    wm_img = nib.load(str(wm_path))
    csf_img = nib.load(str(csf_path))

    gm = np.asanyarray(gm_img.dataobj, dtype=np.float32)
    wm = np.asanyarray(wm_img.dataobj, dtype=np.float32)
    csf = np.asanyarray(csf_img.dataobj, dtype=np.float32)

    if gm.shape != wm.shape or gm.shape != csf.shape:
        raise ValueError("GM/WM/CSF probseg shapes do not match.")

    v_mm3 = voxel_volume_mm3(gm_img)

    # Expected intracranial “soft count”
    soft_voxels = np.sum(gm + wm + csf)

    # Convert mm^3 -> mL (1 mL = 1000 mm^3)
    return (soft_voxels * v_mm3) / 1000.0


def compute_from_brainmask(mask_path: Path, threshold: float = 0.0) -> float:
    mask_img = nib.load(str(mask_path))
    mask = np.asanyarray(mask_img.dataobj)

    v_mm3 = voxel_volume_mm3(mask_img)
    n_vox = np.count_nonzero(mask > threshold)

    return (n_vox * v_mm3) / 1000.0


def find_native_probseg_sets(fmriprep_dir: Path) -> list[dict]:
    """
    Finds sets of GM/WM/CSF probsegs in native (T1w) space.
    We skip files that include 'space-' to avoid MNI versions by default.
    """
    gm_files = sorted(fmriprep_dir.rglob("*_label-GM_probseg.nii.gz"))

    sets = []
    for gm in gm_files:
        if "space-" in gm.name:
            continue

        wm = Path(str(gm).replace("_label-GM_probseg.nii.gz", "_label-WM_probseg.nii.gz"))
        csf = Path(str(gm).replace("_label-GM_probseg.nii.gz", "_label-CSF_probseg.nii.gz"))

        if wm.exists() and csf.exists():
            sets.append({"gm": gm, "wm": wm, "csf": csf})

    return sets


def find_native_brainmasks(fmriprep_dir: Path) -> list[Path]:
    masks = sorted(fmriprep_dir.rglob("*_desc-brain_mask.nii.gz"))
    # Prefer native (no 'space-') if both exist
    masks = [m for m in masks if "space-" not in m.name]
    return masks


def size_bin(volume: float, q25: float, q50: float, q75: float) -> str:
    if volume < q25:
        return "small"
    elif volume < q50:
        return "medium"
    elif volume < q75:
        return "large"
    else:
        return "extra_large"


def main():
    ap = argparse.ArgumentParser(
        description="Extract approximate intracranial volume (ICV) from fMRIPrep outputs."
    )
    ap.add_argument(
        "fmriprep_dir",
        type=str,
        help="Path to fMRIPrep derivatives directory (e.g., derivatives/fmriprep-24)",
    )
    ap.add_argument(
        "--out_csv",
        type=str,
        default="icv_volumes.csv",
        help="Output CSV filename",
    )
    ap.add_argument(
        "--out_png",
        type=str,
        default="icv_histogram.png",
        help="Output histogram PNG filename",
    )
    ap.add_argument(
        "--aggregate",
        choices=["none", "subject"],
        default="subject",
        help="If 'subject', average across sessions/runs per subject before plotting.",
    )
    ap.add_argument(
        "--force_brainmask",
        action="store_true",
        help="Force using brain masks even if tissue probsegs exist (this gives brain volume, not ICV).",
    )
    args = ap.parse_args()

    fmriprep_dir = Path(args.fmriprep_dir).resolve()
    if not fmriprep_dir.exists():
        raise FileNotFoundError(f"Directory not found: {fmriprep_dir}")

    rows = []

    # --- Prefer probseg-based ICV ---
    if not args.force_brainmask:
        probseg_sets = find_native_probseg_sets(fmriprep_dir)
    else:
        probseg_sets = []

    if probseg_sets:
        for s in probseg_sets:
            sub, ses = parse_entities(s["gm"])
            try:
                vol_ml = compute_from_probsegs(s["gm"], s["wm"], s["csf"])
                rows.append(
                    {
                        "subject": sub,
                        "session": ses,
                        "method": "GM+WM+CSF_probseg (ICV-ish)",
                        "volume_ml": vol_ml,
                        "source_path": str(s["gm"]),
                    }
                )
            except Exception as e:
                rows.append(
                    {
                        "subject": sub,
                        "session": ses,
                        "method": "GM+WM+CSF_probseg (FAILED)",
                        "volume_ml": np.nan,
                        "source_path": str(s["gm"]),
                        "error": str(e),
                    }
                )

    # --- Fallback to brain masks ---
    if not rows:
        masks = find_native_brainmasks(fmriprep_dir)
        if not masks:
            raise RuntimeError(
                "Found no probsegs and no native brain masks. "
                "Check that you're pointing at the fMRIPrep derivatives folder."
            )

        for m in masks:
            sub, ses = parse_entities(m)
            try:
                vol_ml = compute_from_brainmask(m, threshold=0.0)
                rows.append(
                    {
                        "subject": sub,
                        "session": ses,
                        "method": "desc-brain_mask (brain volume)",
                        "volume_ml": vol_ml,
                        "source_path": str(m),
                    }
                )
            except Exception as e:
                rows.append(
                    {
                        "subject": sub,
                        "session": ses,
                        "method": "desc-brain_mask (FAILED)",
                        "volume_ml": np.nan,
                        "source_path": str(m),
                        "error": str(e),
                    }
                )

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["volume_ml"]).copy()

    # Clean out any missing subject labels
    df = df[df["subject"].notna()].copy()

    if df.empty:
        raise RuntimeError("No valid volumes computed (all failed or missing).")

    # Aggregate per subject if desired
    if args.aggregate == "subject":
        df_plot = (
            df.groupby("subject", as_index=False)
            .agg(volume_ml=("volume_ml", "mean"))
            .sort_values("subject")
        )
        plot_label = "Subject-level mean volume (mL)"
    else:
        df_plot = df.copy()
        plot_label = "Volume (mL)"

    # Percentiles and bins
    vols = df_plot["volume_ml"].to_numpy()
    pcts = [10, 25, 50, 75, 90]
    pvals = np.percentile(vols, pcts)

    q25, q50, q75 = np.percentile(vols, [25, 50, 75])
    df_plot["size_bin"] = [size_bin(v, q25, q50, q75) for v in vols]

    # Save CSVs
    out_csv = Path(args.out_csv).resolve()
    df.to_csv(out_csv, index=False)

    # Also save aggregated CSV if needed
    if args.aggregate == "subject":
        out_csv2 = out_csv.with_name(out_csv.stem + "_subjectmean.csv")
        df_plot.to_csv(out_csv2, index=False)

    # Plot histogram
    plt.figure()
    plt.hist(vols, bins=30)
    plt.xlabel(plot_label)
    plt.ylabel("Count")
    plt.title("Approx. intracranial volume distribution")

    # Add percentile lines
    ylim = plt.ylim()
    y_text = ylim[1] * 0.95
    for pct, val in zip(pcts, pvals):
        plt.axvline(val, linestyle="--")
        plt.text(val, y_text, f"{pct}th", rotation=90, va="top", ha="right")

    # Add quartile-based labels in subtitle-like text
    subtitle = (
        f"25th={q25:.0f} mL (small/medium), 50th={q50:.0f} mL, 75th={q75:.0f} mL (large/x-large)"
    )
    plt.text(0.5, 0.98, subtitle, transform=plt.gca().transAxes, ha="center", va="top")

    out_png = Path(args.out_png).resolve()
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.close()

    # Console summary
    print(f"\nComputed volumes for {len(df_plot)} entries ({args.aggregate=}).")
    print(f"CSV saved to: {out_csv}")
    if args.aggregate == "subject":
        print(f"Subject-mean CSV saved to: {out_csv2}")
    print(f"Histogram saved to: {out_png}\n")

    print("Percentiles (mL):")
    for pct, val in zip(pcts, pvals):
        print(f"  {pct:>3}th: {val:8.1f}")

    print("\nSummary (mL):")
    print(f"  mean={np.mean(vols):.1f}, sd={np.std(vols, ddof=1):.1f}, "
          f"min={np.min(vols):.1f}, max={np.max(vols):.1f}")


if __name__ == "__main__":
    main()
