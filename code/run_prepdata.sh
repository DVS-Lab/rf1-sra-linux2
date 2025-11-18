#!/bin/bash

# ensure paths are correct irrespective from where user runs the script
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
script="${scriptdir}/prepdata-linux2.sh"

# How many subject/session jobs in parallel and threads/job in container
NCORES=28
OMP_THREADS=4

for sub in $(cat "${scriptdir}/sublist_all.txt"); do
  # for sub in 11058 11065 11301 11316 11345; do
  for ses in "01" "02"; do
    # Limit number of concurrent prepdata-linux2.sh jobs
    while [ "$(ps -ef | grep -v grep | grep "$script" | wc -l)" -ge "$NCORES" ]; do
      sleep 5s
    done

    APPTAINERENV_OMP_NUM_THREADS=$OMP_THREADS \
      bash "$script" "$sub" "$ses" &

    sleep 5s
  done
done

