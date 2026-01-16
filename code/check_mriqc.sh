#!/bin/bash
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$( dirname "${scriptdir}" )"
derivativesdir="${projectdir}/derivatives"
sublist="${scriptdir}/sublist_all.txt"

echo "no mriqc output folder - rerun definitely"
while read -r sub; do
  [[ -z "${sub}" ]] && continue
  mriqcdir="${derivativesdir}/mriqc/sub-${sub}"

  if [[ ! -d "${mriqcdir}" ]]; then
    echo "${sub}"
  fi
done < "${sublist}"

echo
echo "missing some mriqc runs (subs could have just never done tasks in scanner anyway), check/rerun"
while read -r sub; do
  [[ -z "${sub}" ]] && continue
  mriqcdir="${derivativesdir}/mriqc/sub-${sub}"
  [[ ! -d "${mriqcdir}" ]] && continue
  missing=0
  for f in \
    "sub-${sub}_ses-01_task-doors_run-1_bold.html" \
    "sub-${sub}_ses-01_task-sharedreward_run-1_bold.html" \
    "sub-${sub}_ses-01_task-sharedreward_run-2_bold.html" \
    "sub-${sub}_ses-01_task-socialdoors_run-1_bold.html" \
    "sub-${sub}_ses-01_task-trust_run-1_bold.html" \
    "sub-${sub}_ses-01_task-trust_run-2_bold.html" \
    "sub-${sub}_ses-01_task-ugr_run-1_bold.html" \
    "sub-${sub}_ses-01_task-ugr_run-2_bold.html"
  do
    if [[ ! -f "${mriqcdir}/${f}" ]]; then
      missing=1
      break
    fi
  done

  [[ ${missing} -eq 1 ]] && echo "${sub}"

done < "${sublist}"

