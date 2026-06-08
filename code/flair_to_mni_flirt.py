#!/usr/bin/env python3

import os
from pathlib import Path
import subprocess

# =========================
# CONFIG
# =========================
BIDS_DIR = Path("/ZPOOL/data/projects/rf1-sra-linux2/bids")
DERIV_ROOT = Path("/ZPOOL/data/projects/rf1-sra-linux2/derivatives/flirt")

DERIV_ROOT.mkdir(parents=True, exist_ok=True)


# =========================
# FIND MNI REFERENCES
# =========================
def find_mni():
    head_candidates = [
        Path(os.environ.get("FSLDIR", "")) / "data/standard/MNI152_T1_2mm.nii.gz",
        Path("/opt/fsl-6.0.7.16/data/standard/MNI152_T1_2mm.nii.gz"),
        Path("/opt/fsl/data/standard/MNI152_T1_2mm.nii.gz"),
    ]

    brain_candidates = [
        Path(os.environ.get("FSLDIR", "")) / "data/standard/MNI152_T1_2mm_brain.nii.gz",
        Path("/opt/fsl-6.0.7.16/data/standard/MNI152_T1_2mm_brain.nii.gz"),
        Path("/opt/fsl/data/standard/MNI152_T1_2mm_brain.nii.gz"),
    ]

    mni_head = next((p for p in head_candidates if p.exists()), None)
    mni_brain = next((p for p in brain_candidates if p.exists()), None)

    if mni_head is None or mni_brain is None:
        raise FileNotFoundError("MNI templates not found. Check FSL installation.")

    return mni_head, mni_brain


# =========================
# RUN COMMAND
# =========================
def run(cmd):
    print("\nRunning:", " ".join(cmd))
    subprocess.run(cmd, check=True)


# =========================
# PROCESS SUBJECT
# =========================
def process_subject(sub_dir, mni_head):
    sub_id = sub_dir.name

    anat_dirs = []

    # Case 1: no session
    anat_dir = sub_dir / "anat"
    if anat_dir.exists():
        anat_dirs.append((None, anat_dir))

    # Case 2: sessions
    for ses_dir in sorted(sub_dir.glob("ses-*")):
        ses_anat = ses_dir / "anat"
        if ses_anat.exists():
            anat_dirs.append((ses_dir.name, ses_anat))

    if not anat_dirs:
        print(f"Skipping {sub_id}: no anat folders found")
        return

    # Loop over sessions or single anat
    for ses, anat_dir in anat_dirs:

        t1_files = sorted(anat_dir.glob("*T1w.nii.gz"))
        flair_files = sorted(anat_dir.glob("*FLAIR.nii.gz"))

        if not t1_files or not flair_files:
            print(f"Skipping {sub_id} {ses}: missing T1w or FLAIR")
            continue

        t1 = t1_files[0]
        flair = flair_files[0]

        label = sub_id if ses is None else f"{sub_id}_{ses}"

        print(f"\n=== Processing {label} ===")

        # -------------------------
        # Output directory (BIDS-like)
        # -------------------------
        out_dir = DERIV_ROOT / sub_id
        if ses is not None:
            out_dir = out_dir / ses
        out_dir = out_dir / "anat"
        out_dir.mkdir(parents=True, exist_ok=True)

        # -------------------------
        # Output files
        # -------------------------
        t1_to_mni_mat = out_dir / f"{label}_from-T1w_to-MNI152_affine.mat"
        t1_to_mni_img = out_dir / f"{label}_space-MNI152_T1w.nii.gz"

        flair_to_t1_mat = out_dir / f"{label}_from-FLAIR_to-T1w_rigid.mat"
        flair_to_t1_img = out_dir / f"{label}_space-T1w_FLAIR.nii.gz"

        flair_to_mni_mat = out_dir / f"{label}_from-FLAIR_to-MNI152_affine.mat"
        flair_to_mni_img = out_dir / f"{label}_space-MNI152_FLAIR.nii.gz"

        # -------------------------
        # 1. T1 → MNI
        # -------------------------
        run([
            "flirt",
            "-in", str(t1),
            "-ref", str(mni_head),
            "-omat", str(t1_to_mni_mat),
            "-out", str(t1_to_mni_img),
            "-dof", "12"
        ])

        # -------------------------
        # 2. FLAIR → T1
        # -------------------------
        run([
            "flirt",
            "-in", str(flair),
            "-ref", str(t1),
            "-omat", str(flair_to_t1_mat),
            "-out", str(flair_to_t1_img),
            "-dof", "6"
        ])

        # -------------------------
        # 3. Concatenate transforms
        # -------------------------
        run([
            "convert_xfm",
            "-omat", str(flair_to_mni_mat),
            "-concat", str(t1_to_mni_mat),
            str(flair_to_t1_mat)
        ])

        # -------------------------
        # 4. Apply transform
        # -------------------------
        run([
            "flirt",
            "-in", str(flair),
            "-ref", str(mni_head),
            "-applyxfm",
            "-init", str(flair_to_mni_mat),
            "-out", str(flair_to_mni_img)
        ])

        print(f"Finished {label}")


# =========================
# MAIN
# =========================
def main():
    print("BIDS directory:", BIDS_DIR)
    print("Derivatives directory:", DERIV_ROOT)

    mni_head, _ = find_mni()
    print("Using MNI template:", mni_head)

    subjects = sorted([p for p in BIDS_DIR.glob("sub-*") if p.is_dir()])

    if not subjects:
        raise RuntimeError("No subjects found.")

    for sub in subjects:
        process_subject(sub, mni_head)


if __name__ == "__main__":
    main()
