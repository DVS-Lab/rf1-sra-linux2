#!/bin/bash

# Path setup
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
maindir="$(dirname "$scriptdir")"

# Amend this to point to the subject list of interest
sublist="$scriptdir/sublist_new.txt"
mapfile -t myArray < "$sublist"

# Can toggle the number of tasks, jobs
ntasks=1
max_jobs=2
counter=0

while [ $counter -lt ${#myArray[@]} ]; do
    subjects="${myArray[@]:$counter:$ntasks}"
    echo "$subjects"    
    bash "$scriptdir/fmriprep.sh" "$subjects" &
# Parallel jobs 
    while [ "$(jobs -rp | wc -l)" -ge "$max_jobs" ]; do
        sleep 10
    done

    counter=$((counter + ntasks))
done

wait
