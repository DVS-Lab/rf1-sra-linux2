#!/bin/bash

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
script="${scriptdir}/warpkit.sh"

NJOB=8
OMP_THREADS=4

for sub in $(cat "${scriptdir}/sublist_fix.txt"); do
  for ses in 01 02; do

    if [ "$ses" = "01" ]; then
      tasks="ugr trust sharedreward doors socialdoors"
    else
      tasks="ugr doors socialdoors"
    fi

    for task in $tasks; do
      for run in 1 2; do

        # Skip nonexistent run 2 for doors/socialdoors
        if [[ ( "$task" == "doors" || "$task" == "socialdoors" ) && "$run" == "2" ]]; then
          continue
        fi

        while [ "$(pgrep -f "bash $script" -c)" -ge "$NJOB" ]; do
          sleep 2
        done

        APPTAINERENV_OMP_NUM_THREADS=$OMP_THREADS \
        APPTAINERENV_OPENBLAS_NUM_THREADS=1 \
        APPTAINERENV_NUMEXPR_NUM_THREADS=1 \
        APPTAINERENV_MKL_NUM_THREADS=1 \
          bash "$script" "$sub" "$ses" "$task" "$run" &

        sleep 1
      done
    done
  done
done

