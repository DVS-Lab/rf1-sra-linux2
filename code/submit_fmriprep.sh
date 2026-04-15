#!/bin/bash

# Launch fMRIPrep on subjects listed in sublist_ses-2.txt
# Keeps at most 5 fMRIPrep jobs running at once

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

sublist="${scriptdir}/sublist_ses-2.txt"
script="${scriptdir}/fmriprep.sh"
MAXJOBS=5

if [ ! -f "$sublist" ]; then
  echo "Could not find subject list: $sublist"
  exit 1
fi

if [ ! -f "$script" ]; then
  echo "Could not find worker script: $script"
  exit 1
fi

while read -r sub; do
  [ -z "$sub" ] && continue

  while [ "$(jobs -rp | wc -l)" -ge "$MAXJOBS" ]; do
    sleep 10
  done

  echo "Launching sub-${sub}"
  bash "$script" "$sub" &
  sleep 2
done < "$sublist"

wait
echo "All fMRIPrep jobs finished."
