#!/bin/bash

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
script="${scriptdir}/prepdata-linux2.sh"

NJOB=3          # number of parallel subjects
OMP_THREADS=6    # threads inside each container job

for sub in $(cat "${scriptdir}/sublist_all.txt"); do
  for ses in 01 02; do

    # Limit number of active prepdata jobs
    while [ "$(pgrep -f "bash $script" -c)" -ge "$NJOB" ]; do
      sleep 2
    done

    # Launch job with multithreading inside Apptainer
    APPTAINERENV_OMP_NUM_THREADS=$OMP_THREADS \
    APPTAINERENV_OPENBLAS_NUM_THREADS=1 \
    APPTAINERENV_NUMEXPR_NUM_THREADS=1 \
    APPTAINERENV_MKL_NUM_THREADS=1 \
      bash "$script" "$sub" "$ses" &

    sleep 1
  done
done

