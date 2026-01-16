#!/bin/bash

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$( dirname "${scriptdir}" )"
derivativesdir="${projectdir}/derivatives"
sublist="${scriptdir}/sublist_all.txt"

while read -r sub; do
  [[ -z "${sub}" ]] && continue

  for v in 24 25; do
    funcdir="${derivativesdir}/fmriprep-${v}/sub-${sub}/ses-01/func"
    # 1) func dir missing
    if [[ ! -d "${funcdir}" ]]; then
      echo "${sub} missing fmriprep-${v} func dir RERUN"
      continue
    fi
  done
done < "${sublist}"
