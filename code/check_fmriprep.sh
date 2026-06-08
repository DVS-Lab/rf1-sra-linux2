#!/bin/bash
# By Melanie Kos, originally created for hpc in August 2025
# Amended to be linux compatible
# Note that a loop can be created to accomodate outputs in 'fmriprep-24' or 'fmriprep-25' folders in derivatives:
# for v in 24 25; do
#   funcdir="${derivativesdir}/fmriprep-${v}/sub-${sub}/ses-01/func"
#    # 1) func dir missing
#    if [[ ! -d "${funcdir}" ]]; then
#      echo "${sub} missing fmriprep-${v} func dir RERUN"
#      continue
#    fi

# This script checks if your subject list, sessions, and tasks of interest have fmriprep output for FSL analyses. 
# Customize "sublist" and "tasks" accordingly.
scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$( dirname "${scriptdir}" )"
derivativesdir="${projectdir}/derivatives"

sublist="${scriptdir}/sublist_all.txt"
sessions=("01" "02")
tasks=("ugr")
runs=("01" "02")

# Read sublist
while read -r sub; do
  [[ -z "${sub}" ]] && continue
  for ses in  "${sessions[@]}"; do
	  for task in "${tasks[@]}"; do
		  for run in "${runs[@]}"; do
			  funcdir="${derivativesdir}/fmriprep/sub-${sub}/ses-${ses}/func/sub-${sub}_ses-${ses}_task-${task}_run-${run}_part-mag_space-MNI152NLin6Asym_desc-preproc_bold.nii.gz"
			  if [[ ! -f "${funcdir}" ]]; then
				  echo "${sub} missing fmriprep func output for sub ${sub}, session ${ses}, ${task}, run ${run}, RERUN or check for missing data"
			  fi 
		  done
	  done 
  done
done < "${sublist}"

