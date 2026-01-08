#!/usr/bin/env bash
set -euo pipefail

# Relative file paths
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
maindir="$(dirname "$scriptdir")"
logdir="${maindir}/logs"

mkdir -p "$logdir"

# Inputs (come from wrapper run script)
sub=$1
ses=$2
task=$3
run=$4

# Session version
if [[ "$ses" == "02" ]] && [[ ! -d "${maindir}/bids/sub-${sub}/ses-02" ]]; then
    exit 0
fi

indir="${maindir}/bids/sub-${sub}/ses-${ses}/func"

# Check inputs
if [[ ! -e "${indir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" ]]; then
    echo "NO DATA: sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json"
    echo "NO DATA: sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" \
        >> "${logdir}/missingFiles-warpkit.log"
    exit 0
fi

outdir="${maindir}/derivatives/warpkit/sub-${sub}/ses-${ses}/"
mkdir -p "$outdir"
doneflag="${outdir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}.warpkit_done"

# Skip if already completed
if [[ -e "$doneflag" ]]; then
    echo "EXISTS (skipping): warpkit done for sub-${sub} ses-${ses} ${task} run-${run}"
    exit 0
fi

# Skip if final fieldmap already exists
fmap_out="${maindir}/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.nii.gz"

if [[ -e "$fmap_out" ]]; then
    echo "EXISTS (skipping): ${fmap_out}"
    touch "$doneflag"
    exit 0
fi

# Clean default GRE phasediff fmaps
if [[ -e "${maindir}/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-bold_phasediff.nii.gz" ]]; then
    rm -rf "${maindir}/bids/sub-${sub}/ses-${ses}/fmap/sub-${sub}_ses-${ses}_acq-bold"*
fi

# Run warpkit
/usr/bin/singularity run --cleanenv \
    -B "$indir:/base" \
    -B "$outdir:/out" \
    /ZPOOL/data/tools/warpkit.sif \
    --magnitude \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.nii.gz \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-2_part-mag_bold.nii.gz \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-3_part-mag_bold.nii.gz \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-4_part-mag_bold.nii.gz \
    --phase \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.nii.gz \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-2_part-phase_bold.nii.gz \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-3_part-phase_bold.nii.gz \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-4_part-phase_bold.nii.gz \
    --metadata \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.json \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-2_part-phase_bold.json \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-3_part-phase_bold.json \
        /base/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-4_part-phase_bold.json \
    --out_prefix "/out/sub-${sub}_ses-${ses}_task-${task}_run-${run}"

# Outputs to BIDS fmap folders
fmapdir="${maindir}/bids/sub-${sub}/ses-${ses}/fmap"
mkdir -p "$fmapdir"

fslroi \
    "${outdir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_fieldmaps.nii" \
    "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap" \
    0 1

fslroi \
    "${indir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.nii.gz" \
    "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude" \
    0 1

cp \
    "${indir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-mag_bold.json" \
    "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_magnitude.json"

cp \
    "${indir}/sub-${sub}_ses-${ses}_task-${task}_run-${run}_echo-1_part-phase_bold.json" \
    "${fmapdir}/sub-${sub}_ses-${ses}_acq-${task}_run-${run}_fieldmap.json"

