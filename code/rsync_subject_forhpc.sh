#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash rsync_subject_forhpc.sh 10581
#
# Syncs bids/sub-<sub> and derivatives/warpkit/sub-<sub> to HPC.
# Assumes SSH host alias "hpc" is defined in ~/.ssh/config.

sub="$1"

# Paths
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$(dirname "$scriptdir")"
logdir="${projectdir}/logs"
mkdir -p "$logdir"
logfile="${logdir}/rsync_sub-${sub}_tohpc.log"

LOCAL_BIDS="${projectdir}/bids"
LOCAL_WARPKIT="${projectdir}/derivatives/warpkit"

REMOTE_ROOT="hpc:/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2"
REMOTE_BIDS="${REMOTE_ROOT}/bids"
REMOTE_WARPKIT="${REMOTE_ROOT}/derivatives/warpkit"

{
  echo "============================================================"
  echo "Syncing sub-${sub} to HPC"
  date
  echo "Project dir:     ${projectdir}"
  echo "Local BIDS:      ${LOCAL_BIDS}/sub-${sub}"
  echo "Local warpkit:   ${LOCAL_WARPKIT}/sub-${sub}"
  echo "Remote BIDS:     ${REMOTE_BIDS}/sub-${sub}"
  echo "Remote warpkit:  ${REMOTE_WARPKIT}/sub-${sub}"
  echo

  # 1) bids/sub-<sub>
  if [ -d "${LOCAL_BIDS}/sub-${sub}" ]; then
    echo ">>> rsync bids sub-${sub} ..."
    rsync -avL \
      "${LOCAL_BIDS}/sub-${sub}/" \
      "${REMOTE_BIDS}/sub-${sub}/"
  else
    echo "WARNING: local BIDS sub-${sub} not found at ${LOCAL_BIDS}/sub-${sub}"
  fi
  echo

  # 2) derivatives/warpkit/sub-<sub> (if exists)
  if [ -d "${LOCAL_WARPKIT}/sub-${sub}" ]; then
    echo ">>> Rsync warpkit sub-${sub} ..."
    rsync -avL \
      "${LOCAL_WARPKIT}/sub-${sub}/" \
      "${REMOTE_WARPKIT}/sub-${sub}/"
  else
    echo "NOTE: no warpkit directory for sub-${sub} at ${LOCAL_WARPKIT}/sub-${sub} (ok if warpkit not run yet)"
  fi

  echo
  echo "Done syncing sub-${sub}"
  date
  echo "============================================================"
  echo
} 2>&1 | tee -a "$logfile"

