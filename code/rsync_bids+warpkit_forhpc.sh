#!/usr/bin/env bash
set -euo pipefail

# This script rsyncs the *entire* BIDS directory to a remote location.
# It uses -a (archive), -v (verbose), -L (follow symlinks).

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$(dirname "$scriptdir")"
logdir="${projectdir}/logs"
mkdir -p "$logdir"
logfile="${logdir}/rsync_bids_tohpc.log"

# Local BIDS directory
LOCALBIDS="${projectdir}/bids"

# Remote target
REMOTEBIDS="hpc:/gpfs/scratch/tug87422/smithlab-shared/rf1-sra-linux2"

echo "Syncing:"
echo "  FROM: $LOCALBIDS/"
echo "  TO:   $REMOTEBIDS/"
echo "Logging to: $logfile"
echo

# Run rsync and log everything (stdout + stderr)
rsync -avL \
    "${LOCALBIDS}/" \
    "${REMOTEBIDS}/" \
    2>&1 | tee -a "$logfile"

