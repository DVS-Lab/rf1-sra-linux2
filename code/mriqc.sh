#!/usr/bin/env bash
set -euo pipefail

# Run MRIQC only.
#
# usage:  bash mriqc.sh sub ses
# example: bash mriqc.sh 10418 01

sub=$1
ses=$2
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
dsroot="$(dirname "$scriptdir")"

#export SINGULARITYENV_MRIQC_ALLOW_EMPTY_N4=1

if [ ! -d "$dsroot/derivatives/mriqc" ]; then
  mkdir -p "$dsroot/derivatives/mriqc"
fi

scratch=/ZPOOL/data/scratch/$(whoami)
if [ ! -d "$scratch" ]; then
  mkdir -p "$scratch"
fi

# TemplateFlow for MRIQC inside the container
TEMPLATEFLOW_DIR=/ZPOOL/data/tools/templateflow
export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow

echo "Running MRIQC for sub-${sub} ses-${ses}"
singularity run --cleanenv \
  -B "${TEMPLATEFLOW_DIR}:/opt/templateflow" \
  -B "$dsroot/bids:/data" \
  -B "$dsroot/derivatives/mriqc:/out" \
  -B "$scratch:/scratch" \
  /ZPOOL/data/tools/mriqc-24.0.2.simg \
  /data /out participant \
  --participant_label "$sub" \
  --session-id "$ses" \
  --modalities bold \
  --no-sub
