#!/bin/bash
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$( dirname "${scriptdir}" )"
derivativesdir="${projectdir}/derivatives"
sublist="${scriptdir}/sublist_all.txt"

echo "fmriprep-24: HAS ses-02"
while read -r sub; do
  [[ -z "${sub}" ]] && continue
  ses02dir="${derivativesdir}/fmriprep-24/sub-${sub}/ses-02"
  if [[ -d "${ses02dir}" ]]; then
    echo "${sub}"
  fi
done < "${sublist}"

echo
echo "fmriprep-24: HAS ses-02/func"
while read -r sub; do
  [[ -z "${sub}" ]] && continue
  funcdir="${derivativesdir}/fmriprep-24/sub-${sub}/ses-02/func"
  if [[ -d "${funcdir}" ]]; then
    echo "${sub}"
  fi
done < "${sublist}"

echo
echo "fmriprep-25: HAS ses-02"
while read -r sub; do
  [[ -z "${sub}" ]] && continue
  ses02dir="${derivativesdir}/fmriprep-25/sub-${sub}/ses-02"
  if [[ -d "${ses02dir}" ]]; then
    echo "${sub}"
  fi
done < "${sublist}"

echo
echo "fmriprep-25: HAS ses-02/func"
while read -r sub; do
  [[ -z "${sub}" ]] && continue
  funcdir="${derivativesdir}/fmriprep-25/sub-${sub}/ses-02/func"
  if [[ -d "${funcdir}" ]]; then
    echo "${sub}"
  fi
done < "${sublist}"

