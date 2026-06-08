#!/bin/bash

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
script="${scriptdir}/mriqc.sh"

NJOB=10

for sub in $(cat "${scriptdir}/sublist_all.txt"); do
  for ses in 01; do

    while [ "$(pgrep -f "bash $script" -c)" -ge "$NJOB" ]; do
      sleep 2
    done

    bash "$script" "$sub" "$ses" &

    sleep 1
  done
done
