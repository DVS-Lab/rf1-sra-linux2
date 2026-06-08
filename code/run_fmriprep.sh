#!/bin/bash

# Figure out script source (linux or hpc)
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
maindir="$(dirname "$scriptdir")"

# Run .qsub (hpc) or .sh (linux) based on parent dir
if [[ "$maindir" == /gpfs/* ]]; then
    mode="hpc"
elif [[ "$maindir" == /ZPOOL/* ]]; then
    mode="linux"
else
    echo "ERROR: maindir is neither under /gpfs nor /ZPOOL"
    echo "maindir = $maindir"
    exit 1
fi

sublist="$scriptdir/sublist_new.txt"
mapfile -t myArray < "$sublist"

ntasks=1
counter=0

while [ $counter -lt ${#myArray[@]} ]; do
    subjects="${myArray[@]:$counter:$ntasks}"
    echo "$subjects"

    # Deprecated: since hpc is done, this script will never point to the .qsub argument.
    #if [ "$mode" = "hpc" ]; then
    #    qsub -v subjects="$subjects" "$scriptdir/fmriprep25.qsub"
    #else
    #    subjects="$subjects" bash "$scriptdir/fmriprep.sh"
    #fi

    subjects=bash "$scriptdir/fmriprep.sh" "$subjects"
    counter=$((counter + ntasks))
done

