#!/bin/bash

# example code for FMRIPREP
# runs FMRIPREP on input subject
# usage: bash run_fmriprep.sh sub
# example: bash run_fmriprep.sh 102

sub=$1

# ensure paths are correct irrespective of where the user runs the script
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
maindir="$(dirname "$scriptdir")"

# host-system paths
bidsdir="$maindir/bids"
derivdir="$maindir/derivatives"
scratchdir=/ZPOOL/data/scratch/$(whoami)
templateflow_host=/ZPOOL/data/tools/templateflow
mplconfig_host=/ZPOOL/data/tools/mplconfigdir
licenses_host=/ZPOOL/data/tools/licenses
fmriprep_img=/ZPOOL/data/tools/fmriprep-25.2.5.simg

# container paths
base_container=/base
templateflow_container=/opt/templateflow
mplconfig_container=/opt/mplconfigdir
licenses_container=/opts
scratch_container=/scratch

# make derivatives folder if it doesn't exist
if [ ! -d "$derivdir" ]; then
    mkdir -p "$derivdir"
fi

# make scratch folder if it doesn't exist
if [ ! -d "$scratchdir" ]; then
    mkdir -p "$scratchdir"
fi

export APPTAINERENV_TEMPLATEFLOW_HOME=$templateflow_container
export APPTAINERENV_MPLCONFIGDIR=$mplconfig_container

# Check for fmriprep output and run if there is output expected (session-compatible)
# If you want to re-run fmriprep even if output exists, comment the below block out
html="$derivdir/fmriprep/sub-${sub}.html"
all_sessions_done=1
for bids_sesdir in "$bidsdir/sub-${sub}"/ses-*; do
    [ -d "$bids_sesdir" ] || continue
    ses=$(basename "$bids_sesdir")
    if [ ! -d "$derivdir/fmriprep/sub-${sub}/${ses}" ]; then
        all_sessions_done=0
    fi
done
if [ -f "$html" ] && [ "$all_sessions_done" -eq 1 ]; then
    echo "sub-${sub} already has fMRIPrep HTML report and output for all BIDS sessions; skipping"
    exit 0
fi

singularity run --cleanenv \
    -B ${templateflow_host}:${templateflow_container} \
    -B ${mplconfig_host}:${mplconfig_container} \
    -B ${maindir}:${base_container} \
    -B ${licenses_host}:${licenses_container} \
    -B ${scratchdir}:${scratch_container} \
    ${fmriprep_img} \
    ${base_container}/bids ${base_container}/derivatives/fmriprep \
    participant --participant_label $sub \
    --stop-on-first-crash \
    --me-output-echos \
    --output-spaces MNI152NLin6Asym \
    --bids-filter-file ${base_container}/code/fmriprep_config.json \
    --skip-bids-validation \
    --fs-no-reconall \
    --fs-license-file ${licenses_container}/fs_license.txt \
    -w ${scratch_container}

