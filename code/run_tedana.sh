#!/bin/bash

# Path definitions
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
maindir="$(dirname "$scriptdir")"

# Amend sublist to point to your subject list of interest
sublist="$scriptdir/sublist_all.txt"
mapfile -t myArray < "$sublist"

ntasks=10
max_jobs=8
counter=0

while [ $counter -lt ${#myArray[@]} ]; do
    subjects="${myArray[@]:$counter:$ntasks}"
    echo "$subjects"  
    subjects="$subjects" bash "$scriptdir/tedana.sh" &

    # Parallel jobs
    while [ "$(jobs -rp | wc -l)" -ge "$max_jobs" ]; do
        sleep 10
    done

    counter=$((counter + ntasks))
done

wait
