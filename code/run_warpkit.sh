#!/bin/bash

# ensure paths are correct irrespective from where user runs the script
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
script="${scriptdir}/warpkit.sh"
NCORES=30

for sub in `cat ${scriptdir}/sublist_fix.txt` ; do
  for ses in "01" "02"; do

    # Session 1, all tasks 
    if [ "$ses" = "01" ]; then
        tasks="ugr trust sharedreward doors socialdoors"
    else
        # Session 2, only UGR, Doors
        tasks="ugr doors socialdoors"
    fi

    for task in $tasks; do
      for run in "1" "2"; do

        # Skip run 2 for doors and socialdoors (don't exist)
        if [[ ( "$task" == "doors" || "$task" == "socialdoors" ) && "$run" == "2" ]]; then
            continue
        fi

        while [ $(ps -ef | grep -v grep | grep "$script" | wc -l) -ge $NCORES ]; do
            sleep 5s
        done
        bash "$script" "$sub" "$ses" "$task" "$run" &
        sleep 5s

      done
    done
  done
done

