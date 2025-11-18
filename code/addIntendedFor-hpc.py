#!/usr/bin/env python3
import json
import os
import re

# Path to your BIDS directory
bidsdir = "/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/bids/"

# Find all subject directories
subs = [
    d for d in os.listdir(bidsdir)
    if d.startswith("sub-") and os.path.isdir(os.path.join(bidsdir, d))
]

for subj in subs:
    print("Running subject:", subj)
    subj_dir = os.path.join(bidsdir, subj)

    # Find ses-* directories; if none, assume single-session layout
    ses_dirs = [
        d for d in os.listdir(subj_dir)
        if d.startswith("ses-") and os.path.isdir(os.path.join(subj_dir, d))
    ]
    if not ses_dirs:
        ses_dirs = [None]

    for ses in ses_dirs:
        if ses is None:
            fmap_dir     = os.path.join(subj_dir, "fmap")
            func_rel_dir = "func"          # IntendedFor will be "func/..."
            ses_tag      = ""              # no "_ses-01" in filenames
        else:
            fmap_dir     = os.path.join(subj_dir, ses, "fmap")
            func_rel_dir = f"{ses}/func"   # IntendedFor will be "ses-01/func/..."
            ses_tag      = f"_{ses}"       # e.g. "_ses-01"

        if not os.path.isdir(fmap_dir):
            continue

        # Only touch fmap/magnitude JSONs, not DWI/topup stuff
        json_files = [
            f for f in os.listdir(fmap_dir)
            if f.endswith(".json")
            and ("fieldmap" in f or "magnitude" in f)
            and "dwi" not in f
        ]
        if not json_files:
            continue

        for json_file in json_files:
            json_path = os.path.join(fmap_dir, json_file)

            with open(json_path, "r") as f:
                data = json.load(f)

            # 1) Task from JSON (e.g., "ugr", "trust", "doors", "socialdoors")
            task = data.get("TaskName", None)
            if isinstance(task, str):
                task = task.lower()
            else:
                task = None

            # 2) Run number from the FILENAME, e.g.
            #    sub-10317_ses-01_acq-ugr_run-1_fieldmap.json
            m_run = re.search(r"_run-([0-9]+)_", json_file)
            run = m_run.group(1) if m_run else None

            # For doors/socialdoors, if we somehow don't see run in the filename,
            # assume run-1 (by design, they only ever have one run)
            if run is None and task in {"doors", "socialdoors"}:
                run = "1"

            intended_for = []

            if task and run:
                # Build echo-specific magnitude BOLD targets:
                #   sub-10317_ses-01_task-ugr_run-1_echo-1_part-mag_bold.nii.gz
                for echo in range(1, 5):
                    bold_name = (
                        f"{subj}{ses_tag}_task-{task}_run-{run}_echo-{echo}_part-mag_bold.nii.gz"
                    )
                    intended_for.append(f"{func_rel_dir}/{bold_name}")

                data["IntendedFor"] = intended_for
                print(
                    "  Updated", json_path,
                    "with", len(intended_for), "targets (task =", task, ", run =", run, ")"
                )
            else:
                print("  WARNING: could not parse task/run for", json_file)

            # Fieldmap hygiene: always normalize units and drop EchoTime1/2
            data["Units"] = "Hz"
            data.pop("EchoTime1", None)
            data.pop("EchoTime2", None)

            with open(json_path, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)

