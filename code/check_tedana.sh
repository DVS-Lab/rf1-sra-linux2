#!/bin/bash
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$( dirname "${scriptdir}" )"
derivativesdir="${projectdir}/derivatives"
sublist="${scriptdir}/sublist_all.txt"

declare -A printed

while read -r sub; do
  [[ -z "${sub}" ]] && continue

  for v in 24 25; do
    tedanadir="${derivativesdir}/tedana-${v}/sub-${sub}/ses-01"

    if [[ ! -d "${tedanadir}" ]]; then
      [[ -z "${printed[$v]}" ]] && {
        echo "missing tedana-${v} input:"
        printed[$v]=1
      }
      echo "${sub}"
    fi
  done
done < "${sublist}"

