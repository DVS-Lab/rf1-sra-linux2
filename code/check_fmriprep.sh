#!/bin/bash
# By Melanie Kos, originally created for hpc in August 2025
# Amended to be linux compatible

# This script checks if your subject list, sessions, and tasks of interest have fmriprep output for FSL analyses. 
# Customize "sublist", "sessions", and "tasks" accordingly for your sublist, session(s), and task(s) of interest

scriptdir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
projectdir="$( dirname "${scriptdir}" )"
derivativesdir="${projectdir}/derivatives"

# Edit sublist, sessions, and tasks; session 01 = wave 1, 02 = wave 2
# Note that "doors" and "socialdoors" will ALWAYS return no run 02 data (as there is only 1 run for each task)
# Further, for ses02 (wave2), there will only be UGR and socialdoors/doors data (sharedreward and trust are not completed in wave 2).
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
