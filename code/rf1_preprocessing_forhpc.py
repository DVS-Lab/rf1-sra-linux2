#!/usr/bin/env python3
import os, shutil, subprocess
from nipype import Workflow, Node
from nipype.interfaces.utility import Function

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR   = os.path.dirname(SCRIPT_DIR)

SUBLIST = os.path.join(SCRIPT_DIR, "sublist_new.txt")
WORKDIR = os.path.join(PROJ_DIR, "nipype_work")
LOGFILE = os.path.join(PROJ_DIR, "rf1_preprocessing_forhpc.log")

BIDS_DIR = os.path.join(PROJ_DIR, "bids")

def run_prep_all(sublist_file, script_dir, logfile):
    import subprocess, os

    def _run(cmd):
        with open(logfile, "a") as lf:
            lf.write("\n$ " + " ".join(cmd) + "\n")
            lf.flush()
            subprocess.run(cmd, stdout=lf, stderr=lf, check=True)

    with open(sublist_file) as f:
        subs = [s.strip() for s in f if s.strip()]

    for sub in subs:
        _run(["bash", os.path.join(script_dir, "prepdata-linux2.sh"), sub, "01"])
        _run(["bash", os.path.join(script_dir, "prepdata-linux2.sh"), sub, "02"])

    marker = os.path.join(os.path.dirname(sublist_file), ".prepdata_done")
    open(marker, "w").close()
    return marker

def run_warp_all(sublist_file, bids_dir, script_dir, logfile, pass_id):
    import os, subprocess

    def _run(cmd):
        with open(logfile, "a") as lf:
            lf.write("\n$ " + " ".join(cmd) + "\n")
            lf.flush()
            subprocess.run(cmd, stdout=lf, stderr=lf, check=True)

    def task_run_pairs(funcdir, sub, ses):
        pairs = set()
        if not os.path.isdir(funcdir):
            return []
        for fn in os.listdir(funcdir):
            if not fn.endswith("_echo-1_part-mag_bold.json"):
                continue
            if f"sub-{sub}_ses-{ses}_" not in fn:
                continue
            try:
                task = fn.split("_task-")[1].split("_run-")[0]
                run  = fn.split("_run-")[1].split("_")[0]
                if run.isdigit():
                    pairs.add((task, run))
            except Exception:
                continue
        return sorted(pairs)

    with open(sublist_file) as f:
        subs = [s.strip() for s in f if s.strip()]

    warpkit = os.path.join(script_dir, "warpkit.sh")

    for sub in subs:
        for ses in ("01", "02"):
            funcdir = os.path.join(bids_dir, f"sub-{sub}", f"ses-{ses}", "func")
            for task, run in task_run_pairs(funcdir, sub, ses):
                _run(["bash", warpkit, sub, ses, task, run])

        if pass_id == "pass2":
            doneflag = os.path.join(bids_dir, f"sub-{sub}", ".processing_complete")
            os.makedirs(os.path.dirname(doneflag), exist_ok=True)
            open(doneflag, "w").close()

    marker = os.path.join(os.path.dirname(sublist_file), f".warpkit_{pass_id}_done")
    open(marker, "w").close()
    return marker

def run_rsync(sublist_file, logfile):
    import subprocess, os
    with open(sublist_file) as f:
        subs = [s.strip() for s in f if s.strip()]
    bids_root = "/ZPOOL/data/projects/rf1-sra-linux2/bids"
    hpc_root  = "hpc:/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2/bids"
    subprocess.run(["chmod", "-R", "777", bids_root], check=False)
    with open(logfile, "a") as lf:
        lf.write(f"\n$ chmod -R 777 {bids_root}\n")
        for sub in subs:
            src = os.path.join(bids_root, f"sub-{sub}")
            dst = os.path.join(hpc_root, f"sub-{sub}")

            if not os.path.isdir(src):
                lf.write(f"\n# SKIP: {src} does not exist\n")
                continue

            cmd = ["rsync", "-avL", src, dst]
            lf.write("\n$ " + " ".join(cmd) + "\n")
            subprocess.run(cmd, stdout=lf, stderr=lf, check=True)
    marker = os.path.join(os.path.dirname(logfile), ".rsync_done")
    open(marker, "w").close()
    return marker


if os.path.isdir(WORKDIR):
    shutil.rmtree(WORKDIR)

wf = Workflow(name="rf1_prepdata_warpkit", base_dir=WORKDIR)

prep = Node(
    Function(
        input_names=["sublist_file", "script_dir", "logfile"],
        output_names=["marker"],
        function=run_prep_all,
    ),
    name="prepdata_all",
)
prep.inputs.sublist_file = SUBLIST
prep.inputs.script_dir = SCRIPT_DIR
prep.inputs.logfile = LOGFILE

warp1 = Node(
    Function(
        input_names=["sublist_file", "bids_dir", "script_dir", "logfile", "pass_id"],
        output_names=["marker"],
        function=run_warp_all,
    ),
    name="warpkit_pass1_all",
)
warp1.inputs.sublist_file = SUBLIST
warp1.inputs.bids_dir = BIDS_DIR
warp1.inputs.script_dir = SCRIPT_DIR
warp1.inputs.logfile = LOGFILE
warp1.inputs.pass_id = "pass1"

warp2 = Node(
    Function(
        input_names=["sublist_file", "bids_dir", "script_dir", "logfile", "pass_id"],
        output_names=["marker"],
        function=run_warp_all,
    ),
    name="warpkit_pass2_all",
)
warp2.inputs.sublist_file = SUBLIST
warp2.inputs.bids_dir = BIDS_DIR
warp2.inputs.script_dir = SCRIPT_DIR
warp2.inputs.logfile = LOGFILE
warp2.inputs.pass_id = "pass2"

rsync = Node(
    Function(
        input_names=["sublist_file", "logfile"],
        output_names=["marker"],
        function=run_rsync,
    ),
    name="final_rsync",
)
rsync.inputs.sublist_file = SUBLIST
rsync.inputs.logfile = LOGFILE

wf.connect(prep, "marker", warp1, "sublist_file")
wf.connect(warp1, "marker", warp2, "sublist_file")
wf.connect(warp2, "marker", rsync, "sublist_file")

if __name__ == "__main__":
    print(f"Log: {LOGFILE}")
    wf.run(plugin="MultiProc", plugin_args={"n_procs": 4})

