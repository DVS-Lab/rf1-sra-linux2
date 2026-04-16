#!/bin/bash

# This script is used to transfer BIDS info from the local to cluster

# Ensure paths are correct irrespective from where user runs the script
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
basedir="$(dirname "$scriptdir")"

SCRIPTNAME="${BASH_SOURCE[0]}"
NCORES=50
output_csv="${basedir}/bet_results.csv"

# Run subject if argument is passed
if [ ! -z "$1" ]; then
    sub=$1
    output_csv=$2

    imagedir=${basedir}/derivatives/flirt/sub-${sub}/ses-01/anat
    input="${imagedir}/sub-${sub}_ses-01_space-MNI152_FLAIR.nii.gz"
    output="${imagedir}/sub-${sub}_ses-01_space-MNI152_FLAIR_brain.nii.gz"

    if bet "$input" "$output" -R; then
        status="SUCCESS"
    else
        status="FAILED"
    fi

    echo "sub-${sub}: ${status}"

    (
        flock 200
        echo "sub-${sub},${status}" >> "$output_csv"
    ) 200>"${output_csv}.lock"

    exit 0
fi

# Main loop
echo "subject,status" > "$output_csv"

for sub in $(cat ${basedir}/code/sublist_all.txt); do
    while [ $(ps -ef | grep -v grep | grep $SCRIPTNAME | wc -l) -ge $NCORES ]; do
        sleep 5s
    done
    bash $SCRIPTNAME $sub $output_csv &
    sleep 1s
done

wait
echo "Done. Results saved to $output_csv"
